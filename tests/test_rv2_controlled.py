import asyncio
import json
from decimal import Decimal
from pathlib import Path

import httpx
from test_rv2_adapters import eb_fixture

from epistemic_search.config import RagConfig
from epistemic_search.evaluation import file_hash
from epistemic_search.models import Usage
from epistemic_search.providers import ModelRequest, ModelResponse
from epistemic_search.rv2_adapters import controlled_conditions, load_entailmentbank
from epistemic_search.rv2_controlled import (
    GivenPoolSearch,
    corpus,
    done_keys,
    load_rows,
    run_example,
)
from epistemic_search.tokens import count_tokens


class ScriptedLuna:
    """An agreeable stand-in: extracts a claim when it is verbatim in the document, answers when
    asked to, and the naive/closed-book scripts are deliberately overconfident."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request.prompt_version)
        version = request.prompt_version
        if version == "evidence-stance-v1":
            data = json.loads(request.prompt[request.prompt.index('{"claim"') :])
            hit = data["claim"] in data["document"]
            items = [{"span": data["claim"], "stance": "SUPPORT", "stance_score": 0.9}] * hit
            text = json.dumps({"items": items})
        elif version == "epistemic-answer-v1":
            payload = json.loads(request.prompt.split("\nPayload:\n")[1])
            ids = sorted({s for e in payload["evidence"] for s in e["source_ids"]})
            text = json.dumps(
                {"answer": "The rocks would break into smaller pieces.", "citation_ids": ids}
            )
        elif version == "naive-answer-v1":
            docs = json.loads(request.prompt.split("\nEvidence:\n")[1])
            text = json.dumps(
                {"answer": "The rocks would break.", "citation_ids": [docs[0]["source_id"]]}
            )
        elif version == "premise-only-decision-v1":
            payload = json.loads(request.prompt.split("\nPayload:\n")[1])
            have = [e["text"] for e in payload["evidence"]]
            missing = [p for p in payload["premises"] if p["text"] not in have]
            if missing:
                step = {
                    "action": "SEARCH_MORE",
                    "target_claim_id": missing[0]["id"],
                    "answer": None,
                    "citation_ids": [],
                }
            else:
                step = {
                    "action": "ANSWER",
                    "target_claim_id": None,
                    "answer": "All premises hold.",
                    "citation_ids": [payload["evidence"][0]["source_id"]],
                }
            text = json.dumps(step)
        elif version == "closed-book-answer-v1":
            text = json.dumps({"answer": "unknown"})
        else:
            raise AssertionError(version)
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


def rag() -> RagConfig:
    return RagConfig(corpus_path=Path("unused"), responses_path=Path("unused"), max_rounds=3)


def run(
    tmp_path: Path, systems: tuple[str, ...]
) -> tuple[list[dict[str, object]], Path, ScriptedLuna]:
    loaded = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path), "dev")}["t1"]
    ex = loaded.model_copy(update={"answer": "The rocks would break into smaller pieces."})
    conditions = controlled_conditions(ex, seed=1)
    out, traces, model = tmp_path / "cases.jsonl", tmp_path / "traces", ScriptedLuna()

    async def go() -> str | None:
        async with httpx.AsyncClient() as client:
            return await run_example(
                ex,
                conditions,
                systems=systems,
                oracle=True,
                mode="oracle",
                base_rag=rag(),
                run_id="test",
                cache_dir=tmp_path / "cache",
                out=out,
                traces=traces,
                client=client,
                model=model,
            )

    assert asyncio.run(go()) is None
    return load_rows(out), traces, model


def by(rows: list[dict[str, object]], system: str) -> dict[str, dict[str, object]]:
    return {str(r["condition"]): r for r in rows if r["system"] == system}


def test_given_pool_returns_the_whole_pool_and_nothing_else(tmp_path: Path) -> None:
    ex = load_entailmentbank(eb_fixture(tmp_path), "dev")[0]
    case = controlled_conditions(ex, seed=1)[3]
    search = GivenPoolSearch(corpus(case))
    full = asyncio.run(search.search("anything at all", len(case.docs)))
    assert [r.text for r in full.results] == [d.text for d in case.docs]
    assert {r.source.title for r in full.results} == {"evidence sentence"}
    assert len(asyncio.run(search.search("q", 2)).results) == 2


def test_epistemic_search_detects_the_missing_leaf_and_stops_without_looping(
    tmp_path: Path,
) -> None:
    rows, traces, _ = run(tmp_path, ("epistemic_search",))
    es = by(rows, "epistemic_search")
    removed = str(es["C2"]["removed_leaf"])
    for complete in ("C1", "C4"):
        assert es[complete]["outcome"] == "ANSWER" and es[complete]["unresolved_leaves"] == []
        assert es[complete]["answer_hit"] is True
    for missing in ("C2", "C3"):
        assert es[missing]["outcome"] == "ABSTAIN" and es[missing]["answered"] is False
        assert es[missing]["unresolved_leaves"] == [removed]
        assert es[missing]["no_progress"] is True
        assert str(es[missing]["decision"]["rationale"]).startswith("NO_PROGRESS")  # type: ignore[index]
        assert es[missing]["usage"]["search_calls"] == 2  # type: ignore[index]
    row = es["C1"]
    assert file_hash(traces / "epistemic_search__t1__C1.json") == row["trace_sha256"]


def test_baselines_are_recorded_even_when_they_answer_without_evidence(tmp_path: Path) -> None:
    rows, _, model = run(tmp_path, ("closed_book", "naive_rag", "premise_only", "epistemic_search"))
    assert len(rows) == 1 + 3 * 4 and len(done_keys(tmp_path / "cases.jsonl")) == 13
    naive = by(rows, "naive_rag")
    assert all(naive[c]["answered"] for c in ("C1", "C2", "C3", "C4"))  # unsupported answers count
    premise = by(rows, "premise_only")
    assert premise["C1"]["answered"] and premise["C4"]["answered"]
    assert not premise["C2"]["answered"] and premise["C2"]["no_progress"] is True
    closed = by(rows, "closed_book")
    assert list(closed) == ["NA"] and closed["NA"]["pool"] == []
    # Oracle structure came from the case: the decomposition prompt is never used.
    assert "premise-decomposition-v1" not in model.calls


def test_a_stopped_run_resumes_without_repeating_or_rewriting_results(tmp_path: Path) -> None:
    first, _, _ = run(tmp_path, ("epistemic_search",))
    before = (tmp_path / "cases.jsonl").read_text()
    rows, _, model = run(tmp_path, ("epistemic_search",))
    assert (tmp_path / "cases.jsonl").read_text() == before and len(rows) == len(first) == 4
    assert model.calls == []  # nothing was re-run
