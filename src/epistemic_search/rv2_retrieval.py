"""RV2-D: does premise-directed retrieval recover required evidence more efficiently?

Retrieval is scored from the traces against the benchmark's own supporting facts, independently of
whether the final answer was right. Same pool, same lexical retriever, same k and budgets for
every system. Answers are still produced by the methods; they are not scored here.
"""

import asyncio
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from epistemic_search.baseline import RunResult
from epistemic_search.benchmarks import BenchmarkDataset
from epistemic_search.config import EvaluationConfig
from epistemic_search.execution import execute_case
from epistemic_search.models import BudgetLimits, QueryCase
from epistemic_search.providers import SearchResponse
from epistemic_search.rv2_controlled import append_row, load_rows, save_trace
from epistemic_search.rv2_metrics import bootstrap_ci, ratio
from epistemic_search.rv2_run import (
    CONFIG_DIR,
    MODEL,
    ROOT,
    SAMPLING_SEED,
    SEED,
    ledger_report,
    rag_config,
    run_config,
    write_new_json,
)

RUN_ID = "rv2-d-retrieval-v1"
CAP_USD = "0.50"
OUT = Path("docs/results/rv2/rv2_d")
METHODS = ("naive_rag", "iterative_rag", "premise_only", "epistemic_search")
PREMISE_DIRECTED = ("premise_only", "epistemic_search")
PLAIN = ("naive_rag", "iterative_rag")
SIZES = (72, 48)  # questions per dataset; largest whose planning cost fits 80% of the cap
Q5_YES_GAP, Q5_NO_GAP, Q5_EQUAL_TOLERANCE, Q5_SEARCH_RATIO = 0.10, 0.02, 0.02, 0.75
SNAPSHOT = datetime(2026, 10, 23, tzinfo=UTC)

# Same ceilings as the Phase 12 comparison configs.
BUDGET = BudgetLimits(
    max_search_calls=3,
    max_documents=6,
    max_retrieved_tokens=50_000,
    max_llm_calls=24,
    max_total_llm_input_tokens=100_000,
    max_total_llm_output_tokens=32_768,
    max_latency_seconds=600,
)


def dataset(root: Path, name: str) -> BenchmarkDataset:
    base = root / "data/external"
    if name == "hotpotqa":
        cfg = EvaluationConfig(
            dataset_path=base / "hotpotqa/hotpot_dev_distractor.json",
            output_dir=root / "artifacts/rv2/unused",
            dataset_name="hotpotqa-distractor-dev",
            format="hotpotqa",
            split="dev",
            snapshot_at=SNAPSHOT,
        )
    else:
        cfg = EvaluationConfig(
            dataset_path=base / "2wikimultihop/dev.json",
            output_dir=root / "artifacts/rv2/unused",
            dataset_name="2wiki-april7-dev",
            format="2wikimultihopqa",
            split="dev",
            aliases_path=base / "2wikimultihop/id_aliases.json",
            snapshot_at=SNAPSHOT,
        )
    return BenchmarkDataset(cfg, root, SEED)


def pilot_ids(root: Path) -> set[str]:
    manifest = json.loads((root / "docs/results/rv1/context_manifest.json").read_text())
    return {c["case_id"].split(":", 1)[1] for c in manifest["cases"]}


def question_type(case: QueryCase) -> str:
    annotations: Any = case.metadata["annotations"]
    return str(annotations["type"])


def sample_cases(
    cases: list[QueryCase], per_type: dict[str, int], exclude: set[str]
) -> list[QueryCase]:
    """Seeded and type-stratified, pilot questions excluded, types interleaved."""
    pools: dict[str, list[QueryCase]] = {}
    for case in sorted(
        cases, key=lambda c: hashlib.sha256(f"{SAMPLING_SEED}:rv2d:{c.id}".encode()).hexdigest()
    ):
        if case.id not in exclude and question_type(case) in per_type:
            pools.setdefault(question_type(case), []).append(case)
    chosen = {t: pools[t][:n] for t, n in per_type.items()}
    longest = max(len(v) for v in chosen.values())
    return [chosen[t][i] for i in range(longest) for t in sorted(chosen) if i < len(chosen[t])]


