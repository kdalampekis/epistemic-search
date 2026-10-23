"""Shared execution accounting for every external call in an epistemic run."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter

from epistemic_search.accounting import UsageLedger
from epistemic_search.config import RunConfig
from epistemic_search.models import AgentEvent, Usage
from epistemic_search.providers import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderError,
    SearchProvider,
    SearchResponse,
)
from epistemic_search.tokens import count_tokens


class BudgetExceeded(ProviderError):
    pass


class RunAccounting:
    def __init__(self, query_id: str, config: RunConfig) -> None:
        self.query_id, self.config = query_id, config
        self.started = perf_counter()
        self.ledger = UsageLedger()
        self.trace: list[AgentEvent] = []
        self.usage_complete = True
        self.stopped_reason: str | None = None
        self.component = "decomposition"

    def add(self, kind: str, payload: dict[str, object], usage: Usage | None = None) -> None:
        record = AgentEvent.model_validate(
            {
                "id": f"{self.query_id}:{len(self.trace)}",
                "query_id": self.query_id,
                "type": kind,
                "component": self.component,
                "timestamp": datetime.now(UTC),
                "usage": usage or Usage(cost_usd=Decimal(0)),
                "payload": payload,
            }
        )
        self.trace.append(record)
        self.ledger.record(record)

    def block(self, reason: str) -> None:
        self.stopped_reason = reason
        self.add("BUDGET_STOP", {"reason": reason})
        raise BudgetExceeded(reason, Usage(cost_usd=Decimal(0)), usage_complete=True)

    def check(self, expected: Usage) -> None:
        used, limits = self.ledger.total(), self.config.budget
        pairs = [
            (used.search_calls + expected.search_calls, limits.max_search_calls),
            (used.documents + expected.documents, limits.max_documents),
            (used.retrieved_tokens + expected.retrieved_tokens, limits.max_retrieved_tokens),
            (used.model_calls + expected.model_calls, limits.max_llm_calls),
            (used.prompt_tokens + expected.prompt_tokens, limits.max_total_llm_input_tokens),
            (
                used.completion_tokens + expected.completion_tokens,
                limits.max_total_llm_output_tokens,
            ),
        ]
        if any(limit is not None and value > limit for value, limit in pairs):
            self.block("Shared call/document/token budget exhausted")
        if (
            limits.max_latency_seconds is not None
            and perf_counter() - self.started >= limits.max_latency_seconds
        ):
            self.block("Shared wall-clock budget exhausted")
        if limits.max_cost_usd is not None:
            if used.cost_usd is None or expected.cost_usd is None:
                self.block("Cannot enforce monetary limit with unknown cost")
            elif used.cost_usd + expected.cost_usd > limits.max_cost_usd:
                self.block("Shared monetary budget exhausted")

    def timeout(self) -> float:
        assert self.config.rag is not None
        timeout = self.config.rag.timeout_seconds
        if self.config.budget.max_latency_seconds is not None:
            timeout = min(
                timeout, self.config.budget.max_latency_seconds - (perf_counter() - self.started)
            )
        return max(0, timeout)


class GuardedModel:
    def __init__(self, provider: ModelProvider, accounting: RunAccounting) -> None:
        self.provider, self.accounting = provider, accounting

    async def complete(self, request: ModelRequest) -> ModelResponse:
        run = self.accounting
        assert run.config.rag is not None
        expected = Usage(
            model_calls=1,
            prompt_tokens=count_tokens(request.prompt),
            completion_tokens=request.max_output_tokens,
            cost_usd=Decimal(0) if run.config.rag.backend == "fixture" else None,
        )
        run.check(expected)
        try:
            response = await asyncio.wait_for(
                self.provider.complete(request), timeout=run.timeout()
            )
        except asyncio.CancelledError:
            run.usage_complete = False
            run.add(
                "MODEL_ERROR",
                {"request": request.model_dump(mode="json"), "error_type": "CancelledError"},
                Usage(model_calls=1),
            )
            raise
        except Exception as exc:
            usage = exc.usage if isinstance(exc, ProviderError) else Usage(model_calls=1)
            run.usage_complete = (
                run.usage_complete and isinstance(exc, ProviderError) and exc.usage_complete
            )
            run.add(
                "MODEL_ERROR",
                {"request": request.model_dump(mode="json"), "error_type": type(exc).__name__},
                usage,
            )
            raise ProviderError(
                "Model attempt failed", usage, usage_complete=run.usage_complete
            ) from exc
        run.add(
            "MODEL",
            {
                "request": request.model_dump(mode="json"),
                "response": response.model_dump(mode="json"),
            },
            response.usage,
        )
        if response.usage.model_calls != 1:
            run.usage_complete = False
            raise ProviderError(
                "Model usage contract violated", Usage(cost_usd=Decimal(0)), usage_complete=False
            )
        run.check(Usage(cost_usd=Decimal(0)))
        return response


class GuardedSearch:
    def __init__(self, provider: SearchProvider, accounting: RunAccounting) -> None:
        self.provider, self.accounting = provider, accounting

    async def search(self, query: str, k: int) -> SearchResponse:
        run = self.accounting
        used, limits = run.ledger.total(), run.config.budget
        if limits.max_documents is not None:
            k = min(k, limits.max_documents - used.documents)
        if k < 1:
            run.block("Document budget exhausted")
        run.check(Usage(search_calls=1, documents=k, retrieved_tokens=1, cost_usd=Decimal(0)))
        try:
            response = await asyncio.wait_for(self.provider.search(query, k), timeout=run.timeout())
        except asyncio.CancelledError:
            run.usage_complete = False
            run.add(
                "SEARCH_ERROR",
                {"query": query, "error_type": "CancelledError"},
                Usage(search_calls=1),
            )
            raise
        except Exception as exc:
            usage = exc.usage if isinstance(exc, ProviderError) else Usage(search_calls=1)
            run.usage_complete = (
                run.usage_complete and isinstance(exc, ProviderError) and exc.usage_complete
            )
            run.add(
                "SEARCH_ERROR", {"query": query, "k": k, "error_type": type(exc).__name__}, usage
            )
            raise ProviderError(
                "Search attempt failed", usage, usage_complete=run.usage_complete
            ) from exc
        run.add(
            "SEARCH",
            {"query": query, "k": k, "response": response.model_dump(mode="json")},
            response.usage,
        )
        if (
            response.usage.search_calls != 1
            or response.usage.documents != len(response.results)
            or len(response.results) > k
            or len({item.source.id for item in response.results}) != len(response.results)
        ):
            run.usage_complete = False
            raise ProviderError(
                "Search usage contract violated", Usage(cost_usd=Decimal(0)), usage_complete=False
            )
        run.check(Usage(cost_usd=Decimal(0)))
        return response
