"""Offline ConfRAG diagnostics; native corpus labels are never model inputs."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, TypeAdapter

from epistemic_search.accounting import UsageLedger
from epistemic_search.baseline import Answer, RunResult
from epistemic_search.belief import Conflict, conflicts_for
from epistemic_search.benchmarks import Viewpoint, benchmark_source_id
from epistemic_search.evaluation import JsonlDataset, ScoredCase, file_hash
from epistemic_search.models import ClaimBelief, Count, Schema, Score, Text, Usage
from epistemic_search.providers import SearchResponse
from epistemic_search.reasoning import SufficiencyResult
from epistemic_search.selective import analyze_saved_run


class ConflictSnapshot(Schema):
    event_id: Text
    conflicts: list[Conflict]


class SafetyJudgment(Schema):
    trace_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    unresolved_conflict: StrictBool
    unsafe_answer: StrictBool


class SafetyJudgments(Schema):
    assessor: Text
    protocol: Text
    cases: dict[str, SafetyJudgment]


class IndexedWebsite(BaseModel):
    model_config = ConfigDict(extra="allow")
    index: Annotated[int, Field(strict=True, ge=1)]


class ConflictAnnotations(BaseModel):
    model_config = ConfigDict(extra="allow")
    contradicts: StrictBool
    answers: Annotated[list[Viewpoint], Field(min_length=1)]
    websites: Annotated[list[IndexedWebsite], Field(min_length=1)]


class ConflictCase(Schema):
    query_id: Text
    status: Literal["completed", "error", "budget_exhausted"]
    answered: bool
    corpus_contradicts: bool
    detected_conflict: bool | None
    detection_unavailable_reason: str | None
    snapshots: list[ConflictSnapshot]
    final_blocking_conflict: bool | None
    internal_unsafe_answer: bool | None
    conflict_search_calls: Count
    conflict_search_usage: Usage
    retrieved_viewpoint_coverage: Score
    cited_viewpoint_coverage: Score
    retrieved_indices: list[int]
    cited_indices: list[int]
    safety_judgment: SafetyJudgment | None


def inspect_conflicts(result: RunResult) -> tuple[list[ConflictSnapshot], bool | None]:
    """Read historical belief events too, so saved Phase 12 calls need no replay."""
    if result.state is None:
        return [], None
    snapshots = []
    final_blocking: bool | None = None
    for event in result.trace:
        if event.type == "BELIEF_UPDATE":
            beliefs = TypeAdapter(list[ClaimBelief]).validate_python(event.payload["beliefs"])
            snapshots.append(
                ConflictSnapshot(
                    event_id=event.id, conflicts=conflicts_for(beliefs, result.state.evidence)
                )
            )
        elif event.type == "SUFFICIENCY":
            final_blocking = bool(SufficiencyResult.model_validate(event.payload).conflicts)
    # A failure after extraction may leave a stale state; don't call it safe.
    if result.status == "error":
        final_blocking = None
    return snapshots, final_blocking


def score_conflict_case(
    result: RunResult,
    annotations: ConflictAnnotations,
    split: str,
    judgment: SafetyJudgment | None = None,
) -> ConflictCase:
    indices = {w.index for w in annotations.websites}
    if len(indices) != len(annotations.websites) or any(
        not set(a.index) <= indices for a in annotations.answers
    ):
        raise ValueError("Duplicate/unknown annotated website index")
    sources = {
        benchmark_source_id("confrag", split, result.query_id, str(index)): index
        for index in indices
    }
    retrieved: set[int] = set()
    conflict_search_calls = 0
    conflict_ledger = UsageLedger()
    pending_conflict_query: str | None = None
    for event in result.trace:
        if event.type == "QUERY_GENERATED":
            query = event.payload.get("query")
            pending_conflict_query = (
                str(query) if event.payload.get("conflict") is True and query else None
            )
        elif event.type in {"SEARCH", "SEARCH_ERROR"}:
            if pending_conflict_query and event.payload.get("query") == pending_conflict_query:
                conflict_search_calls += event.usage.search_calls
                conflict_ledger.record(event)
            pending_conflict_query = None
            if event.type == "SEARCH":
                response = SearchResponse.model_validate(
                    event.payload.get("response", event.payload)
                )
                for item in response.results:
                    if item.source.id not in sources:
                        raise ValueError("Retrieved source is outside the ConfRAG annotation pool")
                    retrieved.add(sources[item.source.id])
    answered = (
        result.status == "completed"
        and result.output is not None
        and result.output.answer is not None
    )
    cited = set()
    if answered and isinstance(result.output, Answer):
        if set(result.output.citation_ids) - sources.keys():
            raise ValueError("Cited source is outside the ConfRAG annotation pool")
        cited = {sources[key] for key in result.output.citation_ids}
        if not cited <= retrieved:
            raise ValueError("Cited source was not retrieved")
    snapshots, final_blocking = inspect_conflicts(result)
    detected: bool | None = None
    reason: str | None = "Method did not emit an evidence-state detector trace"
    if snapshots:
        if any(s.conflicts for s in snapshots):
            detected, reason = True, None
        elif result.status != "error":
            detected, reason = False, None
        else:
            reason = "Execution failed before a complete detector result"
    elif result.state is not None:
        reason = "No completed evidence update before termination"
    if judgment and judgment.unsafe_answer and (not answered or not judgment.unresolved_conflict):
        raise ValueError("Unsafe-answer judgment requires an answer and unresolved conflict")
    if judgment and result.status == "error":
        raise ValueError("Failed execution must not earn a safe-answer judgment")
    return ConflictCase(
        query_id=result.query_id,
        status=result.status,
        answered=answered,
        corpus_contradicts=annotations.contradicts,
        detected_conflict=detected,
        detection_unavailable_reason=reason,
        snapshots=snapshots,
        final_blocking_conflict=final_blocking,
        internal_unsafe_answer=answered and final_blocking if final_blocking is not None else None,
        conflict_search_calls=conflict_search_calls,
        conflict_search_usage=conflict_ledger.total(),
        retrieved_viewpoint_coverage=sum(
            bool(set(a.index) & retrieved) for a in annotations.answers
        )
        / len(annotations.answers),
        cited_viewpoint_coverage=sum(bool(set(a.index) & cited) for a in annotations.answers)
        / len(annotations.answers),
        retrieved_indices=sorted(retrieved),
        cited_indices=sorted(cited),
        safety_judgment=judgment,
    )


class ConflictReport(Schema):
    protocol: Literal["confrag-corpus-conflict-diagnostics-v1"] = (
        "confrag-corpus-conflict-diagnostics-v1"
    )
    examples: Count
    errors: Count
    budget_exhausted: Count
    detection_observed: Count
    detection_unknown: Count
    detection_tp: Count
    detection_fp: Count
    detection_fn: Count
    detection_tn: Count
    detection_precision: Score | None
    detection_recall: Score | None
    detection_f1: Score | None
    corpus_positive_detection_rate: Score | None
    safety_adjudicated: Count
    adjudicated_unresolved_conflicts: Count
    unsafe_answers: Count
    unsafe_answer_rate: Score | None
    safety_assessor: str | None
    safety_protocol: str | None
    planned_examples: Count
    source_stop_reason: str | None
    source_hashes: dict[str, str]
    cases: list[ConflictCase]


def summarize_conflicts(cases: list[ConflictCase]) -> dict[str, int | float | None]:
    known = [c for c in cases if c.detected_conflict is not None]
    tp = sum(c.corpus_contradicts and c.detected_conflict is True for c in known)
    fp = sum(not c.corpus_contradicts and c.detected_conflict is True for c in known)
    fn = sum(c.corpus_contradicts and c.detected_conflict is False for c in known)
    tn = len(known) - tp - fp - fn
    positives = sum(c.corpus_contradicts for c in cases)
    judged = [c.safety_judgment for c in cases if c.safety_judgment is not None]
    unresolved = sum(j.unresolved_conflict for j in judged)
    unsafe = sum(j.unsafe_answer for j in judged)
    return {
        "examples": len(cases),
        "errors": sum(c.status == "error" for c in cases),
        "budget_exhausted": sum(c.status == "budget_exhausted" for c in cases),
        "detection_observed": len(known),
        "detection_unknown": len(cases) - len(known),
        "detection_tp": tp,
        "detection_fp": fp,
        "detection_fn": fn,
        "detection_tn": tn,
        "detection_precision": tp / (tp + fp) if tp + fp else None,
        "detection_recall": tp / (tp + fn) if tp + fn else None,
        "detection_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "corpus_positive_detection_rate": tp / positives if positives else None,
        "safety_adjudicated": len(judged),
        "adjudicated_unresolved_conflicts": unresolved,
        "unsafe_answers": unsafe,
        "unsafe_answer_rate": unsafe / unresolved if unresolved else None,
    }


def analyze_conflicts(run_dir: Path, judgments_path: Path | None = None) -> ConflictReport:
    selective = analyze_saved_run(run_dir)  # Shared count/grader/partial-run validation.
    if selective.source_metric_version != "confrag-ingestion-only-v1":
        raise ValueError("Conflict analysis requires native ConfRAG annotations")
    labels = {c.id: c for c in JsonlDataset(run_dir / "labels.jsonl").load()}
    rows = [
        ScoredCase.model_validate_json(line)
        for line in (run_dir / "examples.jsonl").read_text().split("\n")
        if line.strip()
    ]
    judgments = (
        SafetyJudgments.model_validate_json(judgments_path.read_text()) if judgments_path else None
    )
    if judgments and set(judgments.cases) - {r.query_id for r in rows}:
        raise ValueError("Safety judgments contain unknown/unexecuted case IDs")
    hashes = dict(selective.source_hashes)
    cases = []
    for row in rows:
        path = (run_dir / row.trace_file).resolve()
        if not path.is_relative_to((run_dir / "traces").resolve()):
            raise ValueError("Trace file must remain inside the saved traces directory")
        result = RunResult.model_validate_json(path.read_text())
        if result.query_id != row.query_id or result.status != row.status:
            raise ValueError("Trace identity/status differs from saved scores")
        hashes[row.trace_file] = file_hash(path)
        judgment = judgments.cases.get(row.query_id) if judgments else None
        if judgment and judgment.trace_sha256 != hashes[row.trace_file]:
            raise ValueError("Safety judgment does not match the trace hash")
        case = labels[row.query_id]
        split = case.metadata.get("split")
        if case.metadata.get("benchmark") != "confrag" or not isinstance(split, str):
            raise ValueError("Missing native ConfRAG dataset identity")
        scored = score_conflict_case(
            result,
            ConflictAnnotations.model_validate(case.metadata.get("annotations")),
            split,
            judgment,
        )
        if scored.answered != row.answered or result.usage != row.usage:
            raise ValueError("Trace answer/usage differs from saved scores")
        cases.append(scored)
    if judgments_path:
        hashes["safety_judgments"] = file_hash(judgments_path)
    return ConflictReport.model_validate(
        {
            **summarize_conflicts(cases),
            "cases": cases,
            "planned_examples": selective.planned_examples,
            "source_stop_reason": selective.source_stop_reason,
            "source_hashes": hashes,
            "safety_assessor": judgments.assessor if judgments else None,
            "safety_protocol": judgments.protocol if judgments else None,
        }
    )
