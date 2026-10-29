"""RV2-B/C: controlled epistemic-state runs on EntailmentBank evidence pools.

Every system is the real method (v1.1), driven through a search provider that always returns the
whole controlled pool, so nothing can be retrieved from outside it and retrieval is not a
confound. Results are appended one case at a time and never rewritten, so a stopped run resumes
and a capped run still reports exactly what it completed.
"""

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from epistemic_search.adapters import CorpusDocument, FixtureSearchProvider
from epistemic_search.baseline import RunResult
from epistemic_search.comparators import run_comparator, run_guarded_baseline
from epistemic_search.config import RagConfig
from epistemic_search.decomposition import ORACLE_KEY, ProofGraph
from epistemic_search.engine import run_epistemic
from epistemic_search.evaluation import file_hash
from epistemic_search.execution import configured_model
from epistemic_search.models import BudgetLimits, QueryCase, Source, Usage
from epistemic_search.providers import ModelProvider, SearchResponse, SearchResult
from epistemic_search.rv2_adapters import ControlledCase, EBExample, eb_proof_graph
from epistemic_search.rv2_metrics import token_f1
from epistemic_search.rv2_run import CONFIG_DIR, run_config
from epistemic_search.tokens import count_tokens

SYSTEMS = ("closed_book", "naive_rag", "premise_only", "epistemic_search")
SNAPSHOT = datetime(2026, 10, 29, tzinfo=UTC)
ANSWER_HIT_F1 = 0.5


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def doc_id(text: str) -> str:
    """Same sentence, same id, in every condition (so identical model requests are reused)."""
    return "pool-" + hashlib.sha256(text.encode()).hexdigest()[:12]


def corpus(case: ControlledCase) -> list[CorpusDocument]:
    return [
        CorpusDocument(
            source=Source(
                id=doc_id(d.text),
                uri=f"pool://{doc_id(d.text)}",
                title="evidence sentence",  # neutral: never reveals leaf or distractor
                retrieved_at=SNAPSHOT,
                source_type="benchmark",
            ),
            text=d.text,
        )
        for d in case.docs
    ]


class GivenPoolSearch:
    """Returns the entire controlled pool, in its fixed order, for every query."""

    def __init__(self, documents: list[CorpusDocument]) -> None:
        self.documents = documents

    async def search(self, query: str, k: int) -> SearchResponse:
        if k < 1 or not query.strip():
            raise ValueError("search requires a query and positive k")
        chosen = self.documents[:k]
        results = [
            SearchResult(source=d.source, text=d.text, query=query, rank=i, retrieval_score=1.0)
            for i, d in enumerate(chosen, 1)
        ]
        return SearchResponse(
            results=results,
            usage=Usage(
                search_calls=1,
                documents=len(results),
                retrieved_tokens=sum(count_tokens(r.text) for r in results),
                cost_usd=Decimal(0),
            ),
            metadata={"retrieval": "given-controlled-pool"},
        )


def pool_budget(pool: int) -> BudgetLimits:
    """Identical ceilings for every system on a case; sized to the pool, not to a method."""
    return BudgetLimits(
        max_search_calls=3,
        max_documents=3 * max(pool, 1),
        max_retrieved_tokens=100_000,
        max_llm_calls=250,
        max_total_llm_input_tokens=800_000,
        max_total_llm_output_tokens=400_000,
        max_latency_seconds=1800,
    )


def case_for(ex: EBExample, condition: str, graph: ProofGraph | None) -> QueryCase:
    metadata = {ORACLE_KEY: graph.model_dump(mode="json")} if graph is not None else {}
    return QueryCase(
        id=f"{ex.id}|{condition}", question=ex.question, gold_answer=ex.answer, metadata=metadata
    )


async def run_system(
    system: str,
    ex: EBExample,
    condition: ControlledCase | None,
    *,
    oracle: bool,
    base_rag: RagConfig,
    run_id: str,
    cache_dir: Path,
    client: httpx.AsyncClient,
    model: ModelProvider | None = None,
) -> RunResult:
    """One method on one case. ``condition`` is None only for closed-book (no pool)."""
    pool = condition.docs if condition else []
    graph = (
        eb_proof_graph(ex)[0] if oracle and system in {"premise_only", "epistemic_search"} else None
    )
    if oracle and system in {"premise_only", "epistemic_search"} and graph is None:
        raise ValueError(f"{ex.id}: no convertible proof graph")
    name = condition.condition if condition else "NA"
    case = case_for(ex, name, graph)
    rag = base_rag.model_copy(update={"k": max(1, len(pool))})
    config = run_config(system, run_id, rag, pool_budget(len(pool)), cache_dir)
    model = model or configured_model(rag, CONFIG_DIR, client)
    search = GivenPoolSearch(corpus(condition)) if condition else FixtureSearchProvider([])
    if system == "closed_book":
        return await run_comparator(case, config, FixtureSearchProvider([]), model, cache_dir)
    if system == "naive_rag":
        return await run_guarded_baseline(case, config, search, model)
    if system == "premise_only":
        return await run_comparator(case, config, search, model, cache_dir)
    return await run_epistemic(case, config, search, model, cache_dir)


def cost_dec(value: object) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal(0)


