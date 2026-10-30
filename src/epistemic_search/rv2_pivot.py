"""RV2-E: one last, narrow test of the simpler architecture (premise-state) on fresh examples.

Systems: B0 naive RAG, B1 iterative RAG, M1 premise-only, M2 premise-state. Primary experiment
(E-A) is the controlled sufficiency test of RV2-C on EntailmentBank examples never used before;
secondary (E-B) lets the systems find evidence by search in the full 25-sentence context.
M1 and M2 get the gold premises (as in RV2-C), so this isolates sufficiency judgment and control.
"""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from epistemic_search.rv2_adapters import (
    EBExample,
    controlled_conditions,
    eb_proof_graph,
    load_entailmentbank,
    pick,
    retrieval_conditions,
)
from epistemic_search.rv2_analysis import (
    CONDITIONS,
    index,
    j_stat,
    rate,
    system_metrics,
)
from epistemic_search.rv2_controlled import load_rows, run_example
from epistemic_search.rv2_metrics import bootstrap_ci
from epistemic_search.rv2_run import (
    MODEL,
    ROOT,
    SAMPLING_SEED,
    SEED,
    ledger_report,
    rag_config,
    write_new_json,
)

RUN_ID = "rv2-e-pivot-v1"
CAP_USD = "0.50"
OUT = Path("docs/results/rv2/rv2_e")
CACHE = Path("artifacts/rv2/decomposition-cache")
SIZES = (3, 4, 5)
PER_SIZE_CHOICES = (12, 8, 4)
SYSTEMS = ("naive_rag", "iterative_rag", "premise_only", "premise_state")
B0, B1, M1, M2 = SYSTEMS
BASELINES = (B0, B1)
RETRIEVAL = ("R1", "R2")

# Pre-registered thresholds.
J_MIN, COVERAGE_MIN, BASELINE_MARGIN = 0.75, 0.90, 0.50
ADD_J, ADD_RECALL, COST_RATIO, MIN_EXAMPLES = 0.05, 0.10, 1.5, 24


def used_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for name in ("rv2_b", "rv2_c"):
        path = root / "docs/results/rv2" / name / "results.json"
        if path.exists():
            ids |= set(json.loads(path.read_text())["sample_ids"])
    return ids


def fresh_sample(root: Path, per_size: int) -> list[EBExample]:
    """Dev examples never used in RV2-B/C, seeded, round-robin over leaf counts."""
    dev = load_entailmentbank(root / "data/external/entailmentbank", "dev")
    used = used_ids(root)
    groups = []
    for size in SIZES:
        pool = [
            e
            for e in dev
            if len(e.leaves) == size
            and e.id not in used
            and len(e.distractors) >= 4
            and eb_proof_graph(e)[0] is not None
        ]
        groups.append(pick(pool, lambda e: e.id, SAMPLING_SEED, f"eb-pivot-{size}", per_size))
    return [g[i] for i in range(per_size) for g in groups if i < len(g)]


async def drive(examples: list[EBExample], root: Path) -> str | None:
    rag = rag_config(RUN_ID, CAP_USD, max_rounds=3)
    traces = root / "artifacts/rv2" / RUN_ID / "traces"
    async with httpx.AsyncClient() as client:
        for ex in examples:
            for mode, conditions, retrieval in (
                ("given", controlled_conditions(ex, SAMPLING_SEED), "given"),
                ("lexical", retrieval_conditions(ex, SAMPLING_SEED), "lexical"),
            ):
                reason = await run_example(
                    ex,
                    conditions,
                    systems=SYSTEMS,
                    oracle=True,
                    mode=mode,
                    base_rag=rag,
                    run_id=RUN_ID,
                    cache_dir=root / CACHE,
                    out=root / OUT / f"cases_{mode}.jsonl",
                    traces=traces / mode,
                    client=client,
                    retrieval=retrieval,
                )
                if reason:
                    return reason
    return None


def complete_for(rows: Any, systems: Sequence[str], conditions: Sequence[str]) -> list[str]:
    """Examples where every listed system finished every listed condition."""
    sets = [{e for e, c in rows.get(s, {}).items() if set(conditions) <= set(c)} for s in systems]
    return sorted(set.intersection(*sets)) if sets else []


