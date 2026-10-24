"""Offline selective prediction metrics, without fabricated labels or scores."""

import json
from collections.abc import Mapping
from itertools import groupby
from pathlib import Path
from typing import Literal

from pydantic import Field, FiniteFloat

from epistemic_search.evaluation import (
    BENCHMARK_METRICS,
    JsonlDataset,
    ScoredCase,
    Summary,
    file_hash,
)
from epistemic_search.models import Count, Schema, Score, Text

PROTOCOL: Literal["selective-em-uniform-ties-v1"] = "selective-em-uniform-ties-v1"


class RankingScores(Schema):
    source: Text
    scores: dict[str, FiniteFloat]


class RankedPrediction(Schema):
    query_id: Text
    score: FiniteFloat
    loss: Score


class RiskCoveragePoint(Schema):
    accepted: Count
    coverage: Score
    risk: Score | None
    threshold: FiniteFloat | None
    tie_fraction: Score | None


class RiskCoverage(Schema):
    points: list[RiskCoveragePoint]
    aurc: Score
    tie_policy: Literal["expected-uniform-within-score-ties"] = "expected-uniform-within-score-ties"


def risk_coverage(predictions: list[RankedPrediction]) -> RiskCoverage:
    """Mean prefix risk; equal scores use expected loss under uniform tie order.

    Scores rank candidates, higher first. They are not calibrated probabilities.
    A full curve requires a candidate loss for every example, even those a
    deployed policy would reject. Null answers are not counterfactual predictions.
    """
    if not predictions or len({p.query_id for p in predictions}) != len(predictions):
        raise ValueError("Ranking requires a nonempty set of unique prediction IDs")
    points = [
        RiskCoveragePoint(accepted=0, coverage=0, risk=None, threshold=None, tie_fraction=None)
    ]
    count, loss = 0, 0.0
    for score, values in groupby(
        sorted(predictions, key=lambda p: -p.score), key=lambda p: p.score
    ):
        group = list(values)
        group_loss = sum(p.loss for p in group)
        for j in range(1, len(group) + 1):
            points.append(
                RiskCoveragePoint(
                    accepted=count + j,
                    coverage=(count + j) / len(predictions),
                    risk=(loss + j * group_loss / len(group)) / (count + j),
                    threshold=score,
                    tie_fraction=j / len(group),
                )
            )
        count += len(group)
        loss += group_loss
    return RiskCoverage(points=points, aurc=sum(p.risk or 0 for p in points[1:]) / len(predictions))


class SelectiveReport(Schema):
    protocol: Literal["selective-em-uniform-ties-v1"] = PROTOCOL
    examples: Count
    answered: Count
    answered_labelled: Count
    coverage: Score
    selective_risk: Score | None
    policy_abstentions: Count
    errors: Count
    budget_exhausted: Count
    answerability_labelled: Count
    unanswerable: Count
    abstention_tp: Count
    abstention_fp: Count
    abstention_fn: Count
    abstention_precision: Score | None
    abstention_recall: Score | None
    abstention_f1: Score | None
    risk_coverage: RiskCoverage | None
    curve_unavailable_reason: str | None
    score_source: str | None
    source_hashes: dict[str, str] = Field(default_factory=dict)
    source_metric_version: str | None = None
    planned_examples: Count | None = None
    source_stop_reason: str | None = None


