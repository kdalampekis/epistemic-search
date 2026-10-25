import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from epistemic_search.baseline import RunResult
from epistemic_search.cli import app
from epistemic_search.config import RunConfig, load_config
from epistemic_search.evaluation import ScoredCase, file_hash
from epistemic_search.evidence import PROMPT_VERSION
from epistemic_search.models import QueryCase
from epistemic_search.pilot_audit import (
    CATEGORIES,
    audit_pilot,
    diagnostic,
    gold_title_retrieval,
    surface_form,
)


def setup_audit(tmp_path: Path) -> Path:
    config = load_config(Path("configs/epistemic_fixture.yaml"))
    assert config.rag and config.evaluation and config.decomposition
    config.rag.corpus_path = Path("tests/fixtures/epistemic_corpus.json").resolve()
    config.rag.responses_path = Path("tests/fixtures/epistemic_responses.json").resolve()
    config.evaluation.dataset_path = Path("tests/fixtures/epistemic_benchmark.jsonl").resolve()
    config.evaluation.output_dir = tmp_path / "run"
    config.decomposition.cache_dir = tmp_path / "cache"
    path = tmp_path / "evaluate.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    executed = CliRunner().invoke(app, ["evaluate", str(path)])
    assert executed.exit_code == 0, executed.output
    plan = tmp_path / "audit.yaml"
    plan.write_text(
        yaml.safe_dump({"runs": {"fixture": "run"}, "output_dir": "audit", "annotation_groups": 1})
    )
    return plan


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def tree_hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): file_hash(p) for p in sorted(root.rglob("*")) if p.is_file()}


def test_cli_records_observations_and_leaves_judgments_blank(tmp_path: Path) -> None:
    plan = setup_audit(tmp_path)
    before = tree_hashes(tmp_path / "run")
    result = CliRunner().invoke(app, ["audit-pilot", str(plan)])
    assert result.exit_code == 0, result.output
    assert "additional API cost $0" in result.output
    assert tree_hashes(tmp_path / "run") == before

    root = tmp_path / "audit"
    summary = json.loads((root / "summary.json").read_text())
    assert summary["additional_api_calls"] == 0 and summary["additional_api_cost_usd"] == "0"
    assert summary["human_annotations_completed"] == 0
    assert summary["semantic_failure_distribution"] is None
    assert summary["allowed_rv1_categories"] == CATEGORIES
    assert summary["methods"]["epistemic_search"]["belief_replay_mismatches"] == 0
    assert summary["methods"]["epistemic_search"]["reasoner_replay_mismatches"] == 0
    for name, digest in summary["output_hashes"].items():
        assert file_hash(root / name) == digest

    [record] = jsonl(root / "diagnostics.jsonl")
    obs = record["observations"]
    assert record["semantic_audit_scope"] and obs["decomposition"]["claims"]
    assert obs["retrieval"] and obs["controller_actions"] and obs["final_decision"]
    assert obs["accepted_evidence"] and obs["belief_transitions"]
    unchanged = sum(t["before"] == t["after"] for t in obs["belief_transitions"])
    assert obs["belief_updates_unchanged"] == unchanged
    assert summary["methods"]["epistemic_search"]["belief_updates_unchanged"] == unchanged
    assert unchanged < len(obs["belief_transitions"])
    assert obs["gold_title_retrieval"] == {
        "available": False,
        "reason": "no_supporting_fact_annotation",
    }
    human = record["human_judgments"]
    assert human["status"] == "REQUIRES_MANUAL_REVIEW" and human["assessor"] is None
    assert human["primary_attribution"] == "UNKNOWN_REQUIRES_HUMAN_REVIEW"
    assert human["answer_correct"] is None and human["abstention_appropriate"] is None
    assert all(v is None for p in human["premises"] for k, v in p.items() if k != "claim_id")
    assert all(
        item["semantic_stance_review"] == "REQUIRES_MANUAL_REVIEW"
        for batch in obs["extractions"]
        for item in batch["items"]
    )
    # A produced answer is never labelled correct by the audit.
    assert record["matched_naive_rag"]["available"] is False

    [template] = jsonl(root / "rv1_annotation_template.jsonl")
    assert template["status"] == "NOT_ANNOTATED" and template["primary_category"] is None
    assert template["trace_sha256"] == record["trace_sha256"]
    assert len(jsonl(root / "manual_review_priority.jsonl")) == 1
    assert len((root / "diagnostics.csv").read_text().splitlines()) == 2
    documents = jsonl(root / "documents.jsonl")
    keys = {s["document_key"] for r in obs["retrieval"] for s in r["sources"]}
    assert keys == {d["key"] for d in documents}


