"""Deterministic premise-directed policy with explicit acquisition budgets."""

import random

from epistemic_search.config import ControllerConfig
from epistemic_search.decomposition import ProofGraph
from epistemic_search.models import (
    AcquisitionRanking,
    BeliefStatus,
    BudgetState,
    ClaimBelief,
    Decision,
    Usage,
)
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
    settings: ControllerConfig | None = None,
    seed: int = 0,
    step: int = 0,
    context_id: str = "",
) -> tuple[Decision, SufficiencyResult]:
    settings = ControllerConfig.model_validate((settings or ControllerConfig()).model_dump())
    if set(settings.estimates) - {c.id for c in graph.claims}:
        raise ValueError("Acquisition estimates reference unknown claim IDs")
    if seed < 0 or step < 0:
        raise ValueError("Acquisition seed and step must be nonnegative")
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
    candidates = sorted(candidates)
    belief_by_id = {b.claim_id: b for b in beliefs}
    uncertainties = {
        c: belief_by_id[c].uncertainty if c in belief_by_id else 1.0 for c in candidates
    }
    criticality = {
        c: sum(c in frontier for frontier in result.alternative_frontiers)
        / len(result.alternative_frontiers)
        for c in candidates
    }
    estimates = {c: settings.estimates.get(c, settings.default_estimate) for c in candidates}
    rng = random.Random(f"{seed}:{context_id}:{step}")
    scores = {}
    for c in candidates:
        if settings.policy == "random":
            scores[c] = rng.random()
        elif settings.policy == "uncertainty":
            scores[c] = uncertainties[c]
        elif settings.policy == "voi":
            scores[c] = (
                claims[c].importance
                * uncertainties[c]
                * criticality[c]
                * estimates[c].retrievability
                / estimates[c].cost
            )
        else:
            scores[c] = claims[c].importance
    target = min(candidates, key=lambda c: (-scores[c], c))
    ranking = AcquisitionRanking(
        policy=settings.policy,
        seed=seed,
        step=step,
        context_id=context_id,
        cost_unit=settings.cost_unit,
        estimate_provenance=settings.estimate_provenance,
        scores=scores,
        estimates=estimates,
        criticality=criticality,
        uncertainty=uncertainties,
    )
    return Decision(
        action="RESOLVE_CONFLICT" if conflicting else "SEARCH_MORE",
        target_claim_id=target,
        blocking_claims=result.blockers,
        rationale=f"Resolve {target} toward {result.required_stances[target].value}",
        acquisition=ranking,
    ), result
