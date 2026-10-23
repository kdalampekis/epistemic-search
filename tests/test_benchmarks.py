import asyncio
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from epistemic_search.baseline import Answer, RunResult
from epistemic_search.benchmarks import BenchmarkDataset
from epistemic_search.config import EvaluationConfig
from epistemic_search.dataset_setup import prepare_datasets
from epistemic_search.evaluation import (
    BENCHMARK_METRICS,
    evaluate,
    multihop_f1,
    score_case,
)
from epistemic_search.models import QueryCase, Usage


def settings(tmp_path: Path, kind: str = "hotpotqa", **kwargs: object) -> EvaluationConfig:
    return EvaluationConfig.model_validate(
        dict(
            dataset_path=tmp_path / "data.json",
            output_dir=tmp_path / "out",
            dataset_name=kind,
            format=kind,
            split="dev",
            snapshot_at=datetime(2026, 10, 23, tzinfo=UTC),
            **kwargs,
        )
    )


def multihop() -> dict[str, object]:
    return {
        "_id": "q",
        "question": "Where is the town?",
        "answer": "Secret Gold",
        "answer_id": "Q1",
        "context": [
            ["Town", ["Town is here.", " Other sentence."]],
            ["Distractor", ["Unrelated content."]],
        ],
        "supporting_facts": [["Town", 0]],
        "evidences": [["secret", "gold", "triple"]],
    }


