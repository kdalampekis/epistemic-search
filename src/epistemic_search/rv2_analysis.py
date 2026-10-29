"""RV2-B/C analysis: the pre-registered metrics and Q1-Q4 rules, with no discretion.

Thresholds are the ones committed in RV2_EXTERNAL_VALIDATION_PLAN.md before any model call.
"""

from collections.abc import Sequence
from typing import Any, Literal

from epistemic_search.rv2_metrics import bootstrap_ci, ratio

Verdict = Literal["YES", "NO", "UNDETERMINED"]
COMPLETE = ("C1", "C4")
INCOMPLETE = ("C2", "C3")
CONDITIONS = ("C1", "C2", "C3", "C4")
BASELINES = ("premise_only", "naive_rag")

# Pre-registered thresholds.
Q1_COVERAGE_YES, Q1_HIT_YES, Q1_COVERAGE_NO = 0.80, 0.70, 0.60
Q2_DELTA_YES, Q2_COVERAGE_YES, Q2_DELTA_NO, Q2_COVERAGE_NO = 0.20, 0.60, 0.05, 0.50
Q3_ABSOLUTE, Q3_MARGIN = 0.25, 0.20
Q4_DELTA = 0.20
MIN_EXAMPLES = 12
DEPTH_MIN_GROUP = 5


Rows = dict[str, dict[str, dict[str, Any]]]  # system -> example -> condition -> row


def index(rows: Sequence[dict[str, Any]]) -> Rows:
    out: Rows = {}
    for r in rows:
        out.setdefault(r["system"], {}).setdefault(r["example_id"], {})[r["condition"]] = r
    return out


def complete_examples(rows: Rows, systems: Sequence[str]) -> list[str]:
    """Examples where every listed system finished all four conditions (closed-book needs NA)."""
    sets = []
    for system in systems:
        need = {"NA"} if system == "closed_book" else set(CONDITIONS)
        sets.append({e for e, c in rows.get(system, {}).items() if need <= set(c)})
    return sorted(set.intersection(*sets)) if sets else []


def answered(row: dict[str, Any]) -> bool:
    return bool(row["answered"])


def rate(
    rows: Rows, system: str, examples: Sequence[str], conditions: Sequence[str]
) -> float | None:
    cells = [rows[system][e][c] for e in examples for c in conditions]
    return ratio(sum(answered(r) for r in cells), len(cells))


def j_stat(rows: Rows, system: str, examples: Sequence[str]) -> float | None:
    """Coverage on complete evidence minus answer rate on incomplete evidence."""
    a, b = rate(rows, system, examples, COMPLETE), rate(rows, system, examples, INCOMPLETE)
    return None if a is None or b is None else a - b


