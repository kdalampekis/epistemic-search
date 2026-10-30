"""RV2-F: does premise-aware sufficiency survive when the premises are generated, not gold?

Final go/no-go for the surviving idea. Four systems on fresh EntailmentBank examples, COMPLETE vs
MISSING_ONE leaf-only evidence pools, no outside retrieval. The thresholds implemented here are
pre-registered in docs/experiments/RV2_F_GENERATED_PREMISES.md (committed before any call).
"""

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from epistemic_search.config import RagConfig
from epistemic_search.execution import configured_model, configured_spend
from epistemic_search.providers import ModelProvider
from epistemic_search.rv2_adapters import (
    EBExample,
    eb_proof_graph,
    leaf_conditions,
    load_entailmentbank,
    pick,
)
from epistemic_search.rv2_controlled import (
    append_row,
    corpus,
    done_keys,
    load_rows,
    pool_budget,
    row_from,
    run_system,
    save_trace,
    stop_reason,
)
from epistemic_search.rv2_metrics import bootstrap_ci, normalize_answer
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
from epistemic_search.sufficiency import generate_premises, run_sufficiency

RUN_ID = "rv2-f-generated-premises-v1"
CAP_USD = "0.40"
OUT = Path("docs/results/rv2/rv2_f")
CACHE = Path("artifacts/rv2/decomposition-cache")
TARGET_N, MIN_N, SIZES = 30, 24, (3, 4, 5)
B0, B1, M0, M1 = "B0_naive_rag", "B1_iterative_rag", "M0_gold_premises", "M1_generated_premises"
SYSTEMS = (B0, B1, M0, M1)
METHOD = {B0: "naive_rag", B1: "iterative_rag", M0: "sufficiency_check", M1: "sufficiency_check"}
LABEL = {"C1": "COMPLETE", "C2": "MISSING_ONE"}

# Pre-registered thresholds (docs/experiments/RV2_F_GENERATED_PREMISES.md).
COVERAGE_MIN, J_MIN, DELTA_POINT, DELTA_CI_POINT = 0.90, 0.65, 0.25, 0.20
RETAIN, USABLE_MIN = 0.75, 0.90
M0_COVERAGE, M0_J, M0_MARGIN = 0.90, 0.65, 0.25
NO_SIGNAL_DELTA, NO_SIGNAL_COVERAGE, NO_SIGNAL_J = 0.10, 0.75, 0.40


def seen_ids(root: Path) -> dict[str, list[str]]:
    """Every EntailmentBank example any earlier experiment saw (planned samples included)."""
    seen: dict[str, list[str]] = {}
    for name in ("rv2_b", "rv2_c", "rv2_e"):
        path = root / "docs/results/rv2" / name / "results.json"
        if path.exists():
            seen[name] = sorted(json.loads(path.read_text())["sample_ids"])
    return seen


def fresh_sample(root: Path, n: int) -> tuple[list[EBExample], dict[str, list[str]]]:
    dev = load_entailmentbank(root / "data/external/entailmentbank", "dev")
    seen = seen_ids(root)
    excluded = {i for ids in seen.values() for i in ids}
    groups = [
        pick(
            [
                e
                for e in dev
                if len(e.leaves) == s and e.id not in excluded and eb_proof_graph(e)[0]
            ],
            lambda e: e.id,
            SAMPLING_SEED,
            f"eb-f-{s}",
            10**6,
        )
        for s in SIZES
    ]
    chosen: list[EBExample] = []
    for i in range(max(len(g) for g in groups)):
        for g in groups:
            if i < len(g) and len(chosen) < n:
                chosen.append(g[i])
    return chosen, seen


def premises_for(
    system: str, ex: EBExample, generated: dict[str, Any] | None
) -> list[dict[str, str]] | None:
    if system == M0:
        return [{"id": s, "text": t} for s, t in sorted(ex.leaves.items())]
    if generated and generated["valid"]:
        return [{"id": p["id"], "text": p["assertion"]} for p in generated["premises"]]
    return None


