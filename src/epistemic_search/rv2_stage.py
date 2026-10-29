"""RV2-B and RV2-C stage drivers: estimate (probe) -> run -> analysis, with hard ledger caps."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from epistemic_search.rv2_adapters import (
    ControlledCase,
    EBExample,
    controlled_conditions,
    load_entailmentbank,
    sample_eb,
)
from epistemic_search.rv2_analysis import (
    BASELINES,
    CONDITIONS,
    classify,
    complete_examples,
    depth_split,
    distractor_robustness,
    index,
    j_stat,
    q1,
    q2,
    q3,
    q4,
    system_metrics,
)
from epistemic_search.rv2_controlled import load_rows, run_example
from epistemic_search.rv2_run import (
    MODEL,
    ROOT,
    SAMPLING_SEED,
    SEED,
    ledger_report,
    rag_config,
    write_new_json,
)

SIZES = (3, 4, 5)
PER_SIZE_CHOICES = (9, 6)  # tried in this order; largest whose planning cost fits 80% of the cap
CACHE = Path("artifacts/rv2/decomposition-cache")


@dataclass(frozen=True)
class Spec:
    name: str
    run_id: str
    cap_usd: str
    arms: tuple[tuple[str, bool, tuple[str, ...]], ...]  # (mode, oracle?, systems)
    out: Path


SPEC_B = Spec(
    "RV2-B oracle structure",
    "rv2-b-oracle-structure-v1",
    "0.25",
    (("oracle", True, ("epistemic_search",)), ("generated", False, ("epistemic_search",))),
    Path("docs/results/rv2/rv2_b"),
)
SPEC_C = Spec(
    "RV2-C controlled epistemic state",
    "rv2-c-controlled-v1",
    "0.50",
    (("oracle", True, ("closed_book", "naive_rag", "premise_only", "epistemic_search")),),
    Path("docs/results/rv2/rv2_c"),
)


def interleaved(root: Path, per_size: int) -> list[EBExample]:
    """Round-robin over leaf counts, so a capped run is still balanced across sizes."""
    dev = load_entailmentbank(root / "data/external/entailmentbank", "dev")
    chosen = sample_eb(dev, per_size, SIZES, SAMPLING_SEED)
    groups = [[e for e in chosen if len(e.leaves) == s] for s in SIZES]
    return [g[i] for i in range(per_size) for g in groups if i < len(g)]


def logical_cost(rows: list[dict[str, Any]]) -> float:
    return sum(
        float(r["usage"]["new_api_cost_usd"]) + float(r["usage"]["reused_cost_usd"]) for r in rows
    )


def plan_cost(probe: list[dict[str, Any]], probe_leaves: int, sample: list[EBExample]) -> float:
    """Logical-cost planning figure. Epistemic Search extraction scales with leaves x pool."""
    es = logical_cost([r for r in probe if r["system"] == "epistemic_search"])
    other = logical_cost([r for r in probe if r["system"] != "epistemic_search"])
    unit = probe_leaves * (probe_leaves + 4)
    return sum(es * (len(e.leaves) * (len(e.leaves) + 4)) / unit + other for e in sample)


async def drive(
    spec: Spec, examples: list[EBExample], root: Path, seed_conditions: int = SEED
) -> str | None:
    rag = rag_config(spec.run_id, spec.cap_usd, max_rounds=3)
    traces = root / "artifacts/rv2" / spec.run_id / "traces"
    async with httpx.AsyncClient() as client:
        for ex in examples:
            conditions = controlled_conditions(ex, SAMPLING_SEED)
            for mode, oracle, systems in spec.arms:
                reason = await run_example(
                    ex,
                    conditions,
                    systems=systems,
                    oracle=oracle,
                    mode=mode,
                    base_rag=rag,
                    run_id=spec.run_id,
                    cache_dir=root / CACHE,
                    out=root / spec.out / f"cases_{mode}.jsonl",
                    traces=traces / mode,
                    client=client,
                )
                if reason:
                    return reason
    return None


def all_rows(spec: Spec, root: Path) -> dict[str, list[dict[str, Any]]]:
    return {mode: load_rows(root / spec.out / f"cases_{mode}.jsonl") for mode, _, _ in spec.arms}


def stage_estimate(spec: Spec, root: Path = ROOT) -> dict[str, Any]:
    probe_ex = interleaved(root, 6)[0]
    reason = asyncio.run(drive(spec, [probe_ex], root))
    if reason:
        raise RuntimeError(f"Probe stopped: {reason}")
    probe_rows = [r for rows in all_rows(spec, root).values() for r in rows]
    leaves = len(probe_ex.leaves)
    plans = {}
    for per_size in PER_SIZE_CHOICES:
        sample = interleaved(root, per_size)
        plans[str(per_size)] = {
            "examples": len(sample),
            "planning_cost_usd": plan_cost(probe_rows, leaves, sample),
        }
    cap = float(spec.cap_usd)
    chosen = next(
        (p for p in PER_SIZE_CHOICES if plans[str(p)]["planning_cost_usd"] <= 0.8 * cap), 6
    )
    report = {
        "experiment": spec.name,
        "run_id": spec.run_id,
        "hard_cap_usd": spec.cap_usd,
        "probe_example": probe_ex.id,
        "probe_leaves": leaves,
        "probe_logical_cost_usd": logical_cost(probe_rows),
        "probe_new_api_cost_usd": sum(float(r["usage"]["new_api_cost_usd"]) for r in probe_rows),
        "probe_mean_case_seconds": sum(r["wall_seconds"] for r in probe_rows) / len(probe_rows),
        "plans": plans,
        "rule": "largest per-size in (9, 6) with planning cost <= 80% of the cap",
        "chosen_per_size": chosen,
        "chosen_examples": 3 * chosen,
        "ledger_after_probe": ledger_report(rag_config(spec.run_id, spec.cap_usd)),
    }
    write_new_json(root / spec.out / "estimate.json", report)
    return report


def summarize_c(rows: list[dict[str, Any]], resamples: int = 10_000) -> dict[str, Any]:
    systems = ["closed_book", "naive_rag", "premise_only", "epistemic_search"]
    idx = index(rows)
    core = ["epistemic_search", *BASELINES]
    examples = complete_examples(idx, core)
    out: dict[str, Any] = {"complete_examples": len(examples), "example_ids": examples}
    if not examples:
        return out
    out["systems"] = {s: system_metrics(idx, s, examples) for s in core}
    if "closed_book" in idx:
        cb = [e for e in examples if e in idx["closed_book"]]
        cells = [idx["closed_book"][e]["NA"] for e in cb]
        out["closed_book"] = {
            "examples": len(cb),
            "answer_rate": sum(r["answered"] for r in cells) / max(len(cells), 1),
            "answer_hit_rate": sum(bool(r["answer_hit"]) for r in cells) / max(len(cells), 1),
            "note": "pool-independent: it answers every condition identically by construction",
        }
    out["distractor_robustness"] = {s: distractor_robustness(idx, s, examples) for s in core}
    out["Q1"] = q1(idx, examples)
    out["Q2"] = q2(idx, examples, resamples)
    out["Q3"] = q3(idx, examples)
    out["depth"] = depth_split(idx, examples)
    out["systems_listed"] = systems
    return out


def summarize_b(
    by_mode: dict[str, list[dict[str, Any]]], resamples: int = 10_000
) -> dict[str, Any]:
    oracle, generated = index(by_mode["oracle"]), index(by_mode["generated"])
    both = sorted(
        set(complete_examples(oracle, ["epistemic_search"]))
        & set(complete_examples(generated, ["epistemic_search"]))
    )
    out: dict[str, Any] = {"examples_with_both_arms": len(both), "example_ids": both}
    if not both:
        return out
    out["oracle"] = system_metrics(oracle, "epistemic_search", both)
    out["generated"] = system_metrics(generated, "epistemic_search", both)
    # Pre-registered Q4: structural failures count as no answer, exactly as in the plan.
    out["Q4"] = q4(oracle, generated, both)
    valid = [
        e
        for e in both
        if all(generated["epistemic_search"][e][c]["decomposition_valid"] for c in CONDITIONS)
    ]
    out["generated_decomposition_validity"] = {
        "examples": len(both),
        "valid": len(valid),
        "rate": len(valid) / len(both),
        "note": "invalid = the model's graph failed the pipeline's structural validation",
    }
    # Secondary, not used for the verdict: separates "invalid graph" from "worse graph".
    if len(valid) >= 6:
        jo = j_stat(oracle, "epistemic_search", valid)
        jg = j_stat(generated, "epistemic_search", valid)
        out["conditional_on_valid_generated_decomposition"] = {
            "examples": len(valid),
            "J_oracle": jo,
            "J_generated": jg,
            "gap": None if jo is None or jg is None else jo - jg,
            "generated": system_metrics(generated, "epistemic_search", valid),
        }
    return out


def stage_run(spec: Spec, root: Path = ROOT) -> dict[str, Any]:
    estimate_path = root / spec.out / "estimate.json"
    if not estimate_path.exists():
        raise RuntimeError("Run the estimate stage first; the full run needs a logged estimate")
    import json

    from epistemic_search.rv2_run import write_new_json as write

    estimate = json.loads(estimate_path.read_text())
    sample = interleaved(root, int(estimate["chosen_per_size"]))
    started = perf_counter()
    halted = asyncio.run(drive(spec, sample, root))
    rows = all_rows(spec, root)
    result: dict[str, Any] = {
        "experiment": spec.name,
        "code": "tag epistemic-search-v1.1 + oracle injection harness",
        "run_id": spec.run_id,
        "model": MODEL,
        "reasoning_effort": "medium",
        "seed": SEED,
        "sampling_seed": SAMPLING_SEED,
        "dataset": "entailmentbank task_2 dev",
        "sample_ids": [e.id for e in sample],
        "conditions": list(CONDITIONS),
        "arms": [{"mode": m, "oracle_structure": o, "systems": list(s)} for m, o, s in spec.arms],
        "stopped_by_cap": halted,
        "estimate": estimate,
        "ledger": ledger_report(rag_config(spec.run_id, spec.cap_usd)),
        "wall_seconds": perf_counter() - started,
        "case_rows": {m: len(r) for m, r in rows.items()},
    }
    result["metrics"] = summarize_c(rows["oracle"]) if spec is SPEC_C else summarize_b(rows)
    write(root / spec.out / "results.json", result)
    return result


__all__ = ["SPEC_B", "SPEC_C", "classify", "ControlledCase", "stage_estimate", "stage_run"]
