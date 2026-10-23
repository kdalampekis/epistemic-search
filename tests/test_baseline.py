import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import create_autospec

import httpx
import pytest
from typer.testing import CliRunner

from epistemic_search.adapters import (
    FixtureModelProvider,
    FixtureSearchProvider,
    OpenAIModelProvider,
)
from epistemic_search.baseline import Answer, run_naive
from epistemic_search.cli import app
from epistemic_search.config import RagConfig, RunConfig, load_config
from epistemic_search.models import QueryCase, Usage
from epistemic_search.providers import ModelProvider, ModelRequest, ProviderError


def fixture_search() -> FixtureSearchProvider:
    return FixtureSearchProvider.from_path(Path("tests/fixtures/corpus.json"))


def test_deterministic_full_run_and_no_gold_leak() -> None:
    case = QueryCase(id="q1", question="capital France", gold_answer="SECRET_GOLD")
    config = load_config(Path("configs/naive_fixture.yaml"))

    def run() -> str:
        result = asyncio.run(
            run_naive(
                case,
                config,
                fixture_search(),
                FixtureModelProvider.from_path(Path("tests/fixtures/responses.json")),
                clock=lambda: datetime(2026, 10, 23, tzinfo=UTC),
                timer=lambda: 0.0,
            )
        )
        assert result.status == "completed"
        assert result.output == Answer(answer="Paris", citation_ids=["s-paris"])
        assert result.usage.search_calls == result.usage.model_calls == 1
        assert result.usage.cost_usd == Decimal(0)
        assert result.usage.prompt_tokens > result.usage.context_tokens > 0
        assert "SECRET_GOLD" not in result.model_dump_json()
        assert len(result.sources) == 2
        return result.model_dump_json()

    assert run() == run()


@pytest.mark.parametrize(
    "output",
    [
        "broken JSON",
        '{"answer":"Paris","citation_ids":["fake"]}',
        '{"answer":"Paris","citation_ids":[]}',
    ],
)
def test_invalid_answers_preserve_usage(output: str) -> None:
    result = asyncio.run(
        run_naive(
            QueryCase(id="q", question="France"),
            load_config(Path("configs/naive_fixture.yaml")),
            fixture_search(),
            FixtureModelProvider([output]),
        )
    )
    assert result.status == "error"
    assert result.usage.model_calls == 1
    assert result.usage.completion_tokens > 0
    assert result.trace[-1].type == "MODEL"


def test_empty_search_abstains_without_losing_search_call() -> None:
    result = asyncio.run(
        run_naive(
            QueryCase(id="q", question="unknownword"),
            load_config(Path("configs/naive_fixture.yaml")),
            fixture_search(),
            FixtureModelProvider(['{"answer":null,"citation_ids":[]}']),
        )
    )
    assert result.output is not None and result.output.answer is None
    assert result.sources == []
    assert result.usage.search_calls == 1


def test_model_failure_is_recorded() -> None:
    model = create_autospec(ModelProvider, instance=True)
    model.complete.side_effect = ProviderError("timeout", Usage(model_calls=1))
    result = asyncio.run(
        run_naive(
            QueryCase(id="q", question="France"),
            load_config(Path("configs/naive_fixture.yaml")),
            fixture_search(),
            model,
        )
    )
    assert result.status == "error" and not result.usage_complete
    assert result.usage.model_calls == result.usage.search_calls == 1
    assert result.usage.cost_usd is None


@pytest.mark.parametrize(
    "budget",
    [
        {"max_search_calls": 0},
        {"max_llm_calls": 0},
        {"max_total_llm_input_tokens": 1},
        {"max_retrieved_tokens": 0},
    ],
)
def test_budget_blocks_calls(budget: dict[str, int]) -> None:
    config = RunConfig.model_validate(
        {
            "run_id": "test",
            "budget": budget,
            "rag": {"corpus_path": "unused", "responses_path": "unused"},
        }
    )
    model = create_autospec(ModelProvider, instance=True)
    result = asyncio.run(
        run_naive(QueryCase(id="q", question="France"), config, fixture_search(), model)
    )
    assert result.status == "budget_exhausted"
    model.complete.assert_not_called()


def test_search_ties_top_k_and_unique_ids() -> None:
    provider = fixture_search()
    result = asyncio.run(provider.search("capital", 1))
    assert result.results[0].source.id == "s-athens"
    with pytest.raises(ValueError, match="unique"):
        FixtureSearchProvider([provider.documents[0], provider.documents[0]])


def test_cli_run_and_refuse_overwrite(tmp_path: Path) -> None:
    args = [
        "run-naive",
        "configs/naive_fixture.yaml",
        "tests/fixtures/query.json",
        str(tmp_path / "run.json"),
    ]
    runner = CliRunner()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    saved = (tmp_path / "run.json").read_text()
    assert json.loads(saved)["output"]["answer"] == "Paris"
    assert runner.invoke(app, args).exit_code == 1
    assert (tmp_path / "run.json").read_text() == saved


@pytest.mark.parametrize("mode", ["success", "http_error", "refusal", "incomplete", "malformed"])
def test_openai_adapter_offline(mode: str) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert "seed" not in payload
        assert payload["text"]["format"]["strict"] is True
        if mode == "http_error":
            return httpx.Response(429, json={"error": "secret server detail"})
        if mode == "malformed":
            return httpx.Response(200, json={})
        part = (
            {"type": "refusal", "refusal": "no"}
            if mode == "refusal"
            else {"type": "output_text", "text": '{"answer":"Paris","citation_ids":["s-paris"]}'}
        )
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "test-model",
                "status": "incomplete" if mode == "incomplete" else "completed",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "input_tokens_details": {"cached_tokens": 10},
                },
                "output": [{"type": "message", "content": [part]}],
            },
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            cfg = RagConfig(
                corpus_path=Path("unused"),
                backend="openai",
                model="test-model",
                input_usd_per_million=Decimal("1"),
                cached_input_usd_per_million=Decimal("0.5"),
                output_usd_per_million=Decimal("2"),
            )
            provider = OpenAIModelProvider(client, "test-key", cfg)
            request = ModelRequest(
                prompt="test",
                model="test-model",
                prompt_version="v1",
                max_output_tokens=100,
                output_schema=Answer.model_json_schema(),
            )
            if mode == "success":
                response = await provider.complete(request)
                assert response.parse(Answer).answer == "Paris"
                assert response.usage.cost_usd == Decimal("0.000135")
                assert response.usage.prompt_tokens == 100
            else:
                with pytest.raises(ProviderError) as caught:
                    await provider.complete(request)
                assert caught.value.usage.model_calls == 1
                assert "test-key" not in str(caught.value)
                assert caught.value.usage_complete == (mode in {"refusal", "incomplete"})

    asyncio.run(run())
    assert len(calls) == 1
