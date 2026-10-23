"""Deterministic premise-directed policy with explicit acquisition budgets."""

from epistemic_search.decomposition import ProofGraph
from epistemic_search.models import BeliefStatus, BudgetState, ClaimBelief, Decision, Usage
from epistemic_search.reasoning import SufficiencyResult, reason


def acquisition_blockers(budget: BudgetState, expected: Usage) -> list[str]:
    """Expected usage is a reservation, not a guarantee about a remote call."""
    used, limits = budget.used, budget.limits
    checks = {
        "search_calls": (used.search_calls, expected.search_calls, limits.max_search_calls),
        "documents": (used.documents, expected.documents, limits.max_documents),
        "retrieved_tokens": (
            used.retrieved_tokens,
            expected.retrieved_tokens,
            limits.max_retrieved_tokens,
        ),
        "model_calls": (used.model_calls, expected.model_calls, limits.max_llm_calls),
        "prompt_tokens": (
            used.prompt_tokens,
            expected.prompt_tokens,
            limits.max_total_llm_input_tokens,
        ),
        "completion_tokens": (
            used.completion_tokens,
            expected.completion_tokens,
            limits.max_total_llm_output_tokens,
        ),
        "latency_seconds": (
            used.latency_seconds,
            expected.latency_seconds,
            limits.max_latency_seconds,
        ),
    }
    blocked = [
        name
        for name, (actual, estimate, limit) in checks.items()
        if limit is not None and (actual >= limit or actual + estimate > limit)
    ]
    if limits.max_cost_usd is not None:
        if used.cost_usd is None or expected.cost_usd is None:
            blocked.append("cost_unknown")
        elif used.cost_usd + expected.cost_usd > limits.max_cost_usd:
            blocked.append("cost_usd")
    return blocked


def choose_action(
    graph: ProofGraph,
    beliefs: list[ClaimBelief],
    budget: BudgetState,
    *,
    expected_acquisition: Usage | None = None,
    frontier_limit: int = 1024,
) -> tuple[Decision, SufficiencyResult]:
    result = reason(graph, beliefs, frontier_limit=frontier_limit)
    if result.sufficient:
        return Decision(
            action="ANSWER", rationale="Supported by the extracted evidence model"
        ), result
    if not result.structurally_satisfiable:
        return Decision(
            action="ABSTAIN",
            blocking_claims=result.blockers,
            rationale="No consistent structural repair can support this conclusion",
        ), result
    expected = (
        expected_acquisition
        if expected_acquisition is not None
        else Usage(
            search_calls=1,
            documents=1,
            retrieved_tokens=1,
            model_calls=1,
            prompt_tokens=1,
            completion_tokens=1,
        )
    )
    blocked = acquisition_blockers(budget, expected)
    if blocked:
        return Decision(
            action="ABSTAIN",
            blocking_claims=result.blockers,
            rationale="Acquisition budget unavailable: " + ", ".join(blocked),
        ), result
    claims = {claim.id: claim for claim in graph.claims}
    states = {belief.claim_id: belief.status for belief in beliefs}
    frontier = result.minimal_frontier
    conflicting = [
        c for c in frontier if states.get(c, BeliefStatus.UNKNOWN) != BeliefStatus.UNKNOWN
    ]
    candidates = conflicting or frontier
    if not candidates:
        return Decision(
            action="ABSTAIN",
            blocking_claims=result.blockers,
            rationale="No unresolved acquisition target",
        ), result
    target = min(candidates, key=lambda c: (-claims[c].importance, c))
    return Decision(
        action="RESOLVE_CONFLICT" if conflicting else "SEARCH_MORE",
        target_claim_id=target,
        blocking_claims=result.blockers,
        rationale=f"Resolve {target} toward {result.required_stances[target].value}",
    ), result
