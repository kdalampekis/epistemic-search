"""RV2 metrics: deterministic, label-driven, no model involved."""

import random
import re
import string
from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any

CLASSES = ("SUPPORT", "CONTRADICT", "NEUTRAL")


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def stance_metrics(pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """(gold, predicted) pairs. Predictions outside the three classes (MIXED, ERROR, NOT_RUN)
    are kept as their own confusion column and count as wrong for every gold class."""
    confusion: dict[str, Counter[str]] = {g: Counter() for g in CLASSES}
    for gold, pred in pairs:
        confusion[gold][pred] += 1
    per_class: dict[str, dict[str, float | int | None]] = {}
    for c in CLASSES:
        tp = confusion[c][c]
        predicted = sum(confusion[g][c] for g in CLASSES)
        actual = sum(confusion[c].values())
        precision, recall = ratio(tp, predicted), ratio(tp, actual)
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else 0.0
        )
        per_class[c] = {"precision": precision, "recall": recall, "f1": f1, "support": actual}
    n = len(pairs)
    non_c = sum(sum(confusion[g].values()) for g in CLASSES if g != "CONTRADICT")
    non_s = sum(sum(confusion[g].values()) for g in CLASSES if g != "SUPPORT")
    return {
        "n": n,
        "accuracy": ratio(sum(confusion[c][c] for c in CLASSES), n),
        "macro_f1": sum(float(per_class[c]["f1"] or 0) for c in CLASSES) / len(CLASSES),
        "per_class": per_class,
        "confusion": {g: dict(sorted(confusion[g].items())) for g in CLASSES},
        "false_contradict_rate": ratio(
            sum(confusion[g]["CONTRADICT"] for g in CLASSES if g != "CONTRADICT"), non_c
        ),
        "contradict_precision": per_class["CONTRADICT"]["precision"],
        "false_support_rate": ratio(
            sum(confusion[g]["SUPPORT"] for g in CLASSES if g != "SUPPORT"), non_s
        ),
        "not_in_three_classes": sum(
            v for g in CLASSES for k, v in confusion[g].items() if k not in CLASSES
        ),
    }


def pair_metrics(items: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    """(group, gold, predicted) for items that come in contrastive pairs.

    both_correct: both members right. flips_when_gold_differs: the two predictions differ
    (every pair here has differing gold labels). A pair needs exactly two members.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for group, gold, pred in items:
        groups.setdefault(group, []).append((gold, pred))
    pairs = [g for g in groups.values() if len(g) == 2]
    return {
        "pairs": len(pairs),
        "both_correct": ratio(sum(all(g == p for g, p in pr) for pr in pairs), len(pairs)),
        "predictions_differ": ratio(sum(pr[0][1] != pr[1][1] for pr in pairs), len(pairs)),
        "both_wrong": ratio(sum(all(g != p for g, p in pr) for pr in pairs), len(pairs)),
    }


def bootstrap_ci[T](
    units: Sequence[T],
    statistic: Callable[[Sequence[T]], float | None],
    *,
    resamples: int = 10_000,
    seed: int = 20261029,
) -> dict[str, float | None]:
    """Percentile 95% interval resampling whole units (examples) with replacement."""
    point = statistic(units)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        value = statistic([units[rng.randrange(len(units))] for _ in units])
        if value is not None:
            draws.append(value)
    draws.sort()
    if not draws:
        return {"point": point, "lower": None, "upper": None}
    return {
        "point": point,
        "lower": draws[int(0.025 * (len(draws) - 1))],
        "upper": draws[int(0.975 * (len(draws) - 1))],
    }


def normalize_answer(text: str) -> str:
    """SQuAD-style: lowercase, drop punctuation and articles, collapse whitespace."""
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def token_f1(prediction: str, reference: str) -> float:
    p, r = normalize_answer(prediction).split(), normalize_answer(reference).split()
    common = Counter(p) & Counter(r)
    overlap = sum(common.values())
    if not p or not r or not overlap:
        return 0.0
    precision, recall = overlap / len(p), overlap / len(r)
    return 2 * precision * recall / (precision + recall)
