import datetime
import json
import typing
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_pilot_audit import setup_audit

from epistemic_search.pilot_audit import audit_pilot
from epistemic_search.rv1 import (
    add_assessor,
    aggregate_rv1,
    init_rv1,
    kappa,
    validate_rv1,
)
from epistemic_search.rv1_schema import (
    CaseFile,
    Judgment,
    OracleClaim,
    OracleDecomposition,
    OracleLogic,
    blank_fields,
    check,
    dump_case,
    judgments,
    load_case,
    oracle_graph,
    problems,
)


def setup_rv1(tmp_path: Path) -> Path:
    plan = setup_audit(tmp_path)
    audit_pilot(plan)
    config = {
        "rv0_dir": "audit",
        "frozen_rv0_summary": "audit/summary.json",
        "annotations_dir": "ann",
        "sheets_dir": "sheets",
        "results_dir": "res",
        "assessors": ["primary"],
    }
    path = tmp_path / "rv1.yaml"
    path.write_text(yaml.safe_dump(config))
    return path


def only_file(tmp_path: Path, assessor: str = "primary") -> Path:
    [path] = (tmp_path / "ann" / assessor).glob("*.yaml")
    return path


def choices(judgment: Judgment, name: str) -> list[str]:
    values: list[str] = []
    for arm in typing.get_args(type(judgment).model_fields[name].annotation):
        values += [v for v in typing.get_args(arm) if isinstance(v, str)]
    return values


def fill(case: CaseFile, root_cause: str = "UNCERTAIN") -> CaseFile:
    """Test-only stand-in for a person: answers every field consistently with the rules."""
    case.assessor, case.date, case.status = "tester", datetime.date(2026, 11, 1), "COMPLETE"
    case.oracle.authored_before_viewing_generated = "YES"
    case.oracle.required_claims = [
        OracleClaim(id="o1", assertion="Paris is the capital of France."),
        OracleClaim(id="o2", assertion="France is in Europe."),
    ]
    case.oracle.logic = OracleLogic(type="AND")
    for _, _, j in judgments(case):
        for name in j.blanks():
            options = [v for v in choices(j, name) if v != "NOT_APPLICABLE"] or ["YES"]
            setattr(j, name, options[0])
    for m in case.methods.values():
        answered = bool(m.outcome.context["answered"])
        m.outcome.judgment.answer_correct = "YES" if answered else "NOT_APPLICABLE"
        m.outcome.judgment.abstention_appropriate = "NOT_APPLICABLE" if answered else "YES"
        for r in m.retrieval_rounds:
            first = r.context["round"] == 1
            r.judgment.query_materially_different_from_previous = (
                "NOT_APPLICABLE" if first else "NO"
            )
        for d in m.controller_decisions:
            repeats = d.context["next_query_exact_repeat_of_earlier"]
            d.judgment.repeat_justified = "NO" if repeats else "NOT_APPLICABLE"
        m.root_cause.primary = root_cause  # type: ignore[assignment]
        m.root_cause.rationale = "test rationale"
    return case


def write(path: Path, case: CaseFile) -> None:
    path.write_text(dump_case(case, "test"), encoding="utf-8")


