from typing import Any

import pytest
from test_rv2_analysis import GOOD, build

from epistemic_search.rv2_stage import (
    SPEC_B,
    SPEC_C,
    plan_cost,
    stage_run,
    summarize_b,
    summarize_c,
)


def test_caps_and_arms_are_the_preregistered_ones() -> None:
    assert (SPEC_B.cap_usd, SPEC_C.cap_usd) == ("0.25", "0.50")
    assert [m for m, _, _ in SPEC_B.arms] == ["oracle", "generated"]
    assert SPEC_C.arms[0][2] == ("closed_book", "naive_rag", "premise_only", "epistemic_search")
    assert SPEC_B.run_id != SPEC_C.run_id  # separate ledger caps


def test_summaries_reproduce_the_decision_inputs() -> None:
    rows = build({**GOOD, "closed_book": (True, True, True, True)}, n=12)
    for r in rows:
        if r["system"] == "closed_book":
            r["condition"] = "NA"
    summary = summarize_c(
        [r for r in rows if r["condition"] != "NA" or r["system"] == "closed_book"][:0] + rows
    )
    assert summary["complete_examples"] == 12
    assert summary["Q2"]["verdict"] == "YES" and summary["Q1"]["verdict"] == "YES"
    assert summary["systems"]["epistemic_search"]["J"] == 1.0
    assert "closed_book" in summary and summary["closed_book"]["answer_rate"] == pytest.approx(1.0)


def test_summarize_b_pairs_the_same_examples_across_arms() -> None:
    oracle = build({"epistemic_search": GOOD["epistemic_search"]}, n=12)
    generated = build({"epistemic_search": (True, True, True, True)}, n=12)
    summary: dict[str, Any] = summarize_b({"oracle": oracle, "generated": generated})
    assert summary["examples_with_both_arms"] == 12 and summary["Q4"]["verdict"] == "YES"
    assert summary["oracle"]["J"] == 1.0 and summary["generated"]["J"] == 0.0


def test_planning_cost_scales_with_leaves_but_not_for_the_other_systems() -> None:
    probe = build(
        {"epistemic_search": GOOD["epistemic_search"], "naive_rag": GOOD["naive_rag"]}, n=1
    )
    from epistemic_search.rv2_adapters import EBExample

    def ex(leaves: int) -> EBExample:
        return EBExample(
            id=f"x{leaves}",
            question="q",
            answer="a",
            hypothesis="h",
            leaves={f"s{i}": f"t{i}" for i in range(leaves)},
            intermediates={},
            steps=[],
            depth=1,
        )

    small, large = plan_cost(probe, 3, [ex(3)]), plan_cost(probe, 3, [ex(5)])
    assert large > small
    each = 4 * 0.0015  # one example's cost: 4 conditions x 0.0015 logical per case, per system
    assert small == pytest.approx(2 * each)


def test_a_full_run_needs_a_logged_estimate(tmp_path: Any) -> None:
    with pytest.raises(RuntimeError, match="estimate"):
        stage_run(SPEC_C, tmp_path)


def test_invalid_generated_decompositions_are_counted_and_analysed_separately() -> None:
    oracle = build({"epistemic_search": GOOD["epistemic_search"]}, n=12)
    generated = build({"epistemic_search": GOOD["epistemic_search"]}, n=12)  # valid graphs match
    for r in generated:
        if int(r["example_id"][1:]) < 6:  # half the examples: the model's graph was invalid
            r.update(decomposition_valid=False, answered=False, answer_hit=None, outcome="ERROR")
    summary = summarize_b({"oracle": oracle, "generated": generated})
    validity = summary["generated_decomposition_validity"]
    assert validity["valid"] == 6 and validity["rate"] == 0.5
    # Pre-registered Q4 counts structural failures as no answer, so it reports a gap that is
    # entirely broken graphs; the conditional block shows the valid graphs are not worse.
    assert summary["Q4"]["verdict"] == "YES" and summary["Q4"]["gap"] == pytest.approx(0.5)
    conditional = summary["conditional_on_valid_generated_decomposition"]
    assert conditional["examples"] == 6 and conditional["gap"] == 0.0
