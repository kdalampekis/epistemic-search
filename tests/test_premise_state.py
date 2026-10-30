import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_rv2_adapters import eb_fixture

from epistemic_search.adapters import CorpusDocument, FixtureSearchProvider
from epistemic_search.config import RunConfig
from epistemic_search.decomposition import ORACLE_KEY
from epistemic_search.models import QueryCase, Source, Usage
from epistemic_search.premise_state import StateJudgment, run_premise_state
from epistemic_search.providers import ModelRequest, ModelResponse
from epistemic_search.rv2_adapters import eb_proof_graph, load_entailmentbank
from epistemic_search.rv2_controlled import GivenPoolSearch
from epistemic_search.tokens import count_tokens


def config(rounds: int = 3, k: int = 3) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": "ps",
            "method": "premise_state",
            "rag": {
                "corpus_path": "u",
                "responses_path": "u",
                "k": k,
                "max_rounds": rounds,
                "max_output_tokens": 512,
            },
            "decomposition": {"cache_dir": "u"},
            "budget": {"max_search_calls": 5, "max_documents": 40, "max_llm_calls": 30},
        }
    )


def docs(texts: list[str]) -> list[CorpusDocument]:
    from datetime import UTC, datetime

    return [
        CorpusDocument(
            source=Source(
                id=f"d{i}",
                uri=f"p://{i}",
                title="t",
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                source_type="benchmark",
            ),
            text=t,
        )
        for i, t in enumerate(texts)
    ]


class Judge:
    """Resolves a premise iff some evidence text equals it; overrides inject misbehaviour."""

    def __init__(self, override: Any = None) -> None:
        self.calls: list[str] = []
        self.override = override

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.prompt_version)
        if request.prompt_version == "premise-state-v1":
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            by_text = {e["text"]: e["source_id"] for e in payload["evidence"]}
            out = []
            for p in payload["premises"]:
                hit = by_text.get(p["text"])
                out.append(
                    {
                        "premise_id": p["id"],
                        "status": "RESOLVED" if hit else "UNRESOLVED",
                        "evidence_ids": [hit] if hit else [],
                    }
                )
            data: Any = {"premises": out}
            if self.override:
                data = self.override(data)
            text = json.dumps(data)
        else:
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            text = json.dumps(
                {"answer": "ok", "citation_ids": [payload["evidence"][0]["source_id"]]}
            )
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


def case(tmp_path: Path) -> tuple[QueryCase, list[str]]:
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path), "dev")}["t1"]
    graph, _ = eb_proof_graph(ex)
    assert graph is not None
    return (
        QueryCase(id="c", question="Q?", metadata={ORACLE_KEY: graph.model_dump(mode="json")}),
        list(ex.leaves.values()),
    )


def run(
    tmp_path: Path, pool: list[str], model: Judge, lexical: bool = False, rounds: int = 3
) -> Any:
    qc, _ = case(tmp_path)
    search = FixtureSearchProvider(docs(pool)) if lexical else GivenPoolSearch(docs(pool))
    return asyncio.run(
        run_premise_state(qc, config(rounds, 2 if lexical else 3), search, model, tmp_path)
    )


def test_every_premise_resolved_answers_with_cited_evidence(tmp_path: Path) -> None:
    _, leaves = case(tmp_path)
    result = run(tmp_path, leaves, Judge())
    assert result.status == "completed" and result.output.answer == "ok"
    assert result.decision.action == "ANSWER" and result.state.blockers == []
    assert result.usage.search_calls == 1 and result.method == "premise_state"


def test_a_missing_premise_is_named_searched_once_then_abstained_without_looping(
    tmp_path: Path,
) -> None:
    _, leaves = case(tmp_path)
    result = run(tmp_path, leaves[:-1], Judge())
    assert result.output.answer is None and result.decision.action == "ABSTAIN"
    assert len(result.state.blockers) == 1
    missing = next(c.id for c in result.state.claims if c.text == leaves[-1])
    assert result.state.blockers == [missing]
    assert result.usage.search_calls == 2  # the second search repeated the pool: no progress
    assert any(e.type == "NO_PROGRESS" for e in result.trace)
    assert result.decision.rationale.startswith("NO_PROGRESS")


def test_a_targeted_search_finds_what_the_first_search_missed(tmp_path: Path) -> None:
    _, leaves = case(tmp_path)
    filler = [f"zzz{i} qqq{i}" for i in range(4)]
    # The question shares no words with the leaves, so the first search returns nothing useful;
    # the premise text, used as the query, finds the leaf.
    result = run(tmp_path, filler + leaves, Judge(), lexical=True, rounds=5)
    queries = [e.payload["query"] for e in result.trace if e.type == "SEARCH"]
    assert queries[0] == "Q?" and set(queries[1:]) <= set(leaves)
    assert result.decision.action == "ANSWER" and result.output.answer == "ok"
    assert result.usage.search_calls == len(queries) <= 4


def test_a_conflicting_premise_is_not_answered(tmp_path: Path) -> None:
    _, leaves = case(tmp_path)

    def conflict(data: dict[str, Any]) -> dict[str, Any]:
        data["premises"][0]["status"] = "CONFLICTING"
        data["premises"][0]["evidence_ids"] = ["d0", "d1"]
        return data

    result = run(tmp_path, leaves, Judge(conflict))
    assert result.output.answer is None and result.state.contradictions
    assert any(
        e.type == "DECISION" and e.payload["action"] == "RESOLVE_CONFLICT" for e in result.trace
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: {"premises": d["premises"][:-1]},  # a premise left unjudged
        lambda d: {"premises": d["premises"] + d["premises"][:1]},  # judged twice
        lambda d: {"premises": [{**p, "premise_id": "nope"} for p in d["premises"]]},
        lambda d: {"premises": [{**p, "evidence_ids": ["not-supplied"]} for p in d["premises"]]},
    ],
)
def test_malformed_or_ungrounded_judgments_never_produce_an_answer(
    tmp_path: Path, mutate: Any
) -> None:
    _, leaves = case(tmp_path)
    result = run(tmp_path, leaves, Judge(mutate))
    assert result.status == "error" and result.output.answer is None


def test_resolved_without_evidence_is_rejected_by_the_schema() -> None:
    with pytest.raises(ValueError, match="must cite evidence"):
        StateJudgment.model_validate(
            {"premises": [{"premise_id": "a", "status": "RESOLVED", "evidence_ids": []}]}
        )
    StateJudgment.model_validate(
        {"premises": [{"premise_id": "a", "status": "UNRESOLVED", "evidence_ids": []}]}
    )
