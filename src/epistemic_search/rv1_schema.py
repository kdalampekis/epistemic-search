"""RV1 human-annotation contracts. Judgments are human-only and never inferred."""

import datetime
import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import Field, JsonValue, ValidationError

from epistemic_search.decomposition import DraftNode, ProofGraph, canonicalize
from epistemic_search.models import Claim, ProofNode, Schema, Text

SCHEMA: Literal["rv1-case-v1"] = "rv1-case-v1"
PROTOCOL = "rv1-human-annotation-v1"
Tri = Literal["YES", "NO", "UNSURE"]
TriNA = Literal["YES", "NO", "UNSURE", "NOT_APPLICABLE"]
GoldStance = Literal["SUPPORT", "CONTRADICT", "NEUTRAL", "UNSURE"]
Status = Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETE"]
LogicType = Literal["AND", "OR", "NOT", "OTHER"]
BetterAction = Literal["SEARCH_MORE", "RESOLVE_CONFLICT", "ANSWER", "ABSTAIN", "OTHER", "NONE"]
RootCauseLabel = Literal[
    "DECOMPOSITION_ERROR",
    "RETRIEVAL_ERROR",
    "QUERY_GENERATION_ERROR",
    "EVIDENCE_EXTRACTION_ERROR",
    "STANCE_ERROR",
    "BELIEF_AGGREGATION_ERROR",
    "FORMALIZATION_ERROR",
    "CONTROLLER_ERROR",
    "ANSWER_GENERATION_ERROR",
    "APPROPRIATE_ABSTENTION",
    "MULTIPLE_FAILURES",
    "NO_IDENTIFIED_FAILURE",
    "UNCERTAIN",
]
NO_SECONDARY = {"APPROPRIATE_ABSTENTION", "NO_IDENTIFIED_FAILURE", "UNCERTAIN"}
Context = dict[str, JsonValue]


class Judgment(Schema):
    """Every field is None until a human answers. Blank is never read as NO."""

    optional: ClassVar[frozenset[str]] = frozenset({"notes"})
    notes: str | None = None

    def blanks(self) -> list[str]:
        return [
            name
            for name in type(self).model_fields
            if name not in self.optional and getattr(self, name) is None
        ]


class DecompositionJudgment(Judgment):
    semantically_correct: Tri | None = None
    complete: Tri | None = None
    has_unnecessary_premises: Tri | None = None
    has_missing_required_premises: Tri | None = None
    dependency_structure_matches: Tri | None = None


class PremiseJudgment(Judgment):
    is_assertion: Tri | None = None
    necessary: Tri | None = None
    relevant: Tri | None = None
    atomic: Tri | None = None
    well_formed: Tri | None = None
    correct: TriNA | None = None


class RoundJudgment(Judgment):
    target_premise_appropriate: TriNA | None = None
    query_appropriate_for_target: Tri | None = None
    query_materially_different_from_previous: TriNA | None = None
    retrieved_docs_contained_needed_info: Tri | None = None
    retrieved_set_contained_gold_supporting_evidence: TriNA | None = None
    missing_info_retrievable_from_corpus: TriNA | None = None


class ItemJudgment(Judgment):
    addresses_assigned_premise: Tri | None = None
    gold_stance: GoldStance | None = None
    span_sufficient_alone: TriNA | None = None
    span_meaning_faithful: TriNA | None = None


class BatchJudgment(Judgment):
    decisive_evidence_present_in_document: Tri | None = None
    decisive_evidence_missed_by_extraction: TriNA | None = None


class BeliefJudgment(Judgment):
    optional: ClassVar[frozenset[str]] = frozenset({"notes", "missing_blockers_description"})
    claim_status_justified: Tri | None = None
    unjustified_premise_labels: list[str] = Field(default_factory=list)
    blockers_genuinely_blocking: TriNA | None = None
    more_important_blockers_missing: Tri | None = None
    missing_blockers_description: str | None = None
    formal_conclusion_appropriate: Tri | None = None


