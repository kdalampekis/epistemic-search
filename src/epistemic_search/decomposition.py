"""Premise decomposition and structural validation, not evidence or inference."""

import asyncio
import hashlib
import json
import os
import tempfile
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from epistemic_search.config import RunConfig
from epistemic_search.models import Claim, ProofNode, QueryCase, Schema, Text, Usage
from epistemic_search.providers import ModelProvider, ModelRequest, ModelResponse, ProviderError

PROMPT_VERSION = "premise-decomposition-v1"


class ProofGraph(Schema):
    claims: list[Claim] = Field(min_length=1, max_length=128)
    nodes: list[ProofNode] = Field(min_length=2, max_length=512)
    conclusion_id: Text

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        claims = {c.id: c for c in self.claims}
        nodes = {n.id: n for n in self.nodes}
        if len(claims) != len(self.claims) or len(nodes) != len(self.nodes):
            raise ValueError("Claim/node IDs must be unique")
        if self.conclusion_id not in nodes or nodes[self.conclusion_id].kind != "CONCLUSION":
            raise ValueError("A CONCLUSION root is required")
        if sum(n.kind == "CONCLUSION" for n in self.nodes) != 1:
            raise ValueError("Exactly one conclusion is required")
        represented: list[str] = []
        for node in self.nodes:
            if len(set(node.children)) != len(node.children):
                raise ValueError("Duplicate child references")
            if any(child not in nodes for child in node.children):
                raise ValueError("Dangling child reference")
            if node.kind == "CLAIM":
                if node.children or node.claim_id not in claims:
                    raise ValueError("CLAIM needs one valid claim reference and no children")
                assert node.claim_id is not None
                represented.append(node.claim_id)
            else:
                if node.claim_id is not None:
                    raise ValueError("Only CLAIM nodes may reference a claim")
                if node.kind in {"NOT", "CONCLUSION"} and len(node.children) != 1:
                    raise ValueError("NOT and CONCLUSION require one child")
                if node.kind in {"AND", "OR"} and len(node.children) < 2:
                    raise ValueError("AND/OR require at least two children")
        if set(represented) != set(claims) or len(represented) != len(claims):
            raise ValueError("Each claim must appear in exactly one leaf")
        visited: set[str] = set()
        active: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in active:
                raise ValueError("Proof graph contains a cycle")
            if node_id in visited:
                return
            active.add(node_id)
            for child in nodes[node_id].children:
                visit(child)
            active.remove(node_id)
            visited.add(node_id)

        visit(self.conclusion_id)
        if visited != set(nodes):
            raise ValueError("Every node must be connected to the conclusion")
        return self


class DraftClaim(Schema):
    id: Text
    text: Text
    polarity: Literal["POSITIVE", "NEGATIVE"]


class DraftNode(Schema):
    id: Text
    kind: Literal["CLAIM", "AND", "OR", "NOT", "CONCLUSION"]
    children: list[Text]
    claim_id: Text | None


class DecompositionDraft(Schema):
    claims: list[DraftClaim] = Field(min_length=1, max_length=128)
    nodes: list[DraftNode] = Field(min_length=2, max_length=512)
    conclusion_id: Text

    def graph(self) -> ProofGraph:
        return canonicalize(
            ProofGraph(
                claims=[Claim(id=c.id, text=c.text, polarity=c.polarity) for c in self.claims],
                nodes=[ProofNode.model_validate(n.model_dump()) for n in self.nodes],
                conclusion_id=self.conclusion_id,
            )
        )


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def canonicalize(graph: ProofGraph) -> ProofGraph:
    claim_ids: dict[str, str] = {}
    claims = []
    for claim in graph.claims:
        text = " ".join(unicodedata.normalize("NFKC", claim.text).split())
        identifier = "c_" + digest([text.casefold(), claim.polarity])[:16]
        claim_ids[claim.id] = identifier
        claims.append(Claim(id=identifier, text=text, polarity=claim.polarity))
    if len({c.id for c in claims}) != len(claims):
        raise ValueError("Duplicate normalized claims")
    original = {n.id: n for n in graph.nodes}
    rewritten: dict[str, ProofNode] = {}
    mapping: dict[str, str] = {}

    def rewrite(old_id: str) -> str:
        if old_id in mapping:
            return mapping[old_id]
        node = original[old_id]
        children = sorted(rewrite(child) for child in node.children)
        claim_id = claim_ids[node.claim_id] if node.claim_id is not None else None
        identifier = "n_" + digest([node.kind, claim_id, children])[:16]
        rewritten[identifier] = ProofNode(
            id=identifier, kind=node.kind, children=children, claim_id=claim_id
        )
        mapping[old_id] = identifier
        return identifier

    root = rewrite(graph.conclusion_id)
    return ProofGraph(
        claims=sorted(claims, key=lambda c: c.id),
        nodes=sorted(rewritten.values(), key=lambda n: n.id),
        conclusion_id=root,
    )


