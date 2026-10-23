from datetime import UTC, datetime
from decimal import Decimal

import pytest

from epistemic_search.models import AgentEvent, Source, Usage


@pytest.fixture
def source() -> Source:
    return Source(
        id="s1",
        uri="fixture://source/1",
        title="Fixture source",
        retrieved_at=datetime(2026, 10, 23, tzinfo=UTC),
        source_type="benchmark",
    )


@pytest.fixture
def event() -> AgentEvent:
    return AgentEvent(
        id="event-1",
        query_id="q1",
        type="MODEL_CALL",
        component="answering",
        timestamp=datetime(2026, 10, 23, tzinfo=UTC),
        usage=Usage(
            prompt_tokens=10,
            completion_tokens=4,
            context_tokens=6,
            model_calls=1,
            latency_seconds=0.25,
            cost_usd=Decimal("0.001"),
        ),
        payload={"model": "fixture-model", "prompt_version": "test-v1"},
    )
