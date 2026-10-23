import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from epistemic_search.models import (
    AgentEvent,
    BeliefStatus,
    BudgetLimits,
    BudgetState,
    Claim,
    ClaimBelief,
    Decision,
    EpistemicState,
    EvidenceItem,
    EvidenceProvenance,
    ProofNode,
    QueryCase,
    Source,
    Usage,
)


def test_all_core_schemas_round_trip(source: Source, event: AgentEvent) -> None:
    claim = Claim(id="c1", text="A premise")
    node = ProofNode(id="n1", kind="CLAIM", claim_id=claim.id)
    evidence = EvidenceItem(
        id="e1",
        claim_id=claim.id,
        source=source,
        span="  Exact evidence span.\n",
        stance="SUPPORT",
        stance_score=0.8,
        provenance=EvidenceProvenance(
            search_query="query", rank=1, extraction_model="fixture", prompt_version="v1"
        ),
    )
    belief = ClaimBelief(claim_id=claim.id, evidence_ids=[evidence.id])
    budget = BudgetState(limits=BudgetLimits(max_cost_usd=Decimal("0.10")), used=event.usage)
    state = EpistemicState(
        query_id="q1",
        claims=[claim],
        proof_graph=[node],
        evidence=[evidence],
        beliefs=[belief],
        budget=budget,
        trace=[event],
    )
    models: list[BaseModel] = [
        QueryCase(id="q1", question="Question?"),
        claim,
        node,
        evidence,
        belief,
        budget,
        Decision(action="ABSTAIN", rationale="Missing evidence"),
        event,
        state,
    ]
    for model in models:
        encoded = model.model_dump_json()
        assert type(model).model_validate_json(encoded) == model
        assert isinstance(json.loads(encoded), dict)
    restored = EpistemicState.model_validate_json(state.model_dump_json())
    assert restored.evidence[0].span == "  Exact evidence span.\n"
    assert restored.evidence[0].source.uri == source.uri
    assert restored.evidence[0].provenance.prompt_version == "v1"


def test_unknown_is_explicit_and_not_false() -> None:
    belief = ClaimBelief(claim_id="c1")
    assert belief.status is BeliefStatus.UNKNOWN
    assert belief.uncertainty == 1
    assert not belief.calibrated
    for status in (False, "FALSE"):
        with pytest.raises(ValidationError):
            ClaimBelief.model_validate({"claim_id": "c1", "status": status})


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan"), float("inf")])
def test_reject_invalid_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        Claim(id="c1", text="claim", importance=score)


@pytest.mark.parametrize(
    "field,value",
    [
        ("prompt_tokens", -1),
        ("search_calls", 1.5),
        ("model_calls", True),
        ("cost_usd", "-0.01"),
        ("cost_usd", "NaN"),
        ("latency_seconds", float("inf")),
    ],
)
def test_reject_invalid_usage(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Usage.model_validate({field: value})


def test_reject_unknown_fields_blank_ids_and_missing_provenance() -> None:
    for data in (
        {"id": " ", "question": "Question?"},
        {"id": "q1", "question": "Question?", "typo": 1},
    ):
        with pytest.raises(ValidationError):
            QueryCase.model_validate(data)
    with pytest.raises(ValidationError):
        EvidenceItem.model_validate(
            {
                "id": "e1",
                "claim_id": "c1",
                "span": "evidence",
                "stance": "SUPPORT",
                "stance_score": 1,
            }
        )


def test_timestamp_requires_timezone(source: Source) -> None:
    data = source.model_dump()
    data["retrieved_at"] = "2026-10-23T00:00:00"
    with pytest.raises(ValidationError):
        Source.model_validate(data)


def test_defaults_are_independent_and_assignment_validates() -> None:
    first = EpistemicState(query_id="q1")
    second = EpistemicState(query_id="q2")
    first.blockers.append("c1")
    assert second.blockers == []
    assert second.budget.used.cost_usd == Decimal(0)
    with pytest.raises(ValidationError):
        first.budget.used.prompt_tokens = -1
    assert BudgetLimits(max_search_calls=0).max_search_calls == 0
    assert BudgetLimits().max_search_calls is None
