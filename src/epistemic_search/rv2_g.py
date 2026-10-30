"""RV2-G: does a decomposition grounded in the available evidence restore the oracle signal?

Four systems on fresh EntailmentBank examples, COMPLETE vs MISSING_ONE leaf-only pools, no outside
retrieval. B1 is the RV2-F question-only generated-premise system, unchanged; M2 generates its
decomposition once per condition from question + the evidence actually present. Thresholds are
pre-registered in docs/experiments/RV2_G_EVIDENCE_GROUNDED_DECOMPOSITION.md (committed before
any call).
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
from epistemic_search.grounded import category, run_grounded
from epistemic_search.models import QueryCase
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
from epistemic_search.rv2_f import LABEL, generation_summary, index_rows, j_of, sys_metrics
from epistemic_search.rv2_metrics import bootstrap_ci
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

RUN_ID = "rv2-g-evidence-grounded-v1"
CAP_USD = "0.30"
OUT = Path("docs/results/rv2/rv2_g")
CACHE = Path("artifacts/rv2/decomposition-cache")
TARGET_N, MIN_N, SIZES = 30, 24, (2, 3, 4, 5, 6)
B0, B1, M0, M2 = "B0_naive_rag", "B1_question_only", "M0_gold_premises", "M2_evidence_grounded"
SYSTEMS = (B0, B1, M0, M2)
PRIOR = ("rv2_b", "rv2_c", "rv2_e", "rv2_f")

# Pre-registered thresholds (docs/experiments/RV2_G_EVIDENCE_GROUNDED_DECOMPOSITION.md).
COVERAGE_MIN, J_MIN, RECOVERY_MIN, RETAIN, USABLE_MIN = 0.90, 0.65, 0.30, 0.70, 0.90
STRONG_COVERAGE, STRONG_J = 0.95, 0.75
PARTIAL_DELTA, PARTIAL_COVERAGE, PARTIAL_J = 0.20, 0.50, 0.40
PLANNING_FACTOR = 2.0


def seen_ids(root: Path) -> dict[str, list[str]]:
    """Every EntailmentBank example any earlier experiment saw (planned samples included)."""
    seen: dict[str, list[str]] = {}
    for name in PRIOR:
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
            f"eb-g-{s}",
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


def premise_list(
    system: str, ex: EBExample, generated: dict[str, Any] | None
) -> list[dict[str, str]] | None:
    if system == M0:
        return [{"id": s, "text": t} for s, t in sorted(ex.leaves.items())]
    if generated and generated["valid"]:
        return [{"id": p["id"], "text": p["assertion"]} for p in generated["premises"]]
    return None


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
    decomp_path = root / OUT / "decompositions.jsonl"
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
                    info: dict[str, Any] | None = None
                    case = QueryCase(
                        id=f"{ex.id}|{condition.condition}",
                        question=ex.question,
                        gold_answer=ex.answer,
                    )
                    if system == B0:
                        result = await run_system(
                            "naive_rag",
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
                        config = run_config(
                            "grounded_decomposition" if system == M2 else "sufficiency_check",
                            RUN_ID,
                            rag.model_copy(update={"k": 1}),
                            pool_budget(len(condition.docs)),
                            root / CACHE,
                        )
                        if system == M2:
                            result, info = await run_grounded(
                                case, config, corpus(condition), model
                            )
                        else:
                            result = await run_sufficiency(
                                case,
                                config,
                                corpus(condition),
                                premise_list(system, ex, generated),
                                model,
                            )
                    if reason := stop_reason(result, rag):
                        return reason
                    sha = save_trace(result, traces, f"{system}__{ex.id}__{condition.condition}")
                    row = row_from(
                        result, system, ex, condition, "G", RUN_ID, sha, perf_counter() - started
                    )
                    row["condition_label"] = LABEL[condition.condition]
                    row["decision_answer"] = (
                        bool(row["answered"])
                        if system == B0
                        else result.decision is not None and result.decision.action == "ANSWER"
                    )
                    row["premises_used"] = (
                        premise_list(system, ex, generated) if system in (M0, B1) else None
                    )
                    row["generation_valid"] = generated["valid"] if system == B1 else None
                    if info is not None:
                        row["m2_valid"] = info["valid"]
                        row["m2_unresolved_required"] = info["unresolved_required"]
                        row["m2_category"] = (
                            None
                            if row["answered"]
                            else category(info, bool(row["decision_answer"]))
                        )
                        append_row(
                            decomp_path,
                            {
                                "example_id": ex.id,
                                "condition": condition.condition,
                                "condition_label": LABEL[condition.condition],
                                "leaves": len(ex.leaves),
                                "evidence_sentences": len(condition.docs),
                                **info,
                            },
                        )
                    append_row(out, row)
    return None


# ------------------------------------------------------------------ analysis


def complete_set(idx: dict[str, Any]) -> list[str]:
    sets = [{e for e, c in idx.get(s, {}).items() if {"C1", "C2"} <= set(c)} for s in SYSTEMS]
    return sorted(set.intersection(*sets))


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def decomposition_summary(decomps: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]]) -> Any:
    """Deterministic structure statistics for M2; no model judges any node."""
    out: dict[str, Any] = {"decompositions": len(decomps)}
    usable = [d for d in decomps if d["valid"]]
    out["usable"] = len(usable)
    out["usable_rate"] = len(usable) / len(decomps) if decomps else None
    out["malformed_rate"] = (
        sum(d["decomposition"] is None for d in decomps) / len(decomps) if decomps else None
    )
    out["dangling_reference_decompositions"] = sum(
        d.get("dangling_references", 0) > 0 for d in decomps
    )
    out["failures"] = [
        {"example_id": d["example_id"], "condition": d["condition"], "errors": d["errors"][:2]}
        for d in decomps
        if not d["valid"]
    ]
    for label in ("COMPLETE", "MISSING_ONE"):
        stats = [d["stats"] for d in usable if d["condition_label"] == label]
        facts = [s["n_evidence_facts"] for s in stats]
        out[label] = {
            "n": len(stats),
            "evidence_sentences": mean([s["n_evidence_sentences"] for s in stats]),
            "evidence_facts": mean(facts),
            "derived_claims": mean([s["n_derived_claims"] for s in stats]),
            "graph_depth": mean([s["graph_depth"] for s in stats]),
            "required_nodes": mean([s["n_required_nodes"] for s in stats]),
            "required_evidence_facts": mean([s["n_required_evidence_facts"] for s in stats]),
            "compression_ratio": mean([s["compression_ratio"] for s in stats]),
            "decomposition_size": mean([s["decomposition_size"] for s in stats]),
            "duplicate_claims": sum(s["duplicate_claims"] for s in stats),
            "required_equals_all_evidence": sum(s["required_equals_all_evidence"] for s in stats),
            "facts_without_cited_support": mean([s["facts_without_cited_support"] for s in stats]),
            "share_of_required_nodes_that_are_evidence_facts": (
                sum(s["required_nodes_that_are_facts"] for s in stats)
                / sum(s["n_required_nodes"] for s in stats)
                if stats
                else None
            ),
            "claimed_support_rejected_facts": sum(
                d["claimed_support_rejected"] for d in usable if d["condition_label"] == label
            ),
        }
    m2 = [r for r in rows if r["system"] == M2]
    for label in ("COMPLETE", "MISSING_ONE"):
        cells = [r for r in m2 if r["condition_label"] == label]
        counts: dict[str, int] = {}
        for r in cells:
            if r.get("m2_category"):
                counts[r["m2_category"]] = counts.get(r["m2_category"], 0) + 1
        out[label]["no_answer_categories"] = counts
        out[label]["answered"] = sum(bool(r["answered"]) for r in cells)
        out[label]["cases"] = len(cells)
    return out


def decide(
    idx: dict[str, Any],
    gens: Sequence[dict[str, Any]],
    decomps: Sequence[dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    resamples: int = 10_000,
) -> dict[str, Any]:
    units = complete_set(idx)
    out: dict[str, Any] = {"complete_examples": len(units), "example_ids": units}
    if len(units) < MIN_N:
        out["classification"] = {
            "class": "INCONCLUSIVE",
            "rule": f"fewer than {MIN_N} completed fresh examples",
        }
        out["stop_rule_fired"] = False
        return out
    unit_set = set(units)
    systems = {s: sys_metrics(idx, s, units) for s in SYSTEMS}
    out["systems"] = systems
    out["question_only_generation"] = generation_summary(gens, units)
    out["m2_decompositions"] = decomposition_summary(
        [d for d in decomps if d["example_id"] in unit_set],
        [r for r in rows if r["example_id"] in unit_set],
    )

    def ci(stat: Any) -> dict[str, float | None]:
        return bootstrap_ci(list(units), stat, resamples=resamples)

    out["J_ci95"] = {s: ci(lambda u, s=s: j_of(idx, s, list(u))) for s in SYSTEMS}
    out["difference_ci95"] = {
        "M2_minus_B1": ci(lambda u: j_of(idx, M2, list(u)) - j_of(idx, B1, list(u))),
        "M2_minus_B0": ci(lambda u: j_of(idx, M2, list(u)) - j_of(idx, B0, list(u))),
        "M2_minus_M0": ci(lambda u: j_of(idx, M2, list(u)) - j_of(idx, M0, list(u))),
        "M0_minus_B1": ci(lambda u: j_of(idx, M0, list(u)) - j_of(idx, B1, list(u))),
    }
    m2, m0, b1 = systems[M2], systems[M0], systems[B1]
    recovery = m2["J"] - b1["J"]
    usable = out["m2_decompositions"]["usable_rate"] or 0.0
    cond = {
        "A_complete_coverage_ge_0.90": m2["complete_answer_rate"] >= COVERAGE_MIN,
        "B_J_ge_0.65": m2["J"] >= J_MIN,
        "C_recovery_over_question_only_ge_0.30": recovery >= RECOVERY_MIN,
        "D_retains_70pct_of_gold_J": m2["J"] >= RETAIN * m0["J"],
        "E_structurally_usable_ge_0.90": usable >= USABLE_MIN,
        "F_not_abstention_only": m2["complete_answer_rate"] >= COVERAGE_MIN,
    }
    lower = out["difference_ci95"]["M2_minus_B1"]["lower"]
    partial = (
        recovery >= PARTIAL_DELTA
        and lower is not None
        and lower > 0
        and m2["complete_answer_rate"] >= PARTIAL_COVERAGE
        and m2["J"] >= PARTIAL_J
    )
    out["viability"] = cond
    out["inputs"] = {
        "M2_minus_B1": recovery,
        "M2_J_over_M0_J": m2["J"] / m0["J"] if m0["J"] else None,
        "partial_signal_requirements_met": partial,
        "failed_thresholds": [k for k, v in cond.items() if not v],
    }
    out["strong_signal"] = m2["complete_answer_rate"] >= STRONG_COVERAGE and m2["J"] >= STRONG_J
    if all(cond.values()):
        label, rule = "EVIDENCE_GROUNDED_SIGNAL", "A-F all hold"
    elif partial:
        label, rule = (
            "PARTIAL_SIGNAL",
            "M2 clearly beats B1 but misses: " + ", ".join(out["inputs"]["failed_thresholds"]),
        )
    else:
        label, rule = "NO_SIGNAL", "M2 does not materially outperform B1, or J/coverage remain weak"
    out["classification"] = {"class": label, "rule": rule}
    out["stop_rule_fired"] = label == "NO_SIGNAL"
    return out


# ------------------------------------------------------------------ stages


def stage_sample(root: Path = ROOT, n: int = TARGET_N) -> list[EBExample]:
    path = root / OUT / "sample.json"
    sample, seen = fresh_sample(root, n)
    if not path.exists():
        write_new_json(
            root / OUT / "exclusions.json",
            {
                "experiment": "RV2-G evidence-grounded decomposition",
                "excluded_by_experiment": seen,
                "excluded_total": len({i for v in seen.values() for i in v}),
                "note": "RV2-A/D and the earlier pilots used other datasets, not EntailmentBank "
                "examples; no EntailmentBank id outside these samples was seen.",
            },
        )
        write_new_json(
            path,
            {
                "experiment": "RV2-G evidence-grounded decomposition",
                "sampling_seed": SAMPLING_SEED,
                "target_n": n,
                "eligible_leaf_counts": list(SIZES),
                "sample_ids": [e.id for e in sample],
                "leaf_counts": {str(s): sum(len(e.leaves) == s for e in sample) for s in SIZES},
                "overlap_with_excluded": sorted(
                    {e.id for e in sample} & {i for v in seen.values() for i in v}
                ),
            },
        )
    return sample


def total_cost(rows: Sequence[dict[str, Any]], gens: Sequence[dict[str, Any]]) -> float:
    cost = sum(
        float(r["usage"]["new_api_cost_usd"]) + float(r["usage"]["reused_cost_usd"]) for r in rows
    )
    return cost + sum(
        float(g["usage"]["new_api_cost_usd"]) + float(g["usage"]["reused_cost_usd"])
        for g in gens
        if g.get("usage")
    )


def stage_estimate(root: Path = ROOT) -> dict[str, Any]:
    sample = stage_sample(root)
    reason = asyncio.run(drive(sample[:1], root))
    if reason:
        raise RuntimeError(f"Probe stopped: {reason}")
    rows = load_rows(root / OUT / "cases.jsonl")
    gens = load_rows(root / OUT / "generated_premises.jsonl")
    probe = total_cost(rows, gens)
    plans = {str(n): probe * n * PLANNING_FACTOR for n in (TARGET_N, MIN_N)}
    if plans[str(MIN_N)] > float(CAP_USD):
        raise RuntimeError("Even the minimum sample exceeds the hard cap; stop and ask")
    chosen = TARGET_N if plans[str(TARGET_N)] <= float(CAP_USD) * 0.8 else MIN_N
    report = {
        "experiment": "RV2-G evidence-grounded decomposition",
        "run_id": RUN_ID,
        "hard_cap_usd": CAP_USD,
        "probe_example": sample[0].id,
        "probe_leaves": len(sample[0].leaves),
        "probe_logical_cost_usd": probe,
        "planning_factor": PLANNING_FACTOR,
        "planning_cost_usd": plans,
        "chosen_examples": chosen,
        "rule": "30 if probe x N x 2 is within 80% of the cap, else 24; never fewer",
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
    decomps = load_rows(root / OUT / "decompositions.jsonl")
    analysis = decide(index_rows(rows), gens, decomps, rows)
    result = {
        "experiment": "RV2-G evidence-grounded decomposition",
        "code": "tag epistemic-search-v1.1.1 + sufficiency + grounded",
        "run_id": RUN_ID,
        "model": MODEL,
        "reasoning_effort": "medium",
        "seed": SEED,
        "sampling_seed": SAMPLING_SEED,
        "sample_ids": [e.id for e in sample],
        "stopped_by": halted,
        "case_rows": len(rows),
        "generation_rows": len(gens),
        "decomposition_rows": len(decomps),
        "ledger": ledger_report(rag_config(RUN_ID, CAP_USD)),
        "wall_seconds": perf_counter() - started,
        "analysis": analysis,
    }
    write_new_json(root / OUT / "metrics.json", result)
    keep = {"classification", "stop_rule_fired", "viability", "inputs", "complete_examples"}
    write_new_json(
        root / OUT / "decision.json",
        {
            **{k: analysis[k] for k in analysis if k in keep},
            "strong_signal": analysis.get("strong_signal"),
        },
    )
    return result


__all__ = ["stage_estimate", "stage_run"]
