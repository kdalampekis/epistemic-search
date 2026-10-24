import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from epistemic_search.baseline import Answer, RunResult
from epistemic_search.benchmarks import benchmark_source_id
from epistemic_search.cli import app
from epistemic_search.conflicts import (
    ConflictAnnotations,
    SafetyJudgment,
    SafetyJudgments,
    analyze_conflicts,
    score_conflict_case,
    summarize_conflicts,
)
from epistemic_search.evaluation import JsonlDataset, evaluate, file_hash
from epistemic_search.models import (
    AgentEvent,
    ClaimBelief,
    EpistemicState,
    QueryCase,
    Source,
    Usage,
)
from epistemic_search.providers import SearchResponse, SearchResult


def annotations() -> ConflictAnnotations:
    return ConflictAnnotations.model_validate(
        {
            "contradicts": True,
            "websites": [{"index": 1}, {"index": 2}],
            "answers": [{"answer": "Alpha", "index": [1]}, {"answer": "Beta", "index": [2]}],
        }
    )


def result(source: Source, event: AgentEvent) -> RunResult:
    source = source.model_copy(update={"id": benchmark_source_id("confrag", "dev", "q", "1")})
    usage = Usage(search_calls=1, documents=1, retrieved_tokens=3, cost_usd=0)
    response = SearchResponse(
        results=[SearchResult(source=source, text="Alpha", query="q", rank=1)], usage=usage
    )
    search = event.model_copy(
        update={
            "id": "search",
            "query_id": "q",
            "type": "SEARCH",
            "usage": usage,
            "payload": {"query": "q", "response": response.model_dump(mode="json")},
        }
    )
    update = event.model_copy(
        update={
            "id": "belief",
            "query_id": "q",
            "type": "BELIEF_UPDATE",
            "usage": Usage(cost_usd=0),
            "payload": {
                "beliefs": [ClaimBelief(claim_id="c", status="SUPPORTED").model_dump(mode="json")]
            },
        }
    )
    return RunResult(
        query_id="q",
        method="epistemic_search",
        status="completed",
        output=Answer(answer="Alpha", citation_ids=[source.id]),
        usage=usage,
        wall_seconds=0,
        trace=[search, update],
        state=EpistemicState(query_id="q"),
    )


def test_corpus_conflict_is_not_single_answer_truth_or_internal_safety(
    source: Source, event: AgentEvent
) -> None:
    run = result(source, event)
    scored = score_conflict_case(run, annotations(), "dev")
    assert scored.detected_conflict is False and scored.corpus_contradicts
    assert scored.retrieved_viewpoint_coverage == scored.cited_viewpoint_coverage == 0.5
    assert scored.internal_unsafe_answer is None and scored.safety_judgment is None
    summary = summarize_conflicts([scored])
    assert summary["detection_fn"] == 1 and summary["detection_recall"] == 0
    assert summary["unsafe_answer_rate"] is None
    run.state = None
    scored = score_conflict_case(run, annotations(), "dev")
    assert scored.detected_conflict is None
    assert summarize_conflicts([scored])["detection_unknown"] == 1
    run = result(source, event)
    run.status = "error"
    scored = score_conflict_case(run, annotations(), "dev")
    assert scored.detected_conflict is None and not scored.answered


def test_conflict_query_counts_only_executed_searches_including_failures(
    source: Source, event: AgentEvent
) -> None:
    run = result(source, event)
    query = event.model_copy(
        update={
            "id": "query",
            "type": "QUERY_GENERATED",
            "payload": {"query": "resolve", "conflict": True},
            "usage": Usage(cost_usd=0),
        }
    )
    run.trace.append(query)
    assert score_conflict_case(run, annotations(), "dev").conflict_search_calls == 0
    run.trace.append(
        event.model_copy(
            update={
                "id": "failed-search",
                "type": "SEARCH_ERROR",
                "payload": {"query": "resolve"},
                "usage": Usage(search_calls=1, cost_usd=None),
            }
        )
    )
    scored = score_conflict_case(run, annotations(), "dev")
    assert scored.conflict_search_calls == 1 and scored.conflict_search_usage.cost_usd is None


