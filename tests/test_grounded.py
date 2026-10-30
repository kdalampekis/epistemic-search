import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_premise_state import docs

from epistemic_search.config import RunConfig
from epistemic_search.grounded import (
    Decomposition,
    category,
    depth,
    fact_closure,
    reference_errors,
    resolve,
    run_grounded,
    structure_stats,
)
from epistemic_search.models import QueryCase, Usage
from epistemic_search.providers import ModelRequest, ModelResponse
from epistemic_search.tokens import count_tokens


def config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_id": "g",
            "method": "grounded_decomposition",
            "rag": {"corpus_path": "u", "responses_path": "u", "k": 1, "max_output_tokens": 512},
            "budget": {"max_llm_calls": 20, "max_documents": 50, "max_search_calls": 5},
        }
    )


def decomposition(
    facts: list[tuple[str, str, list[str]]],
    derived: list[tuple[str, str, list[str]]] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_facts": [{"id": i, "assertion": a, "supported_by": s} for i, a, s in facts],
        "derived_claims": [{"id": i, "assertion": a, "depends_on": d} for i, a, d in derived or []],
        "required_for_answer": required or [f[0] for f in facts],
    }


class Scripted:
    """Decomposer returns a fixed structure; the judge resolves a fact iff its text is verbatim."""

    def __init__(self, raw: Any) -> None:
        self.raw, self.calls, self.requests = raw, [], []  # type: ignore[var-annotated]

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.prompt_version)
        self.requests.append(request)
        v = request.prompt_version
        if v == "evidence-grounded-decomposition-v1":
            text = self.raw if isinstance(self.raw, str) else json.dumps(self.raw)
        elif v == "sufficiency-judge-v1":
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            have = {e["text"]: e["source_id"] for e in payload["evidence"]}
            text = json.dumps(
                {
                    "premises": [
                        {
                            "premise_id": p["id"],
                            "status": "RESOLVED" if p["text"] in have else "UNRESOLVED",
                            "evidence_ids": [have[p["text"]]] if p["text"] in have else [],
                        }
                        for p in payload["premises"]
                    ]
                }
            )
        else:
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            text = json.dumps(
                {"answer": "A", "citation_ids": [payload["evidence"][0]["source_id"]]}
            )
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


def run(model: Scripted, pool: list[str]) -> Any:
    case = QueryCase(id="c", question="Q?", gold_answer="A")
    return asyncio.run(run_grounded(case, config(), docs(pool), model))


FACTS = [("f1", "Fact one.", ["d0"]), ("f2", "Fact two.", ["d1"])]
DERIVED = [("d1", "One and two.", ["f1", "f2"])]
GAP = [("f1", "Fact one.", ["d0"]), ("f2", "Fact two.", [])]  # the decomposer sees the gap


def test_a_derived_claim_is_resolved_by_its_dependencies_never_looked_up_in_the_evidence() -> None:
    raw = decomposition(FACTS, DERIVED, ["d1"])
    result, info = run(Scripted(raw), ["Fact one.", "Fact two."])
    assert result.decision.action == "ANSWER" and result.output.answer == "A"
    assert info["node_status"] == {"f1": "RESOLVED", "f2": "RESOLVED", "d1": "RESOLVED"}
    # d1's text is in no document, yet it holds because both dependencies do
    assert info["unresolved_required"] == [] and info["valid"] and info["judged"]


def test_a_missing_dependency_leaves_the_derived_claim_unresolved_and_abstains() -> None:
    model = Scripted(decomposition(GAP, DERIVED, ["d1"]))
    result, info = run(model, ["Fact one."])
    assert result.decision.action == "ABSTAIN" and info["unresolved_required"] == ["d1"]
    assert info["fact_status"] == {"f1": "RESOLVED", "f2": "UNRESOLVED"}
    assert "sufficiency-answer-v1" not in model.calls
    assert category(info, decision_answer=False) == "DERIVED_CLAIM"


def test_an_unresolved_required_evidence_fact_is_an_evidence_fact_failure() -> None:
    result, info = run(Scripted(decomposition(GAP)), ["Fact one."])
    assert result.decision.action == "ABSTAIN" and info["unresolved_required"] == ["f2"]
    assert category(info, decision_answer=False) == "EVIDENCE_FACT"
    assert info["claimed_support_rejected"] == 0  # the decomposer itself cited nothing for f2
    wrong = decomposition([("f1", "Fact one.", ["d0"]), ("f2", "Fact two.", ["d0"])])
    _, info = run(Scripted(wrong), ["Fact one."])
    assert info["claimed_support_rejected"] == 1  # f2 cited d0, which does not state it


