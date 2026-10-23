"""Conservative max-per-stance heuristic; these scores are not probabilities."""

from epistemic_search.config import BeliefConfig
from epistemic_search.evidence import EvidenceLedger
from epistemic_search.models import BeliefStatus, Claim, ClaimBelief, EvidenceItem


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
