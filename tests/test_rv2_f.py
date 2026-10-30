import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_rv2_adapters import eb_fixture
from test_rv2_controlled import ScriptedLuna

from epistemic_search.config import RagConfig
from epistemic_search.models import Usage
from epistemic_search.providers import ModelRequest, ModelResponse
from epistemic_search.rv2_adapters import leaf_conditions, load_entailmentbank
from epistemic_search.rv2_controlled import load_rows
from epistemic_search.rv2_f import (
    B0,
    B1,
    M0,
    M1,
    OUT,
    SYSTEMS,
    decide,
    drive,
    fresh_sample,
    index_rows,
    stage_run,
)
from epistemic_search.tokens import count_tokens

USAGE = {
    "model_calls": 2,
    "search_calls": 0,
    "prompt_tokens": 50,
    "completion_tokens": 20,
    "new_api_cost_usd": "0.0005",
    "reused_cost_usd": "0",
    "latency_seconds": 1.0,
}


def row(system: str, ex: str, cond: str, answer: bool) -> dict[str, Any]:
    return {
        "system": system,
        "example_id": ex,
        "condition": cond,
        "decision_answer": answer,
        "answered": answer,
        "answer": "a" if answer else None,
        "gold_answer": "a",
        "answer_f1": 1.0 if answer else None,
        "answer_hit": answer or None,
        "outcome": "ANSWER" if answer else "ABSTAIN",
        "usage": USAGE,
    }


def world(patterns: dict[str, tuple[bool, bool]], n: int = 30) -> list[dict[str, Any]]:
    return [
        row(s, f"e{i}", c, a)
        for i in range(n)
        for s in SYSTEMS
        for c, a in zip(("C1", "C2"), patterns[s], strict=True)
    ]


def gens(n: int = 30, valid: int | None = None) -> list[dict[str, Any]]:
    out = []
    for i in range(n):
        ok = i < (n if valid is None else valid)
        out.append(
            {
                "example_id": f"e{i}",
                "leaves": 3,
                "valid": ok,
                "error": None if ok else "unusable",
                "usage": {
                    "model_calls": 1,
                    "prompt_tokens": 80,
                    "completion_tokens": 40,
                    "new_api_cost_usd": "0.0003",
                    "reused_cost_usd": "0",
                    "latency_seconds": 1.0,
                },
                "flags": {
                    "n_premises": 3,
                    "non_assertion_premises": 0,
                    "duplicate_premises": 0,
                    "proof_graph_conversion_ok": True,
                }
                if ok
                else None,
            }
        )
    return out


SEP = (True, False)  # answers when complete, abstains when a leaf is missing: J = 1
LEAK = (True, True)  # answers regardless: J = 0
BASE = {B0: LEAK, B1: LEAK}


def verdict(
    patterns: dict[str, tuple[bool, bool]], n: int = 30, valid: int | None = None
) -> dict[str, Any]:
    return decide(index_rows(world(patterns, n)), gens(n, valid), resamples=200)


def test_all_five_viability_conditions_pass_is_a_promising_component() -> None:
    result = verdict({**BASE, M0: SEP, M1: SEP})
    assert (
        all(result["viability"].values())
        and result["classification"]["class"] == "PROMISING_COMPONENT"
    )
    assert result["stop_rule_fired"] is False


def mixed(n_ok: int) -> list[dict[str, Any]]:
    """M1 answers COMPLETE in n_ok of 30 examples and never answers MISSING_ONE."""
    rows = world({**BASE, M0: SEP, M1: SEP})
    for r in rows:
        if r["system"] == M1 and r["condition"] == "C1" and int(r["example_id"][1:]) >= n_ok:
            r.update(decision_answer=False, answered=False, outcome="ABSTAIN")
    return rows


@pytest.mark.parametrize("n_ok,expected", [(27, "PROMISING_COMPONENT"), (26, "ORACLE_DEPENDENT")])
def test_the_coverage_threshold_is_applied_exactly(n_ok: int, expected: str) -> None:
    # 27/30 = 0.90 passes; 26/30 = 0.867 fails condition A (and condition B's J stays 0.867)
    result = decide(index_rows(mixed(n_ok)), gens(), resamples=200)
    assert result["classification"]["class"] == expected, result["viability"]


