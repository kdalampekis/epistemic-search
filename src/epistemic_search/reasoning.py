"""Conservative derivability over an extracted graph, never real-world truth."""

from itertools import product
from typing import Literal

from epistemic_search.decomposition import ProofGraph
from epistemic_search.models import BeliefStatus, ClaimBelief, Schema, Text


class DerivationStep(Schema):
    node_id: Text
    kind: str
    status: BeliefStatus
    children: list[Text]


class SufficiencyResult(Schema):
    status: BeliefStatus
    sufficient: bool
    blockers: list[Text]
    minimal_frontier: list[Text]
    required_stances: dict[str, BeliefStatus]
    alternative_frontiers: list[dict[str, BeliefStatus]]
    structurally_satisfiable: bool
    conflicts: list[Text]
    trace: list[DerivationStep]
    scope: Literal["derivability_from_extracted_model"] = "derivability_from_extracted_model"


def negate(status: BeliefStatus) -> BeliefStatus:
    return {
        BeliefStatus.SUPPORTED: BeliefStatus.CONTRADICTED,
        BeliefStatus.CONTRADICTED: BeliefStatus.SUPPORTED,
        BeliefStatus.UNKNOWN: BeliefStatus.UNKNOWN,
        BeliefStatus.MIXED: BeliefStatus.MIXED,
    }[status]


def propagate(kind: str, children: list[BeliefStatus]) -> BeliefStatus:
    if kind == "NOT":
        return negate(children[0])
    if kind == "CONCLUSION":
        return children[0]
    if kind == "AND":
        order = [BeliefStatus.CONTRADICTED, BeliefStatus.MIXED, BeliefStatus.UNKNOWN]
        fallback = BeliefStatus.SUPPORTED
    elif kind == "OR":
        order = [BeliefStatus.SUPPORTED, BeliefStatus.MIXED, BeliefStatus.UNKNOWN]
        fallback = BeliefStatus.CONTRADICTED
    else:
        raise ValueError("Expected AND, OR, NOT, or CONCLUSION")
    return next((state for state in order if state in children), fallback)


def reason(
    graph: ProofGraph, beliefs: list[ClaimBelief], *, frontier_limit: int = 1024
) -> SufficiencyResult:
    if frontier_limit < 1:
        raise ValueError("frontier_limit must be positive")
    # Revalidate caller-owned nested lists before recursive graph traversal.
    graph = ProofGraph.model_validate(graph.model_dump())
    states = {belief.claim_id: belief.status for belief in beliefs}
    if len(states) != len(beliefs) or states.keys() - {c.id for c in graph.claims}:
        raise ValueError("Beliefs must have unique, known claim IDs")
    nodes = {node.id: node for node in graph.nodes}
    evaluated: dict[str, BeliefStatus] = {}
    trace: list[DerivationStep] = []

    def evaluate(node_id: str) -> BeliefStatus:
        if node_id in evaluated:
            return evaluated[node_id]
        node = nodes[node_id]
        if node.kind == "CLAIM":
            assert node.claim_id is not None
            status = states.get(node.claim_id, BeliefStatus.UNKNOWN)
        else:
            status = propagate(node.kind, [evaluate(child) for child in node.children])
        evaluated[node_id] = status
        trace.append(
            DerivationStep(node_id=node_id, kind=node.kind, status=status, children=node.children)
        )
        return status

    status = evaluate(graph.conclusion_id)
    if status == BeliefStatus.SUPPORTED:
        return SufficiencyResult(
            status=status,
            sufficient=True,
            blockers=[],
            minimal_frontier=[],
            required_stances={},
            alternative_frontiers=[{}],
            structurally_satisfiable=True,
            conflicts=[],
            trace=trace,
        )

    type Obligations = frozenset[tuple[str, BeliefStatus]]

    def prune(candidates: list[Obligations]) -> list[Obligations]:
        minimal: list[Obligations] = []
        for candidate in sorted(set(candidates), key=lambda item: (len(item), sorted(item))):
            if len(dict(candidate)) != len(candidate):
                continue  # One claim cannot simultaneously require opposing pure stances.
            if not any(other <= candidate for other in minimal):
                minimal.append(candidate)
            if len(minimal) > frontier_limit:
                raise ValueError("Exact frontier limit exceeded; no truncated result is returned")
        return minimal

    memo: dict[tuple[str, BeliefStatus], list[Obligations]] = {}

    def frontier(node_id: str, desired: BeliefStatus) -> list[Obligations]:
        key = (node_id, desired)
        if key in memo:
            return memo[key]
        node = nodes[node_id]
        if node.kind == "CLAIM":
            assert node.claim_id is not None
            options = [frozenset([(node.claim_id, desired)])]
        elif node.kind in {"NOT", "CONCLUSION"}:
            options = frontier(node.children[0], negate(desired) if node.kind == "NOT" else desired)
        else:
            branches = [frontier(child, desired) for child in node.children]
            require_all = (node.kind == "AND") == (desired == BeliefStatus.SUPPORTED)
            if require_all:
                options = [frozenset()]
                for branch in branches:
                    if len(options) * len(branch) > frontier_limit * frontier_limit:
                        raise ValueError("Exact frontier combination limit exceeded")
                    options = prune([left | right for left, right in product(options, branch)])
            else:
                options = prune([item for branch in branches for item in branch])
        memo[key] = options
        return options

    assignments = frontier(graph.conclusion_id, BeliefStatus.SUPPORTED)
    options = prune(
        [
            frozenset(
                (claim_id, desired)
                for claim_id, desired in assignment
                if states.get(claim_id, BeliefStatus.UNKNOWN) != desired
            )
            for assignment in assignments
        ]
    )
    ordered = [
        dict(sorted(option))
        for option in sorted(options, key=lambda item: (len(item), sorted(item)))
    ]
    blockers = sorted({claim_id for option in options for claim_id, _ in option})
    return SufficiencyResult(
        status=status,
        sufficient=False,
        blockers=blockers,
        minimal_frontier=list(ordered[0]) if ordered else [],
        required_stances=ordered[0] if ordered else {},
        alternative_frontiers=ordered,
        structurally_satisfiable=bool(assignments),
        conflicts=[c for c in blockers if states.get(c) == BeliefStatus.MIXED],
        trace=trace,
    )
