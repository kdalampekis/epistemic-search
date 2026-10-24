import hashlib
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.evaluation import ScoredCase, summarize
from epistemic_search.models import QueryCase, Usage
from epistemic_search.statistics import (
    analyze_comparison,
    bootstrap,
    distribution,
    holm,
    paired_permutation,
    quantile,
    read_run,
)


def config_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def saved_run(path: Path, scores: list[float], *, failure: bool = False) -> None:
    path.mkdir()
    config = load_config(Path("configs/parity_fixture.yaml")).model_dump(mode="json")
    rows = [
        ScoredCase(
            query_id=str(i),
            status="error" if failure and i == 0 else "completed",
            answered=not (failure and i == 0),
            labelled=True,
            exact_match=score,
            token_f1=score,
            trace_file=f"traces/{i:06}.json",
            usage=Usage(model_calls=1, cost_usd=None if failure and i == 0 else "0.1"),
            usage_complete=not (failure and i == 0),
            wall_seconds=1,
        )
        for i, score in enumerate(scores)
    ]
    labels = [
        QueryCase(
            id=str(i),
            question=f"question {i}",
            gold_answer="yes",
            metadata={"group_id": f"g{i // 2}"},
        )
        for i in range(len(scores))
    ]
    (path / "examples.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in rows))
    (path / "labels.jsonl").write_text("".join(c.model_dump_json() + "\n" for c in labels))
    (path / "summary.json").write_text(summarize(rows, "english-em-token-f1-v1").model_dump_json())
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "config": config,
                "config_hash": config_hash(config),
                "selected_case_ids": [r.query_id for r in rows],
                "metric_version": "english-em-token-f1-v1",
                "retriever": "lexical-overlap-v1",
                "retrieval_scope": "fixture",
                "input_hashes": {"dataset": "fixture"},
                "fixture_only": True,
            }
        )
    )


def analysis_config(tmp_path: Path) -> Path:
    saved_run(tmp_path / "a", [0, 0, 0, 0])
    saved_run(tmp_path / "b", [0, 1, 1, 1], failure=True)
    path = tmp_path / "analysis.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "runs": {"a": "a", "b": "b"},
                "reference": "a",
                "output_path": "report.json",
                "seed": 7,
                "bootstrap_replicates": 500,
                "permutation_replicates": 500,
            }
        )
    )
    return path


def test_cluster_resampling_retains_unequal_family_sizes_and_is_deterministic() -> None:
    groups = {"large": [0.0] * 9, "small": [1.0]}
    result = bootstrap(groups, replicates=500, seed=42, confidence=0.95)
    assert result["mean"] == 0.1 and result["examples"] == 10 and result["groups"] == 2
    assert result["lower"] == 0 and result["upper"] == 1
    assert result == bootstrap(
        dict(reversed(list(groups.items()))), replicates=500, seed=42, confidence=0.95
    )
    assert bootstrap({"one": [1.0, 0.0]}, replicates=500, seed=42, confidence=0.95)["lower"] is None
    assert bootstrap({}, replicates=500, seed=42, confidence=0.95)["mean"] is None
    assert (
        bootstrap({"a": [1.0], "b": [1.0]}, replicates=500, seed=42, confidence=0.95)["degenerate"]
        is True
    )


def test_paired_exact_test_flips_whole_groups_and_mc_never_returns_zero() -> None:
    result = paired_permutation({"a": [1.0, 1.0], "b": [1.0, 1.0]}, replicates=100, seed=0)
    assert result["p_value"] == 0.5 and result["permutations"] == 4 and result["exact"]
    assert (
        paired_permutation({"a": [1.0], "b": [1.0], "c": [1.0]}, replicates=100, seed=0)["p_value"]
        == 0.25
    )
    assert paired_permutation({"a": [0.0], "b": [0.0]}, replicates=100, seed=0)["p_value"] == 1
    groups = {str(i): [1.0] for i in range(17)}
    sampled = paired_permutation(groups, replicates=100, seed=3)
    assert sampled["exact"] is False and sampled["p_value"] >= 1 / 101
    assert sampled == paired_permutation(groups, replicates=100, seed=3)
    assert paired_permutation({"one": [1.0]}, replicates=100, seed=0)["p_value"] is None


