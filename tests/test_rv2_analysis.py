from typing import Any

import pytest

from epistemic_search.rv2_analysis import (
    classify,
    complete_examples,
    contrast,
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

USAGE = {
    "model_calls": 2,
    "search_calls": 1,
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "new_api_cost_usd": "0.001",
    "reused_cost_usd": "0.0005",
    "latency_seconds": 1.0,
}


def row(
    system: str,
    ex: str,
    cond: str,
    answered: bool,
    hit: bool = True,
    depth: int = 2,
    unresolved: list[str] | None = None,
    removed: str | None = None,
) -> dict[str, Any]:
    return {
        "system": system,
        "example_id": ex,
        "condition": cond,
        "answered": answered,
        "answer_hit": hit if answered else None,
        "answer_f1": 1.0 if answered and hit else 0.0,
        "outcome": "ANSWER" if answered else "ABSTAIN",
        "depth": depth,
        "usage": USAGE,
        "span_rejections": 0,
        "no_progress": not answered,
        "removed_leaf": removed,
        "unresolved_leaves": unresolved,
    }


def build(
    behaviour: dict[str, tuple[bool, bool, bool, bool]], n: int = 12, depths: Any = None
) -> list[dict[str, Any]]:
    """behaviour[system] = answered in (C1, C2, C3, C4), identical for every example."""
    rows = []
    for i in range(n):
        d = depths(i) if depths else 2
        for system, pattern in behaviour.items():
            for cond, a in zip(("C1", "C2", "C3", "C4"), pattern, strict=True):
                missing = cond in ("C2", "C3")
                rows.append(
                    row(
                        system,
                        f"e{i}",
                        cond,
                        a,
                        depth=d,
                        unresolved=(
                            ["s1"]
                            if missing and system == "epistemic_search"
                            else []
                            if system == "epistemic_search"
                            else None
                        ),
                        removed="s1" if missing else None,
                    )
                )
    return rows


GOOD = {
    "epistemic_search": (True, False, False, True),
    "premise_only": (True, True, False, True),
    "naive_rag": (True, True, True, True),
}


def test_j_and_metrics_follow_the_definitions() -> None:
    rows = index(build(GOOD))
    ex = complete_examples(rows, ["epistemic_search", "premise_only", "naive_rag"])
    assert len(ex) == 12
    assert j_stat(rows, "epistemic_search", ex) == 1.0
    assert j_stat(rows, "premise_only", ex) == pytest.approx(1.0 - 0.5)
    assert j_stat(rows, "naive_rag", ex) == 0.0
    m = system_metrics(rows, "naive_rag", ex)
    assert m["unsupported_answer_rate"] == 1.0 and m["coverage_on_complete"] == 1.0
    assert m["selective_risk"] == pytest.approx(24 / 48)  # 24 unsupported answers of 48
    es = system_metrics(rows, "epistemic_search", ex)
    assert es["blocker_localization_exact"] == 1.0 and es["proof_completion_accuracy"] == 1.0
    assert es["logical_cost_usd"] > es["new_api_cost_usd"] > 0


def test_examples_missing_any_condition_are_excluded_not_imputed() -> None:
    raw = build(GOOD, n=3)
    raw = [r for r in raw if not (r["example_id"] == "e0" and r["condition"] == "C4")]
    assert "e0" not in complete_examples(index(raw), ["epistemic_search", "naive_rag"])


def test_q2_needs_both_the_margin_and_an_interval_above_zero() -> None:
    rows = index(build(GOOD))
    ex = complete_examples(rows, list(GOOD))
    result = q2(rows, ex, resamples=300)
    assert result["verdict"] == "YES" and result["delta_J"] == pytest.approx(0.5)
    assert result["ci95"][0] > 0
    same = index(build({**GOOD, "premise_only": GOOD["epistemic_search"]}))
    assert q2(same, ex, resamples=300)["verdict"] == "NO"  # delta 0 <= 0.05


def test_near_universal_abstention_cannot_pass_q2() -> None:
    silent = {
        "epistemic_search": (False, False, False, False),
        "premise_only": (True, True, True, True),
        "naive_rag": (True, True, True, True),
    }
    rows = index(build(silent))
    ex = complete_examples(rows, list(silent))
    assert q2(rows, ex, resamples=100)["verdict"] == "NO"  # coverage on complete 0 < 0.50
    assert q1(rows, ex)["verdict"] == "NO"


def test_q1_thresholds_are_applied_exactly() -> None:
    def verdict(coverage: float, hit: bool) -> str:
        n = 20
        raw = []
        for i in range(n):
            ans = i < round(coverage * n)
            for c, a in (("C1", ans), ("C2", False), ("C3", False), ("C4", ans)):
                raw.append(row("epistemic_search", f"e{i}", c, a, hit=hit))
        rows = index(raw)
        return str(q1(rows, complete_examples(rows, ["epistemic_search"]))["verdict"])

    assert verdict(0.8, True) == "YES"
    assert verdict(0.75, True) == "UNDETERMINED"
    assert verdict(0.55, True) == "NO"
    assert verdict(0.9, False) == "UNDETERMINED"  # answers, but wrong


def test_q3_needs_a_margin_over_the_best_baseline_not_just_a_low_rate() -> None:
    both_leak = {**GOOD, "premise_only": (True, True, True, True)}
    rows = index(build(both_leak))
    ex = complete_examples(rows, list(both_leak))
    assert q3(rows, ex)["verdict"] == "YES"  # ES 0.0 vs baselines 1.0 on C3
    assert distractor_robustness(rows, "epistemic_search", ex) == {
        "coverage_drop_C1_to_C4": 0.0,
        "answer_rate_rise_C2_to_C3": 0.0,
    }
    strong = index(build(GOOD))  # premise-only is already perfect on C3: no margin to claim
    assert q3(strong, ex)["verdict"] == "NO"
    leaky = index(build({**both_leak, "epistemic_search": (True, False, True, True)}))
    assert q3(leaky, ex)["verdict"] == "NO"
    assert distractor_robustness(leaky, "epistemic_search", ex)["answer_rate_rise_C2_to_C3"] == 1.0


def test_q4_compares_the_same_examples_and_refuses_an_incomplete_arm() -> None:
    oracle = index(build(GOOD))
    ex = complete_examples(oracle, list(GOOD))
    generated = index(build({"epistemic_search": (True, True, True, True)}))
    result = q4(oracle, generated, ex)
    assert result["verdict"] == "YES" and result["gap"] == 1.0
    small = index(build({"epistemic_search": (True, True, True, True)}, n=5))
    assert q4(oracle, small, ex)["verdict"] == "UNDETERMINED"


def test_depth_criterion_needs_enough_examples_in_each_group() -> None:
    def split(deep_pattern: tuple[bool, bool, bool, bool], n: int = 12) -> dict[str, Any]:
        raw = []
        for i in range(n):
            deep = i % 2 == 1
            pattern = deep_pattern if deep else GOOD["epistemic_search"]
            for c, a in zip(("C1", "C2", "C3", "C4"), pattern, strict=True):
                raw.append(row("epistemic_search", f"e{i}", c, a, depth=4 if deep else 1))
        rows = index(raw)
        return depth_split(rows, complete_examples(rows, ["epistemic_search"]))

    broken = split((False, False, False, False))
    assert broken["evaluable"] and broken["architecture_revision_triggered"]
    assert not split(GOOD["epistemic_search"])["architecture_revision_triggered"]
    assert split((False, False, False, False), n=6)["evaluable"] is False


@pytest.mark.parametrize(
    "args,expected",
    [
        ((11, "YES", "YES", {}, "NO", True), "INCONCLUSIVE"),
        ((18, "NO", "YES", {}, "NO", True), "NOT_PROMISING_IN_CURRENT_FORM"),
        ((18, "YES", "NO", {}, "NO", True), "NOT_PROMISING_IN_CURRENT_FORM"),
        (
            (18, "YES", "YES", {"architecture_revision_triggered": True}, "YES", False),
            "ARCHITECTURE_REVISION_NEEDED",
        ),
        ((18, "YES", "YES", {}, "YES", True), "PROMISING_BUT_FRONTEND_LIMITED"),
        ((18, "UNDETERMINED", "YES", {}, "NO", False), "PROMISING_BUT_FRONTEND_LIMITED"),
        ((18, "YES", "YES", {}, "NO", True), "PROMISING"),
        ((18, "YES", "UNDETERMINED", {}, "NO", True), "INCONCLUSIVE"),
    ],
)
def test_classification_follows_the_committed_order(args: tuple[Any, ...], expected: str) -> None:
    assert classify(*args)["class"] == expected


def test_contrast_is_reproducible() -> None:
    rows = index(build(GOOD))
    ex = complete_examples(rows, list(GOOD))
    assert contrast(rows, ex, 200) == contrast(rows, ex, 200)