def logical(rows: Sequence[dict[str, Any]]) -> float:
    return float(
        sum(
            float(r["usage"]["new_api_cost_usd"]) + float(r["usage"]["reused_cost_usd"])
            for r in rows
        )
    )


def summarize(
    given: list[dict[str, Any]], lexical: list[dict[str, Any]], resamples: int = 10_000
) -> dict[str, Any]:
    gi, lx = index(given), index(lexical)
    examples = complete_for(gi, SYSTEMS, CONDITIONS)
    out: dict[str, Any] = {"complete_examples": len(examples), "example_ids": examples}
    if not examples:
        return out
    out["E_A"] = {s: system_metrics(gi, s, examples) for s in SYSTEMS}
    j = {s: j_stat(gi, s, examples) for s in SYSTEMS}
    cov = {s: rate(gi, s, examples, ("C1", "C4")) for s in SYSTEMS}

    def delta(units: Sequence[str]) -> float | None:
        a, b = j_stat(gi, M2, list(units)), j_stat(gi, M1, list(units))
        return None if a is None or b is None else a - b

    ci = bootstrap_ci(list(examples), delta, resamples=resamples)
    best_base = max(float(j[b] or 0) for b in BASELINES)

    def viable(system: str) -> bool:
        return bool(
            (j[system] or 0) >= J_MIN
            and (cov[system] or 0) >= COVERAGE_MIN
            and (j[system] or 0) - best_base >= BASELINE_MARGIN
        )

    sufficiency_gain = bool(
        ci["point"] is not None
        and ci["point"] >= ADD_J
        and ci["lower"] is not None
        and ci["lower"] > 0
    )
    cost_m1, cost_m2 = (
        logical([r for r in given if r["system"] == M1]),
        logical([r for r in given if r["system"] == M2]),
    )
    cost_ratio = cost_m2 / cost_m1 if cost_m1 else None

    # E-B: evidence must be found by search.
    lex_examples = complete_for(lx, SYSTEMS, RETRIEVAL)
    eb: dict[str, Any] = {"complete_examples": len(lex_examples)}
    search_gain = False
    if lex_examples:

        def recall(system: str, units: Sequence[str]) -> float:
            cells = [lx[system][e]["R1"] for e in units]
            return float(sum(len(c["leaves_retrieved"]) / c["leaves"] for c in cells) / len(cells))

        eb["systems"] = {
            s: {
                "answer_rate_R1_complete": rate(lx, s, lex_examples, ("R1",)),
                "answer_rate_R2_missing": rate(lx, s, lex_examples, ("R2",)),
                "J": (rate(lx, s, lex_examples, ("R1",)) or 0)
                - (rate(lx, s, lex_examples, ("R2",)) or 0),
                "required_leaf_recall_R1": recall(s, lex_examples),
                "mean_searches": sum(
                    lx[s][e][c]["usage"]["search_calls"] for e in lex_examples for c in RETRIEVAL
                )
                / (2 * len(lex_examples)),
                "logical_cost_usd": logical([lx[s][e][c] for e in lex_examples for c in RETRIEVAL]),
            }
            for s in SYSTEMS
        }
        rci = bootstrap_ci(
            list(lex_examples), lambda u: recall(M2, u) - recall(M1, u), resamples=resamples
        )
        eb["recall_gain_M2_minus_M1"] = rci
        search_gain = bool(
            rci["point"] is not None
            and rci["point"] >= ADD_RECALL
            and rci["lower"] is not None
            and rci["lower"] > 0
            and (cost_ratio or 99) <= COST_RATIO
        )
    out["E_B"] = eb
    r1, r2 = viable(M1), viable(M2)
    adds = sufficiency_gain or search_gain
    if len(examples) < MIN_EXAMPLES:
        outcome, rule = "INCONCLUSIVE", f"fewer than {MIN_EXAMPLES} complete examples"
    elif not r1:
        outcome, rule = "STOP", "R1 failed: premise-only did not replicate the RV2-C separation"
    elif r2 and adds:
        outcome, rule = "PIVOT_VALIDATED", "R1 and R2 hold and M2 adds value over M1"
    else:
        outcome, rule = "PREMISE_ONLY_SUFFICES", "R1 holds; M2 adds nothing (or is not viable)"
    out["decision_inputs"] = {
        "J": j,
        "coverage_on_complete": cov,
        "best_baseline_J": best_base,
        "R1_premise_only_viable": r1,
        "R2_premise_state_viable": r2,
        "delta_J_M2_minus_M1": ci,
        "sufficiency_gain": sufficiency_gain,
        "search_gain": search_gain,
        "cost_ratio_M2_over_M1": cost_ratio,
    }
    out["outcome"] = {"class": outcome, "rule": rule}
    return out