class DecompositionResult(Schema):
    query_id: Text
    graph: ProofGraph | None
    request: ModelRequest
    response: ModelResponse | None
    usage: Usage
    usage_complete: bool = True
    cache_hit: bool = False
    error: str | None = None


ORACLE_KEY = "oracle_proof_graph"


async def decompose(
    case: QueryCase, config: RunConfig, model: ModelProvider, cache_dir: Path
) -> DecompositionResult:
    if config.rag is None:
        raise ValueError("Model settings in rag are required")
    if (oracle := case.metadata.get(ORACLE_KEY)) is not None:
        # Experiment harness: a gold structure supplied with the case replaces the model call.
        # Nothing else changes; with no oracle in the case metadata this branch is never taken.
        return DecompositionResult(
            query_id=case.id,
            graph=ProofGraph.model_validate(oracle),
            request=ModelRequest(
                prompt="Oracle structure supplied with the case; no model call was made.",
                model=config.rag.model,
                prompt_version="oracle-decomposition-injected-v1",
                max_output_tokens=1,
            ),
            response=None,
            usage=Usage(cost_usd=Decimal(0)),
        )
    request = ModelRequest(
        prompt="Decompose the question into atomic answer-critical premises "
        "and a dependency graph. "
        "Use CLAIM leaves, AND/OR/NOT operators and exactly one CONCLUSION root. "
        "Every node must be reachable from that root. Do not assert evidence or truth. "
        "Return JSON claims, nodes, conclusion_id. Question: " + json.dumps(case.question),
        model=config.rag.model,
        prompt_version=PROMPT_VERSION,
        max_output_tokens=config.rag.max_output_tokens,
        seed=config.seed,
        output_schema=DecompositionDraft.model_json_schema(),
    )
    key = digest(
        [
            config.rag.backend,
            config.rag.reasoning_effort,
            config.rag.service_tier,
            request.model_dump(mode="json"),
        ]
    )
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        cached = DecompositionResult.model_validate_json(cache_file.read_text(encoding="utf-8"))
        if cached.request != request or cached.graph is None or cached.error is not None:
            raise ValueError("Invalid decomposition cache entry")
        cached.query_id = case.id
        cached.cache_hit = True
        cached.usage = Usage(cost_usd=Decimal(0))
        return cached
    try:
        response = await asyncio.wait_for(
            model.complete(request), timeout=config.rag.timeout_seconds
        )
    except (ProviderError, TimeoutError) as exc:
        return DecompositionResult(
            query_id=case.id,
            graph=None,
            request=request,
            response=None,
            usage=exc.usage if isinstance(exc, ProviderError) else Usage(model_calls=1),
            usage_complete=isinstance(exc, ProviderError) and exc.usage_complete,
            error=f"Decomposition call failed ({type(exc).__name__})",
        )
    try:
        graph = response.parse(DecompositionDraft).graph()
    except ValueError as exc:
        return DecompositionResult(
            query_id=case.id,
            graph=None,
            request=request,
            response=response,
            usage=response.usage,
            error=str(exc),
        )
    result = DecompositionResult(
        query_id=case.id, graph=graph, request=request, response=response, usage=response.usage
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=cache_dir, delete=False, encoding="utf-8"
    ) as out:
        temp = Path(out.name)
        out.write(result.model_dump_json())
    try:
        os.replace(temp, cache_file)
    finally:
        temp.unlink(missing_ok=True)
    return result
