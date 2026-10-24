"""Offline paired analysis of saved scores, resampling whole question groups."""

import hashlib
import json
import math
import random
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from statistics import fmean
from typing import Annotated, Any, Self

import yaml
from pydantic import Field, model_validator

from epistemic_search.evaluation import (
    BENCHMARK_METRICS,
    JsonlDataset,
    ScoredCase,
    Summary,
    file_hash,
    summarize,
)
from epistemic_search.models import Count, QueryCase, Schema, Text

Replicates = Annotated[int, Field(strict=True, ge=100, le=100000)]
Groups = dict[str, list[float]]


class StatisticsConfig(Schema):
    runs: dict[Text, Path]
    reference: Text
    output_path: Path
    seed: Count = 42
    confidence: Annotated[float, Field(gt=0, lt=1, allow_inf_nan=False)] = 0.95
    bootstrap_replicates: Replicates = 5000
    permutation_replicates: Replicates = 10000

    @model_validator(mode="after")
    def matched_runs(self) -> Self:
        if len(self.runs) < 2 or self.reference not in self.runs:
            raise ValueError("At least two named runs including the reference are required")
        return self


def quantile(values: list[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1 or any(not math.isfinite(v) for v in values):
        raise ValueError("Quantiles require finite observations and a probability in [0,1]")
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])


def validate_groups(groups: Groups) -> None:
    if any(not values or any(not math.isfinite(x) for x in values) for values in groups.values()):
        raise ValueError("Groups must contain nonempty finite observations")


def bootstrap(groups: Groups, *, replicates: int, seed: int, confidence: float) -> dict[str, Any]:
    validate_groups(groups)
    if type(replicates) is not int or replicates < 1 or not 0 < confidence < 1:
        raise ValueError("Invalid bootstrap repetitions or confidence")
    blocks = [groups[key] for key in sorted(groups)]
    values = [v for block in blocks for v in block]
    result: dict[str, Any] = {
        "mean": fmean(values) if values else None,
        "examples": len(values),
        "groups": len(blocks),
        "confidence": confidence,
        "lower": None,
        "upper": None,
        "replicates": 0,
        "degenerate": None,
        "protocol": "question-cluster-percentile-v1",
    }
    if len(blocks) < 2:
        result["unavailable_reason"] = "At least two independent question groups required"
        return result
    rng = random.Random(seed)
    draws = []
    totals = [(math.fsum(block), len(block)) for block in blocks]
    for _ in range(replicates):
        sampled = [totals[rng.randrange(len(blocks))] for _ in blocks]
        draws.append(math.fsum(s for s, _ in sampled) / sum(n for _, n in sampled))
    tail = (1 - confidence) / 2
    result.update(
        lower=quantile(draws, tail),
        upper=quantile(draws, 1 - tail),
        replicates=replicates,
        degenerate=min(draws) == max(draws),
    )
    return result


def paired_permutation(groups: Groups, *, replicates: int, seed: int) -> dict[str, Any]:
    validate_groups(groups)
    if type(replicates) is not int or replicates < 1:
        raise ValueError("Permutation repetitions must be positive")
    totals = [math.fsum(groups[key]) for key in sorted(groups)]
    count = sum(len(v) for v in groups.values())
    observed = abs(math.fsum(totals))
    result: dict[str, Any] = {
        "protocol": "paired-cluster-sign-flip-absolute-v1",
        "groups": len(totals),
        "mean_difference": math.fsum(totals) / count if count else None,
        "p_value": None,
        "permutations": 0,
        "exact": None,
    }
    if len(totals) < 2:
        result["unavailable_reason"] = "At least two independent question groups required"
        return result
    exact = len(totals) <= 16
    rng = random.Random(seed)
    signs = (
        product((-1, 1), repeat=len(totals))
        if exact
        else (tuple(rng.choice((-1, 1)) for _ in totals) for _ in range(replicates))
    )
    extreme, permutations = 0, 0
    tolerance = 1e-12 * max(1, observed)
    for sign in signs:
        statistic = abs(math.fsum(s * v for s, v in zip(sign, totals, strict=True)))
        extreme += statistic >= observed - tolerance
        permutations += 1
    p = extreme / permutations if exact else (extreme + 1) / (permutations + 1)
    result.update(p_value=p, permutations=permutations, exact=exact)
    return result


