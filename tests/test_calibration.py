import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from epistemic_search.calibration import (
    CalibrationConfig,
    CalibrationData,
    HistogramCalibrator,
    calibration_metrics,
    compare_calibration,
    fit_nli,
)
from epistemic_search.cli import app


def data() -> CalibrationData:
    return CalibrationData.model_validate_json(Path("tests/fixtures/calibration.json").read_text())


def config() -> CalibrationConfig:
    return CalibrationConfig(
        data_path=Path("unused"), output_path=Path("unused"), metric_bins=5, calibration_bins=4
    )


def test_hand_computed_binary_brier_ece_and_boundaries() -> None:
    metrics = calibration_metrics([0, 0.5, 1], [False, True, False], 2)
    assert metrics.brier == pytest.approx(5 / 12)
    assert metrics.ece == pytest.approx(1 / 6)
    assert [b.count for b in metrics.reliability] == [1, 2]
    assert metrics.reliability[1].mean_score == 0.75
    assert metrics.reliability[1].accuracy == 0.5
    assert calibration_metrics([0, 1], [False, True], 10).brier == 0
    assert calibration_metrics([0, 1], [True, False], 10).brier == 1
    assert calibration_metrics([0, 1], [True, False], 10).ece == 1
    empty = calibration_metrics([0.5], [True], 10).reliability[0]
    assert empty.count == 0 and empty.accuracy is empty.mean_score is None


@pytest.mark.parametrize(
    "scores,labels,bins",
    [
        ([], [], 2),
        ([0.1], [], 2),
        ([float("nan")], [True], 2),
        ([float("inf")], [True], 2),
        ([-0.1], [False], 2),
        ([0.1], [False], 0),
    ],
)
def test_invalid_metric_input_fails(scores: list[float], labels: list[bool], bins: int) -> None:
    with pytest.raises(ValueError):
        calibration_metrics(scores, labels, bins)


def test_histogram_smoothing_empty_bin_fallback_and_roundtrip() -> None:
    fit = [c for c in data().cases if c.split == "calibration"]
    model = fit_nli(fit, 4)
    assert model.counts == [2, 0, 1, 1]
    assert model.estimates == pytest.approx([0.25, 0.5, 2 / 3, 2 / 3])
    assert model.predict(0) == 0.25 and model.predict(1) == pytest.approx(2 / 3)
    assert model.predict(0.3) == 0.5
    assert HistogramCalibrator.model_validate_json(model.model_dump_json()) == model
    with pytest.raises(ValueError, match="calibration-split"):
        fit_nli(data().cases, 4)
    with pytest.raises(ValueError):
        model.predict(float("nan"))
    broken = model.model_dump()
    broken["counts"] = []
    with pytest.raises(ValueError, match="bin count"):
        HistogramCalibrator.model_validate(broken)


def test_question_group_leakage_and_duplicate_candidates_are_rejected() -> None:
    payload = data().model_dump()
    payload["cases"][4]["group_id"] = payload["cases"][0]["group_id"]
    with pytest.raises(ValueError, match="disjoint"):
        CalibrationData.model_validate(payload)
    payload = data().model_dump()
    payload["cases"][-1]["id"] = payload["cases"][0]["id"]
    with pytest.raises(ValueError, match="unique"):
        CalibrationData.model_validate(payload)


def test_evaluation_labels_never_change_the_fit_and_comparison_is_paired() -> None:
    original = data()
    report = compare_calibration(original, config())
    assert set(report.metrics) == {
        "raw_confidence",
        "nli_score",
        "calibrated_nli",
        "evidence_aggregation",
    }
    assert all(m.examples == 4 for m in report.metrics.values())
    assert report.calibration_examples == 4 and report.evaluation_examples == 7
    assert set(report.excluded) == {"failed", "unknown", "missing"}
    assert "error" in report.excluded["failed"]
    assert "missing_nli_score" in report.excluded["missing"]
    for case in original.cases:
        if case.split == "evaluation" and case.correct is not None:
            case.correct = not case.correct
    changed = compare_calibration(original, config())
    assert changed.calibrator == report.calibrator
    assert changed.metrics != report.metrics
    reversed_data = data()
    reversed_data.cases.reverse()
    reverse_report = compare_calibration(reversed_data, config())
    assert reverse_report.calibrator == report.calibrator
    for name in report.metrics:
        assert reverse_report.metrics[name].brier == pytest.approx(report.metrics[name].brier)


def test_missing_real_scores_never_become_calibration_results() -> None:
    unavailable = data()
    for case in unavailable.cases:
        case.scores = {}
    report = compare_calibration(unavailable, config())
    assert report.calibrator is None and not report.metrics and not report.evaluated_ids
    assert report.unavailable_reason and len(report.excluded) == 7


def test_fixture_cli_records_sources_and_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"data_path: {Path('tests/fixtures/calibration.json').resolve()}\n"
        "output_path: report.json\nmetric_bins: 5\ncalibration_bins: 4\n"
    )
    result = CliRunner().invoke(app, ["calibrate", str(path)])
    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["fixture_only"] and len(report["source_hashes"]) == 3
    assert len(report["metrics"]) == 4
    assert CliRunner().invoke(app, ["calibrate", str(path)]).exit_code == 1
