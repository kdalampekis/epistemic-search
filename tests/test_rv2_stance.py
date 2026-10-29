import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from epistemic_search.adapters import FixtureModelProvider
from epistemic_search.config import RagConfig
from epistemic_search.rv2_adapters import StanceExample
from epistemic_search.rv2_stance import predict, stage_run, summarize, verdict


def rag() -> RagConfig:
    return RagConfig(corpus_path=Path("unused"), responses_path=Path("unused"))


def example(gold: str = "SUPPORT", ident: str = "e1") -> StanceExample:
    return StanceExample(
        id=ident,
        dataset="vitaminc",
        claim="Paris is the capital.",
        evidence="Paris is the capital of France.",
        gold=gold,
        source_label="SUPPORTS",
        group="g",
    )


def run(output: str, ex: StanceExample | None = None) -> dict[str, Any]:
    return asyncio.run(predict(ex or example(), rag(), FixtureModelProvider([output])))


def items(*triples: tuple[str, str, float]) -> str:
    return json.dumps(
        {"items": [{"span": s, "stance": st, "stance_score": c} for s, st, c in triples]}
    )


def test_prediction_goes_through_the_real_stance_component_and_aggregator() -> None:
    r = run(items(("Paris is the capital", "SUPPORT", 0.9)))
    assert r["predicted"] == "SUPPORT" and r["belief_status"] == "SUPPORTED"
    assert r["items"][0]["alignment"] == "exact" and r["usage"]["model_calls"] == 1
    assert run(items(("Paris", "CONTRADICT", 0.8)))["predicted"] == "CONTRADICT"
    assert (
        run(items(("Paris", "SUPPORT", 0.9), ("capital", "CONTRADICT", 0.9)))["predicted"]
        == "MIXED"
    )


def test_weak_or_neutral_evidence_is_neutral_not_support() -> None:
    assert run(items(("Paris", "SUPPORT", 0.3)))["predicted"] == "NEUTRAL"  # below threshold
    assert run(items(("Paris", "NEUTRAL", 0.99)))["predicted"] == "NEUTRAL"
    assert run(items())["predicted"] == "NEUTRAL"


def test_hallucinated_span_is_rejected_per_item_and_unparseable_output_is_an_error() -> None:
    r = run(items(("Berlin is the capital", "SUPPORT", 0.99), ("Paris", "SUPPORT", 0.9)))
    assert r["predicted"] == "SUPPORT" and len(r["rejections"]) == 1 and not r["errors"]
    only_bad = run(items(("Berlin is the capital", "SUPPORT", 0.99)))
    assert only_bad["predicted"] == "NEUTRAL" and only_bad["rejections"]
    broken = run("not json")
    assert broken["predicted"] == "ERROR" and broken["errors"]


def test_items_that_never_ran_stay_in_the_denominator() -> None:
    planned = {
        "vitaminc": [example("SUPPORT", "a"), example("CONTRADICT", "b"), example("NEUTRAL", "c")],
        "scifact": [example("SUPPORT", "d")],
    }
    records = [run(items(("Paris", "SUPPORT", 0.9)), planned["vitaminc"][0])]
    records[0]["id"] = "a"
    summary = summarize(records, planned)
    three = summary["vitaminc"]["three_way"]
    assert summary["vitaminc"]["planned"] == 3 and summary["vitaminc"]["run"] == 1
    assert three["n"] == 3 and three["accuracy"] == pytest.approx(1 / 3)
    assert three["confusion"]["CONTRADICT"] == {"NOT_RUN": 1}
    assert verdict(summary)["complete"] is False and verdict(summary)["stance_works"] is False


def perfect(dataset_rows: int = 6) -> dict[str, Any]:
    pairs = [("SUPPORT", "SUPPORT"), ("CONTRADICT", "CONTRADICT"), ("NEUTRAL", "NEUTRAL")] * 2
    from epistemic_search.rv2_metrics import stance_metrics

    m = stance_metrics(pairs)
    block = {"three_way": m, "planned": 6, "run": 6}
    return {"vitaminc": block, "scifact": block}


def test_verdict_applies_the_preregistered_thresholds_exactly() -> None:
    good = perfect()
    assert verdict(good)["stance_works"] is True
    bad = perfect()
    bad["vitaminc"] = {
        **bad["vitaminc"],
        "three_way": {**bad["vitaminc"]["three_way"], "false_contradict_rate": 0.11},
    }
    assert verdict(bad)["stance_works"] is False
    low = perfect()
    low["vitaminc"] = {
        **low["vitaminc"],
        "three_way": {**low["vitaminc"]["three_way"], "macro_f1": 0.69},
    }
    assert verdict(low)["stance_works"] is False


def test_the_full_run_refuses_to_start_without_a_logged_estimate(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="estimate"):
        stage_run(tmp_path)