def cell(r: dict[str, Any]) -> dict[str, Any]:
    em = bool(r["answered"]) and normalize_answer(str(r["answer"])) == normalize_answer(
        r["gold_answer"]
    )
    return {**r, "answer_em": em}


async def drive(
    examples: list[EBExample],
    root: Path,
    *,
    rag: RagConfig | None = None,
    provider: ModelProvider | None = None,
) -> str | None:
    """``rag`` and ``provider`` are test seams; the experiment uses the ledgered paid defaults."""
    rag = rag or rag_config(RUN_ID, CAP_USD, max_rounds=3, timeout_seconds=300)
    out, gens_path = root / OUT / "cases.jsonl", root / OUT / "generated_premises.jsonl"
    traces = root / "artifacts/rv2" / RUN_ID / "traces"
    async with httpx.AsyncClient() as client:
        model = provider or configured_model(rag, CONFIG_DIR, client)
        for ex in examples:
            generated = {g["example_id"]: g for g in load_rows(gens_path)}.get(ex.id)
            if generated is None:
                record = await generate_premises(
                    ex.question,
                    model,
                    model_name=MODEL,
                    max_output_tokens=rag.max_output_tokens,
                    seed=SEED,
                )
                spend = configured_spend(rag, CONFIG_DIR)
                if spend and spend.stop_reason():
                    return spend.stop_reason()
                generated = {"example_id": ex.id, "leaves": len(ex.leaves), **record}
                append_row(gens_path, generated)
            finished = done_keys(out)
            for condition in leaf_conditions(ex, SAMPLING_SEED):
                for system in SYSTEMS:
                    if (system, ex.id, condition.condition) in finished:
                        continue
                    started = perf_counter()
                    if system in (B0, B1):
                        result = await run_system(
                            METHOD[system],
                            ex,
                            condition,
                            oracle=False,
                            base_rag=rag,
                            run_id=RUN_ID,
                            cache_dir=root / CACHE,
                            client=client,
                            model=model,
                            retrieval="given",
                        )
                    else:
                        case = _case(ex, condition.condition)
                        config = run_config(
                            "sufficiency_check",
                            RUN_ID,
                            rag.model_copy(update={"k": 1}),
                            pool_budget(len(condition.docs)),
                            root / CACHE,
                        )
                        result = await run_sufficiency(
                            case,
                            config,
                            corpus(condition),
                            premises_for(system, ex, generated),
                            model,
                        )
                    if reason := stop_reason(result, rag):
                        return reason
                    sha = save_trace(result, traces, f"{system}__{ex.id}__{condition.condition}")
                    row = row_from(
                        result, system, ex, condition, "F", RUN_ID, sha, perf_counter() - started
                    )
                    row["condition_label"] = LABEL[condition.condition]
                    row["decision_answer"] = (
                        result.decision is not None and result.decision.action == "ANSWER"
                        if system in (M0, M1)
                        else bool(row["answered"])
                    )
                    row["premises_used"] = (
                        premises_for(system, ex, generated) if system in (M0, M1) else None
                    )
                    row["generation_valid"] = generated["valid"] if system == M1 else None
                    append_row(out, row)
    return None


def _case(ex: EBExample, condition: str) -> Any:
    from epistemic_search.models import QueryCase

    return QueryCase(id=f"{ex.id}|{condition}", question=ex.question, gold_answer=ex.answer)


# ------------------------------------------------------------------ analysis


