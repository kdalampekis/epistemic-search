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
from epistemic_search.rv2_adapters import load_entailmentbank
from epistemic_search.rv2_controlled import load_rows
from epistemic_search.rv2_f import index_rows
from epistemic_search.rv2_g import (
    B0,
    B1,
    M0,
    M2,
    OUT,
    SYSTEMS,
    decide,
    drive,
    fresh_sample,
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
        "condition_label": "COMPLETE" if cond == "C1" else "MISSING_ONE",
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


def decomps(n: int = 30, valid: int | None = None) -> list[dict[str, Any]]:
    stats = {
        "n_evidence_sentences": 3,
        "n_evidence_facts": 3,
        "n_derived_claims": 0,
        "n_required_nodes": 3,
        "n_required_evidence_facts": 3,
        "required_nodes_that_are_facts": 3,
        "decomposition_size": 3,
        "graph_depth": 0,
        "compression_ratio": 1.0,
        "required_equals_all_evidence": True,
        "duplicate_claims": 0,
        "facts_without_cited_support": 0,
    }
    out = []
    for i in range(n):
        for cond, label in (("C1", "COMPLETE"), ("C2", "MISSING_ONE")):
            ok = i < (n if valid is None else valid)
            out.append(
                {
                    "example_id": f"e{i}",
                    "condition": cond,
                    "condition_label": label,
                    "valid": ok,
                    "decomposition": {} if ok else None,
                    "errors": [] if ok else ["unusable"],
                    "stats": stats if ok else None,
                    "claimed_support_rejected": 0,
                }
            )
    return out


def gens(n: int = 30) -> list[dict[str, Any]]:
    flags = {
        "n_premises": 2,
        "non_assertion_premises": 0,
        "duplicate_premises": 0,
        "proof_graph_conversion_ok": True,
    }
    usage = {
        "model_calls": 1,
        "prompt_tokens": 80,
        "completion_tokens": 40,
        "new_api_cost_usd": "0.0003",
        "reused_cost_usd": "0",
        "latency_seconds": 1.0,
    }
    return [
        {
            "example_id": f"e{i}",
            "leaves": 3,
            "valid": True,
            "error": None,
            "usage": usage,
            "flags": flags,
        }
        for i in range(n)
    ]


SEP, LEAK, ABSTAINS = (True, False), (True, True), (False, False)


def verdict(
    patterns: dict[str, tuple[bool, bool]], n: int = 30, valid: int | None = None
) -> dict[str, Any]:
    rows = world(patterns, n)
    return decide(index_rows(rows), gens(n), decomps(n, valid), rows, resamples=200)


def test_all_six_conditions_pass_is_an_evidence_grounded_signal() -> None:
    result = verdict({B0: LEAK, B1: ABSTAINS, M0: SEP, M2: SEP})
    assert all(result["viability"].values())
    assert result["classification"]["class"] == "EVIDENCE_GROUNDED_SIGNAL"
    assert result["strong_signal"] is True and result["stop_rule_fired"] is False


def staged(m2_complete: int, m2_missing_leaks: int, b1_complete: int = 0) -> list[dict[str, Any]]:
    """M2 answers COMPLETE in m2_complete of 30 examples and leaks in the first few MISSING."""
    rows = world({B0: LEAK, B1: ABSTAINS, M0: SEP, M2: SEP})
    for r in rows:
        i = int(r["example_id"][1:])
        if r["system"] == M2 and r["condition"] == "C1" and i >= m2_complete:
            r.update(decision_answer=False, answered=False, outcome="ABSTAIN")
        if r["system"] == M2 and r["condition"] == "C2" and i < m2_missing_leaks:
            r.update(decision_answer=True, answered=True, outcome="ANSWER")
        if r["system"] == B1 and r["condition"] == "C1" and i >= 30 - b1_complete:
            r.update(decision_answer=True, answered=True, outcome="ANSWER")
    return rows


def run_decide(rows: list[dict[str, Any]], valid: int | None = None) -> dict[str, Any]:
    return decide(index_rows(rows), gens(), decomps(30, valid), rows, resamples=300)


@pytest.mark.parametrize(
    "n_ok,expected", [(27, "EVIDENCE_GROUNDED_SIGNAL"), (26, "PARTIAL_SIGNAL")]
)
def test_the_coverage_threshold_is_applied_exactly(n_ok: int, expected: str) -> None:
    result = run_decide(staged(n_ok, 0))  # 27/30 = 0.90 passes; 26/30 = 0.867 fails A and F
    assert result["classification"]["class"] == expected, result["viability"]
    if expected == "PARTIAL_SIGNAL":
        assert (
            result["inputs"]["failed_thresholds"]
            == [
                "A_complete_coverage_ge_0.90",
                "B_J_ge_0.65" if False else "F_not_abstention_only",
            ]
            or "A_complete_coverage_ge_0.90" in result["inputs"]["failed_thresholds"]
        )


def test_recovery_over_the_question_only_system_must_be_at_least_point_three() -> None:
    # M2 J = 0.70 (passes B); B1 J = 0.43 -> recovery 0.27 fails C but is still a partial signal
    rows = staged(30, 9, b1_complete=13)
    result = run_decide(rows)
    assert (
        result["viability"]["B_J_ge_0.65"]
        and not result["viability"]["C_recovery_over_question_only_ge_0.30"]
    )
    assert result["classification"]["class"] == "PARTIAL_SIGNAL"


def test_retention_of_oracle_performance_is_a_ratio_to_the_gold_control() -> None:
    result = run_decide(staged(30, 9))  # J 0.70 against M0 J 1.0 -> exactly 0.70, passes D
    assert result["viability"]["D_retains_70pct_of_gold_J"] is True
    result = run_decide(staged(30, 10))  # J 0.667 < 0.70
    assert result["viability"]["D_retains_70pct_of_gold_J"] is False
    assert result["viability"]["B_J_ge_0.65"] is True


def test_no_better_than_question_only_is_no_signal_and_stops_the_direction() -> None:
    result = verdict({B0: LEAK, B1: (False, False), M0: SEP, M2: (False, False)})
    assert result["classification"]["class"] == "NO_SIGNAL" and result["stop_rule_fired"] is True


def test_an_abstention_only_system_cannot_pass_by_refusing_everything() -> None:
    result = verdict({B0: LEAK, B1: (True, True), M0: SEP, M2: (False, False)})
    assert result["viability"]["A_complete_coverage_ge_0.90"] is False
    assert result["classification"]["class"] == "NO_SIGNAL"


def test_structural_usability_below_ninety_percent_blocks_the_positive_label() -> None:
    result = verdict({B0: LEAK, B1: ABSTAINS, M0: SEP, M2: SEP}, valid=26)  # 52 of 60 usable
    assert result["viability"]["E_structurally_usable_ge_0.90"] is False
    assert result["classification"]["class"] != "EVIDENCE_GROUNDED_SIGNAL"


def test_strong_signal_is_reported_separately_from_the_classification() -> None:
    rows = staged(30, 7)  # coverage 1.0, J 0.767 >= 0.75
    result = run_decide(rows)
    assert result["strong_signal"] is True
    result = run_decide(staged(28, 3))  # coverage 0.933 < 0.95
    assert result["strong_signal"] is False
    assert result["classification"]["class"] == "EVIDENCE_GROUNDED_SIGNAL"


def test_fewer_than_twenty_four_completed_examples_is_inconclusive() -> None:
    assert (
        verdict({B0: LEAK, B1: ABSTAINS, M0: SEP, M2: SEP}, n=23)["classification"]["class"]
        == "INCONCLUSIVE"
    )
    assert (
        verdict({B0: LEAK, B1: ABSTAINS, M0: SEP, M2: SEP}, n=24)["classification"]["class"]
        != "INCONCLUSIVE"
    )


def test_the_fresh_sample_excludes_every_earlier_experiment_including_rv2_f(tmp_path: Path) -> None:
    root = tmp_path / "root"
    eb_fixture(root / "data/external/entailmentbank")
    for name, ids in (("rv2_b", ["t1"]), ("rv2_c", []), ("rv2_e", []), ("rv2_f", ["t2"])):
        path = root / "docs/results/rv2" / name / "results.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"sample_ids": ids}))
    sample, seen = fresh_sample(root, 30)
    assert sample == [] and set(seen) == {"rv2_b", "rv2_c", "rv2_e", "rv2_f"}
    (root / "docs/results/rv2/rv2_f/results.json").write_text(json.dumps({"sample_ids": []}))
    assert [e.id for e in fresh_sample(root, 30)[0]] == ["t2"]  # t1 seen; t3 not convertible


class Ideal(ScriptedLuna):
    """A decomposer that lists every leaf of the question (an ideal one), or only what it sees."""

    def __init__(self, leaves: list[str], question: str, sees_only: bool = False) -> None:
        super().__init__()
        self.leaves, self.question, self.sees_only = leaves, question, sees_only
        self.generations, self.decompositions = 0, 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        v = request.prompt_version
        if v == "premise-generation-v1":
            self.generations += 1
            text = json.dumps(
                {
                    "premises": [
                        {"id": f"p{i}", "assertion": t} for i, t in enumerate(self.leaves)
                    ],
                    "logic": "AND",
                }
            )
        elif v == "evidence-grounded-decomposition-v1":
            self.decompositions += 1
            payload = json.loads(request.prompt.split("Payload:\n")[1])
            have = {e["text"]: e["source_id"] for e in payload["evidence"]}
            wanted = list(have) if self.sees_only else self.leaves
            text = json.dumps(
                {
                    "evidence_facts": [
                        {
                            "id": f"f{i}",
                            "assertion": t,
                            "supported_by": [have[t]] if t in have else [],
                        }
                        for i, t in enumerate(wanted)
                    ],
                    "derived_claims": [],
                    "required_for_answer": [f"f{i}" for i in range(len(wanted))],
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
        else:
            return await super().complete(request)
        return ModelResponse(
            text=text,
            model=request.model,
            usage=Usage(model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)),
        )


def rag() -> RagConfig:
    return RagConfig(corpus_path=Path("unused"), responses_path=Path("unused"), max_rounds=3)


def run_driver(tmp_path: Path, sees_only: bool = False) -> tuple[Path, Ideal]:
    root = tmp_path / "root"
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path / "src"), "dev")}["t1"]
    model = Ideal(list(ex.leaves.values()), ex.question, sees_only)
    assert asyncio.run(drive([ex], root, rag=rag(), provider=model)) is None
    return root / OUT, model


