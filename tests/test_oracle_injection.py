import asyncio
from pathlib import Path

from test_rv2_adapters import eb_fixture

from epistemic_search.adapters import FixtureModelProvider
from epistemic_search.config import RunConfig
from epistemic_search.decomposition import ORACLE_KEY, decompose
from epistemic_search.models import QueryCase
from epistemic_search.rv2_adapters import eb_proof_graph, load_entailmentbank


def config() -> RunConfig:
    return RunConfig.model_validate(
        {"run_id": "r", "rag": {"corpus_path": "u", "responses_path": "u"}}
    )


def test_an_oracle_graph_replaces_the_model_call_and_nothing_else(tmp_path: Path) -> None:
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path), "dev")}["t1"]
    graph, _ = eb_proof_graph(ex)
    assert graph is not None
    model = FixtureModelProvider([])  # any model call would fail: no scripted responses
    case = QueryCase(id="c", question="q", metadata={ORACLE_KEY: graph.model_dump(mode="json")})
    result = asyncio.run(decompose(case, config(), model, tmp_path / "cache"))
    assert result.graph == graph and result.response is None and result.error is None
    assert result.request.prompt_version == "oracle-decomposition-injected-v1"
    assert result.usage.model_calls == 0 and not (tmp_path / "cache").exists()


def test_without_an_oracle_the_normal_path_is_taken(tmp_path: Path) -> None:
    case = QueryCase(id="c", question="q")
    result = asyncio.run(decompose(case, config(), FixtureModelProvider(["not json"]), tmp_path))
    assert result.graph is None and result.error is not None  # model path, parse failure
    assert result.request.prompt_version == "premise-decomposition-v1"
