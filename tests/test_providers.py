import asyncio
from decimal import Decimal
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError

from epistemic_search.models import Claim, Source, Usage
from epistemic_search.providers import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    SearchProvider,
    SearchResponse,
    SearchResult,
)


def test_model_provider_mock_validates_structured_output() -> None:
    mock = create_autospec(ModelProvider, instance=True)
    request = ModelRequest(
        prompt="Return a claim",
        model="fixture",
        prompt_version="v1",
        max_output_tokens=50,
        output_schema=Claim.model_json_schema(),
    )
    response = ModelResponse(
        text='{"id":"c1","text":"A claim"}',
        model="fixture",
        usage=Usage(model_calls=1, cost_usd=Decimal(0)),
    )
    mock.complete.return_value = response
    provider: ModelProvider = mock
    result = asyncio.run(provider.complete(request))
    mock.complete.assert_awaited_once_with(request)
    assert result.parse(Claim).id == "c1"
    assert ModelResponse.model_validate_json(result.model_dump_json()) == response
    assert ModelRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize(
    "text", ["not JSON", '{"id":"c1"}', '{"id":"c1","text":"Claim","importance":2}']
)
def test_invalid_model_output_fails_validation(text: str) -> None:
    response = ModelResponse(text=text, model="fixture", usage=Usage(model_calls=1))
    with pytest.raises(ValidationError):
        response.parse(Claim)


@pytest.mark.parametrize("empty", [False, True])
def test_search_provider_mock_records_empty_search_costs(source: Source, empty: bool) -> None:
    mock = create_autospec(SearchProvider, instance=True)
    results = [] if empty else [SearchResult(source=source, text="Evidence", query="query", rank=1)]
    response = SearchResponse(
        results=results, usage=Usage(search_calls=1, documents=len(results), cost_usd=Decimal(0))
    )
    mock.search.return_value = response
    provider: SearchProvider = mock
    result = asyncio.run(provider.search("query", 3))
    mock.search.assert_awaited_once_with("query", 3)
    assert result.usage.search_calls == 1
    assert result.usage.documents == len(results)
    assert SearchResponse.model_validate_json(result.model_dump_json()) == response
