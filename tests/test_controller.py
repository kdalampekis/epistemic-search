from decimal import Decimal

import pytest

from epistemic_search.controller import choose_action
from epistemic_search.decomposition import ProofGraph
from epistemic_search.models import (
    BeliefStatus,
    BudgetLimits,
    BudgetState,
    Claim,
    ClaimBelief,
    ProofNode,
    Usage,
)


def graph() -> ProofGraph:
    return ProofGraph(
        claims=[Claim(id="a", text="A"), Claim(id="b", text="B", importance=0.5)],
        nodes=[
            ProofNode(id="a", kind="CLAIM", claim_id="a"),
            ProofNode(id="b", kind="CLAIM", claim_id="b"),
            ProofNode(id="and", kind="AND", children=["a", "b"]),
            ProofNode(id="root", kind="CONCLUSION", children=["and"]),
        ],
        conclusion_id="root",
    )


def test_only_unresolved_claim_is_searched() -> None:
    decision, result = choose_action(
        graph(), [ClaimBelief(claim_id="a", status=BeliefStatus.SUPPORTED)], BudgetState()
    )
    assert decision.action == "SEARCH_MORE" and decision.target_claim_id == "b"
    assert decision.blocking_claims == ["b"]
    assert result.required_stances == {"b": "SUPPORTED"}


@pytest.mark.parametrize("state", [BeliefStatus.MIXED, BeliefStatus.CONTRADICTED])
def test_conflict_resolution_precedes_missing_claim(state: BeliefStatus) -> None:
    decision, _ = choose_action(graph(), [ClaimBelief(claim_id="b", status=state)], BudgetState())
    assert decision.action == "RESOLVE_CONFLICT" and decision.target_claim_id == "b"


@pytest.mark.parametrize(
    "field",
    [
        "max_search_calls",
        "max_documents",
        "max_retrieved_tokens",
        "max_llm_calls",
        "max_total_llm_input_tokens",
        "max_total_llm_output_tokens",
        "max_latency_seconds",
    ],
)
def test_zero_budget_abstains_with_blockers(field: str) -> None:
    budget = BudgetState(limits=BudgetLimits.model_validate({field: 0}))
    decision, _ = choose_action(graph(), [], budget)
    assert decision.action == "ABSTAIN" and decision.blocking_claims == ["a", "b"]


def test_actual_plus_reserved_budget_and_unknown_cost() -> None:
    budget = BudgetState(limits=BudgetLimits(max_search_calls=2), used=Usage(search_calls=1))
    decision, _ = choose_action(graph(), [], budget, expected_acquisition=Usage(search_calls=2))
    assert decision.action == "ABSTAIN"
    budget = BudgetState(limits=BudgetLimits(max_cost_usd=Decimal("1")))
    assert choose_action(graph(), [], budget)[0].action == "ABSTAIN"
    free = Usage(search_calls=1, cost_usd=Decimal(0))
    assert choose_action(graph(), [], budget, expected_acquisition=free)[0].action == "SEARCH_MORE"


def test_supported_graph_does_not_search_even_without_acquisition_budget() -> None:
    beliefs = [ClaimBelief(claim_id=c, status=BeliefStatus.SUPPORTED) for c in ["a", "b"]]
    decision, _ = choose_action(
        graph(), beliefs, BudgetState(limits=BudgetLimits(max_search_calls=0))
    )
    assert decision.action == "ANSWER" and decision.target_claim_id is None


def test_or_does_not_resolve_irrelevant_conflict() -> None:
    value = graph()
    value.nodes[2].kind = "OR"
    decision, _ = choose_action(
        value,
        [
            ClaimBelief(claim_id="a", status=BeliefStatus.SUPPORTED),
            ClaimBelief(claim_id="b", status=BeliefStatus.MIXED),
        ],
        BudgetState(),
    )
    assert decision.action == "ANSWER"