def test_generated_premises_that_collapse_with_a_strong_gold_control_stop_the_project() -> None:
    result = verdict({**BASE, M0: SEP, M1: (True, True)}, valid=30)
    assert (
        result["inputs"]["M0_strong"]
        and result["classification"]["class"] == "NO_END_TO_END_SIGNAL"
    )
    assert result["stop_rule_fired"] is True


def test_partial_signal_with_a_strong_gold_control_is_oracle_dependent() -> None:
    rows = world({**BASE, M0: SEP, M1: SEP})
    for r in rows:  # M1 answers complete in 26/30 and wrongly answers 2 missing: J 0.8, cov 0.867
        i = int(r["example_id"][1:])
        if r["system"] == M1 and r["condition"] == "C1" and i >= 26:
            r.update(decision_answer=False)
        if r["system"] == M1 and r["condition"] == "C2" and i < 2:
            r.update(decision_answer=True)
    result = decide(index_rows(rows), gens(), resamples=200)
    assert not all(result["viability"].values()) and not any(
        result["inputs"]["no_signal_flags"].values()
    )
    assert (
        result["classification"]["class"] == "ORACLE_DEPENDENT"
        and result["stop_rule_fired"] is True
    )


def test_a_weak_positive_control_means_no_end_to_end_signal_not_oracle_dependence() -> None:
    result = verdict({**BASE, M0: (True, True), M1: (True, True)})
    assert not result["inputs"]["M0_strong"]
    assert result["classification"]["class"] == "NO_END_TO_END_SIGNAL"


def test_structural_validity_below_ninety_percent_blocks_viability() -> None:
    result = verdict({**BASE, M0: SEP, M1: SEP}, valid=26)  # 0.867 usable
    assert result["viability"]["E_structurally_usable_ge_0.90"] is False
    assert result["classification"]["class"] != "PROMISING_COMPONENT"


def test_the_gold_degradation_condition_compares_against_the_gold_premise_system() -> None:
    rows = world({**BASE, M0: SEP, M1: SEP})
    for r in rows:  # M1 leaks 8 of 30 missing cases: J 0.733 >= 0.75 * 1.0 fails D
        if r["system"] == M1 and r["condition"] == "C2" and int(r["example_id"][1:]) < 8:
            r.update(decision_answer=True)
    result = decide(index_rows(rows), gens(), resamples=200)
    assert result["viability"]["D_retains_75pct_of_gold_J"] is False
    assert result["viability"]["B_J_ge_0.65"] is True


def test_fewer_than_twenty_four_complete_examples_is_inconclusive_never_extrapolated() -> None:
    assert verdict({**BASE, M0: SEP, M1: SEP}, n=23)["classification"]["class"] == "INCONCLUSIVE"
    assert (
        verdict({**BASE, M0: SEP, M1: SEP}, n=24)["classification"]["class"]
        == "PROMISING_COMPONENT"
    )


def test_an_example_missing_any_system_or_condition_does_not_count() -> None:
    rows = [
        r
        for r in world({**BASE, M0: SEP, M1: SEP}, 24)
        if not (r["example_id"] == "e0" and r["system"] == B1 and r["condition"] == "C2")
    ]
    assert (
        decide(index_rows(rows), gens(24), resamples=50)["classification"]["class"]
        == "INCONCLUSIVE"
    )


def test_leaf_conditions_have_no_distractors_and_remove_exactly_one_seeded_leaf(
    tmp_path: Path,
) -> None:
    ex = load_entailmentbank(eb_fixture(tmp_path), "dev")[0]
    complete, missing = leaf_conditions(ex, seed=5)
    assert (complete.condition, missing.condition) == ("C1", "C2")
    assert all(d.role == "leaf" for d in complete.docs + missing.docs)
    assert len(complete.docs) == len(ex.leaves) and len(missing.docs) == len(ex.leaves) - 1
    assert {d.leaf_id for d in complete.docs} - {d.leaf_id for d in missing.docs} == {
        missing.removed_leaf
    }
    assert leaf_conditions(ex, seed=5)[1].removed_leaf == missing.removed_leaf