def test_the_decomposer_sees_only_the_question_and_the_evidence_present() -> None:
    model = Scripted(decomposition(FACTS))
    run(model, ["Fact one.", "Fact two."])
    prompt = model.requests[0].prompt
    payload = json.loads(prompt.split("Payload:\n")[1])
    assert set(payload) == {"question", "evidence"} and len(payload["evidence"]) == 2
    for leaked in ("COMPLETE", "MISSING", "removed", "condition", "gold", "sent1"):
        assert leaked not in prompt


@pytest.mark.parametrize(
    "bad",
    [
        decomposition([("f1", "A.", ["d9"])]),  # cites evidence that was not supplied
        decomposition(FACTS, [("d1", "x", ["f1", "nope"])], ["d1"]),  # dangling dependency
        decomposition(FACTS, None, ["ghost"]),  # required node that does not exist
        decomposition(
            FACTS,
            [("d1", "x", ["d2"]), ("d2", "y", ["d1"])],
            ["d1"],
        ),  # cycle
    ],
)
def test_unusable_structures_abstain_without_a_judge_call_and_are_counted_not_repaired(
    bad: dict[str, Any],
) -> None:
    model = Scripted(bad)
    result, info = run(model, ["Fact one.", "Fact two."])
    assert result.decision.action == "ABSTAIN" and result.error == "NO_USABLE_DECOMPOSITION"
    assert model.calls == ["evidence-grounded-decomposition-v1"]  # no judge, no answer
    assert not info["valid"] and info["errors"]
    assert category(info, decision_answer=False) == "STRUCTURAL_ERROR"


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        {"evidence_facts": [], "derived_claims": [], "required_for_answer": ["f1"]},
        decomposition(FACTS, [("d1", "x", [])], ["d1"]),  # a derived claim with no dependencies
        decomposition([("f1", "A.", []), ("f1", "B.", [])]),  # duplicate ids
    ],
)
def test_malformed_output_is_recorded_raw_and_never_retried(raw: Any) -> None:
    model = Scripted(raw)
    result, info = run(model, ["Fact one."])
    assert result.error == "NO_USABLE_DECOMPOSITION" and info["decomposition"] is None
    assert info["raw_response"] and model.calls == ["evidence-grounded-decomposition-v1"]


def test_the_decision_does_not_depend_on_the_answer_step() -> None:
    class NoAnswer(Scripted):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            if request.prompt_version == "sufficiency-answer-v1":
                return ModelResponse(
                    text=json.dumps({"answer": None, "citation_ids": []}),
                    model=request.model,
                    usage=Usage(model_calls=1, cost_usd=Decimal(0)),
                )
            return await super().complete(request)

    result, info = run(NoAnswer(decomposition(FACTS)), ["Fact one.", "Fact two."])
    assert result.decision.action == "ANSWER" and not result.output.answer
    assert category(info, decision_answer=True) == "ANSWER_GENERATION_FAILURE"


def test_structure_statistics_are_deterministic_and_flag_a_copy_of_the_evidence() -> None:
    d = Decomposition.model_validate(decomposition(FACTS, DERIVED, ["d1"]))
    assert fact_closure(d) == {"f1", "f2"} and depth(d) == 1 and resolve(d, {"f1"})["d1"] is False
    stats = structure_stats(d, n_evidence=2)
    assert stats["required_equals_all_evidence"] and stats["compression_ratio"] == 1.0
    assert stats["n_derived_claims"] == 1 and stats["duplicate_claims"] == 0
    assert structure_stats(d, n_evidence=4)["required_equals_all_evidence"] is False
    dup = Decomposition.model_validate(
        decomposition([("f1", "Same fact.", []), ("f2", "same  fact.", [])])
    )
    assert structure_stats(dup, 2)["duplicate_claims"] == 1
    assert reference_errors(d, {"d0", "d1"}) == []


def test_there_is_no_search_stance_ledger_or_controller_in_this_pipeline() -> None:
    source = Path("src/epistemic_search/grounded.py").read_text()
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