def index_rows(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    out: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for r in rows:
        out.setdefault(r["system"], {}).setdefault(r["example_id"], {})[r["condition"]] = cell(r)
    return out


def complete_set(idx: dict[str, Any]) -> list[str]:
    sets = [{e for e, c in idx.get(s, {}).items() if {"C1", "C2"} <= set(c)} for s in SYSTEMS]
    return sorted(set.intersection(*sets))


def rates(
    idx: dict[str, Any], system: str, units: Sequence[str], key: str = "decision_answer"
) -> tuple[float, float]:
    c = sum(bool(idx[system][e]["C1"][key]) for e in units) / len(units)
    m = sum(bool(idx[system][e]["C2"][key]) for e in units) / len(units)
    return c, m


def j_of(idx: dict[str, Any], system: str, units: Sequence[str]) -> float:
    c, m = rates(idx, system, units)
    return c - m


def sys_metrics(idx: dict[str, Any], system: str, units: Sequence[str]) -> dict[str, Any]:
    cells = [idx[system][e][c] for e in units for c in ("C1", "C2")]
    complete = [idx[system][e]["C1"] for e in units]
    answered_complete = [r for r in complete if r["answered"]]
    c, m = rates(idx, system, units)
    sc, sm = rates(idx, system, units, "answered")
    usage = [r["usage"] for r in cells]
    return {
        "complete_answer_rate": c,
        "missing_answer_rate": m,
        "J": c - m,
        "abstention_rate": 1 - (c + m) / 2,
        "strict_complete_rate": sc,
        "strict_missing_rate": sm,
        "strict_J": sc - sm,
        "errors": sum(r["outcome"] in {"ERROR", "BUDGET_STOP"} for r in cells),
        "resolved_but_no_answer": sum(
            bool(r["decision_answer"]) and not r["answered"] for r in cells
        ),
        "answer_exact_match_among_complete_answers": (
            sum(r["answer_em"] for r in answered_complete) / len(answered_complete)
            if answered_complete
            else None
        ),
        "answer_normalized_match_among_complete_answers": (
            sum(bool(r["answer_hit"]) for r in answered_complete) / len(answered_complete)
            if answered_complete
            else None
        ),
        "model_calls": sum(u["model_calls"] for u in usage),
        "prompt_tokens": sum(u["prompt_tokens"] for u in usage),
        "completion_tokens": sum(u["completion_tokens"] for u in usage),
        "logical_cost_usd": sum(
            float(u["new_api_cost_usd"]) + float(u["reused_cost_usd"]) for u in usage
        ),
        "new_api_cost_usd": sum(float(u["new_api_cost_usd"]) for u in usage),
        "mean_latency_seconds": sum(u["latency_seconds"] for u in usage) / len(usage),
    }


def generation_summary(gens: Sequence[dict[str, Any]], units: Sequence[str]) -> dict[str, Any]:
    chosen = [g for g in gens if g["example_id"] in set(units)]
    valid = [g for g in chosen if g["valid"]]
    flags = [g["flags"] for g in valid]
    cost = sum(
        float(g["usage"]["new_api_cost_usd"]) + float(g["usage"]["reused_cost_usd"])
        for g in chosen
        if g.get("usage")
    )
    return {
        "examples": len(chosen),
        "structurally_usable": len(valid),
        "structural_validity_rate": len(valid) / len(chosen) if chosen else None,
        "generation_failure_rate": 1 - len(valid) / len(chosen) if chosen else None,
        "failures": [
            {"example_id": g["example_id"], "error": g["error"]} for g in chosen if not g["valid"]
        ],
        "mean_premises": sum(f["n_premises"] for f in flags) / len(flags) if flags else None,
        "non_assertion_premise_rate": (
            sum(f["non_assertion_premises"] for f in flags) / sum(f["n_premises"] for f in flags)
            if flags
            else None
        ),
        "duplicate_premise_rate": (
            sum(f["duplicate_premises"] for f in flags) / sum(f["n_premises"] for f in flags)
            if flags
            else None
        ),
        "proof_graph_conversion_rate": sum(f["proof_graph_conversion_ok"] for f in flags)
        / len(flags)
        if flags
        else None,
        "generation_tokens": sum(
            g["usage"]["prompt_tokens"] + g["usage"]["completion_tokens"]
            for g in chosen
            if g.get("usage")
        ),
        "generation_cost_usd": cost,
        "mean_gold_leaves": sum(g["leaves"] for g in chosen) / len(chosen) if chosen else None,
    }


def decide(
    idx: dict[str, Any], gens: Sequence[dict[str, Any]], resamples: int = 10_000
) -> dict[str, Any]:
    units = complete_set(idx)
    out: dict[str, Any] = {"complete_examples": len(units), "example_ids": units}
    if len(units) < MIN_N:
        out["classification"] = {
            "class": "INCONCLUSIVE",
            "rule": f"fewer than {MIN_N} completed fresh examples",
        }
        return out
    systems = {s: sys_metrics(idx, s, units) for s in SYSTEMS}
    out["systems"] = systems
    out["generation"] = generation_summary(gens, units)

    def ci(stat: Any) -> dict[str, float | None]:
        return bootstrap_ci(list(units), stat, resamples=resamples)

    out["J_ci95"] = {s: ci(lambda u, s=s: j_of(idx, s, list(u))) for s in SYSTEMS}

    def best(u: Sequence[str]) -> float:
        return max(j_of(idx, B0, list(u)), j_of(idx, B1, list(u)))

    out["difference_ci95"] = {
        "M1_minus_B0": ci(lambda u: j_of(idx, M1, list(u)) - j_of(idx, B0, list(u))),
        "M1_minus_B1": ci(lambda u: j_of(idx, M1, list(u)) - j_of(idx, B1, list(u))),
        "M1_minus_best_baseline": ci(lambda u: j_of(idx, M1, list(u)) - best(u)),
        "M1_minus_M0": ci(lambda u: j_of(idx, M1, list(u)) - j_of(idx, M0, list(u))),
        "M0_minus_best_baseline": ci(lambda u: j_of(idx, M0, list(u)) - best(u)),
    }
    m1, m0 = systems[M1], systems[M0]
    best_j = max(systems[B0]["J"], systems[B1]["J"])
    delta = m1["J"] - best_j
    d_ci = out["difference_ci95"]["M1_minus_best_baseline"]
    usable = out["generation"]["structural_validity_rate"] or 0.0
    cond = {
        "A_complete_coverage_ge_0.90": m1["complete_answer_rate"] >= COVERAGE_MIN,
        "B_J_ge_0.65": m1["J"] >= J_MIN,
        "C_advantage_over_best_baseline": delta >= DELTA_POINT
        or (d_ci["lower"] is not None and d_ci["lower"] > 0 and delta >= DELTA_CI_POINT),
        "D_retains_75pct_of_gold_J": m1["J"] >= RETAIN * m0["J"],
        "E_structurally_usable_ge_0.90": usable >= USABLE_MIN,
    }
    m0_strong = (
        m0["complete_answer_rate"] >= M0_COVERAGE
        and m0["J"] >= M0_J
        and m0["J"] - best_j >= M0_MARGIN
    )
    no_signal = {
        "delta_over_best_baseline_below_0.10": delta < NO_SIGNAL_DELTA,
        "m1_complete_coverage_below_0.75": m1["complete_answer_rate"] < NO_SIGNAL_COVERAGE,
        "m1_J_below_0.40": m1["J"] < NO_SIGNAL_J,
    }
    out["viability"] = cond
    out["inputs"] = {
        "best_baseline_J": best_j,
        "M1_minus_best_baseline": delta,
        "M0_strong": m0_strong,
        "no_signal_flags": no_signal,
    }
    if all(cond.values()):
        label, rule = "PROMISING_COMPONENT", "A-E all hold"
    elif m0_strong and not any(no_signal.values()):
        label, rule = (
            "ORACLE_DEPENDENT",
            "gold-premise M0 strong; M1 fails viability but keeps partial signal",
        )
    else:
        label, rule = (
            "NO_END_TO_END_SIGNAL",
            (
                "M1 not viable and "
                + (
                    "shows no meaningful signal over the baselines"
                    if any(no_signal.values())
                    else "the positive control M0 is not strong"
                )
            ),
        )
    out["classification"] = {"class": label, "rule": rule}
    out["stop_rule_fired"] = label in {"ORACLE_DEPENDENT", "NO_END_TO_END_SIGNAL"}
    return out


# ------------------------------------------------------------------ stages


def stage_sample(root: Path = ROOT, n: int = TARGET_N) -> list[EBExample]:
    path = root / OUT / "sample.json"
    sample, seen = fresh_sample(root, n)
    if not path.exists():
        write_new_json(
            path,
            {
                "experiment": "RV2-F generated-premise sufficiency",
                "sampling_seed": SAMPLING_SEED,
                "target_n": n,
                "sample_ids": [e.id for e in sample],
                "leaf_counts": {str(s): sum(len(e.leaves) == s for e in sample) for s in SIZES},
                "excluded_seen_ids": seen,
                "excluded_total": len({i for v in seen.values() for i in v}),
                "overlap_with_excluded": sorted(
                    {e.id for e in sample} & {i for v in seen.values() for i in v}
                ),
            },
        )
    return sample


def stage_estimate(root: Path = ROOT) -> dict[str, Any]:
    sample = stage_sample(root)
    reason = asyncio.run(drive(sample[:1], root))
    if reason:
        raise RuntimeError(f"Probe stopped: {reason}")
    rows = load_rows(root / OUT / "cases.jsonl")
    gens = load_rows(root / OUT / "generated_premises.jsonl")
    probe = sum(
        float(r["usage"]["new_api_cost_usd"]) + float(r["usage"]["reused_cost_usd"]) for r in rows
    ) + sum(
        float(g["usage"]["new_api_cost_usd"]) + float(g["usage"]["reused_cost_usd"])
        for g in gens
        if g.get("usage")
    )
    plans = {str(n): probe * n for n in (TARGET_N, MIN_N)}
    chosen = TARGET_N if plans[str(TARGET_N)] <= float(CAP_USD) * 0.8 else MIN_N
    report = {
        "experiment": "RV2-F generated-premise sufficiency",
        "run_id": RUN_ID,
        "hard_cap_usd": CAP_USD,
        "probe_example": sample[0].id,
        "probe_logical_cost_usd": probe,
        "planning_cost_usd": plans,
        "chosen_examples": chosen,
        "rule": "30 if the planning cost is within 80% of the cap, else 24; never fewer",
        "ledger_after_probe": ledger_report(rag_config(RUN_ID, CAP_USD)),
    }
    write_new_json(root / OUT / "estimate.json", report)
    return report


def stage_run(root: Path = ROOT) -> dict[str, Any]:
    path = root / OUT / "estimate.json"
    if not path.exists():
        raise RuntimeError("Run the estimate stage first; the full run needs a logged estimate")
    chosen = int(json.loads(path.read_text())["chosen_examples"])
    sample = stage_sample(root, chosen)[:chosen]
    started = perf_counter()
    halted = asyncio.run(drive(sample, root))
    rows = load_rows(root / OUT / "cases.jsonl")
    gens = load_rows(root / OUT / "generated_premises.jsonl")
    idx = index_rows(rows)
    decision = decide(idx, gens)
    result = {
        "experiment": "RV2-F generated-premise sufficiency",
        "code": "tag epistemic-search-v1.1.1 + sufficiency",
        "run_id": RUN_ID,
        "model": MODEL,
        "reasoning_effort": "medium",
        "seed": SEED,
        "sampling_seed": SAMPLING_SEED,
        "sample_ids": [e.id for e in sample],
        "stopped_by": halted,
        "case_rows": len(rows),
        "generation_rows": len(gens),
        "ledger": ledger_report(rag_config(RUN_ID, CAP_USD)),
        "wall_seconds": perf_counter() - started,
        "analysis": decision,
    }
    write_new_json(root / OUT / "results.json", result)
    write_new_json(
        root / OUT / "decision.json",
        {
            k: decision[k]
            for k in decision
            if k
            in {"classification", "stop_rule_fired", "viability", "inputs", "complete_examples"}
        },
    )
    return result


__all__ = ["RagConfig", "stage_estimate", "stage_run"]