def plan_cost(probe_rows: list[dict[str, Any]], n_examples: int, n_probe: int) -> float:
    return logical(probe_rows) / n_probe * n_examples


def stage_estimate(root: Path = ROOT) -> dict[str, Any]:
    probe = fresh_sample(root, 4)[0]
    reason = asyncio.run(drive([probe], root))
    if reason:
        raise RuntimeError(f"Probe stopped: {reason}")
    rows = load_rows(root / OUT / "cases_given.jsonl") + load_rows(
        root / OUT / "cases_lexical.jsonl"
    )
    sizes = {n: len(fresh_sample(root, n)) for n in PER_SIZE_CHOICES}
    plans = {
        str(n): {"examples": sizes[n], "planning_cost_usd": plan_cost(rows, sizes[n], 1)}
        for n in PER_SIZE_CHOICES
    }
    chosen = next(
        (n for n in PER_SIZE_CHOICES if plans[str(n)]["planning_cost_usd"] <= 0.8 * float(CAP_USD)),
        4,
    )
    report = {
        "experiment": "RV2-E pivot validation",
        "run_id": RUN_ID,
        "hard_cap_usd": CAP_USD,
        "probe_example": probe.id,
        "probe_logical_cost_usd": logical(rows),
        "probe_mean_case_seconds": sum(r["wall_seconds"] for r in rows) / len(rows),
        "plans": plans,
        "rule": "largest per-size in (12, 8, 4) with planning cost <= 80% of the cap",
        "chosen_per_size": chosen,
        "chosen_examples": sizes[chosen],
        "ledger_after_probe": ledger_report(rag_config(RUN_ID, CAP_USD)),
    }
    write_new_json(root / OUT / "estimate.json", report)
    return report


def stage_run(root: Path = ROOT) -> dict[str, Any]:
    path = root / OUT / "estimate.json"
    if not path.exists():
        raise RuntimeError("Run the estimate stage first; the full run needs a logged estimate")
    estimate = json.loads(path.read_text())
    sample = fresh_sample(root, int(estimate["chosen_per_size"]))
    started = perf_counter()
    halted = asyncio.run(drive(sample, root))
    given, lexical = (load_rows(root / OUT / f"cases_{m}.jsonl") for m in ("given", "lexical"))
    result = {
        "experiment": "RV2-E pivot validation",
        "code": "tag epistemic-search-v1.1.1 + premise_state",
        "run_id": RUN_ID,
        "model": MODEL,
        "reasoning_effort": "medium",
        "seed": SEED,
        "sampling_seed": SAMPLING_SEED,
        "dataset": "entailmentbank task_2 dev (fresh examples)",
        "sample_ids": [e.id for e in sample],
        "conditions": {"given": list(CONDITIONS), "lexical": list(RETRIEVAL)},
        "systems": {"B0": B0, "B1": B1, "M1": M1, "M2": M2},
        "stopped_by_cap": halted,
        "estimate": estimate,
        "metrics": summarize(given, lexical),
        "ledger": ledger_report(rag_config(RUN_ID, CAP_USD)),
        "wall_seconds": perf_counter() - started,
        "case_rows": {"given": len(given), "lexical": len(lexical)},
    }
    write_new_json(root / OUT / "results.json", result)
    return result
