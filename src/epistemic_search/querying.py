"""Deterministic, logged premise-targeted query templates."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from epistemic_search.decomposition import digest
from epistemic_search.models import AgentEvent, Claim, EvidenceItem, Schema, Text, Usage

QUERY_VERSION = "targeted-query-v1"


class QueryContext(Schema):
    query_id: Text
    original_question: Text
    target: Claim
    entities: list[Text] = Field(default_factory=list)
    temporal_scope: Text | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    conflict: bool = False
    required_stance: Literal["SUPPORTED", "CONTRADICTED"] = "SUPPORTED"


class TargetedQuery(Schema):
    text: Text
    target_claim_id: Text
    version: str = QUERY_VERSION
    event: AgentEvent


def generate_query(
    context: QueryContext, *, timestamp: datetime | None = None, resolve_conflicts: bool = True
) -> TargetedQuery:
    relevant = [item for item in context.evidence if item.claim_id == context.target.id]
    conflict = resolve_conflicts and (
        context.conflict or {e.stance for e in relevant} >= {"SUPPORT", "CONTRADICT"}
    )
    version = QUERY_VERSION if resolve_conflicts else "targeted-query-no-conflict-v1"
    parts = [context.target.text, context.original_question, *context.entities]
    if context.temporal_scope is not None:
        parts.append(context.temporal_scope)
    if conflict:
        parts.append("independent primary sources evidence for and against")
    elif relevant:
        parts.append("independent verification primary source")
    # Preserve constraints, negation and dates; only normalize duplicate whitespace/terms.
    text = " ".join(dict.fromkeys(" ".join(part.split()) for part in parts))
    payload = {
        "query": text,
        "target_claim_id": context.target.id,
        "required_stance": context.required_stance,
        "original_question": context.original_question,
        "entities": context.entities,
        "temporal_scope": context.temporal_scope,
        "evidence_ids": sorted(e.id for e in relevant),
        "conflict": conflict,
        "query_version": version,
    }
    event = AgentEvent.model_validate(
        {
            "id": "query_" + digest(payload)[:16],
            "query_id": context.query_id,
            "type": "QUERY_GENERATED",
            "component": "querying",
            "timestamp": timestamp or datetime.now(UTC),
            "usage": Usage(cost_usd=Decimal(0)),
            "payload": payload,
        }
    )
    return TargetedQuery(text=text, target_claim_id=context.target.id, version=version, event=event)
