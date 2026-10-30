from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from epistemic_search.baseline import RunResult
from epistemic_search.models import AgentEvent, QueryCase, Source, Usage
from epistemic_search.providers import SearchResponse, SearchResult
from epistemic_search.rv2_retrieval import (
    METHODS,
    per_type_sizes,
    retrieval_metrics,
    sample_cases,
    summarize,
)


def case(ident: str, qtype: str = "bridge", gold: tuple[str, ...] = ("A", "B")) -> QueryCase:
    facts = [[t, 0] for t in gold] + [[gold[0], 1]]
    return QueryCase(
        id=ident, question="q", metadata={"annotations": {"type": qtype, "supporting_facts": facts}}
    )


def trace(searches: list[list[str]]) -> RunResult:
    events = []
    seen: dict[str, str] = {}
    for n, titles in enumerate(searches):
        results = []
        for rank, title in enumerate(titles, 1):
            source = Source(
                id=f"id-{title}",
                uri=f"u://{title}",
                title=title,
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                source_type="benchmark",
            )
            results.append(SearchResult(source=source, text=title, query=f"query{n}", rank=rank))
            seen[source.id] = title
        response = SearchResponse(
            results=results,
            usage=Usage(
                search_calls=1,
                documents=len(results),
                retrieved_tokens=len(results),
                cost_usd=Decimal(0),
            ),
        )
        events.append(
            AgentEvent(
                id=f"e{n}",
                query_id="q",
                type="SEARCH",
                component="search",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                usage=response.usage,
                payload={
                    "query": f"query{n}",
                    "k": 2,
                    "response": response.model_dump(mode="json"),
                },
            )
        )
    return RunResult(
        query_id="q",
        status="completed",
        usage=Usage(retrieved_tokens=5, cost_usd=Decimal(0)),
        wall_seconds=0.0,
        trace=events,
    )


def test_retrieval_metrics_count_gold_titles_facts_and_duplicates() -> None:
    m = retrieval_metrics(trace([["A", "X"], ["A", "B"]]), case("1"))
    assert m["gold_document_recall"] == 1.0 and m["all_gold_retrieved"] is True
    assert m["gold_fact_recall"] == 1.0  # three facts, all on retrieved paragraphs
    assert m["searches"] == 2 and m["searches_to_all_gold"] == 2
    assert m["unique_documents"] == 3 and m["duplicate_rate"] == pytest.approx(1 / 4)
    assert m["per_search"][0]["new_gold"] == ["A"] and m["per_search"][1]["new_gold"] == ["B"]
    assert m["useful_gold_per_search"] == 1.0


def test_unrecovered_gold_is_censored_not_imputed() -> None:
    m = retrieval_metrics(trace([["A", "X"], ["A", "X"], ["A", "X"]]), case("1"))
    assert m["gold_document_recall"] == 0.5 and m["all_gold_retrieved"] is False
    assert m["searches_to_all_gold"] is None and m["gold_fact_recall"] == pytest.approx(2 / 3)
    assert m["duplicate_rate"] == pytest.approx(4 / 6)


def test_sampling_is_seeded_type_stratified_and_excludes_the_pilot() -> None:
    cases = [case(f"q{i}", "bridge" if i % 3 else "comparison") for i in range(60)]
    chosen = sample_cases(cases, {"bridge": 5, "comparison": 5}, exclude={"q0", "q1"})
    assert len(chosen) == 10 and not {"q0", "q1"} & {c.id for c in chosen}
    assert [c.id for c in chosen] == [
        c.id
        for c in sample_cases(list(reversed(cases)), {"bridge": 5, "comparison": 5}, {"q0", "q1"})
    ]
    meta: list[Any] = [c.metadata["annotations"] for c in chosen[:4]]
    kinds = [m["type"] for m in meta]
    assert kinds == ["bridge", "comparison", "bridge", "comparison"]
    assert per_type_sizes("hotpotqa", 48) == {"bridge": 24, "comparison": 24}
    assert set(per_type_sizes("2wikimultihop", 48).values()) == {12}


def rows(recall: dict[str, float], searches: dict[str, int], n: int = 20) -> list[dict[str, Any]]:
    out = []
    for i in range(n):
        for m in METHODS:
            out.append(
                {
                    "dataset": "hotpotqa",
                    "example_id": f"q{i}",
                    "system": m,
                    "status": "completed",
                    "gold_document_recall": recall[m],
                    "gold_fact_recall": recall[m],
                    "all_gold_retrieved": recall[m] == 1.0,
                    "searches": searches[m],
                    "searches_to_all_gold": None,
                    "useful_gold_per_search": 0.5,
                    "duplicate_rate": 0.1,
                    "retrieved_tokens": 10,
                    "usage": {
                        "new_api_cost_usd": "0.001",
                        "reused_cost_usd": "0",
                        "model_calls": 2,
                    },
                }
            )
    return out


def test_q5_applies_the_gap_the_interval_and_the_efficiency_rules() -> None:
    base = {"naive_rag": 0.5, "iterative_rag": 0.6, "premise_only": 0.8, "epistemic_search": 0.7}
    searches = {m: 3 for m in METHODS}
    assert summarize(rows(base, searches), 200)["Q5"]["verdict"] == "YES"  # +0.2, interval above 0
    flat = {**base, "premise_only": 0.6, "epistemic_search": 0.58}
    assert summarize(rows(flat, searches), 200)["Q5"]["verdict"] == "NO"  # no gap, no saving
    efficient = {**base, "premise_only": 0.6}
    fewer = {**searches, "premise_only": 2, "epistemic_search": 2, "iterative_rag": 3}
    q5 = summarize(rows(efficient, fewer), 200)["Q5"]
    assert q5["verdict"] == "YES" and q5["search_ratio"] == pytest.approx(2 / 3)
    middle = {**base, "premise_only": 0.65, "epistemic_search": 0.5}
    assert summarize(rows(middle, searches), 200)["Q5"]["verdict"] == "UNDETERMINED"  # +0.05


def test_questions_missing_a_system_are_not_scored() -> None:
    data = rows({m: 0.5 for m in METHODS}, {m: 3 for m in METHODS}, n=3)
    data = [r for r in data if not (r["example_id"] == "q0" and r["system"] == "epistemic_search")]
    assert summarize(data, 50)["complete_questions"] == 2