def test_native_context_allowlist_alias_scoring_and_label_isolation(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text(json.dumps([multihop()]))
    aliases = tmp_path / "aliases.json"
    aliases.write_text(
        json.dumps({"Q_id": "Q1", "aliases": ["Alternative"], "demonyms": ["Other"]})
    )
    data = BenchmarkDataset(settings(tmp_path, "2wikimultihopqa", aliases_path=aliases), tmp_path)
    cases = data.load()
    assert cases[0].metadata["answer_references"] == ["Alternative", "Other", "Secret Gold"]
    documents = data.documents("q")
    assert len(documents) == 2  # Distractors retained; no oracle supporting-fact filtering.
    assert documents[0].text == "Town is here. Other sentence."
    assert all("secret" not in d.model_dump_json().lower() for d in documents)
    assert documents[0].source.source_type == "benchmark"
    assert data.documents("q")[0].source.id == documents[0].source.id
    documents[0].text = "Mutation must not change corpus"
    assert data.documents("q")[0].text != documents[0].text

    async def runner(case: QueryCase) -> RunResult:
        assert case.gold_answer is None and case.metadata == {} and case.answerable is None
        return RunResult(
            query_id=case.id,
            status="completed",
            output=Answer(answer="Alternative", citation_ids=["s"]),
            usage=Usage(),
            wall_seconds=0,
            trace=[],
        )

    summary = asyncio.run(
        evaluate(
            data, runner, tmp_path / "out", {"metric_version": BENCHMARK_METRICS["2wikimultihopqa"]}
        )
    )
    assert summary.exact_match == summary.token_f1 == 1
    assert summary.metric_version == "2wiki-answer-aliases-v1.1"
    assert "Secret Gold" in (tmp_path / "out/labels.jsonl").read_text()
    assert "Secret Gold" not in (tmp_path / "out/traces/000000.json").read_text()


def test_confrag_unicode_annotations_are_not_truth_or_context(tmp_path: Path) -> None:
    row = {
        "id": 12,
        "question": "Are the reports consistent?",
        "contradicts": True,
        "websites": [
            {
                "index": 1,
                "website": "https://example.org/one",
                "content": "Raw\u2028page text",
                "answer": "SECRET_WEBSITE_LABEL",
                "trust_score": 7,
                "reason": ["SECRET_REASON"],
            }
        ],
        "answers": [{"answer": "SECRET_CLUSTER", "index": [1]}],
    }
    (tmp_path / "data.json").write_text(json.dumps(row, ensure_ascii=False) + "\n")
    data = BenchmarkDataset(settings(tmp_path, "confrag"), tmp_path)
    case = data.load()[0]
    assert case.gold_answer is None and case.answerable is None
    assert "SECRET_CLUSTER" in case.model_dump_json()
    assert data.documents("12")[0].text == "Raw\u2028page text"
    assert "SECRET" not in data.documents("12")[0].model_dump_json()
    result = RunResult(
        query_id="12",
        status="completed",
        output=Answer(answer="Some answer", citation_ids=["s"]),
        usage=Usage(),
        wall_seconds=0,
        trace=[],
    )
    scored = score_case(case, result, "trace", BENCHMARK_METRICS["confrag"])
    assert scored.answered and not scored.labelled
    assert scored.exact_match is scored.token_f1 is None


@pytest.mark.parametrize(
    "pred,gold,f1",
    [
        ("yes indeed", "yes", 0),
        ("no", "no way", 0),
        ("noanswer", "noanswer!", 1),
        ("", "", 0),
        ("red red blue", "red blue blue", 2 / 3),
    ],
)
def test_multihop_official_answer_edge_cases(pred: str, gold: str, f1: float) -> None:
    assert multihop_f1(pred, gold) == pytest.approx(f1)


def test_selection_is_seeded_and_order_independent_and_validates_all_rows(tmp_path: Path) -> None:
    rows = [{**multihop(), "_id": str(i)} for i in range(10)]
    path = tmp_path / "data.json"
    path.write_text(json.dumps(rows))
    cfg = settings(tmp_path, limit=3)
    first = [c.id for c in BenchmarkDataset(cfg, tmp_path, seed=7).load()]
    path.write_text(json.dumps(rows[::-1]))
    assert [c.id for c in BenchmarkDataset(cfg, tmp_path, seed=7).load()] == first
    assert [c.id for c in BenchmarkDataset(cfg, tmp_path, seed=8).load()] != first
    rows[-1]["context"] = "invalid outside sample"
    path.write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        BenchmarkDataset(cfg, tmp_path, seed=7).load()


@pytest.mark.parametrize("rows", [[], [multihop(), multihop()], [{**multihop(), "context": []}]])
def test_invalid_native_files_fail_before_run(tmp_path: Path, rows: object) -> None:
    (tmp_path / "data.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        BenchmarkDataset(settings(tmp_path), tmp_path).load()


def test_unlabelled_multihop_test_rows_remain_unlabelled(tmp_path: Path) -> None:
    row = multihop()
    del row["answer"]
    (tmp_path / "data.json").write_text(json.dumps([row]))
    assert BenchmarkDataset(settings(tmp_path), tmp_path).load()[0].gold_answer is None


def test_download_checksums_mock_transport_and_safe_zip_selection(tmp_path: Path) -> None:
    member = b'[{"example":1}]'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("dev.json", member)
        archive.writestr("../unsafe", b"not extracted")
    payload = buffer.getvalue()
    release = {
        "name": "data.zip",
        "url": "https://example.org/data.zip",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "license_note": "Synthetic test",
        "archive_members": {"dev.json": hashlib.sha256(member).hexdigest()},
    }
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"files": [release]}))
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=payload))
    ) as client:
        hashes = prepare_datasets(lock, tmp_path / "download", client)
        assert hashes["dev.json"] == hashlib.sha256(member).hexdigest()
        assert not (tmp_path / "unsafe").exists()
        assert (tmp_path / "download/setup-manifest.json").exists()
        with pytest.raises(FileExistsError):
            prepare_datasets(lock, tmp_path / "download", client)
        release["sha256"] = "0" * 64
        lock.write_text(json.dumps({"files": [release]}))
        with pytest.raises(ValueError, match="Checksum"):
            prepare_datasets(lock, tmp_path / "bad", client)
        assert not (tmp_path / "bad/data.zip").exists()
        assert not (tmp_path / "bad/setup-manifest.json").exists()
        assert not list((tmp_path / "bad").glob("*.part"))
    release["name"] = "../escape"
    lock.write_text(json.dumps({"files": [release]}))
    with httpx.Client() as client, pytest.raises(ValueError):
        prepare_datasets(lock, tmp_path / "never-created", client)
    assert not (tmp_path / "never-created").exists()


def test_hotpot_parquet_conversion_preserves_fields(tmp_path: Path) -> None:
    arrow = pytest.importorskip("pyarrow")
    parquet = pytest.importorskip("pyarrow.parquet")
    from epistemic_search.dataset_setup import hotpot_from_parquet

    row = {
        "id": "q",
        "question": "Q?",
        "answer": "gold",
        "level": "hard",
        "context": {"title": ["T"], "sentences": [["Sentence one.", " Sentence two."]]},
        "supporting_facts": {"title": ["T"], "sent_id": [0]},
    }
    source = tmp_path / "source.parquet"
    target = tmp_path / "converted.json"
    parquet.write_table(arrow.Table.from_pylist([row]), source)
    hotpot_from_parquet(source, target)
    result = json.loads(target.read_text())[0]
    assert result["_id"] == row["id"] and "id" not in result
    assert result["context"] == [["T", ["Sentence one.", " Sentence two."]]]
    assert result["supporting_facts"] == [["T", 0]]
    assert result["answer"] == "gold" and result["level"] == "hard"
    with pytest.raises(FileExistsError):
        hotpot_from_parquet(source, target)
