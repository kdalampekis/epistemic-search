import asyncio
import importlib
import json
from itertools import product
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.formal import (
    StructuredData,
    compare_formal,
    judge_prompt,
    solve,
    z3_module,
)
from epistemic_search.models import BeliefStatus, ClaimBelief
from epistemic_search.reasoning import reason

pytest.importorskip("z3")


def data() -> StructuredData:
    return StructuredData.model_validate_json(Path("tests/fixtures/formal_cases.json").read_text())


def configuration(tmp_path: Path) -> Path:
    config = load_config(Path("configs/formal_judge_fixture.yaml"))
    assert config.rag
    config.rag.responses_path = Path("tests/fixtures/formal_responses.json").resolve()
    run_path = tmp_path / "judge.yaml"
    run_path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    path = tmp_path / "comparison.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "data_path": str(Path("tests/fixtures/formal_cases.json").resolve()),
                "run_config_path": str(run_path),
                "output_dir": str(tmp_path / "output"),
            }
        )
    )
    return path


def test_fixture_oracles_and_semantic_differences() -> None:
    differences = []
    for case in data().cases:
        result = solve(case.graph, case.beliefs)
        assert result.verdict == case.expected_classical
        assert result.sufficient == (case.expected_classical == "entailed")
        assert result.checks == len(result.queries)
        assert result.queries[0]["query"] == "assumption-consistency"
        graph = reason(case.graph, case.beliefs)
        assert graph.status == case.expected_graph
        if result.sufficient != graph.sufficient:
            differences.append(case.id)
    assert differences == ["excluded-middle", "irrelevant-conflict"]


def test_exhaustive_consistent_two_atom_assignments_match_truth_table() -> None:
    graph = data().cases[0].graph
    states = [BeliefStatus.SUPPORTED, BeliefStatus.CONTRADICTED, BeliefStatus.UNKNOWN]
    for a, b in product(states, repeat=2):
        beliefs = [ClaimBelief(claim_id="a", status=a), ClaimBelief(claim_id="b", status=b)]
        outcomes = {
            x and y
            for x, y in product([True, False], repeat=2)
            if (a == "UNKNOWN" or x == (a == "SUPPORTED"))
            and (b == "UNKNOWN" or y == (b == "SUPPORTED"))
        }
        expected = (
            "entailed"
            if outcomes == {True}
            else ("refuted" if outcomes == {False} else "undetermined")
        )
        result = solve(graph, beliefs)
        assert result.verdict == expected
        assert result.sufficient == reason(graph, beliefs).sufficient


def test_inconsistency_never_proves_anything_and_smt_queries_replay() -> None:
    z3 = importlib.import_module("z3")
    for case in data().cases:
        result = solve(case.graph, case.beliefs)
        if case.id == "irrelevant-conflict":
            assert result.verdict == "inconsistent" and not result.sufficient
            assert result.checks == 1
        for query in result.queries:
            solver = z3.Solver()
            solver.from_string(query["smt2"])
            assert str(solver.check()) == query["result"]


def test_bad_structure_or_beliefs_fail_before_solver() -> None:
    case = data().cases[0]
    with pytest.raises(ValueError, match="unique, known"):
        solve(case.graph, [ClaimBelief(claim_id="absent")])
    with pytest.raises(ValueError, match="unique, known"):
        solve(case.graph, case.beliefs * 2)
    with pytest.raises(ValueError, match="positive"):
        solve(case.graph, [], timeout_ms=0)
    case.graph.nodes[0].children.append("root")
    with pytest.raises(ValueError):
        solve(case.graph, [])


def test_missing_extra_and_solver_unknown_are_explicit() -> None:
    with patch("epistemic_search.formal.importlib.import_module", side_effect=ImportError):
        with pytest.raises(ValueError, match="extra formal"):
            z3_module()
    z3 = importlib.import_module("z3")
    with patch.object(z3.Solver, "check", return_value=z3.unknown):
        result = solve(data().cases[0].graph, [])
        assert result.verdict == "solver_unknown" and not result.sufficient
        assert result.checks == 1


def test_gold_and_provenance_never_enter_judge_prompt() -> None:
    case = data().cases[0]
    case.formalization_provenance = "PRIVATE_PROVENANCE"
    prompt = judge_prompt(case)
    assert "PRIVATE_PROVENANCE" not in prompt
    assert "expected_classical" not in prompt and "expected_graph" not in prompt
    assert "UNKNOWN is unconstrained" in prompt


def test_comparison_cli_retains_full_traces_and_zero_cost(tmp_path: Path) -> None:
    path = configuration(tmp_path)
    result = CliRunner().invoke(app, ["compare-formal", str(path)])
    assert result.exit_code == 0, result.output
    root = tmp_path / "output"
    report = json.loads((root / "summary.json").read_text())
    assert report["completed_examples"] == report["planned_examples"] == 8
    assert report["fixture_only"] is True
    assert all(v == {"labelled": 8, "correct": 8} for v in report["correctness_counts"].values())
    results = [json.loads(line) for line in (root / "results.jsonl").read_text().splitlines()]
    for row in results:
        assert row["generative_usage"]["model_calls"] == 1
        assert row["generative_usage"]["api_calls"] == 0
        assert row["generative_usage"]["cost_usd"] == "0"
        assert row["graph_usage"]["model_calls"] == row["smt_usage"]["model_calls"] == 0
        assert row["trace"][0]["type"] == "MODEL"
        assert row["generative_usage_complete"] is True
    with pytest.raises(FileExistsError):
        asyncio.run(compare_formal(path))


def test_invalid_model_response_is_retained_without_retry(tmp_path: Path) -> None:
    path = configuration(tmp_path)
    config_path = tmp_path / "judge.yaml"
    config = yaml.safe_load(config_path.read_text())
    script = json.loads(Path("tests/fixtures/formal_responses.json").read_text())
    script[0] = '{"verdict":"entailed"}'  # Missing required rationale.
    responses = tmp_path / "responses.json"
    responses.write_text(json.dumps(script))
    config["rag"]["responses_path"] = str(responses)
    config_path.write_text(yaml.safe_dump(config))
    report = asyncio.run(compare_formal(path))
    assert report["generative_errors"] == 1 and report["completed_examples"] == 8
    rows = [
        json.loads(line) for line in (tmp_path / "output/results.jsonl").read_text().splitlines()
    ]
    assert rows[0]["generative_correct"] is False
    assert rows[0]["generative_usage"]["model_calls"] == 1
    assert rows[1]["generative_correct"] is True


def test_zero_budget_prevents_every_model_call(tmp_path: Path) -> None:
    path = configuration(tmp_path)
    config_path = tmp_path / "judge.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["budget"]["max_llm_calls"] = 0
    config_path.write_text(yaml.safe_dump(config))
    report = asyncio.run(compare_formal(path))
    assert report["generative_errors"] == 8
    rows = [
        json.loads(line) for line in (tmp_path / "output/results.jsonl").read_text().splitlines()
    ]
    assert all(row["generative_usage"]["model_calls"] == 0 for row in rows)
    assert all("smt" in row and "proof_graph" in row for row in rows)
