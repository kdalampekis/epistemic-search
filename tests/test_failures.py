import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from epistemic_search.baseline import RunResult
from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.evaluation import ScoredCase, file_hash
from epistemic_search.failures import (
    FailureJudgments,
    analyze_failures,
    classify,
    fenced,
    render_example,
)
from epistemic_search.models import QueryCase


def setup_run(tmp_path: Path) -> Path:
    config = load_config(Path("configs/evaluation_fixture.yaml"))
    assert config.rag and config.evaluation
    config.rag.corpus_path = Path("tests/fixtures/corpus.json").resolve()
    config.rag.responses_path = Path("tests/fixtures/responses.json").resolve()
    config.evaluation.dataset_path = Path("tests/fixtures/benchmark.jsonl").resolve()
    config.evaluation.output_dir = tmp_path / "run"
    path = tmp_path / "evaluate.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    executed = CliRunner().invoke(app, ["evaluate", str(path)])
    assert executed.exit_code == 0, executed.output
    plan = tmp_path / "failures.yaml"
    plan.write_text(yaml.safe_dump({"runs": {"fixture": "run"}, "output_dir": "reports"}))
    return plan


def first_case(tmp_path: Path) -> tuple[QueryCase, ScoredCase, RunResult]:
    root = tmp_path / "run"
    case = QueryCase.model_validate_json((root / "labels.jsonl").read_text().splitlines()[0])
    row = ScoredCase.model_validate_json((root / "examples.jsonl").read_text().splitlines()[0])
    trace = RunResult.model_validate_json((root / row.trace_file).read_text())
    return case, row, trace


def test_cli_reports_every_case_with_provisional_taxonomy(tmp_path: Path) -> None:
    plan = setup_run(tmp_path)
    result = CliRunner().invoke(app, ["analyze-failures", str(plan)])
    assert result.exit_code == 0, result.output
    root = tmp_path / "reports"
    report = json.loads((root / "summary.json").read_text())
    assert report["examples"] == 2 and report["additional_api_calls"] == 0
    assert report["outcomes"] == {"reference_match": 1, "answer_mismatch": 1}
    assert report["automatic_needs_review"] == 1
    assert report["primary_categories"] == {"ANSWER_GENERATION_ERROR": 1}
    assert len(list((root / "cases").glob("*.html"))) == 2
    assert len(list((root / "cases").glob("*.md"))) == 2
    page = (root / "cases/000000.html").read_text()
    assert "Event timeline" in page and "<details>" in page
    assert "Gold labels are shown only" in page
    with pytest.raises(FileExistsError):
        analyze_failures(plan)


def test_abstention_and_budget_stop_are_not_automatic_failures(tmp_path: Path) -> None:
    setup_run(tmp_path)
    _, row, trace = first_case(tmp_path)
    row.answered = False
    row.exact_match = row.token_f1 = 0
    trace.output = None
    for status, outcome in [("completed", "abstention"), ("budget_exhausted", "budget_stop")]:
        trace.status = status  # type: ignore[assignment]
        classification = classify("fixture", trace, row, "a" * 64)
        assert classification.outcome == outcome and classification.primary is None
        assert classification.needs_review is False


def test_observable_extraction_failure_is_not_called_a_stance_error(tmp_path: Path) -> None:
    setup_run(tmp_path)
    _, row, trace = first_case(tmp_path)
    trace.status = "error"
    trace.error = "Extracted span is absent from exact source text"
    trace.trace[-1].type = "EVIDENCE_ADDED"
    trace.trace[-1].payload = {"errors": [trace.error]}
    classification = classify("fixture", trace, row, "a" * 64)
    assert classification.primary == "EVIDENCE_EXTRACTION_ERROR"
    assert classification.basis == "observed_stage" and classification.needs_review


def test_manual_judgments_bind_trace_and_preserve_assessor(tmp_path: Path) -> None:
    plan = setup_run(tmp_path)
    _, row, _ = first_case(tmp_path)
    annotation = {
        "assessor": "fixture-reviewer",
        "protocol": "test-only-independent-audit",
        "cases": [
            {
                "run": "fixture",
                "query_id": row.query_id,
                "trace_sha256": file_hash(tmp_path / "run" / row.trace_file),
                "primary": "BENCHMARK_AMBIGUITY",
                "secondary": ["STANCE_ERROR"],
                "rationale": "Explicit fixture annotation; not empirical validation.",
            }
        ],
    }
    annotations = tmp_path / "judgments.json"
    annotations.write_text(json.dumps(annotation))
    values = yaml.safe_load(plan.read_text())
    values["judgments_path"] = "judgments.json"
    plan.write_text(yaml.safe_dump(values))
    report = analyze_failures(plan)
    assert report["manual_judgments"] == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "reports/classifications.jsonl").read_text().splitlines()
    ]
    assert records[0]["assessor"] == "fixture-reviewer" and records[0]["basis"] == "manual"
    assert records[0]["secondary"] == ["STANCE_ERROR"]
    values["output_dir"] = "bad-reports"
    plan.write_text(yaml.safe_dump(values))
    annotation["cases"][0]["trace_sha256"] = "0" * 64  # type: ignore[index]
    annotations.write_text(json.dumps(annotation))
    with pytest.raises(ValueError, match="different trace"):
        analyze_failures(plan)
    assert not (tmp_path / "bad-reports").exists()


def test_html_and_markdown_do_not_execute_source_content(tmp_path: Path) -> None:
    setup_run(tmp_path)
    case, row, trace = first_case(tmp_path)
    payload = '</pre><script>alert("x")</script>\n```\n[bad](javascript:alert(1))'
    case.question = payload
    trace.error = payload
    classification = classify("fixture", trace, row, "a" * 64)
    markdown, page = render_example(case, row, trace, classification)
    assert "<script>alert" not in page and "&lt;script&gt;" in page
    assert "default-src 'none'" in page
    assert fenced(payload) in markdown and fenced(payload).startswith("````\n")


def test_trace_path_escape_and_identity_mismatch_are_rejected(tmp_path: Path) -> None:
    plan = setup_run(tmp_path)
    row_path = tmp_path / "run/examples.jsonl"
    rows = row_path.read_text().splitlines()
    row = json.loads(rows[0])
    row["trace_file"] = "../private.json"
    row_path.write_text(json.dumps(row) + "\n" + "\n".join(rows[1:]) + "\n")
    with pytest.raises(ValueError, match="escapes"):
        analyze_failures(plan)
    assert not (tmp_path / "reports").exists()
    row_path.write_text("\n".join(rows) + "\n")
    trace_path = tmp_path / "run" / json.loads(rows[0])["trace_file"]
    trace = json.loads(trace_path.read_text())
    trace["query_id"] = "wrong-case"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="identity"):
        analyze_failures(plan)


def test_invalid_taxonomy_and_duplicate_manual_labels_are_rejected() -> None:
    with pytest.raises(ValueError):
        FailureJudgments.model_validate(
            {
                "assessor": "x",
                "protocol": "x",
                "cases": [
                    {
                        "run": "r",
                        "query_id": "q",
                        "trace_sha256": "a" * 64,
                        "primary": "UNSUPPORTED_INVENTED_CATEGORY",
                        "rationale": "x",
                    },
                ],
            }
        )
