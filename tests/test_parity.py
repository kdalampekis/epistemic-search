import asyncio
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from typer.testing import CliRunner

from epistemic_search.accounting import UsageLedger
from epistemic_search.adapters import FixtureModelProvider, FixtureSearchProvider
from epistemic_search.baseline import Answer, MemoryAnswer, RunResult
from epistemic_search.budgeting import GuardedModel, RunAccounting
from epistemic_search.cli import app
from epistemic_search.comparators import PremiseStep, run_comparator
from epistemic_search.config import Method, RunConfig, load_config
from epistemic_search.execution import execute_case
from epistemic_search.models import QueryCase, Usage
from epistemic_search.parity import METHODS, compare, comparison_configs
from epistemic_search.providers import ModelProvider, ModelRequest, ModelResponse, SearchProvider


def config_for(tmp_path: Path) -> RunConfig:
    config = load_config(Path("configs/parity_fixture.yaml"))
    assert config.rag is not None and config.evaluation is not None
    config.rag.corpus_path = Path("tests/fixtures/epistemic_corpus.json").resolve()
    config.rag.responses_path = Path("tests/fixtures/parity_responses.json").resolve()
    config.evaluation.dataset_path = Path("tests/fixtures/epistemic_benchmark.jsonl").resolve()
    config.evaluation.output_dir = tmp_path / "comparison"
    assert config.decomposition is not None
    config.decomposition.cache_dir = tmp_path / "cache"
    return config