def test_init_writes_blank_hashed_files_and_sheets(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    assert init_rv1(config) == {"cases": 1, "assessors": ["primary"], "api_calls": 0}
    case = load_case(only_file(tmp_path))
    assert case.status == "NOT_STARTED" and case.assessor is None
    assert case.methods["epistemic_search"].retrieval_rounds and case.premises
    assert all(
        v is None
        for _, _, j in judgments(case)
        for v in j.model_dump().values()
        if not isinstance(v, (list, dict))
    )
    assert blank_fields(case) and check(case)["issues"] == []
    assert (tmp_path / "res/context_manifest.json").exists()
    [sheet] = (tmp_path / "sheets").glob("*.md")
    assert "Retrieved documents (full text)" in sheet.read_text()
    report = validate_rv1(config)
    assert report["issues"] == [] and report["assessors"]["primary"]["not_started"] == 1
    with pytest.raises(FileExistsError):
        init_rv1(config)


def test_no_distribution_until_every_case_is_complete(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    summary = aggregate_rv1(config)
    entry = summary["assessors"]["primary"]
    assert entry["failure_distribution"] is None and entry["sections"] is None
    assert summary["oracle_decompositions_exported"] == 0
    path = only_file(tmp_path)
    partial = load_case(path)
    partial.status = "IN_PROGRESS"
    partial.decomposition.judgment.complete = "NO"
    write(path, partial)
    summary = aggregate_rv1(config)
    assert summary["assessors"]["primary"]["in_progress"] == 1
    assert summary["assessors"]["primary"]["failure_distribution"] is None


def test_complete_case_yields_distribution_and_oracle_export(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    path = only_file(tmp_path)
    write(path, fill(load_case(path)))
    assert validate_rv1(config)["issues"] == []
    summary = aggregate_rv1(config)
    entry = summary["assessors"]["primary"]
    assert entry["all_complete"] and entry["blank_fields_total"] == 0
    dist = entry["failure_distribution"]["epistemic_search"]
    assert dist["n"] == 1 and dist["primary"] == {"UNCERTAIN": 1}
    assert "field_counts" in entry["sections"]
    rows = [
        json.loads(x)
        for x in (tmp_path / "res/oracle_decompositions.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 1 and rows[0]["proof_graph"] is not None
    assert rows[0]["authored_before_viewing_generated"] == "YES"
    first = (tmp_path / "res/summary.json").read_bytes()
    aggregate_rv1(config)
    assert (tmp_path / "res/summary.json").read_bytes() == first


def test_complete_requires_every_field_and_consistent_labels(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    path = only_file(tmp_path)
    case = fill(load_case(path))
    case.decomposition.judgment.complete = None
    write(path, case)
    assert any("COMPLETE but blank" in i for i in validate_rv1(config)["issues"])

    case = fill(load_case(path))
    method = case.methods["epistemic_search"]
    method.root_cause.primary = "MULTIPLE_FAILURES"
    method.root_cause.secondary = ["STANCE_ERROR"]
    assert any("two or more" in p for p in problems(case))
    method.root_cause.primary = "UNCERTAIN"
    method.root_cause.secondary = ["STANCE_ERROR"]
    assert any("cannot have secondary" in p for p in problems(case))
    method.root_cause.primary = "APPROPRIATE_ABSTENTION"
    method.root_cause.secondary = []
    method.outcome.context = {**method.outcome.context, "answered": True}
    assert any("answered case" in p for p in problems(case))


def test_edited_context_and_foreign_files_are_rejected(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    path = only_file(tmp_path)
    original = path.read_text()
    case = load_case(path)
    case.question = "A different question?"
    write(path, case)
    assert any("context_sha256 mismatch" in i for i in validate_rv1(config)["issues"])

    # Even a self-consistent rewrite cannot diverge from the committed manifest.
    from epistemic_search.rv1_schema import context_hash

    case.context_sha256 = context_hash(case)
    write(path, case)
    assert any("manifest" in i for i in validate_rv1(config)["issues"])

    path.write_text(original)
    (path.parent / "99_extra.yaml").write_text(original)
    assert any("unexpected or missing" in i for i in validate_rv1(config)["issues"])
    (path.parent / "99_extra.yaml").unlink()
    path.write_text("status: [unterminated")
    assert validate_rv1(config)["issues"]


def test_unquoted_yes_no_stay_strings_not_booleans(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    path = only_file(tmp_path)
    text = path.read_text().replace("semantically_correct: null", "semantically_correct: NO", 1)
    text = text.replace("complete: null", "complete: YES", 1)
    path.write_text(text)
    case = load_case(path)
    assert case.decomposition.judgment.semantically_correct == "NO"
    assert case.decomposition.judgment.complete == "YES"
    write(path, case)
    assert "semantically_correct: NO\n" in path.read_text()
    assert "answered: false" in path.read_text() or "answered: true" in path.read_text()


def test_exponent_like_document_ids_are_quoted_for_other_yaml_tools() -> None:
    from epistemic_search.rv1_schema import _Dumper

    text = yaml.dump({"doc": "4326252e2819", "other": "9c57dad0cb8b"}, Dumper=_Dumper)
    assert "doc: '4326252e2819'" in text and "other: 9c57dad0cb8b" in text


def test_invalid_answers_are_rejected(tmp_path: Path) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    path = only_file(tmp_path)
    path.write_text(
        path.read_text().replace("semantically_correct: null", "semantically_correct: MAYBE", 1)
    )
    with pytest.raises(ValueError, match="semantically_correct"):
        load_case(path)
    assert validate_rv1(config)["issues"]


def test_second_assessor_gets_identical_context_and_disagreements_are_reported(
    tmp_path: Path,
) -> None:
    config = setup_rv1(tmp_path)
    init_rv1(config)
    assert add_assessor(config, "second") == {"cases": 1, "assessor": "second"}
    with pytest.raises(FileExistsError):
        add_assessor(config, "second")
    with pytest.raises(ValueError):
        add_assessor(config, "Bad Id")
    first, second = load_case(only_file(tmp_path)), load_case(only_file(tmp_path, "second"))
    assert first.context_sha256 == second.context_sha256
    a, b = fill(first), fill(second)
    b.decomposition.judgment.complete = "NO"
    b.premises[0].judgment.necessary = "NO"
    write(only_file(tmp_path), a)
    write(only_file(tmp_path, "second"), b)
    summary = aggregate_rv1(config)
    assert summary["disagreements"] == 2
    pair = summary["agreement"]["primary|second"]
    assert pair["cases"] == 1 and "decomposition" in pair["sections"]
    rows = [json.loads(x) for x in (tmp_path / "res/disagreements.jsonl").read_text().splitlines()]
    assert {r["field"] for r in rows} == {"complete", "necessary"}


def test_oracle_conversion_and_kappa() -> None:
    claims = [OracleClaim(id="a", assertion="A holds."), OracleClaim(id="b", assertion="B holds.")]
    graph = oracle_graph(OracleDecomposition(required_claims=claims, logic=OracleLogic(type="AND")))
    assert graph is not None and {n.kind for n in graph.nodes} == {"CLAIM", "AND", "CONCLUSION"}
    assert oracle_graph(OracleDecomposition(required_claims=claims, logic=OracleLogic(type="OR")))
    single = OracleDecomposition(required_claims=claims[:1], logic=OracleLogic(type="NOT"))
    assert oracle_graph(single) is not None
    for bad in (
        OracleDecomposition(required_claims=claims, logic=OracleLogic(type="OTHER")),
        OracleDecomposition(required_claims=claims[:1], logic=OracleLogic(type="AND")),
        OracleDecomposition(required_claims=claims, logic=OracleLogic(type="NOT")),
        OracleDecomposition(required_claims=[OracleClaim(id="a")], logic=OracleLogic(type="AND")),
        OracleDecomposition(),
    ):
        assert oracle_graph(bad) is None
    assert kappa(["YES", "NO", "YES"], ["YES", "NO", "YES"]) == 1.0
    assert kappa(["YES", "YES"], ["YES", "YES"]) is None  # chance agreement is total
    assert kappa(["YES", "YES", "NO", "NO"], ["NO", "NO", "YES", "YES"]) == -1.0
    assert kappa(["YES", "NO", "YES", "NO"], ["YES", "NO", "NO", "YES"]) == 0.0
    assert kappa([], []) is None


def test_committed_pilot_annotation_set_is_intact() -> None:
    """The repository's own 22-question set matches its manifest and stays consistent."""
    report: dict[str, Any] = validate_rv1(Path("configs/rv1.yaml"))
    assert report["issues"] == []
    assert report["assessors"]["primary"]["cases_expected"] == 22
