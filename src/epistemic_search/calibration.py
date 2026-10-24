"""Paired offline calibration, with question-group separation before fitting."""

from math import fsum
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Field, StrictBool, model_validator

from epistemic_search.evaluation import file_hash
from epistemic_search.models import Count, Schema, Score, Text

Signal = Literal["raw_confidence", "nli_score", "evidence_aggregation"]
SIGNALS: tuple[Signal, ...] = ("raw_confidence", "nli_score", "evidence_aggregation")
Bins = Annotated[int, Field(strict=True, ge=1, le=100)]


class CalibrationCase(Schema):
    id: Text
    group_id: Text
    split: Literal["calibration", "evaluation"]
    status: Literal["completed", "error", "budget_exhausted"] = "completed"
    candidate_available: StrictBool = True
    correct: StrictBool | None
    scores: dict[Signal, Score | None]

    @model_validator(mode="after")
    def valid_candidate(self) -> Self:
        if self.status != "completed" and self.candidate_available:
            raise ValueError("Only completed candidates can be calibrated")
        if not self.candidate_available and self.correct is not None:
            raise ValueError("Absent predictions have no candidate correctness label")
        return self


class CalibrationData(Schema):
    event_definition: Text
    label_protocol: Text
    score_protocols: dict[Signal, Text]
    fixture_only: StrictBool
    cases: Annotated[list[CalibrationCase], Field(min_length=1)]

    @model_validator(mode="after")
    def separated_groups(self) -> Self:
        if set(self.score_protocols) != set(SIGNALS):
            raise ValueError("Document all three score-generation protocols")
        if len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError("Candidate IDs must be unique")
        fit = {c.group_id for c in self.cases if c.split == "calibration"}
        evaluation = {c.group_id for c in self.cases if c.split == "evaluation"}
        if not fit or not evaluation or fit & evaluation:
            raise ValueError("Calibration and evaluation need nonempty disjoint question groups")
        return self


class CalibrationConfig(Schema):
    data_path: Path
    output_path: Path
    metric_bins: Bins = 10
    calibration_bins: Bins = 5


class ReliabilityBin(Schema):
    lower: Score
    upper: Score
    count: Count
    mean_score: Score | None
    accuracy: Score | None


class CalibrationMetrics(Schema):
    examples: Count
    brier: Score
    ece: Score
    reliability: list[ReliabilityBin]


def bin_index(score: float, bins: int) -> int:
    # Left-closed, right-open intervals, except the final interval includes 1.
    return min(int(score * bins), bins - 1)


def calibration_metrics(scores: list[float], labels: list[bool], bins: int) -> CalibrationMetrics:
    if not scores or len(scores) != len(labels) or type(bins) is not int or not 1 <= bins <= 100:
        raise ValueError("Metrics need matched nonempty scores/labels and 1–100 bins")
    if any(not 0 <= s <= 1 for s in scores) or any(type(y) is not bool for y in labels):
        raise ValueError("Scores must be finite in [0,1] and correctness labels boolean")
    points = []
    weighted_gaps = []
    for index in range(bins):
        members = [
            (s, y) for s, y in zip(scores, labels, strict=True) if bin_index(s, bins) == index
        ]
        mean = sum(s for s, _ in members) / len(members) if members else None
        accuracy = sum(y for _, y in members) / len(members) if members else None
        if mean is not None and accuracy is not None:
            weighted_gaps.append(len(members) * abs(mean - accuracy))
        points.append(
            ReliabilityBin(
                lower=index / bins,
                upper=(index + 1) / bins,
                count=len(members),
                mean_score=mean,
                accuracy=accuracy,
            )
        )
    return CalibrationMetrics(
        examples=len(scores),
        brier=sum((s - int(y)) ** 2 for s, y in zip(scores, labels, strict=True)) / len(scores),
        ece=fsum(weighted_gaps) / len(scores),
        reliability=points,
    )


class HistogramCalibrator(Schema):
    protocol: Literal["equal-width-laplace-v1"] = "equal-width-laplace-v1"
    bins: Bins
    counts: list[Count]
    positives: list[Count]
    estimates: list[Score]
    empty_bin_fallback: Score
    fit_ids: list[Text]

    @model_validator(mode="after")
    def valid_bins(self) -> Self:
        if any(
            len(values) != self.bins for values in (self.counts, self.positives, self.estimates)
        ):
            raise ValueError("Calibrator arrays must match its bin count")
        if (
            not self.fit_ids
            or len(set(self.fit_ids)) != len(self.fit_ids)
            or sum(self.counts) != len(self.fit_ids)
        ):
            raise ValueError("Calibrator needs unique fit IDs matching observation counts")
        if any(p > n for p, n in zip(self.positives, self.counts, strict=True)):
            raise ValueError("Positive labels cannot exceed bin counts")
        return self

    def predict(self, score: float) -> float:
        if not 0 <= score <= 1:
            raise ValueError("Calibration input must be finite in [0,1]")
        return self.estimates[bin_index(score, self.bins)]


