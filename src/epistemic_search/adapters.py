"""Fixture providers and an optional OpenAI Responses adapter; no domain policy."""

import asyncio
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from pydantic import TypeAdapter

from epistemic_search.config import RagConfig
from epistemic_search.models import Schema, Source, Usage
from epistemic_search.providers import (
    ModelRequest,
    ModelResponse,
    ProviderBudgetExceeded,
    ProviderError,
    SearchResponse,
    SearchResult,
)
from epistemic_search.spending import SpendLedger, SpendStopped
from epistemic_search.tokens import count_tokens


class CorpusDocument(Schema):
    source: Source
    text: str


class FixtureSearchProvider:
    def __init__(self, documents: list[CorpusDocument]) -> None:
        if len({d.source.id for d in documents}) != len(documents):
            raise ValueError("Corpus source IDs must be unique")
        self.documents = documents
        self._cache: dict[tuple[str, int], SearchResponse] = {}

    @classmethod
    def from_path(cls, path: Path) -> "FixtureSearchProvider":
        return cls(
            TypeAdapter(list[CorpusDocument]).validate_json(path.read_text(encoding="utf-8"))
        )

    async def search(self, query: str, k: int) -> SearchResponse:
        if k < 1 or not query.strip():
            raise ValueError("search requires a query and positive k")
        key = (query, k)
        if key in self._cache:
            cached = self._cache[key].model_copy(deep=True)
            cached.metadata["retrieval_cache_hit"] = True
            return cached
        words = set(re.findall(r"\w+", query.casefold()))
        scored = [
            (len(words & set(re.findall(r"\w+", d.text.casefold()))), d) for d in self.documents
        ]
        ranked = sorted(scored, key=lambda pair: (-pair[0], pair[1].source.id))
        selected = [(score, doc) for score, doc in ranked if score > 0][:k]
        results = [
            SearchResult(
                source=doc.source,
                text=doc.text,
                query=query,
                rank=rank,
                retrieval_score=float(score),
            )
            for rank, (score, doc) in enumerate(selected, start=1)
        ]
        response = SearchResponse(
            results=results,
            usage=Usage(
                search_calls=1,
                documents=len(results),
                retrieved_tokens=sum(count_tokens(r.text) for r in results),
                cost_usd=Decimal(0),
            ),
            metadata={"token_measurement": "whitespace-v1-estimate", "latency": "synthetic-zero"},
        )

        self._cache[key] = response.model_copy(deep=True)
        return response


class FixtureModelProvider:
    """Scripted smoke-test outputs, never a model-quality baseline."""

    def __init__(self, responses: list[str] | dict[str, list[str]]) -> None:
        self.responses = iter(responses if isinstance(responses, list) else [])
        self.by_version = (
            {key: iter(values) for key, values in responses.items()}
            if isinstance(responses, dict)
            else None
        )

    @classmethod
    def from_path(cls, path: Path) -> "FixtureModelProvider":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return cls(TypeAdapter(list[str]).validate_python(data))
        return cls(TypeAdapter(dict[str, list[str]]).validate_python(data))

    async def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            text = next(
                self.by_version[request.prompt_version]
                if self.by_version is not None
                else self.responses
            )
        except (StopIteration, KeyError) as exc:
            raise ProviderError(
                "Fixture response script exhausted",
                Usage(model_calls=1, cost_usd=Decimal(0)),
                usage_complete=True,
            ) from exc
        usage = Usage(
            model_calls=1,
            prompt_tokens=count_tokens(request.prompt),
            completion_tokens=count_tokens(text),
            cost_usd=Decimal(0),
        )
        if usage.completion_tokens > request.max_output_tokens:
            raise ProviderError("Fixture output exceeds output budget", usage, usage_complete=True)
        return ModelResponse(
            text=text,
            model=request.model,
            usage=usage,
            metadata={
                "token_measurement": "whitespace-v1-estimate",
                "latency": "synthetic-zero",
                "scripted": True,
            },
        )