def selective_metrics(
    rows: list[ScoredCase],
    answerability: Mapping[str, bool | None],
    ranking: RankingScores | None = None,
) -> SelectiveReport:
    ids = {r.query_id for r in rows}
    if not rows or len(ids) != len(rows):
        raise ValueError("Selective metrics require nonempty unique example IDs")
    if set(answerability) - ids or (ranking and set(ranking.scores) - ids):
        raise ValueError("Labels/scores contain unknown example IDs")
    if any(value is not None and type(value) is not bool for value in answerability.values()):
        raise ValueError("Answerability must be explicit boolean or unknown")
    for row in rows:
        if row.status not in {"completed", "error", "budget_exhausted"}:
            raise ValueError("Unknown execution status")
        if row.answered and row.status != "completed":
            raise ValueError("Only completed outputs may count as answered")
        if row.exact_match not in {None, 0.0, 1.0}:
            raise ValueError("Selective EM risk requires binary exact-match labels")
        if row.labelled != (row.exact_match is not None):
            raise ValueError("Correctness label availability is inconsistent")
    answered = [r for r in rows if r.answered]
    labelled = [r for r in answered if r.exact_match is not None]
    risk = (
        sum(1 - (r.exact_match or 0) for r in labelled) / len(answered)
        if answered and len(labelled) == len(answered)
        else None
    )
    # Budget stops withhold an answer; crashes never earn a true-positive abstention.
    abstained = {r.query_id for r in rows if not r.answered and r.status != "error"}
    known = {key: value for key, value in answerability.items() if value is not None}
    positives = {key for key, value in known.items() if value is False}
    tp = len(abstained & positives)
    fp = len(abstained & {key for key, value in known.items() if value is True})
    fn = len(positives - abstained)
    reason = None
    curve = None
    if ranking is None or set(ranking.scores) != ids:
        reason = "A label-independent ranking score is required for every example"
    elif len(answered) != len(rows):
        reason = "Full AURC needs candidate answers for rejected/failed cases; none are fabricated"
    elif len(labelled) != len(rows):
        reason = "Full AURC needs correctness labels for every candidate answer"
    else:
        curve = risk_coverage(
            [
                RankedPrediction(
                    query_id=r.query_id,
                    score=ranking.scores[r.query_id],
                    loss=1 - (r.exact_match or 0),
                )
                for r in rows
            ]
        )
    return SelectiveReport(
        examples=len(rows),
        answered=len(answered),
        answered_labelled=len(labelled),
        coverage=len(answered) / len(rows),
        selective_risk=risk,
        policy_abstentions=len(abstained),
        errors=sum(r.status == "error" for r in rows),
        budget_exhausted=sum(r.status == "budget_exhausted" for r in rows),
        answerability_labelled=len(known),
        unanswerable=len(positives),
        abstention_tp=tp,
        abstention_fp=fp,
        abstention_fn=fn,
        abstention_precision=tp / (tp + fp) if tp + fp else None,
        abstention_recall=tp / (tp + fn) if tp + fn else None,
        abstention_f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        risk_coverage=curve,
        curve_unavailable_reason=reason,
        score_source=ranking.source if ranking else None,
    )


def analyze_saved_run(run_dir: Path, scores_path: Path | None = None) -> SelectiveReport:
    """Reuse recorded EM, not a new grader. No provider or credential access."""
    examples_path, labels_path = run_dir / "examples.jsonl", run_dir / "labels.jsonl"
    rows = [
        ScoredCase.model_validate_json(line)
        for line in examples_path.read_text().split("\n")
        if line.strip()
    ]
    labels = {c.id: c.answerable for c in JsonlDataset(labels_path).load()}
    if any(row.query_id not in labels for row in rows):
        raise ValueError("Scored examples are missing from the saved label inventory")
    ranking = RankingScores.model_validate_json(scores_path.read_text()) if scores_path else None
    report = selective_metrics(rows, {r.query_id: labels[r.query_id] for r in rows}, ranking)
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "summary.json"
    manifest = json.loads(manifest_path.read_text())
    summary = Summary.model_validate_json(summary_path.read_text())
    if summary.examples != len(rows):
        raise ValueError("Summary example count differs from saved scores")
    if (
        summary.metric_version != manifest.get("metric_version")
        or summary.metric_version not in BENCHMARK_METRICS.values()
    ):
        raise ValueError("Saved manifest and summary grader versions must agree")
    planned = summary.planned_examples if summary.planned_examples is not None else len(labels)
    if (
        planned != len(labels)
        or planned < len(rows)
        or (planned != len(rows) and not summary.stop_reason)
    ):
        raise ValueError("Planned/executed counts or partial-run status are inconsistent")
    report.source_metric_version = summary.metric_version
    report.planned_examples = planned
    report.source_stop_reason = summary.stop_reason
    report.source_hashes = {
        p.name: file_hash(p) for p in (examples_path, labels_path, manifest_path, summary_path)
    }
    if scores_path:
        report.source_hashes["ranking_scores"] = file_hash(scores_path)
    return report