class DecisionJudgment(Judgment):
    target_premise_appropriate: TriNA | None = None
    action_appropriate: Tri | None = None
    repeat_justified: TriNA | None = None
    better_action: BetterAction | None = None


class OutcomeJudgment(Judgment):
    answer_correct: TriNA | None = None
    abstention_appropriate: TriNA | None = None


class RootCauseJudgment(Judgment):
    optional: ClassVar[frozenset[str]] = frozenset({"notes", "secondary"})
    primary: RootCauseLabel | None = None
    secondary: list[RootCauseLabel] = Field(default_factory=list)
    rationale: str | None = None


class OracleClaim(Schema):
    id: Text
    assertion: str | None = None


class OracleLogic(Schema):
    type: LogicType | None = None
    description: str | None = None


class OracleDecomposition(Judgment):
    """Human-authored decomposition, written before viewing the generated one."""

    authored_before_viewing_generated: Tri | None = None
    required_claims: list[OracleClaim] = Field(default_factory=list)
    logic: OracleLogic = Field(default_factory=OracleLogic)


class Unit(Schema):
    id: Text
    context: Context


class PremiseUnit(Unit):
    judgment: PremiseJudgment = Field(default_factory=PremiseJudgment)


class RoundUnit(Unit):
    judgment: RoundJudgment = Field(default_factory=RoundJudgment)


class ItemUnit(Unit):
    judgment: ItemJudgment = Field(default_factory=ItemJudgment)


class BatchUnit(Unit):
    judgment: BatchJudgment = Field(default_factory=BatchJudgment)
    items: list[ItemUnit] = Field(default_factory=list)


class BeliefUnit(Unit):
    judgment: BeliefJudgment = Field(default_factory=BeliefJudgment)


class DecisionUnit(Unit):
    judgment: DecisionJudgment = Field(default_factory=DecisionJudgment)


class OutcomeUnit(Schema):
    context: Context
    judgment: OutcomeJudgment = Field(default_factory=OutcomeJudgment)


class DecompositionUnit(Schema):
    context: Context
    judgment: DecompositionJudgment = Field(default_factory=DecompositionJudgment)


class MethodSection(Schema):
    run: Text
    trace_sha256: Text
    outcome: OutcomeUnit
    retrieval_rounds: list[RoundUnit]
    extraction_batches: list[BatchUnit] = Field(default_factory=list)
    belief_states: list[BeliefUnit] = Field(default_factory=list)
    controller_decisions: list[DecisionUnit]
    root_cause: RootCauseJudgment = Field(default_factory=RootCauseJudgment)


class CaseFile(Schema):
    schema_version: Literal["rv1-case-v1"] = SCHEMA
    case_id: Text
    order: int = Field(strict=True, ge=1)
    dataset: Text
    query_id: Text
    assessor: Text | None = None
    date: datetime.date | None = None
    status: Status = "NOT_STARTED"
    context_sha256: str
    question: Text
    gold: Context
    oracle: OracleDecomposition = Field(default_factory=OracleDecomposition)
    decomposition: DecompositionUnit
    premises: list[PremiseUnit]
    methods: dict[str, MethodSection]


def context_view(case: CaseFile) -> dict[str, Any]:
    """Everything the generator wrote and a human must not edit."""
    methods: dict[str, Any] = {}
    for name, m in sorted(case.methods.items()):
        methods[name] = {
            "run": m.run,
            "trace_sha256": m.trace_sha256,
            "outcome": m.outcome.context,
            "rounds": [(u.id, u.context) for u in m.retrieval_rounds],
            "batches": [
                (b.id, b.context, [(i.id, i.context) for i in b.items])
                for b in m.extraction_batches
            ],
            "belief_states": [(u.id, u.context) for u in m.belief_states],
            "decisions": [(u.id, u.context) for u in m.controller_decisions],
        }
    return {
        "case_id": case.case_id,
        "order": case.order,
        "dataset": case.dataset,
        "query_id": case.query_id,
        "question": case.question,
        "gold": case.gold,
        "decomposition": case.decomposition.context,
        "premises": [(p.id, p.context) for p in case.premises],
        "methods": methods,
    }


