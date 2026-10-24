import asyncio
import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from test_engine import DRAFT, ScenarioModel, ScenarioSearch, config
from typer.testing import CliRunner

from epistemic_search.ablation_control import GenerativeControl
from epistemic_search.ablations import AblationPlan, variant_configs
from epistemic_search.cli import app
from epistemic_search.config import AblationConfig, load_config
from epistemic_search.decomposition import DecompositionDraft
from epistemic_search.engine import run_epistemic
from epistemic_search.models import AcquisitionEstimate, QueryCase, Source, Usage
from epistemic_search.providers import ModelRequest, ModelResponse, SearchResponse


class AblationModel(ScenarioModel):
    def __init__(self, *, null_answer: bool = False) -> None:
        super().__init__()
        self.requests: list[ModelRequest] = []
        self.null_answer = null_answer

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.prompt_version == "generative-control-v1":
            self.calls.append(request.prompt_version)
            return ModelResponse(
                model=request.model,
                text=GenerativeControl(
                    action="ANSWER",
                    target_claim_id=None,
                    required_stance=None,
                    rationale="Scripted judgment",
                ).model_dump_json(),
                usage=Usage(model_calls=1, prompt_tokens=1, completion_tokens=1, cost_usd=0),
            )
        if request.prompt_version in {"epistemic-forced-answer-v1", "epistemic-ablated-answer-v1"}:
            request = request.model_copy(update={"prompt_version": "epistemic-answer-v1"})
        response = await super().complete(request)
        if self.null_answer and request.prompt_version == "epistemic-answer-v1":
            response.text = '{"answer":null,"citation_ids":[]}'
        return response


def test_default_config_hash_compatibility_and_invalid_combinations() -> None:
    original = load_config(Path("configs/parity_fixture.yaml"))
    assert "ablation" not in original.model_dump()
    original.ablation.compact_evidence = False
    assert original.model_dump()["ablation"]["compact_evidence"] is False
    with pytest.raises(ValueError, match="one disabled"):
        AblationConfig(use_premise_graph=False, allow_abstention=False)
    with pytest.raises(ValueError):
        AblationConfig.model_validate({"compact_evidence": "false"})
    with pytest.raises(ValueError, match="VOI"):
        variant_configs(
            load_config(Path("configs/parity_fixture.yaml")), Path("unused"), ["compact_evidence"]
        )


def test_no_formal_uses_schema_validated_judge_without_reasoner(
    tmp_path: Path, source: Source
) -> None:
    settings = config()
    settings.ablation.use_formal_sufficiency = False
    model = AblationModel()
    with patch(
        "epistemic_search.engine.choose_action", side_effect=AssertionError("formal called")
    ):
        result = asyncio.run(
            run_epistemic(
                QueryCase(id="q", question="question", gold_answer="GOLD_LEAK"),
                settings,
                ScenarioSearch("A", source),
                model,
                tmp_path,
            )
        )
    assert result.status == "completed" and result.output and result.output.answer
    assert result.usage.model_calls == 5
    assert any(e.type == "BELIEF_UPDATE" for e in result.trace)
    assert any(e.type == "GENERATIVE_SUFFICIENCY" for e in result.trace)
    assert not any(e.type == "SUFFICIENCY" for e in result.trace)
    assert all("GOLD_LEAK" not in r.prompt for r in model.requests)
    with pytest.raises(ValueError):
        GenerativeControl(
            action="SEARCH_MORE", target_claim_id=None, required_stance=None, rationale="invalid"
        )


def test_no_conflict_resolution_preserves_mixed_but_changes_query(
    tmp_path: Path, source: Source
) -> None:
    settings = config()
    settings.ablation.use_conflict_resolution = False
    search = ScenarioSearch("D", source)
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="question"), settings, search, AblationModel(), tmp_path
        )
    )
    assert result.decision and result.decision.action == "ABSTAIN"
    assert any(e.type == "CONFLICT" for e in result.trace)
    assert any(e.type == "CONFLICT_RESOLUTION_DISABLED" for e in result.trace)
    assert "for and against" not in search.queries[1]
    assert result.state and any(b.status == "MIXED" for b in result.state.beliefs)


def test_voi_removal_changes_ranking_without_relaxing_caps(tmp_path: Path, source: Source) -> None:
    class EmptySearch(ScenarioSearch):
        async def search(self, query: str, k: int) -> SearchResponse:
            response = await super().search(query, k)
            response.results[0].text = "Unrelated text."
            return response

    graph = DecompositionDraft.model_validate(DRAFT).graph()
    ids = sorted(c.id for c in graph.claims)
    selected = []
    for enabled in (True, False):
        settings = config()
        assert settings.rag
        settings.rag.max_rounds = 1
        settings.controller.policy = "voi"
        settings.controller.estimates[ids[0]] = AcquisitionEstimate(cost=100)
        settings.ablation.use_cost_aware_controller = enabled
        result = asyncio.run(
            run_epistemic(
                QueryCase(id="q", question="question"),
                settings,
                EmptySearch("C", source),
                AblationModel(),
                tmp_path / str(enabled),
            )
        )
        event = next(
            e for e in result.trace if e.type == "DECISION" and e.payload.get("acquisition")
        )
        selected.append(event.payload["target_claim_id"])
        assert result.usage.search_calls == 1 and result.usage.model_calls == 3
    assert selected == [ids[1], ids[0]]


