import asyncio
import json
from decimal import Decimal
from pathlib import Path

from test_engine import DRAFT, StuckSearch

from epistemic_search.comparators import run_comparator
from epistemic_search.config import RunConfig
from epistemic_search.models import QueryCase, Source, Usage
from epistemic_search.providers import ModelRequest, ModelResponse, SearchResponse, SearchResult
from epistemic_search.tokens import count_tokens


def config(rounds: int) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": "po",
            "method": "premise_only",
            "rag": {
                "corpus_path": "unused",
                "responses_path": "unused",
                "k": 1,
                "max_rounds": rounds,
                "max_output_tokens": 256,
            },
            "decomposition": {"cache_dir": "unused"},
            "budget": {"max_search_calls": 8, "max_llm_calls": 30, "max_documents": 8},
        }
    )


class SameTargetModel:
    """Decomposes, then always asks to search the 'Beta holds.' premise."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        if request.prompt_version == "premise-decomposition-v1":
            text = json.dumps(DRAFT)
        else:
            payload = json.loads(request.prompt.split("\nPayload:\n")[1])
            beta = next(c["id"] for c in payload["premises"] if c["text"] == "Beta holds.")
            text = json.dumps(
                {
                    "action": "SEARCH_MORE",
                    "target_claim_id": beta,
                    "answer": None,
                    "citation_ids": [],
                }
            )
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


class FreshDocumentSearch:
    """Every search returns a new document, so repeating the query still makes progress."""

    def __init__(self, source: Source) -> None:
        self.source = source
        self.queries: list[str] = []

    async def search(self, query: str, k: int) -> SearchResponse:
        self.queries.append(query)
        source = self.source.model_copy(update={"id": f"s{len(self.queries)}"})
        return SearchResponse(
            results=[SearchResult(source=source, text="Alpha holds.", query=query, rank=1)],
            usage=Usage(search_calls=1, documents=1, retrieved_tokens=2, cost_usd=Decimal(0)),
        )


def test_premise_only_stops_when_the_same_query_returns_nothing_new(
    tmp_path: Path, source: Source
) -> None:
    search = StuckSearch(source)
    result = asyncio.run(
        run_comparator(
            QueryCase(id="q", question="Are both conditions met?"),
            config(5),
            search,
            SameTargetModel(),
            tmp_path,
        )
    )
    assert result.status == "completed" and result.error is None
    assert len(search.queries) == 2
    assert result.output is not None and result.output.answer is None
    event = next(e for e in result.trace if e.type == "NO_PROGRESS")
    assert event.payload["new_documents"] == [] and event.payload["target_unchanged"] is True


def test_premise_only_keeps_searching_while_documents_are_new(
    tmp_path: Path, source: Source
) -> None:
    search = FreshDocumentSearch(source)
    result = asyncio.run(
        run_comparator(
            QueryCase(id="q", question="Are both conditions met?"),
            config(4),
            search,
            SameTargetModel(),
            tmp_path,
        )
    )
    assert len(search.queries) == 4
    assert not any(e.type == "NO_PROGRESS" for e in result.trace)