def row_from(
    result: RunResult,
    system: str,
    ex: EBExample,
    condition: ControlledCase | None,
    mode: str,
    run_id: str,
    trace_sha: str,
    wall: float,
) -> dict[str, Any]:
    answer = None
    if result.status == "completed" and result.output is not None:
        answer = result.output.answer
    answered = bool(answer and str(answer).strip())
    f1 = token_f1(str(answer), ex.answer) if answered else None
    leaf_of = {norm(t): s for s, t in ex.leaves.items()}
    state = result.state
    claim_leaf = {c.id: leaf_of.get(norm(c.text)) for c in state.claims} if state else {}
    blockers = [claim_leaf.get(b) or b for b in (state.blockers if state else [])]
    beliefs = (
        {claim_leaf.get(b.claim_id) or b.claim_id: b.status.value for b in state.beliefs}
        if state
        else {}
    )
    events = result.trace
    payloads: list[Any] = [e.payload for e in events if e.type == "EVIDENCE_ADDED"]
    rejections = sum(len(p.get("rejections", [])) for p in payloads)
    decomposed = [e.payload.get("graph") for e in events if e.type == "DECOMPOSE"]
    usage = result.usage
    outcome = (
        "ANSWER"
        if answered
        else "BUDGET_STOP"
        if result.status == "budget_exhausted"
        else "ERROR"
        if result.status == "error"
        else "ABSTAIN"
    )
    return {
        "run_id": run_id,
        "mode": mode,
        "system": system,
        "example_id": ex.id,
        "condition": condition.condition if condition else "NA",
        "leaves": len(ex.leaves),
        "depth": ex.depth,
        "removed_leaf": condition.removed_leaf if condition else None,
        "pool": [
            {"key": d.key, "role": d.role, "leaf_id": d.leaf_id}
            for d in (condition.docs if condition else [])
        ],
        "question": ex.question,
        "gold_answer": ex.answer,
        "outcome": outcome,
        "decomposition_valid": (bool(decomposed[0]) if decomposed else None),
        "answered": answered,
        "answer": answer,
        "answer_f1": f1,
        "answer_hit": None if f1 is None else f1 >= ANSWER_HIT_F1,
        "status": result.status,
        "error": result.error,
        "decision": result.decision.model_dump(mode="json") if result.decision else None,
        "no_progress": any(e.type == "NO_PROGRESS" for e in events),
        "unresolved_leaves": sorted(blockers) if system == "epistemic_search" else None,
        "belief_by_leaf": beliefs or None,
        "span_rejections": rejections,
        "usage": {
            "model_calls": usage.model_calls,
            "search_calls": usage.search_calls,
            "documents": usage.documents,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "reasoning_tokens": usage.reasoning_tokens,
            "new_api_cost_usd": str(cost_dec(usage.cost_usd)),
            "reused_cost_usd": str(usage.reused_cost_usd),
            "model_cache_hits": usage.model_cache_hits,
            "latency_seconds": usage.latency_seconds,
        },
        "usage_complete": result.usage_complete,
        "wall_seconds": wall,
        "trace_sha256": trace_sha,
    }


def save_trace(result: RunResult, directory: Path, name: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(result.model_dump_json(), encoding="utf-8")
    return file_hash(path)


def done_keys(path: Path) -> set[tuple[str, str, str]]:
    if not path.exists():
        return set()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {(r["system"], r["example_id"], r["condition"]) for r in rows}


def append_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


async def run_example(
    ex: EBExample,
    conditions: list[ControlledCase],
    *,
    systems: tuple[str, ...],
    oracle: bool,
    mode: str,
    base_rag: RagConfig,
    run_id: str,
    cache_dir: Path,
    out: Path,
    traces: Path,
    client: httpx.AsyncClient,
    model: ModelProvider | None = None,
) -> str | None:
    """All systems x conditions for one example; returns a stop reason if a cap interrupted."""
    finished = done_keys(out)
    plan: list[tuple[str, ControlledCase | None]] = []
    for system in systems:
        if system == "closed_book":
            plan.append((system, None))
        else:
            plan += [(system, c) for c in conditions]
    for system, condition in plan:
        key = (system, ex.id, condition.condition if condition else "NA")
        if key in finished:
            continue
        started = perf_counter()
        result = await run_system(
            system,
            ex,
            condition,
            oracle=oracle,
            base_rag=base_rag,
            run_id=run_id,
            cache_dir=cache_dir,
            client=client,
            model=model,
        )
        reason = stop_reason(result, base_rag)
        if reason:
            return reason  # the interrupted case is not recorded as a result
        sha = save_trace(result, traces, f"{key[0]}__{ex.id}__{key[2]}")
        append_row(
            out,
            row_from(result, system, ex, condition, mode, run_id, sha, perf_counter() - started),
        )
    return None


def stop_reason(result: RunResult, rag: RagConfig) -> str | None:
    """A ledger refusal (cap) anywhere in the trace means the case is incomplete, not wrong."""
    from epistemic_search.execution import configured_spend

    spend = configured_spend(rag, CONFIG_DIR)
    reason = spend.stop_reason() if spend else None
    if reason and (result.status != "completed" or result.error):
        return reason
    return None
