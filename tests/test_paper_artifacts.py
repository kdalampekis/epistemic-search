import csv
import json
import shutil
from pathlib import Path

import pytest
import yaml
from test_failures import setup_run
from typer.testing import CliRunner

from epistemic_search.cli import app
from epistemic_search.evaluation import file_hash
from epistemic_search.paper_artifacts import generate_paper_artifacts, tex, write_table


def plan(tmp_path: Path) -> Path:
    setup_run(tmp_path)
    shutil.copytree(tmp_path / "run", tmp_path / "other")
    (tmp_path / "stats.yaml").write_text(
        yaml.safe_dump(
            {
                "runs": {"reference": "run", "other": "other"},
                "reference": "reference",
                "output_path": "unused.json",
                "bootstrap_replicates": 100,
                "permutation_replicates": 100,
            }
        )
    )
    path = tmp_path / "paper.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "groups": {"fixture": {"statistics_config": "stats.yaml"}},
                "output_dir": "paper",
            }
        )
    )
    return path


def test_artifacts_preserve_results_and_repeat_exactly(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    path = plan(tmp_path)
    result = CliRunner().invoke(app, ["paper-artifacts", str(path)])
    assert result.exit_code == 0, result.output
    root = tmp_path / "paper"
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["method_cases"] == 4 and manifest["selected_traces"] == 2
    assert manifest["additional_api_calls"] == 0
    for name, expected in manifest["files"].items():
        assert file_hash(root / name) == expected
    with (root / "fixture/results.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert all(float(row["EM"]) == 0.5 and int(row["n"]) == 2 for row in rows)
    assert "SCRIPTED FIXTURE" in (root / "fixture/results.md").read_text()
    inventory = json.loads((root / "inventory.json").read_text())
    assert {r["outcome"] for r in inventory} == {"reference_match", "answer_mismatch"}
    assert not (tmp_path / "unused.json").exists()
    assert (root / "fixture/quality.pdf").read_bytes().startswith(b"%PDF")
    with pytest.raises(FileExistsError):
        generate_paper_artifacts(path)
    shutil.move(str(root), str(tmp_path / "first"))
    second = generate_paper_artifacts(path)
    assert manifest == second


def test_inconsistent_trace_fails_before_creating_output(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    path = plan(tmp_path)
    trace_path = tmp_path / "run/traces/000000.json"
    trace = json.loads(trace_path.read_text())
    trace["query_id"] = "wrong"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="identity"):
        generate_paper_artifacts(path)
    assert not (tmp_path / "paper").exists()


def test_ablation_requires_intervention_provenance(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    path = plan(tmp_path)
    config = yaml.safe_load(path.read_text())
    config["groups"]["fixture"]["kind"] = "ablation"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="intervention provenance"):
        generate_paper_artifacts(path)
    assert not (tmp_path / "paper").exists()


def test_table_missing_values_are_not_zero_and_tex_is_escaped(tmp_path: Path) -> None:
    write_table(
        tmp_path / "table", [{"method": "a_b&c", "score": None, "cost": 0.000123456789}], "test"
    )
    assert "NA" in (tmp_path / "table.md").read_text()
    assert r"a\_b\&c" in (tmp_path / "table.tex").read_text()
    assert "0.000123456789" in (tmp_path / "table.csv").read_text()
    assert tex("$%#{}") == r"\$\%\#\{\}"
