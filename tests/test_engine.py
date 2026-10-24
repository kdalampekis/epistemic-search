import asyncio
import json
from decimal import Decimal
from pathlib import Path

import pytest

from epistemic_search.config import RunConfig
from epistemic_search.conflicts import inspect_conflicts
from epistemic_search.engine import run_epistemic
from epistemic_search.models import QueryCase, Source, Usage
from epistemic_search.providers import ModelRequest, ModelResponse, SearchResponse, SearchResult
from epistemic_search.tokens import count_tokens

DRAFT = {
    "claims": [
        {"id": "a", "text": "Alpha holds.", "polarity": "POSITIVE"},
        {"id": "b", "text": "Beta holds.", "polarity": "POSITIVE"},
    ],
    "nodes": [
        {"id": "a", "kind": "CLAIM", "claim_id": "a", "children": []},
        {"id": "b", "kind": "CLAIM", "claim_id": "b", "children": []},
        {"id": "both", "kind": "AND", "claim_id": None, "children": ["a", "b"]},
        {"id": "root", "kind": "CONCLUSION", "claim_id": None, "children": ["both"]},
    ],
    "conclusion_id": "root",
}


def config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": "mvp",
            "method": "epistemic_search",
            "rag": {
                "corpus_path": "unused",
                "responses_path": "unused",
                "k": 1,
                "max_rounds": 2,
                "max_output_tokens": 256,
            },
            "budget": {
                "max_search_calls": 3,
                "max_llm_calls": 20,
                "max_documents": 3,
                "max_total_llm_output_tokens": 4096,
            },
        }
    )


class ScenarioSearch:
    def __init__(self, scenario: str, source: Source) -> None:
        self.scenario, self.source = scenario, source
        self.queries: list[str] = []

    async def search(self, query: str, k: int) -> SearchResponse:
        self.queries.append(query)
        if len(self.queries) == 1:
            text = "Alpha holds. Beta holds." if self.scenario == "A" else "Alpha holds."
            if self.scenario == "D":
                text += " Beta holds. Beta fails."
        else:
            text = "Unrelated text." if self.scenario == "C" else "Beta holds."
        source = self.source.model_copy(deep=True)
        source.id = f"source-{len(self.queries)}"
        source.uri = f"fixture://{source.id}"
        return SearchResponse(
            results=[SearchResult(source=source, text=text, query=query, rank=1)],
            usage=Usage(
                search_calls=1,
                documents=1,
                retrieved_tokens=count_tokens(text),
                cost_usd=Decimal(0),
            ),
        )


class ScenarioModel:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.prompt_version)
        if request.prompt_version == "premise-decomposition-v1":
            text = json.dumps(DRAFT)
        elif request.prompt_version == "evidence-stance-v1":
            data = json.loads(request.prompt[request.prompt.index('{"claim"') :])
            items = []
            if data["claim"] in data["document"]:
                items.append({"span": data["claim"], "stance": "SUPPORT", "stance_score": 0.8})
            if data["claim"] == "Beta holds." and "Beta fails." in data["document"]:
                items.append({"span": "Beta fails.", "stance": "CONTRADICT", "stance_score": 0.8})
            text = json.dumps({"items": items})
        else:
            assert request.prompt_version == "epistemic-answer-v1"
            data = json.loads(request.prompt.split("\nPayload:\n")[1])
            citations = sorted(
                {source for item in data["evidence"] for source in item["source_ids"]}
            )
            text = json.dumps({"answer": "Both conditions hold.", "citation_ids": citations})
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(
                model_calls=1,
                prompt_tokens=count_tokens(request.prompt),
                completion_tokens=count_tokens(text),
                cost_usd=Decimal(0),
            ),
        )


@pytest.mark.parametrize(
    "scenario,decision,search_calls",
    [("A", "ANSWER", 1), ("B", "ANSWER", 2), ("C", "ABSTAIN", 2), ("D", "ABSTAIN", 2)],
)
def test_required_mvp_scenarios(
    tmp_path: Path, source: Source, scenario: str, decision: str, search_calls: int
) -> None:
    search, model = ScenarioSearch(scenario, source), ScenarioModel()
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="Are both conditions met?"),
            config(),
            search,
            model,
            tmp_path / "cache",
        )
    )
    assert result.error is None, result.error
    assert result.decision is not None and result.decision.action == decision
    assert result.usage.search_calls == len(search.queries) == search_calls
    assert result.usage.model_calls == len(model.calls)
    assert sum(e.usage.model_calls for e in result.trace) == len(model.calls)
    assert sum(e.usage.search_calls for e in result.trace) == search_calls
    assert result.state is not None and result.state.budget.used == result.usage
    if scenario != "A":
        assert search.queries[1].startswith("Beta holds.")
    if scenario == "C":
        assert result.decision.blocking_claims
    if scenario == "D":
        snapshots, blocking = inspect_conflicts(result)
        assert blocking is True and all(s.conflicts for s in snapshots)
        assert len([e for e in result.trace if e.type == "CONFLICT"]) == 2
        conflict = snapshots[0].conflicts[0]
        assert conflict.support_evidence_ids and conflict.contradiction_evidence_ids
        assert conflict.source_ids == ["source-1"]
        assert any(
            e.type == "DECISION" and e.payload.get("action") == "RESOLVE_CONFLICT"
            for e in result.trace
        )
        assert "for and against" in search.queries[1]


def test_answer_generation_cannot_escape_shared_budget(tmp_path: Path, source: Source) -> None:
    settings = config()
    settings.budget.max_llm_calls = 3
    model = ScenarioModel()
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="question"),
            settings,
            ScenarioSearch("A", source),
            model,
            tmp_path / "cache",
        )
    )
    assert result.status == "budget_exhausted"
    assert result.decision is not None and result.decision.action == "ABSTAIN"
    assert result.usage.model_calls == 3
    assert "epistemic-answer-v1" not in model.calls


def test_cache_hit_has_no_double_charge(tmp_path: Path, source: Source) -> None:
    case = QueryCase(id="q", question="question")
    first = asyncio.run(
        run_epistemic(case, config(), ScenarioSearch("A", source), ScenarioModel(), tmp_path)
    )
    second = asyncio.run(
        run_epistemic(case, config(), ScenarioSearch("A", source), ScenarioModel(), tmp_path)
    )
    assert first.usage.model_calls == second.usage.model_calls + 1
    assert first.output == second.output
    assert any(e.type == "DECOMPOSE" and e.payload["cache_hit"] is True for e in second.trace)


def test_timeout_attempt_is_not_lost_to_outer_timeout(tmp_path: Path, source: Source) -> None:
    class StalledModel:
        async def complete(self, request: ModelRequest) -> ModelResponse:
            await asyncio.sleep(1)
            raise AssertionError("should have timed out")

    settings = config()
    assert settings.rag is not None
    settings.rag.timeout_seconds = 0.01
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="question"),
            settings,
            ScenarioSearch("A", source),
            StalledModel(),
            tmp_path / "cache",
        )
    )
    assert result.status == "error" and not result.usage_complete
    assert result.usage.model_calls == 1
    assert result.usage.cost_usd is None
