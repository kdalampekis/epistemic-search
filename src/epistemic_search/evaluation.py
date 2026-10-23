"""Versioned, method-independent evaluation with explicit denominators."""

import csv
import hashlib
import json
import re
import string
import subprocess
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Protocol

from epistemic_search.accounting import UsageLedger
from epistemic_search.baseline import RunResult
from epistemic_search.config import RunConfig
from epistemic_search.models import AgentEvent, QueryCase, Schema, Usage

METRIC_VERSION = "english-em-token-f1-v1"
BENCHMARK_METRICS = {
    "jsonl": METRIC_VERSION,
    "hotpotqa": "hotpotqa-answer-v1",
    "2wikimultihopqa": "2wiki-answer-aliases-v1.1",
    "confrag": "confrag-ingestion-only-v1",
}


class DatasetAdapter(Protocol):
    def load(self) -> list[QueryCase]: ...


class JsonlDataset:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[QueryCase]:
        cases: list[QueryCase] = []
        seen: set[str] = set()
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").split("\n"), 1):
            if not line.strip():
                continue
            try:
                case = QueryCase.model_validate_json(line)
                if case.id in seen:
                    raise ValueError(f"Duplicate case ID: {case.id}")
            except ValueError as exc:
                raise ValueError(f"{self.path}: line {line_number}: {exc}") from exc
            seen.add(case.id)
            cases.append(case)
        if not cases:
            raise ValueError("Dataset is empty")
        return cases


def normalize_answer(text: str) -> str:
    text = text.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(re.sub(r"\b(a|an|the)\b", " ", text).split())


def exact_match(prediction: str, reference: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(reference))


def token_f1(prediction: str, reference: str) -> float:
    predicted = normalize_answer(prediction).split()
    gold = normalize_answer(reference).split()
    if not predicted or not gold:
        return float(predicted == gold)
    overlap = sum((Counter(predicted) & Counter(gold)).values())
    return 2 * overlap / (len(predicted) + len(gold))


class ScoredCase(Schema):
    query_id: str
    status: str
    answered: bool
    labelled: bool
    exact_match: float | None
    token_f1: float | None
    trace_file: str
    usage: Usage
    usage_complete: bool
    wall_seconds: float


def score_case(
    case: QueryCase, result: RunResult, trace_file: str, metric_version: str = METRIC_VERSION
) -> ScoredCase:
    if result.query_id != case.id:
        raise ValueError("Result query ID does not match case")
    prediction = result.output.answer if result.status == "completed" and result.output else None
    labelled = case.gold_answer is not None
    # Abstention/error gets zero on labelled QA even when the gold normalizes to empty.
    em = f1 = None
    if metric_version not in BENCHMARK_METRICS.values():
        raise ValueError(f"Unknown metric protocol: {metric_version}")
    if metric_version == "confrag-ingestion-only-v1":
        labelled = False  # Opposing viewpoints are not interchangeable QA references.
    elif case.gold_answer is not None and metric_version != METRIC_VERSION:
        references = [case.gold_answer]
        if metric_version == "2wiki-answer-aliases-v1.1":
            raw = case.metadata.get("answer_references")
            if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
                raise ValueError("2Wiki scoring requires validated answer references")
            references = [str(x) for x in raw]
        em = (
            max((exact_match(prediction, ref) for ref in references), default=0.0)
            if prediction is not None
            else 0.0
        )
        f1 = (
            max((multihop_f1(prediction, ref) for ref in references), default=0.0)
            if prediction is not None
            else 0.0
        )
    elif case.gold_answer is not None:
        em = exact_match(prediction, case.gold_answer) if prediction is not None else 0.0
        f1 = token_f1(prediction, case.gold_answer) if prediction is not None else 0.0
    return ScoredCase(
        query_id=case.id,
        status=result.status,
        answered=prediction is not None,
        labelled=labelled,
        exact_match=em,
        token_f1=f1,
        trace_file=trace_file,
        usage=result.usage,
        usage_complete=result.usage_complete,
        wall_seconds=result.wall_seconds,
    )


def multihop_f1(prediction: str, reference: str) -> float:
    """Answer-only Hotpot/2Wiki protocol, including categorical and empty cases."""
    pred, gold = normalize_answer(prediction), normalize_answer(reference)
    if not pred or not gold:
        return 0.0
    if pred != gold and (pred in {"yes", "no", "noanswer"} or gold in {"yes", "no", "noanswer"}):
        return 0.0
    return token_f1(prediction, reference)


class Summary(Schema):
    metric_version: str = METRIC_VERSION
    examples: int
    labelled_examples: int
    answered: int
    errors: int
    budget_exhausted: int
    coverage: float
    exact_match: float | None
    token_f1: float | None
    usage: Usage
    incomplete_usage_examples: int
    unknown_cost_examples: int
    wall_seconds: float
    planned_examples: int | None = None
    stop_reason: str | None = None