def test_five_methods_share_protocol_and_charge_cold_decomposition(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    assert config.evaluation is not None
    # Same question twice must not give the second case free cached decomposition.
    row = json.loads(config.evaluation.dataset_path.read_text())
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(json.dumps(row) + "\n" + json.dumps({**row, "id": "second"}) + "\n")
    config.evaluation.dataset_path = dataset
    configs = comparison_configs(config, tmp_path)
    assert set(configs) == set(METHODS)
    assert all(c.rag == config.rag and c.budget == config.budget for c in configs.values())
    summaries = asyncio.run(compare(config, tmp_path))
    expected_calls = dict(zip(METHODS, [2, 2, 2, 4, 8], strict=True))
    assert {m: s.usage.model_calls for m, s in summaries.items()} == expected_calls
    assert summaries["closed_book"].usage.search_calls == 0
    assert all(s.examples == 2 and s.errors == 0 and s.exact_match == 1 for s in summaries.values())
    root = config.evaluation.output_dir
    manifest = json.loads((root / "comparison-manifest.json").read_text())
    assert manifest["fixture_only"] is True
    assert manifest["cache_policy"].startswith("cold-per-method-per-case")
    assert json.loads((root / "comparison.json").read_text())["complete"] is True
    for method in METHODS:
        result = RunResult.model_validate_json((root / method / "traces/000000.json").read_text())
        ledger = UsageLedger()
        for event in result.trace:
            ledger.record(event)
        assert ledger.total() == result.usage  # No double charging through nested wrappers.
        if method != "epistemic_search":
            assert result.state is None
        method_manifest = json.loads((root / method / "manifest.json").read_text())
        assert method_manifest["selected_case_ids"] == manifest["selected_case_ids"]
        assert method_manifest["input_hashes"] == manifest["dataset_hashes"]
    with pytest.raises(FileExistsError):
        asyncio.run(compare(config, tmp_path))


@pytest.mark.parametrize("method", METHODS)
def test_zero_model_budget_is_enforced_by_every_method(tmp_path: Path, method: Method) -> None:
    config = config_for(tmp_path)
    config.method = method
    config.budget.max_llm_calls = 0
    result = asyncio.run(execute_case(QueryCase(id="q", question="France"), config, tmp_path))
    assert result.status == "budget_exhausted"
    assert result.usage.model_calls == result.usage.search_calls == 0


def test_closed_book_does_not_call_search_or_fabricate_citations(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    config.method = "closed_book"
    search = create_autospec(SearchProvider, instance=True)
    result = asyncio.run(
        run_comparator(
            QueryCase(id="q", question="capital?", gold_answer="DO_NOT_LEAK"),
            config,
            search,
            FixtureModelProvider(['{"answer":"Paris"}']),
            tmp_path,
        )
    )
    search.search.assert_not_called()
    assert result.output == MemoryAnswer(answer="Paris")
    assert not result.sources and result.usage.context_tokens == result.usage.retrieved_tokens == 0
    assert "DO_NOT_LEAK" not in result.model_dump_json()
    with pytest.raises(ValueError, match="cited-answer"):
        RunResult(
            query_id="q",
            method="naive_rag",
            status="completed",
            output=MemoryAnswer(answer="Paris"),
            usage=Usage(),
            wall_seconds=0,
            trace=[],
        )
    with pytest.raises(ValueError, match="ungrounded"):
        RunResult(
            query_id="q",
            method="closed_book",
            status="completed",
            output=Answer(answer="Paris", citation_ids=["fake"]),
            usage=Usage(),
            wall_seconds=0,
            trace=[],
        )


def test_premise_only_targets_a_claim_without_belief_or_formal_reasoning(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    config.method = "premise_only"
    draft = json.loads(Path("tests/fixtures/parity_responses.json").read_text())[
        "premise-decomposition-v1"
    ][0]
    calls: list[ModelRequest] = []
    model = create_autospec(ModelProvider, instance=True)

    async def complete(request: ModelRequest) -> ModelResponse:
        calls.append(request)
        if request.prompt_version == "premise-decomposition-v1":
            text = draft
        else:
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            assert "beliefs" not in payload and "proof_graph" not in payload
            target = payload["premises"][0]["id"]
            text = json.dumps(
                {
                    "action": "SEARCH_MORE" if len(calls) == 2 else "ANSWER",
                    "target_claim_id": target if len(calls) == 2 else None,
                    "answer": None if len(calls) == 2 else "Paris; yes.",
                    "citation_ids": [] if len(calls) == 2 else ["facts"],
                }
            )
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, prompt_tokens=1, completion_tokens=1, cost_usd=Decimal(0)),
        )

    model.complete.side_effect = complete
    result = asyncio.run(
        run_comparator(
            QueryCase(id="q", question="capital France?"),
            config,
            FixtureSearchProvider.from_path(Path("tests/fixtures/epistemic_corpus.json")),
            model,
            tmp_path / "cache",
        )
    )
    assert result.status == "completed", result.error
    assert result.usage.model_calls == 3 and result.usage.search_calls == 2
    assert result.state is None
    assert sum(e.type == "QUERY_GENERATED" for e in result.trace) == 1
    assert not {e.type for e in result.trace} & {"BELIEF_UPDATE", "SUFFICIENCY", "EVIDENCE_ADDED"}


@pytest.mark.parametrize(
    "step",
    [
        {"action": "SEARCH_MORE", "target_claim_id": None, "answer": None, "citation_ids": []},
        {"action": "ANSWER", "target_claim_id": None, "answer": None, "citation_ids": []},
        {"action": "ABSTAIN", "target_claim_id": "c", "answer": None, "citation_ids": []},
    ],
)
def test_premise_step_validation(step: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PremiseStep.model_validate(step)


def test_common_guard_caps_output_to_remaining_budget(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    config.budget.max_total_llm_output_tokens = 5
    run = RunAccounting("q", config)
    run.add("PRIOR", {}, Usage(completion_tokens=3, cost_usd=Decimal(0)))
    model = create_autospec(ModelProvider, instance=True)
    model.complete.return_value = ModelResponse(
        text="ok",
        model="fixture",
        usage=Usage(model_calls=1, completion_tokens=1, cost_usd=Decimal(0)),
    )
    request = ModelRequest(prompt="q", model="fixture", prompt_version="v", max_output_tokens=20)
    asyncio.run(GuardedModel(model, run).complete(request))
    actual = model.complete.call_args.args[0]
    assert actual.max_output_tokens == 2
    assert request.max_output_tokens == 20
    assert run.ledger.total().completion_tokens == 4


def test_missing_credentials_and_unbounded_configs_fail_before_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_for(tmp_path)
    config.budget.max_llm_calls = None
    with pytest.raises(ValueError, match="finite max_llm_calls"):
        comparison_configs(config, tmp_path)
    config.budget.max_llm_calls = 16
    assert config.rag is not None
    config.rag.model = "configured-model"
    config.rag.backend = "openai"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(compare(config, tmp_path))
    assert not (tmp_path / "comparison").exists()


def test_compare_cli(tmp_path: Path) -> None:
    import yaml

    config = config_for(tmp_path)
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")))
    result = CliRunner().invoke(app, ["compare", str(path)])
    assert result.exit_code == 0, result.output
    assert all(method in result.output for method in METHODS)


def test_failed_method_is_retained_and_other_methods_still_run(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    assert config.rag is not None and config.rag.responses_path is not None
    script = json.loads(config.rag.responses_path.read_text())
    script["closed-book-answer-v1"] = ["invalid JSON"]
    responses = tmp_path / "script.json"
    responses.write_text(json.dumps(script))
    config.rag.responses_path = responses
    summaries = asyncio.run(compare(config, tmp_path))
    assert len(summaries) == 5
    assert summaries["closed_book"].errors == 1
    assert summaries["closed_book"].exact_match == 0
    assert summaries["closed_book"].usage.model_calls == 1
    assert summaries["epistemic_search"].errors == 0