def test_refuses_overwrite_overlap_judgments_and_tampered_traces(tmp_path: Path) -> None:
    plan = setup_audit(tmp_path)
    audit_pilot(plan)
    with pytest.raises(ValueError, match="new and separate"):
        audit_pilot(plan)
    values = yaml.safe_load(plan.read_text())

    values["output_dir"] = "run/nested"
    plan.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError, match="new and separate"):
        audit_pilot(plan)

    values["output_dir"] = "second"
    values["judgments_path"] = "judgments.json"
    plan.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError, match="does not import judgments"):
        audit_pilot(plan)
    del values["judgments_path"]

    trace = tmp_path / "run/traces/000000.json"
    trace.write_text(trace.read_text().replace('"completed"', '"error"', 1))
    plan.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError):
        audit_pilot(plan)
    assert not (tmp_path / "second").exists()


def saved_case(tmp_path: Path) -> tuple[QueryCase, ScoredCase, RunResult, RunConfig]:
    root = tmp_path / "run"
    case = QueryCase.model_validate_json((root / "labels.jsonl").read_text().splitlines()[0])
    row = ScoredCase.model_validate_json((root / "examples.jsonl").read_text().splitlines()[0])
    trace = RunResult.model_validate_json((root / row.trace_file).read_text())
    config = RunConfig.model_validate(json.loads((root / "manifest.json").read_text())["config"])
    return case, row, trace, config


def test_span_contract_violation_is_flagged_but_not_repaired(tmp_path: Path) -> None:
    setup_audit(tmp_path)
    case, row, trace, config = saved_case(tmp_path)
    nbsp = "\u00a0"
    for event in trace.trace:
        payload: Any = event.payload
        if event.type == "MODEL" and payload["request"]["prompt_version"] == PROMPT_VERSION:
            items = json.loads(payload["response"]["text"])
            items["items"][0]["span"] = items["items"][0]["span"].replace(" ", nbsp, 1)
            payload["response"]["text"] = json.dumps(items)
            break
    record = diagnostic("fixture", "d", case, row, trace, "a" * 64, config, {})
    obs = record["observations"]
    assert obs["invalid_span_count"] == 1
    assert obs["invalid_spans_matching_after_nbsp_replacement"] == 1
    assert record["candidate_observed_defects"] == [
        {"category": "EVIDENCE_EXTRACTION_ERROR", "basis": "literal_or_schema_contract_violation"}
    ]
    # The audit records the contract violation; it does not assign a stance or semantic verdict.
    assert record["human_judgments"]["primary_attribution"] == "UNKNOWN_REQUIRES_HUMAN_REVIEW"


def test_gold_title_retrieval_uses_benchmark_annotations_only() -> None:
    def case(metadata: dict[str, Any]) -> QueryCase:
        return QueryCase(id="q", question="Q?", metadata=metadata)

    retrieval = [{"sources": [{"title": "  Alpha   Page "}, {"title": "Distractor"}]}]
    annotated = case(
        {"annotations": {"supporting_facts": [["alpha page", 0], ["Beta", 1], ["Beta", 2]]}}
    )
    found = gold_title_retrieval(annotated, retrieval)
    assert found["recall"] == 0.5 and found["gold_titles_missing"] == ["Beta"]
    assert found["decisive_evidence_present"] == "REQUIRES_MANUAL_REVIEW"
    assert gold_title_retrieval(annotated, []) == {
        "available": False,
        "reason": "no_retrieval_events",
    }
    assert gold_title_retrieval(case({}), retrieval) == {
        "available": False,
        "reason": "no_supporting_fact_annotation",
    }


def test_surface_forms_are_lexical_flags_only() -> None:
    assert surface_form("Identify the director of X.") == "TASK_VERB_PREFIX"
    assert surface_form("Who directed X?") == "QUESTION_MARK"
    assert surface_form("Whether the lyrics establish intent") == "WHETHER_CLAUSE"
    assert surface_form("The director of X was born in 1950.") == "OTHER"
    assert surface_form("") == "OTHER"