def summarize(rows: list[ScoredCase], metric_version: str = METRIC_VERSION) -> Summary:
    if not rows:
        raise ValueError("Cannot summarize an empty dataset")
    labelled = [r for r in rows if r.labelled]
    ledger = UsageLedger()
    for row in rows:
        ledger.record(
            AgentEvent(
                id=row.query_id,
                query_id=row.query_id,
                type="CASE_TOTAL",
                timestamp=datetime.now(UTC),
                component="evaluation",
                usage=row.usage,
            )
        )
    answered = sum(r.answered for r in rows)
    return Summary(
        metric_version=metric_version,
        examples=len(rows),
        labelled_examples=len(labelled),
        answered=answered,
        errors=sum(r.status == "error" for r in rows),
        budget_exhausted=sum(r.status == "budget_exhausted" for r in rows),
        coverage=answered / len(rows),
        exact_match=sum(r.exact_match or 0 for r in labelled) / len(labelled) if labelled else None,
        token_f1=sum(r.token_f1 or 0 for r in labelled) / len(labelled) if labelled else None,
        usage=ledger.total(),
        incomplete_usage_examples=sum(not r.usage_complete for r in rows),
        unknown_cost_examples=sum(r.usage.cost_usd is None for r in rows),
        wall_seconds=sum(r.wall_seconds for r in rows),
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(config: RunConfig, base_dir: Path) -> dict[str, object]:
    assert config.evaluation is not None and config.rag is not None
    cfg = config.model_dump(mode="json")
    files = {"dataset": config.evaluation.dataset_path}
    if config.evaluation.format == "jsonl" and config.rag.corpus_path is not None:
        files["corpus"] = config.rag.corpus_path
    if config.evaluation.aliases_path is not None:
        files["aliases"] = config.evaluation.aliases_path
    if config.rag.responses_path is not None:
        files["fixture_responses"] = config.rag.responses_path

    def git(*args: str) -> str | None:
        try:
            return subprocess.check_output(
                ["git", *args], cwd=base_dir, stderr=subprocess.DEVNULL, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = git("status", "--porcelain")
    return {
        "config": cfg,
        "config_hash": hashlib.sha256(
            json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "input_hashes": {name: file_hash(base_dir / path) for name, path in files.items()},
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": status != "" if status is not None else None,
        "metric_version": BENCHMARK_METRICS[config.evaluation.format],
        "retrieval_scope": "configured-corpus"
        if config.evaluation.format == "jsonl"
        else "provided-context-per-question",
        "retriever": "lexical-overlap-v1",
        "subset_policy": "sha256(seed:case_id)-ascending" if config.evaluation.limit else "all",
        "method": config.method,
        "packages": {name: version(name) for name in ("epistemic-search", "pydantic", "httpx")},
        "fixture_only": config.rag.backend == "fixture",
    }


async def evaluate(
    dataset: DatasetAdapter,
    runner: Callable[[QueryCase], Awaitable[RunResult]],
    output_dir: Path,
    run_manifest: dict[str, object],
    stop_requested: Callable[[], str | None] | None = None,
) -> Summary:
    # Validate everything before creating artifacts or making provider calls.
    cases = dataset.load()
    if not cases or len({c.id for c in cases}) != len(cases):
        raise ValueError("Dataset must be nonempty with unique case IDs")
    metric_version = str(run_manifest.get("metric_version", METRIC_VERSION))
    if metric_version not in BENCHMARK_METRICS.values():
        raise ValueError(f"Unknown metric protocol: {metric_version}")
    run_manifest = {**run_manifest, "selected_case_ids": [c.id for c in cases]}
    encoded_manifest = json.dumps(run_manifest, indent=2, allow_nan=False)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "traces").mkdir()
    (output_dir / "manifest.json").write_text(encoded_manifest + "\n", encoding="utf-8")
    with (output_dir / "labels.jsonl").open("w", encoding="utf-8") as labels:
        for case in cases:
            labels.write(case.model_dump_json() + "\n")
    rows: list[ScoredCase] = []
    stopped: str | None = None
    with (output_dir / "examples.jsonl").open("w", encoding="utf-8") as examples:
        for index, case in enumerate(cases):
            start = perf_counter()
            try:
                # Evaluation labels are not available to any method implementation.
                result = await runner(QueryCase(id=case.id, question=case.question))
                if result.query_id != case.id:
                    raise ValueError("Runner returned the wrong query ID")
            except Exception as exc:
                # Keep every failed example. Unknown partial usage is NOT zero usage.
                result = RunResult(
                    query_id=case.id,
                    method=str(run_manifest.get("method", "naive_rag")),
                    status="error",
                    usage=Usage(),
                    usage_complete=False,
                    wall_seconds=perf_counter() - start,
                    trace=[],
                    error=f"Unhandled runner failure ({type(exc).__name__})",
                )
            trace_file = f"traces/{index:06d}.json"
            (output_dir / trace_file).write_text(
                result.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            row = score_case(case, result, trace_file, metric_version)
            rows.append(row)
            examples.write(row.model_dump_json() + "\n")
            examples.flush()
            stopped = stop_requested() if stop_requested else None
            if stopped:
                break
    summary = summarize(rows, metric_version)
    summary.planned_examples = len(cases)
    summary.stop_reason = stopped
    (output_dir / "summary.json").write_text(
        summary.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    flattened = summary.model_dump(mode="json")
    flattened.pop("usage")
    flattened.update(
        {f"total_{key}": value for key, value in summary.usage.model_dump(mode="json").items()}
    )
    flattened["total_llm_tokens"] = summary.usage.total_llm_tokens
    with (output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(flattened))
        writer.writeheader()
        writer.writerow(flattened)
    return summary