def test_the_fresh_sample_excludes_everything_any_earlier_experiment_saw(tmp_path: Path) -> None:
    root = tmp_path / "root"
    eb_fixture(root / "data/external/entailmentbank")
    for name, ids in (("rv2_b", ["t1"]), ("rv2_c", ["t1"]), ("rv2_e", ["zzz"])):
        path = root / "docs/results/rv2" / name / "results.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"sample_ids": ids}))
    sample, seen = fresh_sample(root, 30)
    assert [e.id for e in sample] == ["t2"]  # t1 seen; t3 has a duplicate leaf so not convertible
    assert set(seen) == {"rv2_b", "rv2_c", "rv2_e"}


class Everything(ScriptedLuna):
    """Scripted stand-in covering every prompt the four systems use."""

    def __init__(self, leaves: dict[str, list[str]], valid_for: set[str]) -> None:
        super().__init__()
        self.leaves, self.valid_for, self.generations = leaves, valid_for, 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        v = request.prompt_version
        if v == "premise-generation-v1":
            self.generations += 1
            question = json.loads(request.prompt.split("Question: ", 1)[1])
            if question not in self.valid_for:
                text = "not json at all"
            else:
                text = json.dumps(
                    {
                        "premises": [
                            {"id": f"p{i}", "assertion": t}
                            for i, t in enumerate(self.leaves[question])
                        ],
                        "logic": "AND",
                    }
                )
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
        elif v == "sufficiency-answer-v1":
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            text = json.dumps(
                {"answer": "ok", "citation_ids": [payload["evidence"][0]["source_id"]]}
            )
        elif v == "iterative-relevance-v1":
            docs = json.loads(request.prompt.split("\nEvidence:\n")[1])
            text = json.dumps(
                {
                    "action": "ANSWER",
                    "query": None,
                    "answer": "ok",
                    "citation_ids": [docs[0]["source_id"]],
                }
            )
        else:
            return await super().complete(request)
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


def rag() -> RagConfig:
    return RagConfig(corpus_path=Path("unused"), responses_path=Path("unused"), max_rounds=3)


def run_driver(tmp_path: Path, valid: bool) -> tuple[Path, Everything]:
    root = tmp_path / "root"
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path / "src"), "dev")}["t1"]
    model = Everything({ex.question: list(ex.leaves.values())}, {ex.question} if valid else set())
    assert asyncio.run(drive([ex], root, rag=rag(), provider=model)) is None
    return root / OUT, model


def test_premises_are_generated_once_per_question_and_reused_for_both_conditions(
    tmp_path: Path,
) -> None:
    out, model = run_driver(tmp_path, valid=True)
    generated, rows = load_rows(out / "generated_premises.jsonl"), load_rows(out / "cases.jsonl")
    assert len(generated) == 1 and model.generations == 1  # once, not once per condition
    assert len(rows) == 8 and {r["condition_label"] for r in rows} == {"COMPLETE", "MISSING_ONE"}
    used = {r["condition"]: r["premises_used"] for r in rows if r["system"] == M1}
    assert used["C1"] == used["C2"] and used["C1"] is not None
    m1 = {r["condition"]: r for r in rows if r["system"] == M1}
    assert m1["C1"]["decision_answer"] and not m1["C2"]["decision_answer"]
    assert run_again(tmp_path, out) == 0  # resumable: nothing is regenerated or rerun


def run_again(tmp_path: Path, out: Path) -> int:
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path / "src"), "dev")}["t1"]
    model = Everything({ex.question: list(ex.leaves.values())}, {ex.question})
    asyncio.run(drive([ex], out.parents[3], rag=rag(), provider=model))
    return model.generations + len(model.calls)


def test_an_unusable_generation_is_recorded_and_m1_abstains_in_both_conditions(
    tmp_path: Path,
) -> None:
    out, _ = run_driver(tmp_path, valid=False)
    generated = load_rows(out / "generated_premises.jsonl")
    assert generated[0]["valid"] is False and generated[0]["raw_response"] == "not json at all"
    rows = load_rows(out / "cases.jsonl")
    m1 = [r for r in rows if r["system"] == M1]
    assert len(m1) == 2 and not any(r["decision_answer"] for r in m1)
    assert all(r["generation_valid"] is False for r in m1)
    m0 = {r["condition"]: r for r in rows if r["system"] == M0}
    assert (
        m0["C1"]["decision_answer"] and not m0["C2"]["decision_answer"]
    )  # gold control unaffected


def test_a_full_run_needs_a_logged_estimate(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="estimate"):
        stage_run(tmp_path)