def fit_nli(cases: list[CalibrationCase], bins: int) -> HistogramCalibrator:
    if not cases or any(c.split != "calibration" for c in cases):
        raise ValueError("Fit accepts calibration-split cases only")
    if type(bins) is not int or not 1 <= bins <= 100:
        raise ValueError("Calibration needs 1–100 bins")
    rows = [
        c
        for c in cases
        if c.candidate_available and c.correct is not None and c.scores.get("nli_score") is not None
    ]
    if not rows:
        raise ValueError("No labelled calibration candidates with NLI scores")
    counts = [0] * bins
    positives = [0] * bins
    for row in rows:
        score = row.scores["nli_score"]
        assert score is not None and row.correct is not None
        index = bin_index(score, bins)
        counts[index] += 1
        positives[index] += int(row.correct)
    fallback = (sum(positives) + 1) / (len(rows) + 2)
    return HistogramCalibrator(
        bins=bins,
        counts=counts,
        positives=positives,
        estimates=[
            (p + 1) / (n + 2) if n else fallback for p, n in zip(positives, counts, strict=True)
        ],
        empty_bin_fallback=fallback,
        fit_ids=sorted(c.id for c in rows),
    )


class CalibrationReport(Schema):
    protocol: Literal["paired-binary-calibration-v1"] = "paired-binary-calibration-v1"
    additional_api_calls: Literal[0] = 0
    additional_api_cost_usd: Literal["0"] = "0"
    fixture_only: bool
    event_definition: str
    label_protocol: str
    score_protocols: dict[Signal, str]
    calibration_examples: Count
    evaluation_examples: Count
    evaluated_ids: list[Text]
    excluded: dict[str, list[Text]]
    unavailable_reason: str | None
    calibrator: HistogramCalibrator | None
    metrics: dict[str, CalibrationMetrics]
    metric_bins: Bins
    source_hashes: dict[str, str] = Field(default_factory=dict)


def compare_calibration(data: CalibrationData, config: CalibrationConfig) -> CalibrationReport:
    # Revalidate caller-owned lists before selecting or fitting any observations.
    data = CalibrationData.model_validate(data.model_dump())
    fit = [c for c in data.cases if c.split == "calibration"]
    evaluation = [c for c in data.cases if c.split == "evaluation"]
    excluded: dict[str, list[str]] = {}
    paired = []
    for row in evaluation:
        reasons: list[str] = []
        if row.status != "completed":
            reasons.append(row.status)
        if not row.candidate_available:
            reasons.append("no_candidate")
        if row.correct is None:
            reasons.append("unknown_correctness")
        reasons.extend("missing_" + name for name in SIGNALS if row.scores.get(name) is None)
        if reasons:
            excluded[row.id] = reasons
        else:
            paired.append(row)
    fitted = None
    reason = None
    if any(
        c.candidate_available and c.correct is not None and c.scores.get("nli_score") is not None
        for c in fit
    ):
        fitted = fit_nli(fit, config.calibration_bins)
    else:
        reason = "No labelled calibration candidates with NLI scores"
    metrics: dict[str, CalibrationMetrics] = {}
    if not paired:
        reason = "No evaluation candidates with correctness and all three score families"
    elif fitted is not None:
        labels = [c.correct for c in paired if c.correct is not None]
        for name in SIGNALS:
            scores = [c.scores[name] for c in paired]
            metrics[name] = calibration_metrics(
                [s for s in scores if s is not None], labels, config.metric_bins
            )
        metrics["calibrated_nli"] = calibration_metrics(
            [
                fitted.predict(c.scores["nli_score"])
                for c in paired
                if c.scores["nli_score"] is not None
            ],
            labels,
            config.metric_bins,
        )
    return CalibrationReport(
        fixture_only=data.fixture_only,
        event_definition=data.event_definition,
        label_protocol=data.label_protocol,
        score_protocols=data.score_protocols,
        calibration_examples=len(fit),
        evaluation_examples=len(evaluation),
        evaluated_ids=[c.id for c in paired] if metrics else [],
        excluded=excluded,
        unavailable_reason=reason,
        calibrator=fitted,
        metrics=metrics,
        metric_bins=config.metric_bins,
    )


def run_calibration(config_path: Path) -> CalibrationReport:
    config = CalibrationConfig.model_validate(yaml.safe_load(config_path.read_text()))
    data_path = config_path.parent / config.data_path
    data = CalibrationData.model_validate_json(data_path.read_text())
    report = compare_calibration(data, config)
    report.source_hashes = {
        "config": file_hash(config_path),
        "data": file_hash(data_path),
        "evaluator": file_hash(Path(__file__)),
    }
    with (config_path.parent / config.output_path).open("x", encoding="utf-8") as stream:
        stream.write(report.model_dump_json(indent=2) + "\n")
    return report
