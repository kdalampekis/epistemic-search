"""Conservative max-per-stance heuristic; these scores are not probabilities."""

from epistemic_search.config import BeliefConfig
from epistemic_search.evidence import EvidenceLedger
from epistemic_search.models import BeliefStatus, Claim, ClaimBelief, EvidenceItem, Schema, Text


def aggregate_beliefs(
    claims: list[Claim], evidence: list[EvidenceItem], settings: BeliefConfig
) -> list[ClaimBelief]:
    grouped: dict[str, list[EvidenceItem]] = {c.id: [] for c in claims}
    if len(grouped) != len(claims):
        raise ValueError("Claim IDs must be unique")
    ledger = EvidenceLedger()
    for item in evidence:
        if item.claim_id not in grouped:
            raise ValueError("Evidence references an unknown claim")
        ledger.add(item)
    for item in ledger.items:
        grouped[item.claim_id].append(item)
    beliefs = []
    for claim_id, items in sorted(grouped.items()):
        support = max((e.stance_score for e in items if e.stance == "SUPPORT"), default=0.0)
        contradiction = max(
            (e.stance_score for e in items if e.stance == "CONTRADICT"), default=0.0
        )
        supported, contradicted = support >= settings.threshold, contradiction >= settings.threshold
        if supported and contradicted:
            status = BeliefStatus.MIXED
        elif supported:
            status = BeliefStatus.SUPPORTED
        elif contradicted:
            status = BeliefStatus.CONTRADICTED
        else:
            status = BeliefStatus.UNKNOWN
        beliefs.append(
            ClaimBelief(
                claim_id=claim_id,
                status=status,
                support_score=support,
                contradiction_score=contradiction,
                uncertainty=1 - abs(support - contradiction),
                calibrated=False,
                evidence_ids=sorted(e.id for e in items),
            )
        )
    return beliefs


class Conflict(Schema):
    claim_id: Text
    support_evidence_ids: list[Text]
    contradiction_evidence_ids: list[Text]
    source_ids: list[Text]


def conflicts_for(beliefs: list[ClaimBelief], evidence: list[EvidenceItem]) -> list[Conflict]:
    """MIXED is the existing thresholded detector, not any negative stance."""
    conflicts = []
    for belief in beliefs:
        if belief.status != "MIXED":
            continue
        items = [e for e in evidence if e.id in belief.evidence_ids]
        if {e.id for e in items} != set(belief.evidence_ids):
            raise ValueError("Conflict references missing evidence")
        if any(e.claim_id != belief.claim_id for e in items):
            raise ValueError("Conflict evidence belongs to a different claim")
        support = sorted(e.id for e in items if e.stance == "SUPPORT")
        contradiction = sorted(e.id for e in items if e.stance == "CONTRADICT")
        if not support or not contradiction:
            raise ValueError("MIXED conflict requires both evidence stances with provenance")
        conflicts.append(
            Conflict(
                claim_id=belief.claim_id,
                support_evidence_ids=support,
                contradiction_evidence_ids=contradiction,
                source_ids=sorted({e.source.id for e in items if e.stance != "NEUTRAL"}),
            )
        )
    return conflicts
