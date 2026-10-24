"""Native benchmark ingestion; annotations never enter retrieval documents."""

import hashlib
import json
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from epistemic_search.adapters import CorpusDocument
from epistemic_search.config import EvaluationConfig
from epistemic_search.models import QueryCase, Source, Text


def benchmark_source_id(benchmark: str, split: str, case_id: str, index: str) -> str:
    return (
        "b_"
        + hashlib.sha256(json.dumps([benchmark, split, case_id, index]).encode()).hexdigest()[:24]
    )


class NativeRow(BaseModel):
    # Retain release annotations for audits, including fields not used for scoring.
    model_config = ConfigDict(extra="allow")
    question: Text


class MultiHopRow(NativeRow):
    id: Text = Field(alias="_id")
    answer: str | None = None
    answer_id: str | None = None
    context: Annotated[list[tuple[Text, list[str]]], Field(min_length=1)]


class Website(BaseModel):
    model_config = ConfigDict(extra="allow")
    index: Annotated[int, Field(strict=True, ge=1)]
    website: Text
    content: Annotated[str, Field(min_length=1)]


class Viewpoint(BaseModel):
    model_config = ConfigDict(extra="allow")
    answer: Text
    index: Annotated[list[Annotated[int, Field(strict=True, ge=1)]], Field(min_length=1)]
    reason: list[dict[str, JsonValue]] = Field(default_factory=list)


class ConfRAGRow(NativeRow):
    id: Annotated[int, Field(strict=True, ge=0)]
    websites: Annotated[list[Website], Field(min_length=1)]
    contradicts: Annotated[bool, Field(strict=True)]
    answers: Annotated[list[Viewpoint], Field(min_length=1)]


class AliasRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    Q_id: Text
    aliases: list[str]
    demonyms: list[str]


class BenchmarkDataset:
    """Provided-context retrieval, NOT full-Wikipedia/open-web retrieval.

    All native rows validate before a deterministic, label-independent subset is
    selected. Gold answers/metadata are evaluator-only; documents() returns an
    explicit allowlist of source text fields for the application boundary.
    """

    def __init__(self, settings: EvaluationConfig, base_dir: Path, seed: int = 0) -> None:
        if settings.format == "jsonl" or settings.snapshot_at is None:
            raise ValueError("Native dataset format and snapshot_at required")
        self.settings, self.base_dir, self.seed = settings, base_dir, seed
        self._cases: list[QueryCase] | None = None
        self._documents: dict[str, list[CorpusDocument]] = {}

    def load(self) -> list[QueryCase]:
        if self._cases is not None:
            return self._cases
        cfg = self.settings
        aliases: dict[str, list[str]] = {}
        if cfg.aliases_path is not None:
            # Iterate actual newline records: str.splitlines() also splits valid
            # Unicode line separators inside JSON strings (present in ConfRAG).
            with (self.base_dir / cfg.aliases_path).open(encoding="utf-8") as stream:
                for line in stream:
                    alias = AliasRow.model_validate_json(line)
                    if alias.Q_id in aliases:
                        raise ValueError(f"Duplicate alias ID: {alias.Q_id}")
                    aliases[alias.Q_id] = sorted(set(alias.aliases + alias.demonyms))
        cases: list[QueryCase] = []
        documents: dict[str, list[CorpusDocument]] = {}
        path = self.base_dir / cfg.dataset_path
        if cfg.format == "confrag":
            with path.open(encoding="utf-8") as stream:
                native: list[MultiHopRow] | list[ConfRAGRow] = [
                    ConfRAGRow.model_validate_json(line) for line in stream if line.strip()
                ]
        else:
            native = TypeAdapter(list[MultiHopRow]).validate_json(path.read_bytes())
        for row in native:
            case_id = str(row.id)
            if case_id in documents:
                raise ValueError(f"Duplicate case ID: {case_id}")
            raw = row.model_dump(mode="json", by_alias=True)
            gold: str | None = None
            refs: list[str] = []
            pool: list[tuple[str, str, str, str]] = []
            if isinstance(row, MultiHopRow):
                gold = row.answer
                refs = sorted(
                    set(([gold] if gold is not None else []) + aliases.get(row.answer_id or "", []))
                )
                for index, (title, sentences) in enumerate(row.context):
                    pool.append(
                        (
                            str(index),
                            title,
                            "https://en.wikipedia.org/wiki/" + quote(title, safe=""),
                            "".join(sentences),
                        )
                    )
                raw.pop("context")
            else:
                if len({w.index for w in row.websites}) != len(row.websites):
                    raise ValueError(f"Duplicate website index in case {case_id}")
                indices = {w.index for w in row.websites}
                if any(not set(a.index) <= indices for a in row.answers):
                    raise ValueError(f"Unknown website in answer annotation: {case_id}")
                for website in row.websites:
                    pool.append(
                        (str(website.index), website.website, website.website, website.content)
                    )
                # Preserve annotation fields, without duplicating very long pages.
                raw["websites"] = [
                    w.model_dump(mode="json", exclude={"content"}) for w in row.websites
                ]
            cases.append(
                QueryCase(
                    id=case_id,
                    question=row.question,
                    gold_answer=gold,
                    metadata={
                        "benchmark": cfg.format,
                        "split": cfg.split,
                        "annotations": raw,
                        "answer_references": refs,
                    },
                )
            )
            documents[case_id] = [
                CorpusDocument(
                    source=Source(
                        id=benchmark_source_id(cfg.format, cfg.split, case_id, index),
                        uri=uri,
                        title=title,
                        retrieved_at=cfg.snapshot_at,
                        source_type="benchmark",
                    ),
                    text=text,
                )
                for index, title, uri, text in pool
            ]
        if not cases:
            raise ValueError("Dataset is empty")
        if cfg.limit is not None:
            cases = sorted(
                cases, key=lambda c: hashlib.sha256(f"{self.seed}:{c.id}".encode()).hexdigest()
            )[: cfg.limit]
        self._documents = {c.id: documents[c.id] for c in cases}
        self._cases = cases
        return cases

    def documents(self, case_id: str) -> list[CorpusDocument]:
        self.load()
        return [d.model_copy(deep=True) for d in self._documents[case_id]]
