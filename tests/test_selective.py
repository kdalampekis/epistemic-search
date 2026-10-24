import asyncio
import json
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import pytest
from typer.testing import CliRunner

from epistemic_search.baseline import Answer, RunResult
from epistemic_search.cli import app
from epistemic_search.evaluation import JsonlDataset, ScoredCase, evaluate
from epistemic_search.models import QueryCase, Usage
from epistemic_search.selective import (
    RankedPrediction,
    RankingScores,
    analyze_saved_run,
    risk_coverage,
    selective_metrics,
)


def row(
    key: str, answered: bool = True, em: float | None = 1, status: str = "completed"
) -> ScoredCase:
    return ScoredCase(
        query_id=key,
        status=status,
        answered=answered,
        labelled=em is not None,
        exact_match=em,
        token_f1=em,
        trace_file=f"{key}.json",
        usage=Usage(cost_usd=Decimal(0)),
        usage_complete=True,
        wall_seconds=0,
    )


def test_operating_risk_and_abstention_counts_do_not_reward_crashes() -> None:
    rows = [
        row("right"),
        row("wrong", em=0),
        row("reject", False, 0),
        row("false_reject", False, 0),
        row("crash", False, 0, "error"),
        row("cap", False, 0, "budget_exhausted"),
    ]
    labels = {
        "right": True,
        "wrong": False,
        "reject": False,
        "false_reject": True,
        "crash": False,
        "cap": False,
    }
    report = selective_metrics(rows, labels)
    assert report.coverage == pytest.approx(1 / 3)
    assert report.selective_risk == 0.5
    assert report.policy_abstentions == 3
    assert report.errors == report.budget_exhausted == 1
    assert (report.abstention_tp, report.abstention_fp, report.abstention_fn) == (2, 1, 2)
    assert report.abstention_precision == pytest.approx(2 / 3)
    assert report.abstention_recall == 0.5
    assert report.abstention_f1 == pytest.approx(4 / 7)


def test_unknown_labels_and_no_answers_are_not_zero_risk() -> None:
    report = selective_metrics([row("reject", False, None)], {"reject": None})
    assert report.coverage == 0 and report.selective_risk is None
    assert report.answerability_labelled == 0
    assert report.abstention_precision is report.abstention_recall is report.abstention_f1 is None
    report = selective_metrics([row("known"), row("unknown", em=None)], {})
    assert report.answered_labelled == 1 and report.selective_risk is None
    report = selective_metrics([row("wrong", em=0)], {"wrong": False})
    assert report.abstention_precision is None and report.abstention_recall == 0
    assert report.abstention_f1 == 0


def test_hand_computed_prefix_curve_and_aurc() -> None:
    curve = risk_coverage(
        [
            RankedPrediction(query_id=str(i), score=3 - i, loss=loss)
            for i, loss in enumerate([0, 1, 0])
        ]
    )
    assert curve.points[0].risk is None
    assert [p.risk for p in curve.points[1:]] == pytest.approx([0, 0.5, 1 / 3])
    assert [p.coverage for p in curve.points] == pytest.approx([0, 1 / 3, 2 / 3, 1])
    assert curve.aurc == pytest.approx(5 / 18)


def test_tied_scores_are_permutation_invariant_without_label_ordering() -> None:
    predictions = [
        RankedPrediction(query_id="a", score=0, loss=0),
        RankedPrediction(query_id="b", score=0, loss=1),
        RankedPrediction(query_id="c", score=0, loss=1),
    ]
    results = [risk_coverage(list(order)) for order in permutations(predictions)]
    assert all(result == results[0] for result in results)
    assert results[0].aurc == pytest.approx(2 / 3)
    assert [p.tie_fraction for p in results[0].points[1:]] == pytest.approx([1 / 3, 2 / 3, 1])


