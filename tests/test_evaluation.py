import asyncio
import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from epistemic_search.baseline import Answer, RunResult
from epistemic_search.cli import app
from epistemic_search.evaluation import (
    JsonlDataset,
    evaluate,
    exact_match,
    score_case,
    summarize,
    token_f1,
)
from epistemic_search.models import QueryCase, Usage


@pytest.mark.parametrize(
    "prediction,gold,em,f1",
    [
        ("The Paris!", "paris", 1, 1),
        ("red red blue", "red blue blue", 0, 2 / 3),
        ("", "", 1, 1),
        ("", "Paris", 0, 0),
        ("no", "yes", 0, 0),
        ("New York", "York", 0, 2 / 3),
    ],
)
def test_metrics(prediction: str, gold: str, em: float, f1: float) -> None:
    assert exact_match(prediction, gold) == em
    assert token_f1(prediction, gold) == pytest.approx(f1)


def test_runner_retains_failures_unlabelled_and_abstentions(tmp_path: Path) -> None:
    cases = [
        QueryCase(id=str(i), question="Question", gold_answer="Paris" if i < 3 else None)
        for i in range(4)
    ]
    path = tmp_path / "data.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in cases))
    called = []

    async def runner(case: QueryCase) -> RunResult:
        assert case.gold_answer is None and case.answerable is None and case.metadata == {}
        called.append(case.id)
        if case.id == "1":
            raise RuntimeError("Do not omit this failure")
        answer = None if case.id == "2" else "Paris"
        return RunResult(
            query_id=case.id,
            status="completed",
            output=Answer(answer=answer, citation_ids=["s1"] if answer else []),
            usage=Usage(search_calls=1, prompt_tokens=10, cost_usd=Decimal("0.01")),
            wall_seconds=0.1,
            trace=[],
        )

    output = tmp_path / "output"
    summary = asyncio.run(evaluate(JsonlDataset(path), runner, output, {"seed": 42}))
    assert called == ["0", "1", "2", "3"]
    assert summary.examples == 4 and summary.labelled_examples == 3
    assert summary.exact_match == pytest.approx(1 / 3)
    assert summary.coverage == 0.5
    assert summary.errors == summary.incomplete_usage_examples == 1
    assert summary.usage.cost_usd is None
    assert summary.usage.search_calls == 3
    assert len(list((output / "traces").glob("*.json"))) == 4
    assert len((output / "examples.jsonl").read_text().splitlines()) == 4
    with (output / "summary.csv").open() as csv_file:
        row = next(csv.DictReader(csv_file))
    assert row["examples"] == "4"
    assert row["total_cost_usd"] == ""
    with pytest.raises(FileExistsError):
        asyncio.run(evaluate(JsonlDataset(path), runner, output, {}))
    assert len(called) == 4


@pytest.mark.parametrize(
    "content", ["", "bad JSON", '{"id":"x","question":"q"}\n{"id":"x","question":"q"}']
)
def test_dataset_errors_before_execution(tmp_path: Path, content: str) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text(content)
    with pytest.raises(ValueError):
        JsonlDataset(path).load()


def test_unlabelled_metrics_are_unknown_and_budget_cases_remain_in_coverage() -> None:
    case = QueryCase(id="q", question="Question")
    result = RunResult(
        query_id="q",
        status="budget_exhausted",
        usage=Usage(cost_usd=Decimal(0)),
        wall_seconds=0,
        trace=[],
    )
    summary = summarize([score_case(case, result, "traces/000000.json")])
    assert summary.exact_match is summary.token_f1 is None
    assert summary.coverage == 0
    assert summary.budget_exhausted == 1
    assert summary.labelled_examples == 0
    with pytest.raises(ValueError):
        summarize([])


def test_evaluation_cli_hashes_and_negative_fixture_result(tmp_path: Path) -> None:
    import yaml

    config = yaml.safe_load(Path("configs/evaluation_fixture.yaml").read_text())
    config["rag"]["corpus_path"] = str(Path("tests/fixtures/corpus.json").resolve())
    config["rag"]["responses_path"] = str(Path("tests/fixtures/responses.json").resolve())
    config["evaluation"]["dataset_path"] = str(Path("tests/fixtures/benchmark.jsonl").resolve())
    config["evaluation"]["output_dir"] = str(tmp_path / "results")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    result = CliRunner().invoke(app, ["evaluate", str(path)])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["exact_match"] == 0.5  # Script always says Paris; Greece is wrong.
    assert summary["coverage"] == 1.0
    manifest = json.loads((tmp_path / "results/manifest.json").read_text())
    assert len(manifest["input_hashes"]["dataset"]) == 64
    assert manifest["fixture_only"] is True