def test_decomposition_is_generated_once_per_condition_and_premises_once_per_question(
    tmp_path: Path,
) -> None:
    out, model = run_driver(tmp_path)
    rows, decomps_ = load_rows(out / "cases.jsonl"), load_rows(out / "decompositions.jsonl")
    assert len(rows) == 8 and model.generations == 1  # question-only premises: once, reused
    assert model.decompositions == 2 and len(decomps_) == 2  # M2: once per condition
    assert {d["condition_label"] for d in decomps_} == {"COMPLETE", "MISSING_ONE"}
    assert all(d["raw_response"] and d["decomposition"] for d in decomps_)
    used = {r["condition"]: r["premises_used"] for r in rows if r["system"] == B1}
    assert used["C1"] == used["C2"] and used["C1"] is not None
    m2 = {r["condition"]: r for r in rows if r["system"] == M2}
    assert m2["C1"]["decision_answer"] and not m2["C2"]["decision_answer"]
    assert m2["C2"]["m2_category"] == "EVIDENCE_FACT" and m2["C1"]["m2_category"] is None
    m0 = {r["condition"]: r for r in rows if r["system"] == M0}
    assert m0["C1"]["decision_answer"] and not m0["C2"]["decision_answer"]


def test_a_decomposer_that_only_describes_what_it_sees_is_reported_not_rescued(
    tmp_path: Path,
) -> None:
    out, _ = run_driver(tmp_path, sees_only=True)
    rows = {r["condition"]: r for r in load_rows(out / "cases.jsonl") if r["system"] == M2}
    assert rows["C1"]["decision_answer"] and rows["C2"]["decision_answer"]  # leaks: J would be 0
    missing = [d for d in load_rows(out / "decompositions.jsonl") if d["condition"] == "C2"]
    assert missing[0]["stats"]["required_equals_all_evidence"] is True


def test_the_run_is_resumable_without_regenerating_anything(tmp_path: Path) -> None:
    out, _ = run_driver(tmp_path)
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path / "src"), "dev")}["t1"]
    again = Ideal(list(ex.leaves.values()), ex.question)
    asyncio.run(drive([ex], out.parents[3], rag=rag(), provider=again))
    assert again.generations == again.decompositions == 0 and again.calls == []
    assert len(load_rows(out / "decompositions.jsonl")) == 2


def test_a_full_run_needs_a_logged_estimate(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="estimate"):
        stage_run(tmp_path)