def test_missing_counterfactual_answers_cannot_be_faked_for_aurc() -> None:
    scores = RankingScores(source="fixture-score-not-probability", scores={"a": 2, "b": 1})
    report = selective_metrics([row("a"), row("b", False, 0)], {}, scores)
    assert report.risk_coverage is None
    assert "candidate answers" in (report.curve_unavailable_reason or "")
    report = selective_metrics([row("a"), row("b", em=None)], {}, scores)
    assert report.risk_coverage is None and report.selective_risk is None
    report = selective_metrics([row("a"), row("b", em=0)], {}, scores)
    assert report.risk_coverage and report.risk_coverage.aurc == 0.25


def test_invalid_ranking_and_labels_are_rejected() -> None:
    with pytest.raises(ValueError):
        risk_coverage([])
    with pytest.raises(ValueError):
        risk_coverage([RankedPrediction(query_id="a", score=1, loss=0)] * 2)
    with pytest.raises(ValueError):
        RankingScores(source="invalid", scores={"a": float("nan")})
    with pytest.raises(ValueError, match="unique"):
        selective_metrics([row("a"), row("a")], {})
    with pytest.raises(ValueError, match="unknown example"):
        selective_metrics([row("a")], {"another": False})
    with pytest.raises(ValueError, match="binary"):
        selective_metrics([row("a", em=0.5)], {})
    with pytest.raises(ValueError, match="completed"):
        selective_metrics([row("a", status="error")], {})


def test_saved_run_cli_uses_original_grader_and_does_not_overwrite(tmp_path: Path) -> None:
    cases = [
        QueryCase(id=str(i), question="fixture", gold_answer="yes", answerable=True)
        for i in range(3)
    ]
    data = tmp_path / "data.jsonl"
    data.write_text("\n".join(c.model_dump_json() for c in cases))

    async def runner(case: QueryCase) -> RunResult:
        assert case.gold_answer is None and case.answerable is None
        return RunResult(
            query_id=case.id,
            status="completed",
            output=Answer(answer="no" if case.id == "1" else "yes", citation_ids=["s"]),
            usage=Usage(cost_usd=Decimal(0)),
            wall_seconds=0,
            trace=[],
        )

    run_dir = tmp_path / "run"
    asyncio.run(
        evaluate(JsonlDataset(data), runner, run_dir, {"metric_version": "english-em-token-f1-v1"})
    )
    scores = tmp_path / "scores.json"
    scores.write_text(
        RankingScores(
            source="deterministic-fixture", scores={"0": 3, "1": 2, "2": 1}
        ).model_dump_json()
    )
    report = analyze_saved_run(run_dir, scores)
    assert report.risk_coverage and report.risk_coverage.aurc == pytest.approx(5 / 18)
    assert report.selective_risk == pytest.approx(1 / 3)
    assert report.source_metric_version == "english-em-token-f1-v1"
    assert len(report.source_hashes["ranking_scores"]) == 64
    output = tmp_path / "report.json"
    args = ["selective", str(run_dir), str(output), "--scores-path", str(scores)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text())["examples"] == 3
    assert CliRunner().invoke(app, args).exit_code == 1
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["metric_version"] = "mismatched-grader"
    summary_path.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="grader versions"):
        analyze_saved_run(run_dir, scores)


@pytest.mark.parametrize("loss", [0.0, 1.0])
def test_single_candidate_aurc_endpoints(loss: float) -> None:
    curve = risk_coverage([RankedPrediction(query_id="only", score=-2, loss=loss)])
    assert curve.aurc == loss and curve.points[-1].coverage == 1


def test_mixed_tie_group_has_expected_prefix_risks() -> None:
    curve = risk_coverage(
        [
            RankedPrediction(query_id="best", score=2, loss=0),
            RankedPrediction(query_id="tied-right", score=1, loss=0),
            RankedPrediction(query_id="tied-wrong", score=1, loss=1),
        ]
    )
    assert [p.risk for p in curve.points[1:]] == pytest.approx([0, 0.25, 1 / 3])
    assert curve.aurc == pytest.approx(7 / 36)