def test_safety_rate_requires_independent_judgments_and_no_credit_for_errors(
    source: Source, event: AgentEvent
) -> None:
    run = result(source, event)
    judgment = SafetyJudgment(trace_sha256="0" * 64, unresolved_conflict=True, unsafe_answer=True)
    unsafe = score_conflict_case(run, annotations(), "dev", judgment)
    run.output = Answer(answer=None, citation_ids=[])
    safe_judgment = judgment.model_copy(update={"unsafe_answer": False})
    safe = score_conflict_case(run, annotations(), "dev", safe_judgment)
    assert summarize_conflicts([unsafe, safe])["unsafe_answer_rate"] == 0.5
    with pytest.raises(ValueError, match="requires an answer"):
        score_conflict_case(run, annotations(), "dev", judgment)
    run.status = "error"
    with pytest.raises(ValueError, match="Failed execution"):
        score_conflict_case(run, annotations(), "dev", safe_judgment)


def test_confusion_counts_and_missing_detection_denominators(
    source: Source, event: AgentEvent
) -> None:
    base = score_conflict_case(result(source, event), annotations(), "dev")
    rows = [
        base.model_copy(update={"corpus_contradicts": gold, "detected_conflict": pred})
        for gold, pred in [(True, True), (False, True), (True, False), (False, False), (True, None)]
    ]
    summary = summarize_conflicts(rows)
    assert summary["detection_observed"] == 4 and summary["detection_unknown"] == 1
    assert (
        summary["detection_precision"]
        == summary["detection_recall"]
        == summary["detection_f1"]
        == 0.5
    )
    assert summary["corpus_positive_detection_rate"] == pytest.approx(1 / 3)


def test_saved_confrag_cli_hash_binding_and_invalid_source_rejection(
    tmp_path: Path, source: Source, event: AgentEvent
) -> None:
    case = QueryCase(
        id="q",
        question="Which viewpoint?",
        metadata={
            "benchmark": "confrag",
            "split": "dev",
            "annotations": annotations().model_dump(mode="json"),
        },
    )
    data = tmp_path / "cases.jsonl"
    data.write_text(case.model_dump_json() + "\n")

    async def runner(unlabelled: QueryCase) -> RunResult:
        assert not unlabelled.metadata and unlabelled.gold_answer is None
        return result(source, event)

    directory = tmp_path / "run"
    asyncio.run(
        evaluate(
            JsonlDataset(data), runner, directory, {"metric_version": "confrag-ingestion-only-v1"}
        )
    )
    report = analyze_conflicts(directory)
    assert report.detection_fn == 1 and report.planned_examples == 1
    args = ["conflicts", str(directory), str(tmp_path / "report.json")]
    assert CliRunner().invoke(app, args).exit_code == 0
    assert CliRunner().invoke(app, args).exit_code == 1
    judgments_path = tmp_path / "judgments.json"
    judgment = SafetyJudgment(
        trace_sha256=file_hash(directory / "traces/000000.json"),
        unresolved_conflict=True,
        unsafe_answer=True,
    )
    judgments = SafetyJudgments(
        assessor="fixture", protocol="fixture-independent", cases={"q": judgment}
    )
    judgments_path.write_text(judgments.model_dump_json())
    report = analyze_conflicts(directory, judgments_path)
    assert report.unsafe_answer_rate == 1 and "safety_judgments" in report.source_hashes
    judgment.trace_sha256 = "0" * 64
    judgments_path.write_text(judgments.model_dump_json())
    with pytest.raises(ValueError, match="trace hash"):
        analyze_conflicts(directory, judgments_path)
    run = result(source, event)
    assert isinstance(run.output, Answer)
    run.output.citation_ids = ["unknown"]
    with pytest.raises(ValueError, match="outside"):
        score_conflict_case(run, annotations(), "dev")
    rows_path = directory / "examples.jsonl"
    row = json.loads(rows_path.read_text())
    row["trace_file"] = "../outside.json"
    rows_path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="inside"):
        analyze_conflicts(directory)
