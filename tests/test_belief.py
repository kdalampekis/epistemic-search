import pytest
from pydantic import ValidationError

from epistemic_search.belief import aggregate_beliefs
from epistemic_search.config import BeliefConfig
from epistemic_search.models import Claim, EvidenceItem, EvidenceProvenance, Source


def evidence(source: Source, stance: str, score: float, identifier: str) -> EvidenceItem:
    return EvidenceItem.model_validate(
        {
            "id": identifier,
            "claim_id": "c",
            "source": source,
            "span": "span",
            "stance": stance,
            "stance_score": score,
            "provenance": EvidenceProvenance(
                search_query="query",
                rank=1,
                extraction_model="fixture",
                prompt_version="v1",
                duplication_group="duplicate",
            ),
        }
    )


@pytest.mark.parametrize(
    "stances,status,support,contradiction",
    [
        ([], "UNKNOWN", 0, 0),
        ([("NEUTRAL", 1.0)], "UNKNOWN", 0, 0),
        ([("SUPPORT", 0.8)], "SUPPORTED", 0.8, 0),
        ([("CONTRADICT", 0.7)], "CONTRADICTED", 0, 0.7),
        ([("SUPPORT", 0.8), ("CONTRADICT", 0.7)], "MIXED", 0.8, 0.7),
        ([("SUPPORT", 0.2), ("CONTRADICT", 0.1)], "UNKNOWN", 0.2, 0.1),
    ],
)
def test_evidence_states(
    source: Source,
    stances: list[tuple[str, float]],
    status: str,
    support: float,
    contradiction: float,
) -> None:
    items = [evidence(source, stance, score, str(i)) for i, (stance, score) in enumerate(stances)]
    belief = aggregate_beliefs([Claim(id="c", text="Claim")], items, BeliefConfig())[0]
    assert belief.status == status
    assert belief.support_score == support and belief.contradiction_score == contradiction
    assert not belief.calibrated
    assert belief.uncertainty == pytest.approx(1 - abs(support - contradiction))


def test_duplicates_do_not_amplify_and_order_does_not_matter(source: Source) -> None:
    claims = [Claim(id="c", text="Claim")]
    first = evidence(source, "SUPPORT", 0.4, "a")
    copies = [evidence(source, "SUPPORT", 0.4, str(i)) for i in range(10)]
    copies.extend([first, first])
    original = aggregate_beliefs(claims, [first], BeliefConfig())[0]
    duplicated = aggregate_beliefs(claims, copies, BeliefConfig())[0]
    assert duplicated.status == original.status == "UNKNOWN"
    assert duplicated.support_score == original.support_score
    assert len(duplicated.evidence_ids) == 11
    assert aggregate_beliefs(claims, copies, BeliefConfig()) == aggregate_beliefs(
        claims, copies[::-1], BeliefConfig()
    )


def test_threshold_and_unknown_claim_validation(source: Source) -> None:
    item = evidence(source, "SUPPORT", 0.5, "a")
    claims = [Claim(id="c", text="Claim")]
    assert aggregate_beliefs(claims, [item], BeliefConfig())[0].status == "SUPPORTED"
    assert aggregate_beliefs(claims, [item], BeliefConfig(threshold=0.6))[0].status == "UNKNOWN"
    with pytest.raises(ValueError, match="unknown claim"):
        aggregate_beliefs([], [item], BeliefConfig())
    with pytest.raises(ValidationError):
        BeliefConfig(threshold=0)
