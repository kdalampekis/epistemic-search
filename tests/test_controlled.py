import asyncio
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from epistemic_search.adapters import CorpusDocument, FixtureSearchProvider
from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.controlled import (
    ControlledDataset,
    ControlledExample,
    Transformation,
    TransformationPlan,
    generate_transformations,
    transform,
)
from epistemic_search.parity import compare


def base() -> ControlledExample:
    return ControlledDataset(Path("tests/fixtures/controlled_base.jsonl")).records()[0]


def plan() -> TransformationPlan:
    return TransformationPlan.model_validate(
        yaml.safe_load(Path("configs/transform_fixture.yaml").read_text())
    )


def write_plan(tmp_path: Path) -> Path:
    settings = plan()
    settings.input_path = Path("tests/fixtures/controlled_base.jsonl").resolve()
    settings.output_dir = tmp_path / "generated"
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(settings.model_dump(mode="json")))
    return path


@pytest.mark.parametrize("index,count", [(0, 1), (1, 3), (2, 3), (3, 3), (4, 4), (5, 2), (6, 4)])
def test_interventions_preserve_question_gold_group_and_provenance(index: int, count: int) -> None:
    original = base()
    before = original.model_dump_json()
    spec = plan().transformations[index]
    changed = transform(original, spec, 42)
    assert len(changed.documents) == count
    assert changed.case.question == original.case.question
    assert changed.case.gold_answer == original.case.gold_answer
    assert changed.group_id == original.group_id
    assert changed.metric_version == original.metric_version
    assert changed.case.id.startswith("v_") and spec.kind not in changed.case.id
    assert original.model_dump_json() == before
    assert changed == transform(original, spec, 42)
    metadata = changed.case.model_dump()["metadata"]["controlled"]
    assert metadata["document_order"] == [d.source.id for d in changed.documents]
    assert set(metadata["source_mapping"]) == {d.source.id for d in changed.documents}
    assert set(metadata["original_document_hashes"]) == {"institute", "district"}
    if spec.kind in {"missing_premise", "contradiction", "freshness"}:
        assert changed.case.answerable is None
    else:
        assert changed.case.answerable is True
    if spec.kind == "order":
        assert changed.documents == list(reversed(original.documents))
    if spec.kind == "repetition":
        assert all(d.text == original.documents[1].text for d in changed.documents[2:])
        assert all(d.source.uri == original.documents[1].source.uri for d in changed.documents[2:])
    if spec.additions:
        for supplied, actual in zip(
            spec.additions, changed.documents[-len(spec.additions) :], strict=True
        ):
            assert actual.text == supplied.text
            assert actual.source.uri.startswith("synthetic://")
            assert actual.source.retrieved_at == supplied.source.retrieved_at


def test_explicit_answerability_requires_independent_provenance() -> None:
    values = plan().transformations[0].model_dump()
    with pytest.raises(ValueError, match="provenance"):
        Transformation.model_validate({**values, "answerable": False})
    spec = Transformation.model_validate(
        {**values, "answerable": False, "label_provenance": "Manual fixture audit"}
    )
    assert transform(base(), spec, 42).case.answerable is False
    with pytest.raises(ValueError):
        Transformation.model_validate({**values, "answerable": "false"})


def test_invalid_targets_dates_collisions_and_noop_order_are_rejected() -> None:
    original = base()
    with pytest.raises(ValueError, match="absent"):
        transform(original, Transformation(name="bad", kind="missing_premise", targets=["x"]), 0)
    spec = plan().transformations[1]
    spec.additions[0].source.id = "district"
    with pytest.raises(ValueError, match="collide"):
        transform(original, spec, 0)
    fresh = plan().transformations[-1].model_dump(mode="json")
    for dates in [
        {"old": "2020-01-01"},
        {"old": "2020-01-01", "new": "2020-01-01"},
        {"old": "2020-01-01", "new": "2025-01-01"},
    ]:
        with pytest.raises(ValueError, match="dates"):
            Transformation.model_validate({**fresh, "evidence_dates": dates})
    original.documents = original.documents[:1]
    with pytest.raises(ValueError, match="two documents"):
        transform(original, Transformation(name="order", kind="order"), 0)
    with pytest.raises(ValueError, match="unique"):
        TransformationPlan(input_path=Path("x"), output_dir=Path("y"), transformations=[spec, spec])


def test_deterministic_generation_hashes_and_validation_before_output(tmp_path: Path) -> None:
    path = write_plan(tmp_path)
    report = generate_transformations(path)
    output = tmp_path / "generated/cases.jsonl"
    assert report["generated_examples"] == 8
    assert report["additional_api_calls"] == 0
    assert report["output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    dataset = ControlledDataset(output)
    assert len(dataset.load()) == 8
    case = dataset.load()[0]
    case.metadata.clear()
    assert dataset.load()[0].metadata["group_id"] == "fictional-route"
    documents = dataset.documents(case.id)
    documents[0].text = "mutated"
    assert dataset.documents(case.id)[0].text != "mutated"
    values = yaml.safe_load(path.read_text())
    values["output_dir"] = str(tmp_path / "second")
    path.write_text(yaml.safe_dump(values))
    generate_transformations(path)
    assert output.read_bytes() == (tmp_path / "second/cases.jsonl").read_bytes()
    with pytest.raises(FileExistsError):
        generate_transformations(path)
    values["output_dir"] = str(tmp_path / "invalid")
    values["transformations"][0]["targets"] = ["unknown"]
    path.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError, match="absent"):
        generate_transformations(path)
    assert not (tmp_path / "invalid").exists()


