import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_premise_state import docs

from epistemic_search.config import RunConfig
from epistemic_search.models import QueryCase, Usage
from epistemic_search.providers import ModelRequest, ModelResponse, ProviderError
from epistemic_search.sufficiency import (
    GeneratedPremise,
    GeneratedPremises,
    generate_premises,
    run_sufficiency,
    syntax_flags,
)
from epistemic_search.tokens import count_tokens


def config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": "s",
            "method": "sufficiency_check",
            "rag": {"corpus_path": "u", "responses_path": "u", "k": 1, "max_output_tokens": 512},
            "budget": {"max_llm_calls": 20, "max_documents": 50, "max_search_calls": 5},
        }
    )


class Scripted:
    def __init__(self, generated: str = "", verdict: Any = None, answer: Any = None) -> None:
        self.calls: list[str] = []
        self.generated, self.verdict, self.answer = generated, verdict, answer

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.prompt_version)
        v = request.prompt_version
        if v == "premise-generation-v1":
            text = self.generated
        elif v == "sufficiency-judge-v1":
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            have = {e["text"]: e["source_id"] for e in payload["evidence"]}
            data: Any = {
                "premises": [
                    {
                        "premise_id": p["id"],
                        "status": "RESOLVED" if p["text"] in have else "UNRESOLVED",
                        "evidence_ids": [have[p["text"]]] if p["text"] in have else [],
                    }
                    for p in payload["premises"]
                ]
            }
            text = json.dumps(self.verdict(data) if self.verdict else data)
        else:
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            text = json.dumps(
                self.answer
                or {"answer": "A", "citation_ids": [payload["evidence"][0]["source_id"]]}
            )
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


def premise_set(*texts: str) -> list[dict[str, str]]:
    return [{"id": f"p{i}", "text": t} for i, t in enumerate(texts)]


def run(model: Scripted, pool: list[str], premises: list[dict[str, str]] | None) -> Any:
    case = QueryCase(id="c", question="Q?", gold_answer="A")
    return asyncio.run(run_sufficiency(case, config(), docs(pool), premises, model))


GOOD = {"premises": [{"id": "p1", "assertion": "Water expands when it freezes."}], "logic": "AND"}


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "logic": "OR"},
        {**GOOD, "premises": []},
        {**GOOD, "premises": [{"id": f"p{i}", "assertion": "x"} for i in range(9)]},
        {**GOOD, "premises": [{"id": "p1", "assertion": "a"}, {"id": "p1", "assertion": "b"}]},
        {**GOOD, "premises": [{"id": "p1", "assertion": ""}]},
    ],
)
def test_only_structurally_usable_premise_sets_are_accepted(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        GeneratedPremises.model_validate(bad)
    assert GeneratedPremises.model_validate(GOOD).logic == "AND"


def test_syntax_flags_are_deterministic_and_never_a_semantic_judgment() -> None:
    ps = [
        GeneratedPremise(id=f"p{i}", assertion=a)
        for i, a in enumerate(
            [
                "Identify the cause of freezing.",
                "Water expands when it freezes.",
                "water expands  when it freezes.",
                "Does ice float?",
            ]
        )
    ]
    flags = syntax_flags(ps)
    assert flags["n_premises"] == 4 and flags["non_assertion_premises"] == 2
    assert flags["duplicate_premises"] == 1
    assert (
        flags["surface_forms"][0] == "TASK_VERB_PREFIX"
        and flags["surface_forms"][3] == "QUESTION_MARK"
    )
    assert isinstance(flags["proof_graph_conversion_ok"], bool)


def generate(model: Scripted) -> dict[str, Any]:
    return asyncio.run(
        generate_premises("Q?", model, model_name="m", max_output_tokens=256, seed=1)
    )


def test_generation_is_one_call_never_retried_or_repaired() -> None:
    ok = Scripted(generated=json.dumps(GOOD))
    record = generate(ok)
    assert (
        record["valid"]
        and record["premises"][0]["assertion"].startswith("Water")
        and ok.calls == ["premise-generation-v1"]
    )
    for text in (
        "not json",
        json.dumps({**GOOD, "logic": "OR"}),
        json.dumps({"premises": [], "logic": "AND"}),
    ):
        broken = Scripted(generated=text)
        bad = generate(broken)
        assert not bad["valid"] and bad["premises"] is None and "unusable" in bad["error"]
        assert broken.calls == ["premise-generation-v1"]  # exactly one attempt
        assert bad["raw_response"] == text  # the failure is preserved verbatim


def test_a_provider_failure_is_recorded_as_such() -> None:
    class Down:
        async def complete(self, request: ModelRequest) -> ModelResponse:
            raise ProviderError("down", Usage(cost_usd=Decimal(0)), usage_complete=True)

    record = asyncio.run(
        generate_premises("Q?", Down(), model_name="m", max_output_tokens=9, seed=1)
    )
    assert not record["valid"] and "generation call failed" in record["error"]


def test_every_premise_resolved_answers_and_judges_the_whole_set_in_one_call() -> None:
    model = Scripted()
    result = run(model, ["fact a", "fact b"], premise_set("fact a", "fact b"))
    assert result.decision.action == "ANSWER" and result.output.answer == "A"
    assert model.calls == ["sufficiency-judge-v1", "sufficiency-answer-v1"]


def test_one_unresolved_premise_abstains_without_an_answer_call() -> None:
    model = Scripted()
    result = run(model, ["fact a"], premise_set("fact a", "fact b"))
    assert result.decision.action == "ABSTAIN" and result.decision.blocking_claims == ["p1"]
    assert result.output.answer is None and "sufficiency-answer-v1" not in model.calls


def test_no_usable_premises_abstains_and_makes_no_model_call() -> None:
    model = Scripted()
    result = run(model, ["fact a"], None)
    assert result.decision.action == "ABSTAIN" and result.error == "NO_USABLE_PREMISES"
    assert model.calls == []


def test_the_decision_is_the_check_even_if_the_answer_step_declines() -> None:
    model = Scripted(answer={"answer": None, "citation_ids": []})
    result = run(model, ["fact a"], premise_set("fact a"))
    assert result.decision.action == "ANSWER" and result.output.answer is None  # resolved, no text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: {"premises": d["premises"][:-1]},
        lambda d: {"premises": [{**p, "premise_id": "zz"} for p in d["premises"]]},
        lambda d: {"premises": [{**p, "evidence_ids": ["not-supplied"]} for p in d["premises"]]},
    ],
)
def test_malformed_or_ungrounded_verdicts_never_become_an_answer(mutate: Any) -> None:
    result = run(Scripted(verdict=mutate), ["fact a", "fact b"], premise_set("fact a", "fact b"))
    assert result.status == "error" and result.output.answer is None
    assert result.decision is None


def test_there_is_no_search_stance_ledger_or_controller_in_this_pipeline(tmp_path: Path) -> None:
    source = Path("src/epistemic_search/sufficiency.py").read_text()
    for forbidden in (
        "classify_evidence",
        "aggregate_beliefs",
        "EvidenceLedger",
        "choose_action",
        "GuardedSearch",
        "generate_query",
        "Z3",
        "reason(",
    ):
        assert forbidden not in source
