"""Declared, deterministic evidence interventions; labels stay evaluator-only."""

import hashlib
import json
import random
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Field, StrictBool, model_validator

from epistemic_search.adapters import CorpusDocument
from epistemic_search.models import Count, QueryCase, Schema, Text

Metric = Literal[
    "english-em-token-f1-v1",
    "hotpotqa-answer-v1",
    "2wiki-answer-aliases-v1.1",
    "confrag-ingestion-only-v1",
]
Kind = Literal[
    "missing_premise",
    "contradiction",
    "irrelevant",
    "redundant",
    "repetition",
    "order",
    "freshness",
]


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class ControlledExample(Schema):
    case: QueryCase
    group_id: Text
    metric_version: Metric = "english-em-token-f1-v1"
    documents: list[CorpusDocument]

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        if len({d.source.id for d in self.documents}) != len(self.documents):
            raise ValueError("Controlled document IDs must be unique per example")
        return self


class ControlledDataset:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._rows: dict[str, ControlledExample] | None = None

    def records(self) -> list[ControlledExample]:
        if self._rows is None:
            rows = [
                ControlledExample.model_validate_json(line)
                for line in self.path.read_text().split("\n")
                if line.strip()
            ]
            if not rows or len({r.case.id for r in rows}) != len(rows):
                raise ValueError("Controlled dataset needs nonempty unique case IDs")
            if len({r.metric_version for r in rows}) != 1:
                raise ValueError("Controlled dataset must retain one shared base grading protocol")
            self._rows = {r.case.id: r for r in rows}
        return [r.model_copy(deep=True) for r in self._rows.values()]

    @property
    def metric_version(self) -> str:
        return self.records()[0].metric_version

    def load(self) -> list[QueryCase]:
        cases = []
        for row in self.records():
            case = row.case
            case.metadata["group_id"] = row.group_id
            cases.append(case)
        return cases

    def documents(self, case_id: str) -> list[CorpusDocument]:
        self.records()
        assert self._rows is not None
        return [d.model_copy(deep=True) for d in self._rows[case_id].documents]


class Transformation(Schema):
    name: Text
    kind: Kind
    targets: list[Text] = Field(default_factory=list)
    additions: list[CorpusDocument] = Field(default_factory=list)
    copies: Annotated[int, Field(strict=True, ge=1, le=20)] = 1
    evidence_dates: dict[Text, date] = Field(default_factory=dict)
    answerable: StrictBool | None = None
    label_provenance: Text | None = None

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("Duplicate transformation targets")
        requires_targets = self.kind in {
            "missing_premise",
            "contradiction",
            "redundant",
            "repetition",
        }
        if requires_targets != bool(self.targets):
            raise ValueError("Target sources are required only for targeted interventions")
        requires_additions = self.kind in {"contradiction", "irrelevant", "redundant", "freshness"}
        if requires_additions != bool(self.additions):
            raise ValueError("This intervention has missing or inapplicable supplied documents")
        if len({d.source.id for d in self.additions}) != len(self.additions):
            raise ValueError("Supplied document IDs must be unique")
        if self.kind != "repetition" and self.copies != 1:
            raise ValueError("copies applies only to repetition")
        if self.kind == "freshness":
            if (
                set(self.evidence_dates) != {d.source.id for d in self.additions}
                or len(set(self.evidence_dates.values())) < 2
            ):
                raise ValueError("Freshness needs at least two distinct evidence dates")
            if any(
                self.evidence_dates[d.source.id].isoformat() not in d.text for d in self.additions
            ):
                raise ValueError("Evidence dates must occur explicitly in supplied context")
        elif self.evidence_dates:
            raise ValueError("Evidence dates apply only to freshness interventions")
        if (self.answerable is not None) != (self.label_provenance is not None):
            raise ValueError("An answerability override requires its independent label provenance")
        return self


