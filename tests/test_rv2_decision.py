import json
from pathlib import Path
from typing import Any

from epistemic_search.rv2_decision import decide


def put(root: Path, name: str, value: dict[str, Any]) -> None:
    path = root / "docs/results/rv2" / name / "results.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value))


def full(
    root: Path, q1: str, q2: str, q4: str, stance: bool, n: int = 18, deep: bool = False
) -> None:
    put(root, "rv2_a", {"verdict": {"stance_works": stance}})
    put(root, "rv2_b", {"metrics": {"Q4": {"verdict": q4}}})
    put(
        root,
        "rv2_c",
        {
            "metrics": {
                "complete_examples": n,
                "Q1": {"verdict": q1},
                "Q2": {"verdict": q2},
                "Q3": {"verdict": "YES"},
                "depth": {"architecture_revision_triggered": deep},
            }
        },
    )
    put(root, "rv2_d", {"metrics": {"Q5": {"verdict": "NO"}}})


def test_a_missing_experiment_is_inconclusive_never_guessed(tmp_path: Path) -> None:
    put(tmp_path, "rv2_a", {"verdict": {"stance_works": True}})
    decision = decide(tmp_path)
    assert decision["classification"]["class"] == "INCONCLUSIVE"
    assert (
        "rv2_b" not in decision["classification"]["rule"]
        and "RV2-B" in decision["classification"]["rule"]
    )


def test_the_rule_is_applied_mechanically_to_the_result_files(tmp_path: Path) -> None:
    full(tmp_path, "YES", "YES", "NO", True)
    assert decide(tmp_path)["classification"]["class"] == "PROMISING"


def test_each_class_is_reachable(tmp_path: Path) -> None:
    cases = {
        "NOT_PROMISING_IN_CURRENT_FORM": ("NO", "UNDETERMINED", "NO", True, 18, False),
        "PROMISING_BUT_FRONTEND_LIMITED": ("YES", "YES", "YES", True, 18, False),
        "ARCHITECTURE_REVISION_NEEDED": ("YES", "YES", "NO", True, 18, True),
        "INCONCLUSIVE": ("YES", "UNDETERMINED", "NO", True, 18, False),
    }
    for i, (expected, args) in enumerate(cases.items()):
        root = tmp_path / str(i)
        full(root, *args[:4], n=args[4], deep=args[5])
        assert decide(root)["classification"]["class"] == expected
