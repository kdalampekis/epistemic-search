from collections.abc import Sequence

import pytest

from epistemic_search.rv2_metrics import (
    bootstrap_ci,
    normalize_answer,
    pair_metrics,
    stance_metrics,
    token_f1,
)


def test_stance_metrics_keep_mixed_and_errors_as_wrong_not_dropped() -> None:
    pairs = (
        [("SUPPORT", "SUPPORT")] * 6
        + [("SUPPORT", "NEUTRAL")] * 2
        + [("CONTRADICT", "CONTRADICT")] * 3
        + [("CONTRADICT", "MIXED")]
        + [("NEUTRAL", "NEUTRAL")] * 4
        + [("NEUTRAL", "CONTRADICT")] * 1
        + [("NEUTRAL", "SUPPORT")] * 1
        + [("NEUTRAL", "ERROR")]
    )
    m = stance_metrics(pairs)
    assert m["n"] == 19 and m["accuracy"] == pytest.approx(13 / 19)
    assert m["not_in_three_classes"] == 2 and m["confusion"]["CONTRADICT"] == {
        "CONTRADICT": 3,
        "MIXED": 1,
    }
    # 1 of the 14 non-CONTRADICT items was predicted CONTRADICT.
    assert m["false_contradict_rate"] == pytest.approx(1 / 15)
    assert m["contradict_precision"] == pytest.approx(3 / 4)
    assert m["false_support_rate"] == pytest.approx(1 / 11)
    assert m["per_class"]["SUPPORT"]["recall"] == pytest.approx(6 / 8)
    assert 0 < m["macro_f1"] < 1


def test_metrics_handle_empty_classes_without_dividing_by_zero() -> None:
    m = stance_metrics([("SUPPORT", "SUPPORT")])
    assert m["false_contradict_rate"] == 0.0
    assert m["contradict_precision"] is None and m["per_class"]["NEUTRAL"]["f1"] == 0.0


def test_pair_metrics_distinguish_flipping_from_being_right() -> None:
    items = [
        ("a", "SUPPORT", "SUPPORT"),
        ("a", "CONTRADICT", "CONTRADICT"),
        ("b", "SUPPORT", "SUPPORT"),
        ("b", "NEUTRAL", "SUPPORT"),
        ("c", "CONTRADICT", "NEUTRAL"),
        ("c", "SUPPORT", "CONTRADICT"),
        ("lonely", "SUPPORT", "SUPPORT"),
    ]
    m = pair_metrics(items)
    assert m == {
        "pairs": 3,
        "both_correct": pytest.approx(1 / 3),
        "predictions_differ": pytest.approx(2 / 3),
        "both_wrong": pytest.approx(1 / 3),
    }


def test_bootstrap_is_seeded_and_resamples_units() -> None:
    units = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0]

    def mean(values: Sequence[float]) -> float:
        return sum(values) / len(values)

    a = bootstrap_ci(units, mean, resamples=500, seed=1)
    assert a == bootstrap_ci(units, mean, resamples=500, seed=1)
    assert a["point"] == 0.75 and a["lower"] is not None and a["upper"] is not None
    assert 0.4 <= a["lower"] <= 0.75 <= a["upper"] <= 1.0
    assert bootstrap_ci([1.0, 1.0], mean, resamples=50)["lower"] == 1.0


def test_answer_matching_is_the_standard_squad_normalization() -> None:
    assert normalize_answer("The Sun, rises!") == "sun rises"
    assert token_f1("The Sun rises and sets.", "The Sun rises and sets.") == 1.0
    # prediction {rocks, will, break} vs reference {rocks, would, break, into, smaller, pieces}
    assert token_f1(
        "the rocks will break", "The rocks would break into smaller pieces."
    ) == pytest.approx(4 / 9)
    assert token_f1("", "x") == 0.0 and token_f1("Paris", "London") == 0.0