class TransformationPlan(Schema):
    input_path: Path
    output_dir: Path
    seed: Count = 0
    transformations: Annotated[list[Transformation], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        if len({t.name for t in self.transformations}) != len(self.transformations):
            raise ValueError("Transformation names must be unique")
        return self


def transform(base: ControlledExample, spec: Transformation, seed: int) -> ControlledExample:
    base = ControlledExample.model_validate(base.model_dump())
    spec = Transformation.model_validate(spec.model_dump())
    sources = {d.source.id: d for d in base.documents}
    if set(spec.targets) - sources.keys():
        raise ValueError("Transformation references absent source IDs")
    if sources.keys() & {d.source.id for d in spec.additions}:
        raise ValueError("Supplied source IDs collide with original sources")
    variant = base.model_copy(deep=True)
    variant.case.id = "v_" + fingerprint([base.case.id, spec.model_dump(mode="json"), seed])[:24]
    mapping = {d.source.id: d.source.id for d in variant.documents}
    if spec.kind == "missing_premise":
        variant.documents = [d for d in variant.documents if d.source.id not in spec.targets]
    elif spec.kind == "repetition":
        for source_id in spec.targets:
            for copy in range(spec.copies):
                document = sources[source_id].model_copy(deep=True)
                document.source.id = "t_" + fingerprint([variant.case.id, source_id, copy])[:24]
                mapping[document.source.id] = source_id
                variant.documents.append(document)
    elif spec.kind == "order":
        if len(variant.documents) < 2:
            raise ValueError("Order manipulation needs at least two documents")
        random.Random(f"{seed}:{base.case.id}:{spec.name}").shuffle(variant.documents)
        if [d.source.id for d in variant.documents] == [d.source.id for d in base.documents]:
            variant.documents.reverse()
    for index, supplied in enumerate(spec.additions):
        document = supplied.model_copy(deep=True)
        document.source.id = "t_" + fingerprint([variant.case.id, supplied.source.id, index])[:24]
        # Synthetic additions must never be attributed to a real source URL.
        document.source.uri = "synthetic://" + document.source.id
        mapping[document.source.id] = supplied.source.id
        variant.documents.append(document)
    if spec.kind in {"missing_premise", "contradiction", "freshness"}:
        variant.case.answerable = (
            None  # No inference from deletion/contradiction to unanswerability.
        )
    if spec.answerable is not None:
        variant.case.answerable = spec.answerable
    variant.case.metadata["controlled"] = {
        "protocol": "declared-evidence-intervention-v1",
        "parent_case_id": base.case.id,
        "group_id": base.group_id,
        "seed": seed,
        "spec": spec.model_dump(mode="json", exclude={"additions"}),
        "supplied_document_hashes": {
            d.source.id: fingerprint(d.model_dump(mode="json")) for d in spec.additions
        },
        "original_document_hashes": {
            d.source.id: fingerprint(d.model_dump(mode="json")) for d in base.documents
        },
        "source_mapping": {d.source.id: mapping[d.source.id] for d in variant.documents},
        "document_order": [d.source.id for d in variant.documents],
        "semantic_validation": "author-declared intervention; not inferred by string editing",
    }
    return ControlledExample.model_validate(variant.model_dump())


def generate_transformations(config_path: Path) -> dict[str, object]:
    plan = TransformationPlan.model_validate(yaml.safe_load(config_path.read_text()))
    input_path = config_path.parent / plan.input_path
    bases = ControlledDataset(input_path).records()
    rows = []
    for base in bases:
        rows.append(base)
        rows.extend(transform(base, spec, plan.seed) for spec in plan.transformations)
    if len({r.case.id for r in rows}) != len(rows):
        raise ValueError("Generated case IDs collide")
    encoded = "".join(row.model_dump_json() + "\n" for row in rows)
    report = {
        "protocol": "declared-evidence-intervention-v1",
        "seed": plan.seed,
        "base_examples": len(bases),
        "generated_examples": len(rows),
        "metric_version": bases[0].metric_version,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "additional_api_calls": 0,
        "additional_api_cost_usd": "0",
    }
    output = config_path.parent / plan.output_dir
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases.jsonl").write_text(encoded, encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