def test_holm_and_cost_quantiles_keep_unknowns_explicit() -> None:
    assert holm({"a": 0.01, "b": 0.04, "c": 0.03}) == {"a": 0.03, "c": 0.06, "b": 0.06}
    assert quantile([1, 2, 3, 4, 100], 0.9) == pytest.approx(61.6)
    result = distribution([0.0, 1.0, None])
    assert result == {
        "known": 2,
        "unknown": 1,
        "mean": 0.5,
        "median": 0.5,
        "p90": 0.9,
        "total_known": 1,
    }
    assert distribution([None])["mean"] is None
    with pytest.raises(ValueError):
        bootstrap({"bad": [float("nan")]}, replicates=100, seed=0, confidence=0.95)
    with pytest.raises(ValueError):
        holm({"bad": float("inf")})


def test_saved_comparison_uses_recorded_failures_groups_and_paired_differences(
    tmp_path: Path,
) -> None:
    path = analysis_config(tmp_path)
    report = analyze_comparison(path)
    assert report["additional_api_calls"] == 0 and report["holm_family_size"] == 3
    assert report["runs"]["b"]["errors"] == 1
    assert report["runs"]["b"]["resources"]["cost_usd"]["unknown"] == 1
    assert report["runs"]["b"]["metrics"]["exact_match"]["mean"] == 0.75
    em = next(c for c in report["comparisons"] if c["metric"] == "exact_match")
    assert em["difference"]["mean"] == 0.75 and em["difference"]["groups"] == 2
    assert em["test"]["p_value"] == 0.5 and em["test"]["p_holm"] == 1
    assert all(c["test"]["p_holm"] >= c["test"]["p_value"] for c in report["comparisons"])
    with pytest.raises(FileExistsError):
        analyze_comparison(path)


@pytest.mark.parametrize(
    "mutation", ["model", "budget", "grader", "labels", "partial", "summary", "hash"]
)
def test_incompatible_or_incomplete_results_fail_before_output(
    tmp_path: Path, mutation: str
) -> None:
    path = analysis_config(tmp_path)
    root = tmp_path / "b"
    manifest_path = root / "manifest.json"
    metadata = json.loads(manifest_path.read_text())
    if mutation in {"model", "budget", "hash"}:
        if mutation == "model":
            metadata["config"]["rag"]["model"] = "different-model"
        else:
            metadata["config"]["budget"]["max_llm_calls"] += 1
        if mutation != "hash":
            metadata["config_hash"] = config_hash(metadata["config"])
        manifest_path.write_text(json.dumps(metadata))
    elif mutation == "grader":
        metadata["metric_version"] = "hotpotqa-answer-v1"
        manifest_path.write_text(json.dumps(metadata))
    elif mutation == "labels":
        labels = root / "labels.jsonl"
        labels.write_text(labels.read_text().replace('"gold_answer":"yes"', '"gold_answer":"no"'))
    else:
        summary_path = root / "summary.json"
        summary = json.loads(summary_path.read_text())
        summary["stop_reason" if mutation == "partial" else "exact_match"] = (
            "budget stop" if mutation == "partial" else 0
        )
        summary_path.write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        analyze_comparison(path)
    assert not (tmp_path / "report.json").exists()


def test_duplicate_scores_are_rejected(tmp_path: Path) -> None:
    analysis_config(tmp_path)
    path = tmp_path / "b/examples.jsonl"
    with path.open("a") as stream:
        stream.write(path.read_text().splitlines()[0] + "\n")
    with pytest.raises(ValueError, match="unique"):
        read_run(tmp_path / "b")


def test_cli_is_deterministic_without_model_access(tmp_path: Path) -> None:
    path = analysis_config(tmp_path)
    result = CliRunner().invoke(app, ["analyze-comparison", str(path)])
    assert result.exit_code == 0, result.output
    first = (tmp_path / "report.json").read_bytes()
    (tmp_path / "report.json").unlink()
    assert CliRunner().invoke(app, ["analyze-comparison", str(path)]).exit_code == 0
    assert (tmp_path / "report.json").read_bytes() == first
