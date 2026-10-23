"""Fixture providers and an optional OpenAI Responses adapter; no domain policy."""

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
    ProviderError,
    SearchResponse,
    SearchResult,
)
from epistemic_search.tokens import count_tokens


class CorpusDocument(Schema):
    source: Source
    text: str


class FixtureSearchProvider:
    def __init__(self, documents: list[CorpusDocument]) -> None:
        if len({d.source.id for d in documents}) != len(documents):
            raise ValueError("Corpus source IDs must be unique")
        self.documents = documents

    @classmethod
    def from_path(cls, path: Path) -> "FixtureSearchProvider":
        return cls(
            TypeAdapter(list[CorpusDocument]).validate_json(path.read_text(encoding="utf-8"))
        )

    async def search(self, query: str, k: int) -> SearchResponse:
        if k < 1 or not query.strip():
            raise ValueError("search requires a query and positive k")
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
        return SearchResponse(
            results=results,
            usage=Usage(
                search_calls=1,
                documents=len(results),
                retrieved_tokens=sum(count_tokens(r.text) for r in results),
                cost_usd=Decimal(0),
            ),
            metadata={"token_measurement": "whitespace-v1-estimate", "latency": "synthetic-zero"},
        )


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

    async def complete(self, request: ModelRequest) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": request.model,
            "input": request.prompt,
            "max_output_tokens": request.max_output_tokens,
            "store": False,
        }
        if request.output_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "research_output",
                    "schema": request.output_schema,
                    "strict": True,
                }
            }
        start = perf_counter()
        usage = Usage(model_calls=1)
        known = False
        try:
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
            usage.cost_usd = self._cost(raw)
            known = True
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
            return ModelResponse(
                text="".join(text_parts),
                model=body["model"],
                usage=usage,
                metadata={
                    "token_measurement": "provider-reported",
                    "response_id": body["id"],
                    "seed_supported": False,
                    "cached_input_tokens": raw.get("input_tokens_details", {}).get(
                        "cached_tokens", 0
                    ),
                },
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            usage.latency_seconds = perf_counter() - start
            # Do not serialize HTTP headers, API keys, or vendor error bodies into traces.
            raise ProviderError(
                f"OpenAI response failed ({type(exc).__name__})", usage, usage_complete=known
            ) from exc

    def _cost(self, raw: dict[str, Any]) -> Decimal | None:
        cfg = self.config
        if cfg.input_usd_per_million is None or cfg.output_usd_per_million is None:
            return None
        cached = raw.get("input_tokens_details", {}).get("cached_tokens", 0)
        if cached and cfg.cached_input_usd_per_million is None:
            return None
        return (
            Decimal(raw["input_tokens"] - cached) * cfg.input_usd_per_million
            + Decimal(cached) * (cfg.cached_input_usd_per_million or Decimal(0))
            + Decimal(raw["output_tokens"]) * cfg.output_usd_per_million
        ) / Decimal(1_000_000)