class OpenAIModelProvider:
    """No retries, no hidden calls; injectable HTTP client for offline tests."""

    def __init__(self, client: httpx.AsyncClient, api_key: str, config: RagConfig) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai backend")
        self.client, self.api_key, self.config = client, api_key, config
        self.spend = SpendLedger(config.experiment_spend) if config.experiment_spend else None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "input": request.prompt,
            "max_output_tokens": request.max_output_tokens,
            "store": False,
            "service_tier": self.config.service_tier,
            "truncation": "disabled",
        }
        if self.config.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.config.reasoning_effort}
        if self.spend is not None:
            payload["prompt_cache_options"] = {"mode": "implicit", "ttl": "30m"}
            if request.model != self.config.model:
                raise SpendStopped("Request model differs from locked experiment model")
            reason = self.spend.stop_reason()
            if reason:
                raise SpendStopped(reason)
        if request.output_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "research_output",
                    "schema": request.output_schema,
                    "strict": True,
                }
            }
        cache_key = hashlib.sha256(
            json.dumps(
                ["responses-cache-v1", payload, request.seed, request.prompt_version],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if self.spend is not None and (cached := self.spend.cached(cache_key)) is not None:
            if (
                request.max_input_tokens is not None
                and cached.usage.prompt_tokens > request.max_input_tokens
            ):
                raise ProviderBudgetExceeded(
                    "Cached input exceeds remaining token budget",
                    Usage(cost_usd=Decimal(0)),
                    usage_complete=True,
                )
            cached.metadata["original_usage"] = cached.usage.model_dump(mode="json")
            cached.metadata["model_cache_hit"] = True
            cached.metadata["cumulative_project_cost_usd"] = str(
                self.spend.report()["cumulative_project_cost_usd"]
            )
            # Charge the same logical tokens/calls to each architecture, but no new API spend.
            cached.usage.reused_cost_usd = cached.usage.cost_usd or Decimal(0)
            cached.usage.cost_usd = Decimal(0)
            cached.usage.api_calls = cached.usage.preflight_calls = 0
            cached.usage.model_cache_hits = 1
            cached.usage.latency_seconds = 0
            return cached
        start = perf_counter()
        usage = Usage(cost_usd=Decimal(0))
        known = True
        reservation: str | None = None
        counted_input: int | None = None
        try:
            if self.spend is not None:
                usage.api_calls += 1
                usage.preflight_calls += 1
                counted = await self.client.post(
                    "https://api.openai.com/v1/responses/input_tokens",
                    json={
                        k: v
                        for k, v in payload.items()
                        if k in {"model", "input", "text", "reasoning"}
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.config.timeout_seconds,
                )
                counted.raise_for_status()
                value = counted.json()["input_tokens"]
                if type(value) is not int or value < 0 or value > 100_000:
                    raise ValueError(
                        "Exact input count outside audited short-context pricing regime"
                    )
                counted_input = value
                if request.max_input_tokens is not None and value > request.max_input_tokens:
                    usage.latency_seconds = perf_counter() - start
                    raise ProviderBudgetExceeded(
                        "Exact cumulative input budget exhausted", usage, usage_complete=True
                    )
                assert self.config.cache_write_usd_per_million is not None
                assert self.config.output_usd_per_million is not None
                maximum = (
                    Decimal(value) * self.config.cache_write_usd_per_million
                    + Decimal(request.max_output_tokens) * self.config.output_usd_per_million
                ) / Decimal(1_000_000)
                reservation = self.spend.reserve(
                    maximum,
                    Usage(
                        model_calls=1,
                        api_calls=usage.api_calls + 1,
                        preflight_calls=usage.preflight_calls,
                    ),
                    request.model,
                    self.config.reasoning_effort or "unspecified",
                )
            usage.model_calls = 1
            usage.api_calls += 1
            usage.cost_usd = None
            known = False
            response = await self.client.post(
                "https://api.openai.com/v1/responses",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            raw = body["usage"]
            usage.prompt_tokens = raw["input_tokens"]
            usage.completion_tokens = raw["output_tokens"]
            details = raw.get("input_tokens_details", {})
            usage.cached_input_tokens = details.get("cached_tokens")
            usage.cache_write_tokens = details.get("cache_write_tokens")
            usage.reasoning_tokens = raw.get("output_tokens_details", {}).get("reasoning_tokens")
            if (usage.cached_input_tokens or 0) + (
                usage.cache_write_tokens or 0
            ) > usage.prompt_tokens:
                raise ValueError("Input token breakdown exceeds total")
            if (usage.reasoning_tokens or 0) > usage.completion_tokens:
                raise ValueError("Reasoning count exceeds output total")
            usage.cost_usd = self._cost(raw)
            known = True
            usage.latency_seconds = perf_counter() - start
            if self.spend is not None and reservation is not None:
                if usage.cost_usd is None:
                    raise ValueError("Missing audited pricing details")
                self.spend.settle(reservation, usage)
                reservation = None
                if (
                    usage.prompt_tokens != counted_input
                    or usage.completion_tokens > request.max_output_tokens
                    or body.get("service_tier", "default") != "default"
                ):
                    self.spend.halt("Provider count/output/tier differed from preflight contract")
                    raise ValueError("Provider preflight contract mismatch")
            if body["status"] != "completed":
                raise ValueError("Model response was not completed")
            text_parts: list[str] = []
            for output in body["output"]:
                if output["type"] == "message":
                    for part in output["content"]:
                        if part["type"] == "refusal":
                            raise ValueError("Model refused the request")
                        if part["type"] == "output_text":
                            text_parts.append(part["text"])
            if not text_parts:
                raise ValueError("Model response contained no text")
            usage.latency_seconds = perf_counter() - start
            result = ModelResponse(
                text="".join(text_parts),
                model=body["model"],
                usage=usage,
                metadata={
                    "token_measurement": "provider-reported",
                    "response_id": body["id"],
                    "seed_supported": False,
                    "reasoning_effort": self.config.reasoning_effort,
                    "service_tier": body.get("service_tier", "default"),
                    "preflight_input_tokens": counted_input,
                    "cached_input_tokens": raw.get("input_tokens_details", {}).get(
                        "cached_tokens", 0
                    ),
                },
            )
            if self.spend is not None:
                result.metadata["cumulative_project_cost_usd"] = str(
                    self.spend.report()["cumulative_project_cost_usd"]
                )
                result.metadata["model_cache_hit"] = False
                self.spend.cache(cache_key, result)
            return result
        except SpendStopped as exc:
            usage.latency_seconds = perf_counter() - start
            raise ProviderBudgetExceeded(str(exc), usage, usage_complete=True) from None
        except ProviderBudgetExceeded:
            raise
        except asyncio.CancelledError:
            if self.spend is not None:
                self.spend.halt(
                    "Cancelled API attempt; any pending maximum charge remains reserved"
                )
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if self.spend is not None and reservation is not None:
                self.spend.halt("API failure with uncertain charge; maximum reservation retained")
            usage.latency_seconds = perf_counter() - start
            # Do not serialize HTTP headers, API keys, or vendor error bodies into traces.
            raise ProviderError(
                f"OpenAI response failed ({type(exc).__name__})", usage, usage_complete=known
            ) from None

    def _cost(self, raw: dict[str, Any]) -> Decimal | None:
        cfg = self.config
        if cfg.input_usd_per_million is None or cfg.output_usd_per_million is None:
            return None
        details = raw.get("input_tokens_details", {})
        cached = details.get("cached_tokens", 0)
        writes = details.get("cache_write_tokens", 0)
        if cached and cfg.cached_input_usd_per_million is None:
            return None
        if writes and cfg.cache_write_usd_per_million is None:
            return None
        if self.spend is not None and (
            "cached_tokens" not in details or "cache_write_tokens" not in details
        ):
            return None
        ttl = details.get("cache_write_tokens_details", {})
        if ttl.get("ttl_12h_tokens", 0):
            raise ValueError("Unexpected cache TTL outside audited rate card")
        ordinary = raw["input_tokens"] - cached - writes
        if ordinary < 0:
            raise ValueError("Invalid overlapping input-token counts")
        return (
            Decimal(ordinary) * cfg.input_usd_per_million
            + Decimal(cached) * (cfg.cached_input_usd_per_million or Decimal(0))
            + Decimal(writes) * (cfg.cache_write_usd_per_million or Decimal(0))
            + Decimal(raw["output_tokens"]) * cfg.output_usd_per_million
        ) / Decimal(1_000_000)
