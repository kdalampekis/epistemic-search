import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from epistemic_search.config import RunConfig
from epistemic_search.conflicts import inspect_conflicts
from epistemic_search.engine import run_epistemic
from epistemic_search.models import AcquisitionPolicy, QueryCase, Source, Usage
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
@pytest.mark.parametrize("policy", ["importance", "random", "uncertainty", "voi"])
def test_required_mvp_scenarios(
    tmp_path: Path,
    source: Source,
    scenario: str,
    decision: str,
    search_calls: int,
    policy: AcquisitionPolicy,
) -> None:
    search, model = ScenarioSearch(scenario, source), ScenarioModel()
    settings = config()
    settings.controller.policy = policy
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="Are both conditions met?"),
            settings,
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
    for item in result.trace:
        if item.type == "DECISION" and item.payload.get("acquisition"):
            selection = item.payload["acquisition"]
            assert isinstance(selection, dict) and selection["policy"] == policy
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


class SloppySpanModel(ScenarioModel):
    """Like the scripted model, but every extraction also returns a hallucinated span."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        response = await super().complete(request)
        if request.prompt_version == "evidence-stance-v1":
            items = json.loads(response.text)["items"]
            items.append({"span": "Gamma is invented.", "stance": "SUPPORT", "stance_score": 0.9})
            response.text = json.dumps({"items": items})
        return response


def test_v11_a_hallucinated_span_no_longer_aborts_the_question(
    tmp_path: Path, source: Source
) -> None:
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="Are both conditions met?"),
            config(),
            ScenarioSearch("A", source),
            SloppySpanModel(),
            tmp_path / "cache",
        )
    )
    assert result.error is None and result.decision is not None
    assert result.decision.action == "ANSWER" and result.output is not None
    added = [e for e in result.trace if e.type == "EVIDENCE_ADDED"]
    payloads: list[Any] = [e.payload for e in added]
    rejections = [r for payload in payloads for r in payload["rejections"]]
    assert rejections and all(r["span"] == "Gamma is invented." for r in rejections)
    assert all(payload["errors"] == [] for payload in payloads)
    assert result.state is not None
    assert all(item.span != "Gamma is invented." for item in result.state.evidence)


class NbspModel(ScenarioModel):
    """Returns spans with ordinary spaces, as a model reading the page would."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        if request.prompt_version != "evidence-stance-v1":
            return await super().complete(request)
        self.calls.append(request.prompt_version)
        data = json.loads(request.prompt[request.prompt.index('{"claim"') :])
        found = data["claim"] in data["document"].replace("\u00a0", " ")
        items = [{"span": data["claim"], "stance": "SUPPORT", "stance_score": 0.8}] * found
        text = json.dumps({"items": items})
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


class NbspSearch(ScenarioSearch):
    async def search(self, query: str, k: int) -> SearchResponse:
        response = await super().search(query, k)
        for r in response.results:
            r.text = r.text.replace("Alpha holds.", "Alpha holds.")
        return response


def test_v11_nbsp_difference_is_repaired_to_the_exact_source_text(
    tmp_path: Path, source: Source
) -> None:
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="Are both conditions met?"),
            config(),
            NbspSearch("A", source),
            NbspModel(),
            tmp_path / "cache",
        )
    )
    assert result.error is None and result.decision is not None
    assert result.decision.action == "ANSWER"
    assert result.state is not None
    repaired = [e for e in result.state.evidence if e.metadata.get("alignment") == "normalized"]
    assert repaired and all(" " in e.span for e in repaired)
    assert all(e.metadata["model_span"] == "Alpha holds." for e in repaired)


class StuckSearch:
    """A retriever that keeps returning the same document, however the query changes."""

    def __init__(self, source: Source) -> None:
        self.source = source
        self.queries: list[str] = []

    async def search(self, query: str, k: int) -> SearchResponse:
        self.queries.append(query)
        text = "Alpha holds."
        return SearchResponse(
            results=[SearchResult(source=self.source, text=text, query=query, rank=1)],
            usage=Usage(
                search_calls=1,
                documents=1,
                retrieved_tokens=count_tokens(text),
                cost_usd=Decimal(0),
            ),
        )


def long_config() -> RunConfig:
    settings = config()
    assert settings.rag is not None
    settings.rag.max_rounds = 5
    settings.budget.max_search_calls = 6
    settings.budget.max_documents = 6
    return settings


def test_v11_no_progress_guard_stops_a_repeated_search_loop(tmp_path: Path, source: Source) -> None:
    search = StuckSearch(source)
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="Are both conditions met?"),
            long_config(),
            search,
            ScenarioModel(),
            tmp_path / "cache",
        )
    )
    # search 1 (question) then one targeted search; the next proposal repeats it exactly.
    assert len(search.queries) == 2 and search.queries[1].startswith("Beta holds.")
    assert result.status == "completed" and result.error is None
    assert result.decision is not None and result.decision.action == "ABSTAIN"
    assert result.decision.rationale.startswith("NO_PROGRESS")
    event = next(e for e in result.trace if e.type == "NO_PROGRESS")
    assert event.payload["new_documents"] == [] and event.payload["state_unchanged"] is True
    assert result.decision.blocking_claims  # the unresolved premise is still reported


def test_v11_guard_does_not_fire_when_a_search_makes_progress(
    tmp_path: Path, source: Source
) -> None:
    search, model = ScenarioSearch("B", source), ScenarioModel()
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="Are both conditions met?"),
            long_config(),
            search,
            model,
            tmp_path / "cache",
        )
    )
    assert result.decision is not None and result.decision.action == "ANSWER"
    assert not any(e.type == "NO_PROGRESS" for e in result.trace)
    assert len(search.queries) == 2