@pytest.mark.parametrize("ceiling,expected", [(20, "completed"), (4, "budget_exhausted")])
def test_forced_answer_attempt_keeps_hard_budget(
    tmp_path: Path, source: Source, ceiling: int, expected: str
) -> None:
    settings = config()
    settings.ablation.allow_abstention = False
    settings.budget.max_llm_calls = ceiling
    model = AblationModel()
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="question"),
            settings,
            ScenarioSearch("C", source),
            model,
            tmp_path,
        )
    )
    assert result.status == expected, result.error
    assert result.usage.model_calls <= ceiling
    assert any(e.type == "FORCED_ANSWER" for e in result.trace)
    assert (result.output is not None and result.output.answer is not None) == (
        expected == "completed"
    )


def test_forced_null_is_retained_as_error(tmp_path: Path, source: Source) -> None:
    settings = config()
    settings.ablation.allow_abstention = False
    result = asyncio.run(
        run_epistemic(
            QueryCase(id="q", question="question"),
            settings,
            ScenarioSearch("A", source),
            AblationModel(null_answer=True),
            tmp_path,
        )
    )
    assert result.status == "error" and result.error == "Answer model returned no answer"


def test_no_compaction_exposes_raw_context_not_only_spans(tmp_path: Path, source: Source) -> None:
    class VerboseSearch(ScenarioSearch):
        async def search(self, query: str, k: int) -> SearchResponse:
            result = await super().search(query, k)
            result.results[0].text += " OMITTED_BACKGROUND" * 50
            return result

    prompts = []
    for compact in (True, False):
        settings = config()
        settings.ablation.compact_evidence = compact
        model = AblationModel()
        result = asyncio.run(
            run_epistemic(
                QueryCase(id="q", question="question"),
                settings,
                VerboseSearch("A", source),
                model,
                tmp_path / str(compact),
            )
        )
        assert result.status == "completed", result.error
        prompts.append(model.requests[-1].prompt)
    assert "OMITTED_BACKGROUND" not in prompts[0] and "OMITTED_BACKGROUND" in prompts[1]


def test_all_variants_match_protocol_and_generate_tables(tmp_path: Path) -> None:
    settings = load_config(Path("configs/ablation_run_fixture.yaml"))
    assert settings.rag and settings.evaluation
    settings.rag.corpus_path = Path("tests/fixtures/epistemic_corpus.json").resolve()
    settings.rag.responses_path = Path("tests/fixtures/ablation_responses.json").resolve()
    settings.evaluation.dataset_path = Path("tests/fixtures/epistemic_benchmark.jsonl").resolve()
    config_path = tmp_path / "run.yaml"
    config_path.write_text(yaml.safe_dump(settings.model_dump(mode="json")))
    plan = AblationPlan.model_validate(
        yaml.safe_load(Path("configs/ablation_fixture.yaml").read_text())
    )
    plan.run_config_path = config_path
    plan.output_dir = tmp_path / "output"
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(plan.model_dump(mode="json")))
    result = CliRunner().invoke(app, ["ablate", str(path)])
    assert result.exit_code == 0, result.output
    root = plan.output_dir
    report = json.loads((root / "comparison.json").read_text())
    assert report["complete"] is True
    assert len(report["summaries"]) == 8
    reference = json.loads((root / "reference/manifest.json").read_text())
    table = list(csv.DictReader((root / "table.csv").open()))
    assert len(table) == 8
    for row in table:
        name = row["variant"]
        summary = report["summaries"][name]
        assert summary["errors"] == 0 and summary["exact_match"] == 1
        assert row["estimated_cost_usd"] == "0" and row["partial"] == "False"
        manifest = json.loads((root / name / "manifest.json").read_text())
        for key in ("input_hashes", "metric_version", "selected_case_ids", "retriever"):
            assert manifest[key] == reference[key]
        trace = json.loads((root / name / "traces/000000.json").read_text())
        if name in {"use_premise_graph", "use_belief_state"}:
            assert trace["state"] is None
            assert any(e["type"] == "ABLATION_FORWARD" for e in trace["trace"])
            assert not any(e["type"] in {"BELIEF_UPDATE", "SUFFICIENCY"} for e in trace["trace"])
    assert [s["usage"]["model_calls"] for s in report["summaries"].values()] == [
        4,
        1,
        2,
        5,
        4,
        4,
        4,
        4,
    ]
    assert CliRunner().invoke(app, ["ablate", str(path)]).exit_code != 0
