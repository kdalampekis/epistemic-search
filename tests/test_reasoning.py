import pytest

from epistemic_search.decomposition import ProofGraph
from epistemic_search.models import BeliefStatus, Claim, ClaimBelief, ProofNode
from epistemic_search.reasoning import negate, propagate, reason


def graph(kind: str = "AND") -> ProofGraph:
    return ProofGraph(
        claims=[Claim(id="a", text="A"), Claim(id="b", text="B")],
        nodes=[
            ProofNode(id="a", kind="CLAIM", claim_id="a"),
            ProofNode(id="b", kind="CLAIM", claim_id="b"),
            ProofNode.model_validate({"id": "op", "kind": kind, "children": ["a", "b"]}),
            ProofNode(id="root", kind="CONCLUSION", children=["op"]),
        ],
        conclusion_id="root",
    )


@pytest.mark.parametrize("state", list(BeliefStatus))
def test_negation_is_involutive_and_preserves_unknown(state: BeliefStatus) -> None:
    assert negate(negate(state)) == state
    if state in {BeliefStatus.UNKNOWN, BeliefStatus.MIXED}:
        assert negate(state) == state


@pytest.mark.parametrize(
    "kind,a,b,expected",
    [
        ("AND", "SUPPORTED", "UNKNOWN", "UNKNOWN"),
        ("AND", "SUPPORTED", "MIXED", "MIXED"),
        ("AND", "CONTRADICTED", "UNKNOWN", "CONTRADICTED"),
        ("AND", "SUPPORTED", "SUPPORTED", "SUPPORTED"),
        ("OR", "SUPPORTED", "UNKNOWN", "SUPPORTED"),
        ("OR", "MIXED", "UNKNOWN", "MIXED"),
        ("OR", "CONTRADICTED", "UNKNOWN", "UNKNOWN"),
        ("OR", "CONTRADICTED", "CONTRADICTED", "CONTRADICTED"),
    ],
)
def test_propagation(kind: str, a: str, b: str, expected: str) -> None:
    assert propagate(kind, [BeliefStatus(a), BeliefStatus(b)]) == expected


def test_missing_beliefs_are_unknown_with_exact_blockers() -> None:
    result = reason(graph(), [ClaimBelief(claim_id="a", status=BeliefStatus.SUPPORTED)])
    assert result.status == "UNKNOWN" and not result.sufficient
    assert result.blockers == result.minimal_frontier == ["b"]
    assert result.trace[-1].node_id == "root"
    assert result.scope == "derivability_from_extracted_model"


def test_or_frontiers_and_irrelevant_conflict() -> None:
    result = reason(graph("OR"), [])
    assert result.alternative_frontiers == [{"a": "SUPPORTED"}, {"b": "SUPPORTED"}]
    resolved = reason(
        graph("OR"),
        [
            ClaimBelief(claim_id="a", status=BeliefStatus.SUPPORTED),
            ClaimBelief(claim_id="b", status=BeliefStatus.MIXED),
        ],
    )
    assert resolved.sufficient and resolved.blockers == resolved.conflicts == []


def test_shared_premise_frontier_is_global_not_greedy() -> None:
    claims = [Claim(id=c, text=c) for c in "abc"]
    nodes = [ProofNode(id=c, kind="CLAIM", claim_id=c) for c in "abc"] + [
        ProofNode(id="ab", kind="OR", children=["a", "b"]),
        ProofNode(id="bc", kind="OR", children=["b", "c"]),
        ProofNode(id="both", kind="AND", children=["ab", "bc"]),
        ProofNode(id="root", kind="CONCLUSION", children=["both"]),
    ]
    result = reason(ProofGraph(claims=claims, nodes=nodes, conclusion_id="root"), [])
    assert result.minimal_frontier == ["b"]
    assert result.alternative_frontiers == [
        {"b": "SUPPORTED"},
        {"a": "SUPPORTED", "c": "SUPPORTED"},
    ]


def test_not_requires_explicit_refutation() -> None:
    value = ProofGraph(
        claims=[Claim(id="a", text="A")],
        nodes=[
            ProofNode(id="a", kind="CLAIM", claim_id="a"),
            ProofNode(id="not", kind="NOT", children=["a"]),
            ProofNode(id="root", kind="CONCLUSION", children=["not"]),
        ],
        conclusion_id="root",
    )
    assert reason(value, []).status == "UNKNOWN"
    assert reason(value, [ClaimBelief(claim_id="a", status=BeliefStatus.CONTRADICTED)]).sufficient


def test_frontier_limit_fails_without_partial_answer() -> None:
    with pytest.raises(ValueError, match="frontier limit"):
        reason(graph("OR"), [], frontier_limit=1)


@pytest.mark.parametrize("status", list(BeliefStatus))
def test_incompatible_polarities_are_not_repairable(status: BeliefStatus) -> None:
    value = ProofGraph(
        claims=[Claim(id="a", text="A")],
        nodes=[
            ProofNode(id="a", kind="CLAIM", claim_id="a"),
            ProofNode(id="not_a", kind="NOT", children=["a"]),
            ProofNode(id="both", kind="AND", children=["a", "not_a"]),
            ProofNode(id="root", kind="CONCLUSION", children=["both"]),
        ],
        conclusion_id="root",
    )
    result = reason(value, [ClaimBelief(claim_id="a", status=status)])
    assert not result.sufficient and not result.structurally_satisfiable
    assert result.alternative_frontiers == []


def test_repair_cannot_break_an_already_supported_branch() -> None:
    from itertools import product

    value = graph("OR")
    value.nodes.insert(-1, ProofNode(id="not_a", kind="NOT", children=["a"]))
    value.nodes.insert(-1, ProofNode(id="both", kind="AND", children=["op", "not_a"]))
    value.nodes[-1].children = ["both"]
    for a, b in product(BeliefStatus, repeat=2):
        current = {"a": a, "b": b}
        result = reason(value, [ClaimBelief(claim_id=c, status=s) for c, s in current.items()])
        for repair in result.alternative_frontiers:
            updated = current | repair
            verified = reason(
                value, [ClaimBelief(claim_id=c, status=s) for c, s in updated.items()]
            )
            assert verified.sufficient
    original = reason(value, [ClaimBelief(claim_id="a", status=BeliefStatus.SUPPORTED)])
    assert original.required_stances == {"a": "CONTRADICTED", "b": "SUPPORTED"}


def test_supported_graph_needs_no_frontier_enumeration() -> None:
    result = reason(
        graph("OR"), [ClaimBelief(claim_id="a", status=BeliefStatus.SUPPORTED)], frontier_limit=1
    )
    assert result.sufficient