def test_duplicate_cases_and_mixed_graders_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    original = base()
    path.write_text(original.model_dump_json() + "\n" + original.model_dump_json())
    with pytest.raises(ValueError, match="unique"):
        ControlledDataset(path).load()
    other = original.model_copy(deep=True)
    other.case.id = "other"
    other.metric_version = "hotpotqa-answer-v1"
    path.write_text(original.model_dump_json() + "\n" + other.model_dump_json())
    with pytest.raises(ValueError, match="grading protocol"):
        ControlledDataset(path).load()


def test_order_changes_presentation_without_selection_or_usage_changes() -> None:
    documents = base().documents
    lexical = FixtureSearchProvider(documents)
    provided = FixtureSearchProvider(documents, preserve_document_order=True)
    reversed_provider = FixtureSearchProvider(
        list(reversed(documents)), preserve_document_order=True
    )
    a = asyncio.run(lexical.search("district city", 2))
    b = asyncio.run(provided.search("district city", 2))
    c = asyncio.run(reversed_provider.search("district city", 2))
    assert {r.source.id for r in a.results} == {r.source.id for r in b.results}
    assert [r.source.id for r in b.results] == list(reversed([r.source.id for r in c.results]))
    assert a.usage == b.usage == c.usage
    assert b.metadata["lexical_ranks"] == {r.source.id: r.rank for r in a.results}
    assert asyncio.run(provided.search("district city", 2)).metadata["retrieval_cache_hit"] is True


def test_cli_evaluates_all_variants_without_label_leakage(tmp_path: Path) -> None:
    path = write_plan(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["transform", str(path)])
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["transform", str(path)]).exit_code != 0
    config = load_config(Path("configs/controlled_fixture.yaml"))
    assert config.rag is not None and config.evaluation is not None
    config.rag.corpus_path = Path("tests/fixtures/corpus.json").resolve()
    config.rag.responses_path = Path("tests/fixtures/controlled_responses.json").resolve()
    config.evaluation.dataset_path = tmp_path / "generated/cases.jsonl"
    config.evaluation.output_dir = tmp_path / "evaluation"
    run_path = tmp_path / "run.yaml"
    run_path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    result = runner.invoke(app, ["evaluate", str(run_path)])
    assert result.exit_code == 0, result.output
    root = config.evaluation.output_dir
    summary = json.loads((root / "summary.json").read_text())
    assert summary["examples"] == 8 and summary["errors"] == 0
    assert summary["usage"]["api_calls"] == 0
    prompts = []
    for trace in sorted((root / "traces").glob("*.json")):
        events = json.loads(trace.read_text())["trace"]
        prompt = next(e["payload"]["request"]["prompt"] for e in events if e["type"] == "MODEL")
        assert "Hand-authored" not in prompt and "semantic_validation" not in prompt
        assert "parent_case_id" not in prompt and "gold_answer" not in prompt
        prompts.append(prompt)
    # The order variant is the sixth intervention, after the unchanged base.
    a = json.loads(prompts[0].split("Evidence:\n")[1])
    b = json.loads(prompts[6].split("Evidence:\n")[1])
    assert a == list(reversed(b))
    assert "label_provenance" in (root / "labels.jsonl").read_text()


def test_all_methods_use_controlled_documents_and_original_grader(tmp_path: Path) -> None:
    config = load_config(Path("configs/parity_fixture.yaml"))
    assert config.rag is not None and config.evaluation is not None and config.decomposition
    config.rag.corpus_path = tmp_path / "unused-nonexistent-corpus.json"
    config.rag.responses_path = Path("tests/fixtures/parity_responses.json").resolve()
    config.decomposition.cache_dir = tmp_path / "cache"
    config.evaluation.format = "controlled"
    config.evaluation.dataset_path = tmp_path / "cases.jsonl"
    config.evaluation.output_dir = tmp_path / "comparison"
    data = json.loads(Path("tests/fixtures/epistemic_benchmark.jsonl").read_text())
    documents = [
        CorpusDocument.model_validate(d)
        for d in json.loads(Path("tests/fixtures/epistemic_corpus.json").read_text())
    ]
    row = ControlledExample(
        case=data, group_id="family", documents=documents, metric_version="hotpotqa-answer-v1"
    )
    config.evaluation.dataset_path.write_text(row.model_dump_json() + "\n")
    summaries = asyncio.run(compare(config, tmp_path))
    assert len(summaries) == 5
    assert all(s.errors == 0 and s.exact_match == 1 for s in summaries.values())
    for method in summaries:
        manifest = json.loads((config.evaluation.output_dir / method / "manifest.json").read_text())
        assert manifest["metric_version"] == "hotpotqa-answer-v1"
        assert manifest["retriever"] == "lexical-overlap-v1-provided-presentation"
