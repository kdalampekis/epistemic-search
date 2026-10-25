import json
from pathlib import Path

import pytest
import yaml
from test_rv1 import fill, only_file, setup_rv1, write

from epistemic_search.rv1 import init_rv1
from epistemic_search.rv1_schema import load_case
from epistemic_search.rv2_review import build_review, score_review


def setup_review(tmp_path: Path) -> Path:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    path = only_file(tmp_path)
    write(path, fill(load_case(path)))
    plan = tmp_path / "review.yaml"
    plan.write_text(
        yaml.safe_dump(
            {
                "rv1_annotations": "ann/primary",
                "rv0_dir": "audit",
                "output_dir": "out",
                "responses_path": "resp/responses.yaml",
                "cases": [1],
                "seed": 7,
                "strata": [
                    {"system": "SUPPORT", "gold": "SUPPORT", "n": 5},
                    {"system": "CONTRADICT", "gold": "NEUTRAL"},
                ],
            }
        )
    )
    return plan


def test_blind_files_hide_labels_and_selection_is_deterministic(tmp_path: Path) -> None:
    plan = setup_review(tmp_path)
    report = build_review(plan)
    assert report["api_calls"] == 0 and report["items"] > 0 and report["cases"] == 1
    review = (tmp_path / "out/RV2_0_REVIEW.md").read_text()
    cases = (tmp_path / "out/RV2_0_CASES.md").read_text()
    reveal = (tmp_path / "out/RV2_0_REVEAL.md").read_text()
    assert "[system" not in review and "RV1 SUPPORT" not in review and "SUPPORT->" not in review
    assert "[system SUPPORT]" in cases and "RV1 conclusions" not in cases
    assert "| SUPPORT | SUPPORT |" in reveal and "RV1 conclusions" in reveal
    selection = json.loads((tmp_path / "out/rv2_0_selection.json").read_text())
    values = yaml.safe_load(plan.read_text())
    values.update(output_dir="out2", responses_path="resp2/responses.yaml")
    plan.write_text(yaml.safe_dump(values))
    build_review(plan)
    again = json.loads((tmp_path / "out2/rv2_0_selection.json").read_text())
    assert again == selection
    with pytest.raises(FileExistsError):
        build_review(plan)


def test_unknown_case_is_rejected(tmp_path: Path) -> None:
    plan = setup_review(tmp_path)
    values = yaml.safe_load(plan.read_text())
    values["cases"] = [99]
    plan.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError, match="Unknown case"):
        build_review(plan)


def test_scoring_excludes_unsure_and_reports_without_a_verdict(tmp_path: Path) -> None:
    plan = setup_review(tmp_path)
    build_review(plan)
    responses = tmp_path / "resp/responses.yaml"
    data = yaml.safe_load(responses.read_text())
    stances = ["SUPPORT", "NEUTRAL", "UNSURE"]
    for row, stance in zip(data["stance_items"], stances, strict=False):
        row["human_stance"] = stance
    data["cases"][0]["human_primary_cause_epistemic_search"] = "STANCE_ERROR"
    data["cases"][0]["agrees_with_rv1_epistemic_search"] = "NO"
    responses.write_text(yaml.safe_dump(data))
    report = score_review(plan)
    overall = report["human_vs_rv1"]["all"]
    assert overall["n"] == min(3, len(data["stance_items"]))
    assert overall["compared"] == overall["n"] - overall["unsure_excluded"]
    assert report["cases_agree_with_rv1"] == {"NO": 1} and report["api_calls"] == 0
    assert "human decision" in report["note"] and "pass" not in json.dumps(report).lower()
    assert (tmp_path / "out/rv2_0_score.json").exists()

    data["stance_items"][0]["id"] = "S99"
    responses.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="selection"):
        score_review(plan)