def system_metrics(rows: Rows, system: str, examples: Sequence[str]) -> dict[str, Any]:
    cells = {c: [rows[system][e][c] for e in examples] for c in CONDITIONS}
    all_cells = [r for cs in cells.values() for r in cs]
    complete_answers = [r for c in COMPLETE for r in cells[c] if answered(r)]
    wrong = [r for r in complete_answers if not r["answer_hit"]]
    unsupported = [r for c in INCOMPLETE for r in cells[c] if answered(r)]
    n_answers = sum(answered(r) for r in all_cells)
    usage = [r["usage"] for r in all_cells]
    out: dict[str, Any] = {
        "examples": len(examples),
        "answer_rate": {
            c: ratio(sum(answered(r) for r in cells[c]), len(cells[c])) for c in CONDITIONS
        },
        "coverage_on_complete": rate(rows, system, examples, COMPLETE),
        "unsupported_answer_rate": rate(rows, system, examples, INCOMPLETE),
        "J": j_stat(rows, system, examples),
        "abstention_rate": ratio(sum(r["outcome"] == "ABSTAIN" for r in all_cells), len(all_cells)),
        "errors_and_budget_stops": sum(r["outcome"] in {"ERROR", "BUDGET_STOP"} for r in all_cells),
        "answer_hit_rate_among_complete_answers": ratio(
            len(complete_answers) - len(wrong), len(complete_answers)
        ),
        "mean_answer_f1_among_complete_answers": (
            sum(r["answer_f1"] or 0 for r in complete_answers) / len(complete_answers)
            if complete_answers
            else None
        ),
        "selective_risk": ratio(len(unsupported) + len(wrong), n_answers),
        "cases": len(all_cells),
        "model_calls": sum(u["model_calls"] for u in usage),
        "search_calls": sum(u["search_calls"] for u in usage),
        "prompt_tokens": sum(u["prompt_tokens"] for u in usage),
        "completion_tokens": sum(u["completion_tokens"] for u in usage),
        "new_api_cost_usd": sum(float(u["new_api_cost_usd"]) for u in usage),
        "logical_cost_usd": sum(
            float(u["new_api_cost_usd"]) + float(u["reused_cost_usd"]) for u in usage
        ),
        "mean_latency_seconds": sum(u["latency_seconds"] for u in usage) / len(usage)
        if usage
        else None,
        "span_rejections": sum(r["span_rejections"] for r in all_cells),
    }
    if system == "epistemic_search":
        complete_cells = [r for c in COMPLETE for r in cells[c]]
        missing_cells = [r for c in INCOMPLETE for r in cells[c]]
        out["proof_completion_accuracy"] = ratio(
            sum(r["unresolved_leaves"] == [] for r in complete_cells), len(complete_cells)
        )
        out["blocker_localization_exact"] = ratio(
            sum(r["unresolved_leaves"] == [r["removed_leaf"]] for r in missing_cells),
            len(missing_cells),
        )
        out["removed_leaf_among_blockers"] = ratio(
            sum(r["removed_leaf"] in (r["unresolved_leaves"] or []) for r in missing_cells),
            len(missing_cells),
        )
        out["mean_unresolved_premises"] = {
            c: sum(len(r["unresolved_leaves"] or []) for r in cells[c]) / len(cells[c])
            for c in CONDITIONS
        }
        out["no_progress_stops"] = sum(r["no_progress"] for r in all_cells)
    return out


def distractor_robustness(
    rows: Rows, system: str, examples: Sequence[str]
) -> dict[str, float | None]:
    def at(condition: str) -> float | None:
        return rate(rows, system, examples, (condition,))

    c1, c4, c2, c3 = at("C1"), at("C4"), at("C2"), at("C3")
    return {
        "coverage_drop_C1_to_C4": None if c1 is None or c4 is None else c1 - c4,
        "answer_rate_rise_C2_to_C3": None if c2 is None or c3 is None else c3 - c2,
    }


def contrast(rows: Rows, examples: Sequence[str], resamples: int = 10_000) -> dict[str, Any]:
    """J(ES) - max(J(premise-only), J(naive)), paired over examples with a seeded bootstrap."""

    def delta(units: Sequence[str]) -> float | None:
        # resampled units may repeat an example; rate() averages over the multiset
        js = {s: j_stat(rows, s, list(units)) for s in ("epistemic_search", *BASELINES)}
        if any(v is None for v in js.values()):
            return None
        return float(js["epistemic_search"] or 0) - max(float(js[s] or 0) for s in BASELINES)

    ci = bootstrap_ci(list(examples), delta, resamples=resamples)
    return {"delta_J": ci["point"], "ci95": [ci["lower"], ci["upper"]]}


def depth_split(rows: Rows, examples: Sequence[str]) -> dict[str, Any]:
    depth = {e: rows["epistemic_search"][e]["C1"]["depth"] for e in examples}
    shallow = [e for e in examples if depth[e] <= 2]
    deep = [e for e in examples if depth[e] >= 3]
    js = j_stat(rows, "epistemic_search", shallow) if shallow else None
    jd = j_stat(rows, "epistemic_search", deep) if deep else None
    enough = len(shallow) >= DEPTH_MIN_GROUP and len(deep) >= DEPTH_MIN_GROUP
    triggered = bool(enough and js is not None and jd is not None and js > 0 and jd < 0.5 * js)
    return {
        "shallow_examples": len(shallow),
        "deep_examples": len(deep),
        "J_depth_le_2": js,
        "J_depth_ge_3": jd,
        "evaluable": enough,
        "architecture_revision_triggered": triggered,
    }