def per_type_sizes(name: str, total: int) -> dict[str, int]:
    if name == "hotpotqa":
        return {"bridge": total // 2, "comparison": total // 2}
    return {
        t: total // 4 for t in ("compositional", "comparison", "bridge_comparison", "inference")
    }


def gold(case: QueryCase) -> tuple[set[str], list[tuple[str, int]]]:
    annotations: Any = case.metadata["annotations"]
    facts = [(str(t), int(i)) for t, i in annotations["supporting_facts"]]
    return {t for t, _ in facts}, facts


def searches(result: RunResult) -> list[tuple[str, list[tuple[str, str]]]]:
    """(query, [(source id, title)]) for every search, in order, read from the trace.

    A SEARCH event's payload is ``{"query", "k", "response"}``.
    """
    out = []
    for event in result.trace:
        if event.type == "SEARCH":
            payload: Any = event.payload
            response = SearchResponse.model_validate(payload["response"])
            out.append(
                (str(payload["query"]), [(r.source.id, r.source.title) for r in response.results])
            )
    return out


def retrieval_metrics(result: RunResult, case: QueryCase) -> dict[str, Any]:
    titles, facts = gold(case)
    seen: set[str] = set()
    found: set[str] = set()
    instances = 0
    first_complete: int | None = None
    per_search = []
    for number, (query, docs) in enumerate(searches(result), 1):
        ids = [d for d, _ in docs]
        instances += len(ids)
        new_gold = {t for d, t in docs if t in titles and d not in seen} - found
        seen.update(ids)
        found |= {t for _, t in docs if t in titles}
        per_search.append(
            {"query": query, "documents": [t for _, t in docs], "new_gold": sorted(new_gold)}
        )
        if first_complete is None and found >= titles:
            first_complete = number
    unique = len(seen)
    n_searches = len(per_search)
    return {
        "gold_titles": sorted(titles),
        "retrieved_gold": sorted(found),
        "gold_document_recall": len(found) / len(titles),
        "gold_fact_recall": sum(t in found for t, _ in facts) / len(facts),
        "all_gold_retrieved": found >= titles,
        "searches": n_searches,
        "searches_to_all_gold": first_complete,
        "unique_documents": unique,
        "duplicate_rate": ratio(instances - unique, instances),
        "useful_gold_per_search": ratio(len(found), n_searches) if n_searches else None,
        "per_search": per_search,
        "no_progress": any(e.type == "NO_PROGRESS" for e in result.trace),
        "retrieved_tokens": result.usage.retrieved_tokens,
    }


def row_for(
    result: RunResult, case: QueryCase, dataset_name: str, method: str, sha: str, wall: float
) -> dict[str, Any]:
    usage = result.usage
    return {
        "run_id": RUN_ID,
        "dataset": dataset_name,
        "example_id": case.id,
        "type": question_type(case),
        "system": method,
        "status": result.status,
        "error": result.error,
        **retrieval_metrics(result, case),
        "answered": bool(result.output and getattr(result.output, "answer", None)),
        "usage": {
            "model_calls": usage.model_calls,
            "search_calls": usage.search_calls,
            "documents": usage.documents,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "new_api_cost_usd": str(usage.cost_usd or 0),
            "reused_cost_usd": str(usage.reused_cost_usd),
            "latency_seconds": usage.latency_seconds,
        },
        "wall_seconds": wall,
        "trace_sha256": sha,
    }


async def run_questions(
    items: list[tuple[str, QueryCase, BenchmarkDataset]], out: Path, traces: Path
) -> str | None:
    finished = {(r["system"], r["dataset"], r["example_id"]) for r in load_rows(out)}
    rag = rag_config(RUN_ID, CAP_USD, k=2, max_rounds=3, timeout_seconds=120)
    cache = ROOT / "artifacts/rv2/decomposition-cache-d"
    from epistemic_search.execution import configured_spend

    for name, case, data in items:
        for method in METHODS:
            if (method, name, case.id) in finished:
                continue
            config = run_config(method, RUN_ID, rag, BUDGET, cache)
            started = perf_counter()
            result = await execute_case(case, config, CONFIG_DIR, data.documents(case.id))
            spend = configured_spend(rag, CONFIG_DIR)
            reason = spend.stop_reason() if spend else None
            if reason and (result.status != "completed" or result.error):
                return reason
            sha = save_trace(result, traces, f"{name}__{case.id}__{method}")
            append_row(out, row_for(result, case, name, method, sha, perf_counter() - started))
    return None


def plan(root: Path, total_per_dataset: int) -> list[tuple[str, QueryCase, BenchmarkDataset]]:
    exclude = pilot_ids(root)
    items: dict[str, list[tuple[str, QueryCase, BenchmarkDataset]]] = {}
    for name in ("hotpotqa", "2wikimultihop"):
        data = dataset(root, name)
        chosen = sample_cases(data.load(), per_type_sizes(name, total_per_dataset), exclude)
        items[name] = [(name, c, data) for c in chosen]
    longest = max(len(v) for v in items.values())
    return [items[n][i] for i in range(longest) for n in sorted(items) if i < len(items[n])]


def summarize(rows: list[dict[str, Any]], resamples: int = 10_000) -> dict[str, Any]:
    by_q: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        by_q.setdefault(f"{r['dataset']}|{r['example_id']}", {})[r["system"]] = r
    complete = sorted(q for q, v in by_q.items() if set(METHODS) <= set(v))

    def mean(system: str, key: str, units: Sequence[str]) -> float | None:
        values = [by_q[q][system][key] for q in units if by_q[q][system][key] is not None]
        return sum(float(v) for v in values) / len(values) if values else None

    def block(units: Sequence[str]) -> dict[str, Any]:
        return {
            m: {
                "questions": len(units),
                "gold_document_recall": mean(m, "gold_document_recall", units),
                "gold_fact_recall": mean(m, "gold_fact_recall", units),
                "all_gold_retrieved": mean(m, "all_gold_retrieved", units),
                "mean_searches": mean(m, "searches", units),
                "useful_gold_per_search": mean(m, "useful_gold_per_search", units),
                "duplicate_rate": mean(m, "duplicate_rate", units),
                "retrieved_tokens": mean(m, "retrieved_tokens", units),
                "searches_to_all_gold_censored_mean": mean_censored(by_q, m, units),
                "new_api_cost_usd": sum(
                    float(by_q[q][m]["usage"]["new_api_cost_usd"]) for q in units
                ),
                "logical_cost_usd": sum(
                    float(by_q[q][m]["usage"]["new_api_cost_usd"])
                    + float(by_q[q][m]["usage"]["reused_cost_usd"])
                    for q in units
                ),
                "model_calls": sum(by_q[q][m]["usage"]["model_calls"] for q in units),
                "errors_or_budget_stops": sum(by_q[q][m]["status"] != "completed" for q in units),
            }
            for m in METHODS
        }

    out: dict[str, Any] = {"complete_questions": len(complete)}
    if not complete:
        return out
    out["pooled"] = block(complete)
    for name in ("hotpotqa", "2wikimultihop"):
        units = [q for q in complete if q.startswith(name + "|")]
        if units:
            out[name] = block(units)
    out["Q5"] = q5(by_q, complete, resamples)
    return out


def mean_censored(
    by_q: dict[str, dict[str, dict[str, Any]]], system: str, units: Sequence[str]
) -> float:
    """Searches until all gold is held; never recovered counts as 4 (the cap is 3), so it is a
    lower bound on cost, not an estimate of it."""
    values = [by_q[q][system]["searches_to_all_gold"] or 4 for q in units]
    return sum(values) / len(values)


def q5(
    by_q: dict[str, dict[str, dict[str, Any]]], units: Sequence[str], resamples: int
) -> dict[str, Any]:
    def recall(system: str, sample: Sequence[str]) -> float:
        return float(sum(by_q[q][system]["gold_document_recall"] for q in sample)) / len(sample)

    def gap(sample: Sequence[str]) -> float | None:
        return max(recall(s, sample) for s in PREMISE_DIRECTED) - max(
            recall(s, sample) for s in PLAIN
        )

    point = gap(units)
    ci = bootstrap_ci(list(units), gap, resamples=resamples)
    best_pd = max(PREMISE_DIRECTED, key=lambda s: recall(s, units))
    best_plain = max(PLAIN, key=lambda s: recall(s, units))
    searches_pd = sum(by_q[q][best_pd]["searches"] for q in units) / len(units)
    searches_plain = sum(by_q[q][best_plain]["searches"] for q in units) / len(units)
    search_ratio = searches_pd / searches_plain if searches_plain else None
    lower = ci["lower"]
    verdict = "UNDETERMINED"
    if point is not None and point >= Q5_YES_GAP and lower is not None and lower > 0:
        verdict = "YES"
    elif (
        point is not None
        and point >= -Q5_EQUAL_TOLERANCE
        and search_ratio is not None
        and search_ratio <= Q5_SEARCH_RATIO
    ):
        verdict = "YES"
    elif point is not None and point <= Q5_NO_GAP:
        verdict = "NO"
    return {
        "verdict": verdict,
        "gap_best_premise_directed_minus_best_plain": point,
        "ci95": [ci["lower"], ci["upper"]],
        "best_premise_directed": best_pd,
        "best_plain": best_plain,
        "mean_searches": {best_pd: searches_pd, best_plain: searches_plain},
        "search_ratio": search_ratio,
    }


def stage_estimate(root: Path = ROOT) -> dict[str, Any]:
    items = plan(root, SIZES[1])
    probe = [items[0], items[1]]  # one HotpotQA, one 2Wiki question
    out = root / OUT / "cases.jsonl"
    reason = asyncio.run(run_questions(probe, out, root / "artifacts/rv2" / RUN_ID / "traces"))
    if reason:
        raise RuntimeError(f"Probe stopped: {reason}")
    rows = load_rows(out)
    per_question = sum(
        float(r["usage"]["new_api_cost_usd"]) + float(r["usage"]["reused_cost_usd"]) for r in rows
    ) / len(probe)
    cap = float(CAP_USD)
    plans = {str(n): {"questions": 2 * n, "planning_cost_usd": per_question * 2 * n} for n in SIZES}
    chosen = next((n for n in SIZES if plans[str(n)]["planning_cost_usd"] <= 0.8 * cap), SIZES[-1])
    report = {
        "experiment": "RV2-D retrieval only",
        "run_id": RUN_ID,
        "hard_cap_usd": CAP_USD,
        "probe_questions": [
            (r["dataset"], r["example_id"]) for r in rows if r["system"] == METHODS[0]
        ],
        "probe_logical_cost_per_question_usd": per_question,
        "probe_mean_case_seconds": sum(r["wall_seconds"] for r in rows) / len(rows),
        "plans": plans,
        "rule": "largest per-dataset size in (72, 48) with planning cost <= 80% of the cap",
        "chosen_per_dataset": chosen,
        "ledger_after_probe": ledger_report(rag_config(RUN_ID, CAP_USD)),
    }
    write_new_json(root / OUT / "estimate.json", report)
    return report


def stage_run(root: Path = ROOT) -> dict[str, Any]:
    path = root / OUT / "estimate.json"
    if not path.exists():
        raise RuntimeError("Run the estimate stage first; the full run needs a logged estimate")
    estimate = json.loads(path.read_text())
    items = plan(root, int(estimate["chosen_per_dataset"]))
    started = perf_counter()
    halted = asyncio.run(
        run_questions(items, root / OUT / "cases.jsonl", root / "artifacts/rv2" / RUN_ID / "traces")
    )
    rows = load_rows(root / OUT / "cases.jsonl")
    result = {
        "experiment": "RV2-D retrieval only",
        "code": "tag epistemic-search-v1.1",
        "run_id": RUN_ID,
        "model": MODEL,
        "reasoning_effort": "medium",
        "seed": SEED,
        "sampling_seed": SAMPLING_SEED,
        "datasets": {"hotpotqa": "dev distractor", "2wikimultihop": "dev"},
        "settings": {"k": 2, "max_rounds": 3, "budget": BUDGET.model_dump(mode="json")},
        "sample": [(n, c.id, question_type(c)) for n, c, _ in items],
        "excluded_pilot_ids": sorted(pilot_ids(root)),
        "stopped_by_cap": halted,
        "estimate": estimate,
        "metrics": summarize(rows),
        "ledger": ledger_report(rag_config(RUN_ID, CAP_USD)),
        "wall_seconds": perf_counter() - started,
        "case_rows": len(rows),
    }
    write_new_json(root / OUT / "results.json", result)
    return result
