"""Async provider-neutral boundaries. Implementations own transport and credentials."""

from typing import Annotated, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, Field, JsonValue

from epistemic_search.models import Count, Schema, Source, Text, Usage

Output = TypeVar("Output", bound=BaseModel)


class ModelRequest(Schema):
    prompt: Text
    model: Text
    prompt_version: Text
    max_output_tokens: Annotated[int, Field(strict=True, gt=0)]
    seed: Count = 0
    output_schema: dict[str, JsonValue] | None = None


class ModelResponse(Schema):
    text: str
    model: Text
    usage: Usage

    def parse(self, schema: type[Output]) -> Output:
        """Every structured response must pass validation before domain use."""
        return schema.model_validate_json(self.text)


class SearchResult(Schema):
    source: Source
    text: str
    query: Text
    rank: Annotated[int, Field(strict=True, ge=1)]
    retrieval_score: Annotated[float, Field(allow_inf_nan=False)] | None = None


class SearchResponse(Schema):
    results: list[SearchResult]
    usage: Usage


@runtime_checkable
class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...


@runtime_checkable
class SearchProvider(Protocol):
    async def search(self, query: str, k: int) -> SearchResponse: ...