def q1(rows: Rows, examples: Sequence[str]) -> dict[str, Any]:
    m = system_metrics(rows, "epistemic_search", examples)
    cov, hit = m["coverage_on_complete"], m["answer_hit_rate_among_complete_answers"]
    verdict: Verdict
    if cov is not None and cov < Q1_COVERAGE_NO:
        verdict = "NO"
    elif cov is not None and cov >= Q1_COVERAGE_YES and hit is not None and hit >= Q1_HIT_YES:
        verdict = "YES"
    else:
        verdict = "UNDETERMINED"
    return {"verdict": verdict, "coverage_on_complete": cov, "answer_hit_rate": hit}


def q2(rows: Rows, examples: Sequence[str], resamples: int = 10_000) -> dict[str, Any]:
    c = contrast(rows, examples, resamples)
    cov = system_metrics(rows, "epistemic_search", examples)["coverage_on_complete"]
    delta, lower = c["delta_J"], c["ci95"][0]
    verdict: Verdict
    if (delta is not None and delta <= Q2_DELTA_NO) or (cov is not None and cov < Q2_COVERAGE_NO):
        verdict = "NO"
    elif (
        delta is not None
        and delta >= Q2_DELTA_YES
        and lower is not None
        and lower > 0
        and cov is not None
        and cov >= Q2_COVERAGE_YES
    ):
        verdict = "YES"
    else:
        verdict = "UNDETERMINED"
    return {"verdict": verdict, **c, "es_coverage_on_complete": cov}


def q3(rows: Rows, examples: Sequence[str]) -> dict[str, Any]:
    es = rate(rows, "epistemic_search", examples, ("C3",))
    best = min(float(rate(rows, s, examples, ("C3",)) or 0) for s in BASELINES)
    ok = es is not None and es <= Q3_ABSOLUTE and es <= best - Q3_MARGIN
    return {
        "verdict": "YES" if ok else "NO",
        "es_answer_rate_C3": es,
        "best_baseline_answer_rate_C3": best,
    }


def q4(oracle: Rows, generated: Rows, examples: Sequence[str]) -> dict[str, Any]:
    usable = [
        e
        for e in examples
        if e in generated.get("epistemic_search", {})
        and set(CONDITIONS) <= set(generated["epistemic_search"][e])
    ]
    if len(usable) < MIN_EXAMPLES:
        return {
            "verdict": "UNDETERMINED",
            "examples": len(usable),
            "reason": "generated arm incomplete",
        }
    jo, jg = (
        j_stat(oracle, "epistemic_search", usable),
        j_stat(generated, "epistemic_search", usable),
    )
    gap = None if jo is None or jg is None else jo - jg
    return {
        "verdict": "YES" if gap is not None and gap >= Q4_DELTA else "NO",
        "examples": len(usable),
        "J_oracle": jo,
        "J_generated": jg,
        "gap": gap,
    }


def classify(
    es_examples: int,
    q1v: Verdict,
    q2v: Verdict,
    depth: dict[str, Any],
    q4v: Verdict,
    stance_works: bool | None,
) -> dict[str, str]:
    """Exactly one class, by the committed order of rules."""
    if es_examples < MIN_EXAMPLES:
        return {
            "class": "INCONCLUSIVE",
            "rule": "1: fewer than 12 complete Epistemic Search examples",
        }
    if q1v == "NO":
        return {
            "class": "NOT_PROMISING_IN_CURRENT_FORM",
            "rule": "2: Q1 = NO (gold upper bound fails)",
        }
    if q2v == "NO":
        return {"class": "NOT_PROMISING_IN_CURRENT_FORM", "rule": "2: Q2 = NO"}
    if q2v == "YES":
        if depth.get("architecture_revision_triggered"):
            return {
                "class": "ARCHITECTURE_REVISION_NEEDED",
                "rule": "3: Q2 = YES, deep proofs fail",
            }
        if q4v == "YES" or stance_works is False:
            why = (
                "oracle structure materially beats generated"
                if q4v == "YES"
                else "stance does not work"
            )
            return {"class": "PROMISING_BUT_FRONTEND_LIMITED", "rule": f"3: Q2 = YES; {why}"}
        return {"class": "PROMISING", "rule": "3: Q2 = YES, no front-end limit triggered"}
    return {"class": "INCONCLUSIVE", "rule": "4: Q2 undetermined"}