def context_hash(case: CaseFile) -> str:
    canonical = json.dumps(context_view(case), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


class _Loader(yaml.SafeLoader):
    """YAML 1.2-style booleans: only true/false, so an unquoted NO stays the string NO."""


class _Dumper(yaml.SafeDumper):
    pass


_BOOL = "tag:yaml.org,2002:bool"
for _cls in (_Loader, _Dumper):
    _cls.yaml_implicit_resolvers = {
        key: [(tag, regex) for tag, regex in value if tag != _BOOL]
        for key, value in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    _cls.add_implicit_resolver(_BOOL, re.compile(r"^(?:true|false)$"), list("tf"))


def load_case(path: Path) -> CaseFile:
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506
        return CaseFile.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"{path}: {exc}") from exc


def notes_last(value: Any) -> Any:
    """Keep free-text notes after the fields a person must answer."""
    if isinstance(value, dict):
        ordered = {k: notes_last(v) for k, v in value.items() if k != "notes"}
        return {**ordered, "notes": notes_last(value["notes"])} if "notes" in value else ordered
    if isinstance(value, list):
        return [notes_last(v) for v in value]
    return value


def dump_case(case: CaseFile, header: str) -> str:
    body = yaml.dump(
        notes_last(case.model_dump(mode="json")),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    return "".join(f"# {line}\n" if line else "#\n" for line in header.splitlines()) + body


def judgments(case: CaseFile) -> Iterator[tuple[str, str, Judgment]]:
    """(path, section, judgment) for every human field group, in a stable order."""
    yield "oracle", "oracle", case.oracle
    yield "decomposition", "decomposition", case.decomposition.judgment
    for p in case.premises:
        yield f"premises[{p.id}]", "premise", p.judgment
    for name, m in sorted(case.methods.items()):
        base = f"methods.{name}"
        yield f"{base}.outcome", "outcome", m.outcome.judgment
        for r in m.retrieval_rounds:
            yield f"{base}.rounds[{r.id}]", "retrieval_round", r.judgment
        for b in m.extraction_batches:
            yield f"{base}.batches[{b.id}]", "extraction_batch", b.judgment
            for i in b.items:
                yield f"{base}.items[{i.id}]", "evidence_item", i.judgment
        for u in m.belief_states:
            yield f"{base}.belief[{u.id}]", "belief_state", u.judgment
        for d in m.controller_decisions:
            yield f"{base}.decisions[{d.id}]", "controller_decision", d.judgment
        yield f"{base}.root_cause", "root_cause", m.root_cause


def blank_fields(case: CaseFile) -> list[str]:
    blanks = [f"{path}.{name}" for path, _, j in judgments(case) for name in j.blanks()]
    oracle = case.oracle
    if not oracle.required_claims:
        blanks.append("oracle.required_claims")
    blanks += [
        f"oracle.required_claims[{c.id}].assertion"
        for c in oracle.required_claims
        if not (c.assertion or "").strip()
    ]
    if oracle.logic.type is None:
        blanks.append("oracle.logic.type")
    return blanks


def problems(case: CaseFile) -> list[str]:
    """Consistency of answers already given; applies to partial files too."""
    found: list[str] = []
    labels = {p.context["label"] for p in case.premises}
    ids = [c.id for c in case.oracle.required_claims]
    if len(set(ids)) != len(ids):
        found.append("oracle: duplicate required-claim ids")
    logic = case.oracle.logic
    if logic.type == "OTHER" and not (logic.description or "").strip():
        found.append("oracle.logic: type OTHER needs a description")
    if logic.type == "NOT" and len(ids) != 1:
        found.append("oracle.logic: NOT applies to exactly one required claim")
    if logic.type in {"AND", "OR"} and len(ids) == 1:
        found.append("oracle.logic: AND/OR needs at least two required claims")
    for name, m in sorted(case.methods.items()):
        base = f"methods.{name}"
        rc = m.root_cause
        if rc.primary in rc.secondary or len(set(rc.secondary)) != len(rc.secondary):
            found.append(f"{base}.root_cause: primary/secondary labels must be distinct")
        if rc.primary in NO_SECONDARY and rc.secondary:
            found.append(f"{base}.root_cause: {rc.primary} cannot have secondary labels")
        if rc.primary == "MULTIPLE_FAILURES" and len(rc.secondary) < 2:
            found.append(f"{base}.root_cause: MULTIPLE_FAILURES needs two or more secondary labels")
        if rc.primary == "APPROPRIATE_ABSTENTION" and m.outcome.context.get("answered"):
            found.append(f"{base}.root_cause: APPROPRIATE_ABSTENTION on an answered case")
        out = m.outcome
        answered = bool(out.context.get("answered"))
        if out.judgment.answer_correct == "NOT_APPLICABLE" and answered:
            found.append(f"{base}.outcome: answer_correct cannot be NOT_APPLICABLE for an answer")
        if out.judgment.abstention_appropriate == "NOT_APPLICABLE" and not answered:
            found.append(f"{base}.outcome: abstention_appropriate needed for a non-answer")
        for r in m.retrieval_rounds:
            first = r.context.get("round") == 1
            v = r.judgment.query_materially_different_from_previous
            if v is not None and (v == "NOT_APPLICABLE") != first:
                found.append(
                    f"{base}.rounds[{r.id}]: query_materially_different applies from round 2"
                )
        for b in m.extraction_batches:
            j = b.judgment
            if j.decisive_evidence_present_in_document == "NO" and (
                j.decisive_evidence_missed_by_extraction not in {None, "NOT_APPLICABLE"}
            ):
                found.append(f"{base}.batches[{b.id}]: nothing decisive to miss")
        for u in m.belief_states:
            if (
                u.judgment.claim_status_justified == "NO"
                and not u.judgment.unjustified_premise_labels
            ):
                found.append(f"{base}.belief[{u.id}]: name the unjustified premise labels")
            if not set(u.judgment.unjustified_premise_labels) <= labels:
                found.append(f"{base}.belief[{u.id}]: unknown premise label")
        for d in m.controller_decisions:
            repeats = d.context.get("next_query_exact_repeat_of_earlier")
            if repeats and d.judgment.repeat_justified == "NOT_APPLICABLE":
                found.append(
                    f"{base}.decisions[{d.id}]: repeat_justified needed for a repeated query"
                )
    return found


def check(case: CaseFile) -> dict[str, Any]:
    """Structural completeness. COMPLETE is valid only when nothing is blank or inconsistent."""
    blanks = blank_fields(case)
    issues = problems(case)
    if context_hash(case) != case.context_sha256:
        issues.append("read-only context was modified (context_sha256 mismatch)")
    if case.status == "COMPLETE":
        issues += [f"COMPLETE but blank: {b}" for b in blanks]
        if not (case.assessor or "").strip():
            issues.append("COMPLETE needs an assessor")
        if case.date is None:
            issues.append("COMPLETE needs a date")
    return {"blank": len(blanks), "issues": issues, "blank_fields": blanks}


def oracle_graph(oracle: OracleDecomposition) -> ProofGraph | None:
    """Convertible oracles become the same ProofGraph type the pipeline consumes."""
    given = oracle.required_claims
    kind = oracle.logic.type
    if not given or kind in {None, "OTHER"} or any(not (c.assertion or "").strip() for c in given):
        return None
    if (kind == "NOT" and len(given) != 1) or (kind != "NOT" and len(given) < 2):
        return None
    leaves = [DraftNode(id=f"leaf_{c.id}", kind="CLAIM", children=[], claim_id=c.id) for c in given]
    operator = DraftNode(id="op", kind=str(kind), children=[n.id for n in leaves], claim_id=None)
    root = DraftNode(id="root", kind="CONCLUSION", children=["op"], claim_id=None)
    graph = ProofGraph(
        claims=[Claim(id=c.id, text=(c.assertion or "").strip()) for c in given],
        nodes=[ProofNode.model_validate(n.model_dump()) for n in [*leaves, operator, root]],
        conclusion_id="root",
    )
    return canonicalize(graph)
