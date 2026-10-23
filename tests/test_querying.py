from datetime import UTC, datetime

from epistemic_search.models import Claim, EvidenceItem, EvidenceProvenance, Source
from epistemic_search.querying import QueryContext, generate_query


def test_query_is_deterministic_and_preserves_constraints() -> None:
    context = QueryContext(
        query_id="q",
        original_question="Is X eligible?",
        target=Claim(id="c", text="X is not exempt"),
        entities=["Company X", "California"],
        temporal_scope="effective on 2025-01-01",
        required_stance="CONTRADICTED",
    )
    timestamp = datetime(2026, 10, 23, tzinfo=UTC)
    first = generate_query(context, timestamp=timestamp)
    assert first == generate_query(context, timestamp=timestamp)
    assert first.text.startswith("X is not exempt")
    assert "effective on 2025-01-01" in first.text and "California" in first.text
    assert first.event.usage.model_calls == first.event.usage.search_calls == 0
    assert first.event.usage.cost_usd == 0
    assert first.event.payload["required_stance"] == "CONTRADICTED"


def test_query_uses_only_target_evidence_and_logs_conflict(source: Source) -> None:
    provenance = EvidenceProvenance(
        search_query="query", rank=1, extraction_model="fixture", prompt_version="v1"
    )
    items = [
        EvidenceItem(
            id="s",
            claim_id="c",
            source=source,
            span="support",
            stance="SUPPORT",
            stance_score=0.8,
            provenance=provenance,
        ),
        EvidenceItem(
            id="r",
            claim_id="c",
            source=source,
            span="refutation",
            stance="CONTRADICT",
            stance_score=0.8,
            provenance=provenance,
        ),
        EvidenceItem(
            id="other",
            claim_id="other",
            source=source,
            span="elsewhere",
            stance="SUPPORT",
            stance_score=0.8,
            provenance=provenance,
        ),
    ]
    query = generate_query(
        QueryContext(
            query_id="q",
            original_question="Question",
            target=Claim(id="c", text="Target premise"),
            evidence=items,
        )
    )
    assert "for and against" in query.text
    assert query.event.payload["evidence_ids"] == ["r", "s"]
    assert query.event.payload["conflict"] is True


def test_missing_scope_does_not_invent_a_date() -> None:
    query = generate_query(
        QueryContext(query_id="q", original_question="Same", target=Claim(id="c", text="Same"))
    )
    assert query.text == "Same"
    assert query.event.payload["temporal_scope"] is None
