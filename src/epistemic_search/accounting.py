"""Component-level accounting independent of model/search providers."""

from decimal import Decimal
from typing import Protocol

from epistemic_search.models import AgentEvent, Usage


class UsageRecorder(Protocol):
    def record(self, event: AgentEvent) -> None: ...


class UsageLedger:
    def __init__(self) -> None:
        self._events: list[AgentEvent] = []

    def record(self, event: AgentEvent) -> None:
        # Snapshot caller-owned data so later mutations cannot rewrite recorded costs.
        self._events.append(event.model_copy(deep=True))

    def total(self, component: str | None = None) -> Usage:
        entries = [e.usage for e in self._events if component is None or e.component == component]
        costs = [u.cost_usd for u in entries]

        def detail(name: str) -> int | None:
            values = [getattr(u, name) for u in entries]
            return None if None in values else sum(values)

        return Usage(
            prompt_tokens=sum(u.prompt_tokens for u in entries),
            completion_tokens=sum(u.completion_tokens for u in entries),
            cached_input_tokens=detail("cached_input_tokens"),
            cache_write_tokens=detail("cache_write_tokens"),
            reasoning_tokens=detail("reasoning_tokens"),
            model_cache_hits=sum(u.model_cache_hits for u in entries),
            reused_cost_usd=sum((u.reused_cost_usd for u in entries), Decimal(0)),
            api_calls=sum(u.api_calls for u in entries),
            preflight_calls=sum(u.preflight_calls for u in entries),
            retrieved_tokens=sum(u.retrieved_tokens for u in entries),
            context_tokens=sum(u.context_tokens for u in entries),
            search_calls=sum(u.search_calls for u in entries),
            model_calls=sum(u.model_calls for u in entries),
            documents=sum(u.documents for u in entries),
            latency_seconds=sum(u.latency_seconds for u in entries),
            cost_usd=None
            if None in costs
            else sum((c for c in costs if c is not None), Decimal(0)),
        )