def holm(values: dict[str, float]) -> dict[str, float]:
    if any(not 0 <= p <= 1 for p in values.values()):
        raise ValueError("P-values must be finite in [0,1]")
    adjusted = {}
    maximum = 0.0
    for rank, (key, p) in enumerate(sorted(values.items(), key=lambda item: (item[1], item[0]))):
        maximum = max(maximum, min(1, (len(values) - rank) * p))
        adjusted[key] = maximum
    return adjusted


def distribution(values: list[float | None]) -> dict[str, Any]:
    known = [v for v in values if v is not None]
    if any(not math.isfinite(v) or v < 0 for v in known):
        raise ValueError("Resource measurements must be nonnegative and finite")
    return {
        "known": len(known),
        "unknown": len(values) - len(known),
        "mean": fmean(known) if known else None,
        "median": quantile(known, 0.5) if known else None,
        "p90": quantile(known, 0.9) if known else None,
        "total_known": math.fsum(known),
    }


@dataclass
class SavedRun:
    rows: dict[str, ScoredCase]
    labels: dict[str, QueryCase]
    manifest: dict[str, Any]
    summary: Summary
    hashes: dict[str, str]


def read_run(path: Path) -> SavedRun:
    paths = {
        name: path / name
        for name in ("examples.jsonl", "labels.jsonl", "manifest.json", "summary.json")
    }
    rows = [
        ScoredCase.model_validate_json(line)
        for line in paths["examples.jsonl"].read_text().split("\n")
        if line.strip()
    ]
    labels = {c.id: c for c in JsonlDataset(paths["labels.jsonl"]).load()}
    metadata = json.loads(paths["manifest.json"].read_text())
    summary = Summary.model_validate_json(paths["summary.json"].read_text())
    ids = [r.query_id for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != set(labels):
        raise ValueError("Paired analysis requires complete, unique scores for every planned label")
    if summary.stop_reason or summary.planned_examples not in {None, len(rows)}:
        raise ValueError("Partial runs cannot be silently reduced to a paired subset")
    if set(metadata.get("selected_case_ids", [])) != set(ids):
        raise ValueError("Manifest selection and scored cases differ")
    config_hash = hashlib.sha256(
        json.dumps(metadata.get("config"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if metadata.get("config_hash") != config_hash:
        raise ValueError("Saved config hash does not match manifest")
    if (
        summary.metric_version not in BENCHMARK_METRICS.values()
        or metadata.get("metric_version") != summary.metric_version
    ):
        raise ValueError("Saved grader versions do not agree")
    recomputed = summarize(rows, summary.metric_version)
    for key in (
        "examples",
        "labelled_examples",
        "answered",
        "errors",
        "budget_exhausted",
        "coverage",
        "exact_match",
        "token_f1",
        "usage",
    ):
        if getattr(recomputed, key) != getattr(summary, key):
            raise ValueError(f"Saved summary differs from scored rows: {key}")
    for row in rows:
        if row.status not in {"completed", "error", "budget_exhausted"}:
            raise ValueError("Unknown recorded execution status")
        if row.exact_match is not None and row.exact_match not in {0, 1}:
            raise ValueError("Exact-match scores must be binary")
        for metric in (row.exact_match, row.token_f1):
            if metric is not None and not 0 <= metric <= 1:
                raise ValueError("Answer scores must be finite in [0,1]")
        if row.labelled != (row.exact_match is not None) or row.labelled != (
            row.token_f1 is not None
        ):
            raise ValueError("Labelled scores cannot be missing or fabricated")
        if row.status != "completed" and (
            row.answered or (row.exact_match or 0) != 0 or (row.token_f1 or 0) != 0
        ):
            raise ValueError("Failed cases must retain zero answer scores and no answer")
    return SavedRun(
        dict(zip(ids, rows, strict=True)),
        labels,
        metadata,
        summary,
        {name: file_hash(p) for name, p in paths.items()},
    )


def matched_protocol(run: SavedRun) -> dict[str, Any]:
    m = run.manifest
    config = m["config"]
    rag = config["rag"]
    return {
        **{key: m[key] for key in ("metric_version", "retriever", "retrieval_scope")},
        "inputs": m["input_hashes"],
        "budget": config["budget"],
        "seed": config["seed"],
        "model": {
            key: value
            for key, value in rag.items()
            if key not in {"experiment_spend", "responses_path", "corpus_path"}
        },
        "dataset": {
            key: config["evaluation"].get(key)
            for key in ("dataset_name", "split", "format", "snapshot_at", "limit")
        },
    }


def metric_groups(run: SavedRun, metric: str) -> Groups:
    groups: Groups = {}
    for case_id in sorted(run.rows):
        row = run.rows[case_id]
        value = float(row.answered) if metric == "coverage" else getattr(row, metric)
        group = run.labels[case_id].metadata.get("group_id", case_id)
        if not isinstance(group, str) or not group.strip():
            raise ValueError("Question group IDs must be nonempty strings")
        if value is not None:
            groups.setdefault(group, []).append(float(value))
    return groups


def analyze_comparison(config_path: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    config = StatisticsConfig.model_validate(yaml.safe_load(config_path.read_text()))
    runs = {name: read_run(config_path.parent / path) for name, path in config.runs.items()}
    reference = runs[config.reference]
    for name, run in runs.items():
        if matched_protocol(run) != matched_protocol(reference):
            raise ValueError(f"Mismatched comparison protocol for {name}")
        if run.labels != reference.labels:
            raise ValueError("Paired runs must have identical question/gold/group inventories")
        if any(run.rows[i].labelled != reference.rows[i].labelled for i in reference.rows):
            raise ValueError("Methods must share the same labelled population")
    reports: dict[str, Any] = {}
    comparisons: dict[str, dict[str, Any]] = {}
    p_values: dict[str, float] = {}
    for name, run in runs.items():
        metrics = {}
        for metric in ("coverage", "exact_match", "token_f1"):
            groups = metric_groups(run, metric)
            metrics[metric] = bootstrap(
                groups,
                replicates=config.bootstrap_replicates,
                seed=config.seed,
                confidence=config.confidence,
            )
            if name == config.reference:
                continue
            baseline = metric_groups(reference, metric)
            differences = {
                group: [a - b for a, b in zip(values, baseline[group], strict=True)]
                for group, values in groups.items()
            }
            comparison: dict[str, Any] = {
                "method": name,
                "reference": config.reference,
                "metric": metric,
                "difference": bootstrap(
                    differences,
                    replicates=config.bootstrap_replicates,
                    seed=config.seed,
                    confidence=config.confidence,
                ),
                "test": paired_permutation(
                    differences, replicates=config.permutation_replicates, seed=config.seed
                ),
            }
            key = json.dumps([name, metric])
            comparisons[key] = comparison
            if comparison["test"]["p_value"] is not None:
                p_values[key] = comparison["test"]["p_value"]
        rows = list(run.rows.values())
        resources = {
            key: distribution(
                [
                    float(value) if (value := getattr(row.usage, key)) is not None else None
                    for row in rows
                ]
            )
            for key in (
                "cost_usd",
                "prompt_tokens",
                "cached_input_tokens",
                "completion_tokens",
                "reasoning_tokens",
                "model_calls",
                "search_calls",
                "api_calls",
                "model_cache_hits",
            )
        }
        resources["wall_seconds"] = distribution([r.wall_seconds for r in rows])
        reports[name] = {
            "metrics": metrics,
            "resources": resources,
            "source_hashes": run.hashes,
            "errors": run.summary.errors,
            "budget_exhausted": run.summary.budget_exhausted,
            "incomplete_usage_examples": run.summary.incomplete_usage_examples,
        }
    adjusted = holm(p_values)
    for key, comparison in comparisons.items():
        comparison["test"]["p_holm"] = adjusted.get(key)
    report = {
        "protocol": "paired-saved-run-analysis-v1",
        "config": config.model_dump(mode="json"),
        "config_sha256": file_hash(config_path),
        "implementation_sha256": file_hash(Path(__file__)),
        "matched_protocol": matched_protocol(reference),
        "fixture_only": any(r.manifest.get("fixture_only", True) for r in runs.values()),
        "runs": reports,
        "comparisons": list(comparisons.values()),
        "holm_family_size": len(p_values),
        "additional_api_calls": 0,
        "additional_api_cost_usd": "0",
        "limitations": [
            "Exploratory saved-run analysis; no new independent model replicates.",
            "Cluster bootstrap assumes independent question groups; variants stay together.",
            "Percentile intervals may be degenerate or unstable; not simultaneous intervals.",
            "Permutation tests assume jointly exchangeable method labels within each group.",
            "Absolute two-sided test: exact through 16 groups, otherwise plus-one Monte Carlo.",
            "Holm family is all available reference comparisons and metrics in this report only.",
            "Unknown resources are counted, never zero-filled; observed totals may be incomplete.",
            "Cost is recorded physical estimated spend; cache reuse affects cost and latency.",
            "Dataset metrics are not pooled; failed labelled cases retain zero answer scores.",
        ],
    }
    with (output_path or config_path.parent / config.output_path).open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return report
