import asyncio
import json
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from epistemic_search.adapters import FixtureModelProvider, FixtureSearchProvider
from epistemic_search.baseline import IterativeStep, run_baseline
from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.models import QueryCase
from epistemic_search.providers import SearchProvider, SearchResponse

SEARCH = '{"action":"SEARCH_MORE","query":"France Paris","answer":null,"citation_ids":[]}'
ANSWER = '{"action":"ANSWER","query":null,"answer":"Paris","citation_ids":["s-paris"]}'


def test_iterative_retrieves_model_query_and_retains_all_usage() -> None:
    config = load_config(Path("configs/iterative_fixture.yaml"))
    search = FixtureSearchProvider.from_path(Path("tests/fixtures/corpus.json"))
    result = asyncio.run(
        run_baseline(
            QueryCase(id="q", question="capital"),
            config,
            search,
            FixtureModelProvider([SEARCH, ANSWER]),
        )
    )
    assert result.status == "completed"
    assert result.method == "iterative_rag"
    assert result.output is not None and result.output.answer == "Paris"
    assert result.usage.search_calls == result.usage.model_calls == 2
    queries = [
        SearchResponse.model_validate(event.payload).results[0].query
        for event in result.trace
        if event.type == "SEARCH"
    ]
    assert queries == ["capital", "France Paris"]
    assert [
        IterativeStep.model_validate(e.payload["step"]).action
        for e in result.trace
        if e.type == "DECISION"
    ] == [
        "SEARCH_MORE",
        "ANSWER",
    ]
    assert result.usage.documents == 3  # Repeated source retrieval is still charged.
    assert len(result.sources) == 2  # Context deduplicates by stable source ID.
    assert result.usage.retrieved_tokens > 0


@pytest.mark.parametrize(
    "bound", ["max_rounds", "max_search_calls", "max_llm_calls", "max_documents"]
)
def test_iterative_loop_is_bounded(bound: str) -> None:
    config = load_config(Path("configs/iterative_fixture.yaml"))
    assert config.rag is not None
    if bound == "max_rounds":
        config.rag.max_rounds = 1
    else:
        setattr(config.budget, bound, 1)
    result = asyncio.run(
        run_baseline(
            QueryCase(id="q", question="France"),
            config,
            FixtureSearchProvider.from_path(Path("tests/fixtures/corpus.json")),
            FixtureModelProvider([SEARCH, SEARCH, SEARCH]),
        )
    )
    assert result.status == "budget_exhausted"
    assert result.usage.model_calls == result.usage.search_calls == 1


def test_cumulative_output_budget_not_reset_per_round() -> None:
    config = load_config(Path("configs/iterative_fixture.yaml"))
    config.budget.max_total_llm_output_tokens = 2  # SEARCH has two whitespace tokens.
    result = asyncio.run(
        run_baseline(
            QueryCase(id="q", question="France"),
            config,
            FixtureSearchProvider.from_path(Path("tests/fixtures/corpus.json")),
            FixtureModelProvider([SEARCH, ANSWER]),
        )
    )
    assert result.status == "budget_exhausted"
    assert result.usage.model_calls == 1


def test_model_abstains_without_an_answer() -> None:
    result = asyncio.run(
        run_baseline(
            QueryCase(id="q", question="unknownword"),
            load_config(Path("configs/iterative_fixture.yaml")),
            FixtureSearchProvider.from_path(Path("tests/fixtures/corpus.json")),
            FixtureModelProvider(
                ['{"action":"ABSTAIN","query":null,"answer":null,"citation_ids":[]}']
            ),
        )
    )
    assert result.status == "completed"
    assert result.output is not None and result.output.answer is None


@pytest.mark.parametrize(
    "data",
    [
        {"action": "SEARCH_MORE", "query": None, "answer": None, "citation_ids": []},
        {"action": "ANSWER", "query": "another query", "answer": "Paris", "citation_ids": ["s"]},
        {"action": "ABSTAIN", "query": None, "answer": "Paris", "citation_ids": ["s"]},
    ],
)
def test_invalid_steps_are_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        IterativeStep.model_validate(data)


def test_timeout_stops_loop_and_marks_incomplete_usage() -> None:
    config = load_config(Path("configs/iterative_fixture.yaml"))
    config.budget.max_latency_seconds = 0.01
    search = create_autospec(SearchProvider, instance=True)

    async def stalled(query: str, k: int) -> None:
        await asyncio.sleep(1)

    search.search.side_effect = stalled
    result = asyncio.run(
        run_baseline(
            QueryCase(id="q", question="France"), config, search, FixtureModelProvider([ANSWER])
        )
    )
    assert result.status == "error" and not result.usage_complete
    assert result.usage.search_calls == 1 and result.usage.model_calls == 0
    search.search.assert_awaited_once()


def test_iterative_cli(tmp_path: Path) -> None:
    path = tmp_path / "iterative.json"
    result = CliRunner().invoke(
        app, ["run", "configs/iterative_fixture.yaml", "tests/fixtures/query.json", str(path)]
    )
    assert result.exit_code == 0, result.output
    run = json.loads(path.read_text())
    assert run["method"] == "iterative_rag"
    assert run["usage"]["search_calls"] == 2
