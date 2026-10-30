from pathlib import Path
from typing import Any

import pytest

from epistemic_search.rv2_pivot import SYSTEMS, stage_run, summarize

USAGE = {
    "model_calls": 3,
    "search_calls": 2,
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "new_api_cost_usd": "0.001",
    "reused_cost_usd": "0",
    "latency_seconds": 1.0,
}


def cell(
    system: str,
    ex: str,
    cond: str,
    answered: bool,
    leaves: int = 3,
    got: int = 3,
    cost: str = "0.001",
) -> dict[str, Any]:
    return {
        "system": system,
        "example_id": ex,
        "condition": cond,
        "answered": answered,
        "answer_hit": answered,
        "answer_f1": 1.0 if answered else 0.0,
        "outcome": "ANSWER" if answered else "ABSTAIN",
        "depth": 2,
        "leaves": leaves,
        "leaves_retrieved": list(range(got)),
        "usage": {**USAGE, "new_api_cost_usd": cost},
        "span_rejections": 0,
        "no_progress": False,
        "removed_leaf": None,
        "unresolved_leaves": None,
        "decomposition_valid": True,
    }


def rows(
    pattern: dict[str, tuple[bool, bool, bool, bool]],
    lex: dict[str, tuple[bool, int]] | None = None,
    n: int = 24,
    cost: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    given, lexical = [], []
    for i in range(n):
        for s in SYSTEMS:
            for c, a in zip(("C1", "C2", "C3", "C4"), pattern[s], strict=True):
                given.append(cell(s, f"e{i}", c, a, cost=(cost or {}).get(s, "0.001")))
            answers, got = (lex or {}).get(s, (True, 3))
            lexical.append(cell(s, f"e{i}", "R1", answers, got=got))
            lexical.append(cell(s, f"e{i}", "R2", False, got=got))
    return given, lexical


GOOD = (True, False, False, True)
BAD = (True, True, True, True)
BASE = {"naive_rag": BAD, "iterative_rag": BAD}


def outcome(pattern: dict[str, tuple[bool, bool, bool, bool]], **kw: Any) -> dict[str, Any]:
    given, lexical = rows(pattern, **kw)
    return summarize(given, lexical, resamples=300)


def test_both_premise_systems_equal_is_premise_only_sufficing() -> None:
    result = outcome({**BASE, "premise_only": GOOD, "premise_state": GOOD})
    assert result["outcome"]["class"] == "PREMISE_ONLY_SUFFICES"
    assert (
        result["decision_inputs"]["R1_premise_only_viable"]
        and result["decision_inputs"]["R2_premise_state_viable"]
    )


def test_failure_to_replicate_premise_only_stops_everything() -> None:
    result = outcome({**BASE, "premise_only": BAD, "premise_state": GOOD})
    assert result["outcome"]["class"] == "STOP"  # R1 fails even though M2 looks fine


def test_m2_must_beat_premise_only_by_the_margin_with_an_interval_above_zero() -> None:
    weaker = (True, True, False, True)  # premise-only lets one condition leak: J 0.5 -> fails R1
    assert (
        outcome({**BASE, "premise_only": weaker, "premise_state": GOOD})["outcome"]["class"]
        == "STOP"
    )
    # M1 viable (J 0.75 exactly on the boundary pattern) and M2 clearly better
    near = (True, False, True, True)  # coverage 1.0, unsupported 0.5 -> J 0.5 (not viable)
    assert (
        outcome({**BASE, "premise_only": near, "premise_state": GOOD})["outcome"]["class"] == "STOP"
    )


def test_a_targeted_search_gain_counts_only_with_recall_and_bounded_cost() -> None:
    lex_better = {"premise_only": (True, 1), "premise_state": (True, 3)}
    both = {**BASE, "premise_only": GOOD, "premise_state": GOOD}
    gain = outcome(both, lex=lex_better)
    assert gain["E_B"]["recall_gain_M2_minus_M1"]["point"] == pytest.approx(2 / 3)
    assert gain["outcome"]["class"] == "PIVOT_VALIDATED"
    costly = outcome(both, lex=lex_better, cost={"premise_state": "0.004", "premise_only": "0.001"})
    assert costly["outcome"]["class"] == "PREMISE_ONLY_SUFFICES"  # recall gain, but 4x the cost
    assert costly["decision_inputs"]["cost_ratio_M2_over_M1"] == pytest.approx(4.0)


def test_too_few_complete_examples_is_inconclusive_not_a_guess() -> None:
    result = outcome({**BASE, "premise_only": GOOD, "premise_state": GOOD}, n=10)
    assert result["outcome"]["class"] == "INCONCLUSIVE"


def test_the_full_run_needs_a_logged_estimate(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="estimate"):
        stage_run(tmp_path)


def test_the_harness_runs_all_four_systems_in_both_settings_end_to_end(tmp_path: Path) -> None:
    import asyncio
    import json
    from decimal import Decimal

    import httpx
    from test_premise_state import Judge
    from test_rv2_adapters import eb_fixture
    from test_rv2_controlled import ScriptedLuna, rag

    from epistemic_search.models import Usage
    from epistemic_search.providers import ModelRequest, ModelResponse
    from epistemic_search.rv2_adapters import (
        controlled_conditions,
        load_entailmentbank,
        retrieval_conditions,
    )
    from epistemic_search.rv2_controlled import load_rows, run_example
    from epistemic_search.tokens import count_tokens

    class Everything(ScriptedLuna):
        judge = Judge()

        async def complete(self, request: ModelRequest) -> ModelResponse:
            if request.prompt_version.startswith("premise-state"):
                return await self.judge.complete(request)
            if request.prompt_version == "iterative-relevance-v1":
                docs = json.loads(request.prompt.split("\nEvidence:\n")[1])
                text = json.dumps(
                    {
                        "action": "ANSWER",
                        "query": None,
                        "answer": "x",
                        "citation_ids": [docs[0]["source_id"]],
                    }
                )
                return ModelResponse(
                    text=text,
                    model=request.model,
                    usage=Usage(
                        model_calls=1, completion_tokens=count_tokens(text), cost_usd=Decimal(0)
                    ),
                )
            return await super().complete(request)

    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path), "dev")}["t1"]
    ex = ex.model_copy(update={"answer": "The rocks would break into smaller pieces."})
    model = Everything()

    async def go(conditions: Any, retrieval: str, mode: str) -> str | None:
        async with httpx.AsyncClient() as client:
            return await run_example(
                ex,
                conditions,
                systems=SYSTEMS,
                oracle=True,
                mode=mode,
                base_rag=rag(),
                run_id="t",
                cache_dir=tmp_path / "c",
                out=tmp_path / f"{mode}.jsonl",
                traces=tmp_path / "tr",
                client=client,
                model=model,
                retrieval=retrieval,
            )

    assert asyncio.run(go(controlled_conditions(ex, 1), "given", "given")) is None
    assert asyncio.run(go(retrieval_conditions(ex, 1), "lexical", "lexical")) is None
    given, lexical = load_rows(tmp_path / "given.jsonl"), load_rows(tmp_path / "lexical.jsonl")
    assert len(given) == 16 and len(lexical) == 8
    ps = {r["condition"]: r for r in given if r["system"] == "premise_state"}
    assert ps["C1"]["answered"] and ps["C4"]["answered"]
    assert not ps["C2"]["answered"] and ps["C2"]["unresolved_leaves"] == [ps["C2"]["removed_leaf"]]
    lex = {(r["system"], r["condition"]): r for r in lexical}
    found = set(lex[("premise_state", "R1")]["leaves_retrieved"])
    assert found and found <= set(ex.leaves)  # it located gold leaves by searching the pool
    assert all(r["leaves"] == 3 for r in lexical)
    summary = summarize(given, lexical, resamples=50)
    assert summary["complete_examples"] == 1 and summary["E_B"]["complete_examples"] == 1
