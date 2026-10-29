import asyncio
import json
from pathlib import Path

import pytest

from epistemic_search.adapters import CorpusDocument, FixtureModelProvider, FixtureSearchProvider
from epistemic_search.config import RagConfig
from epistemic_search.evidence import (
    EvidenceBatch,
    EvidenceLedger,
    align_span,
    classify_evidence,
    collect_evidence,
)
from epistemic_search.models import Claim, Source
from epistemic_search.providers import SearchResult


def settings() -> RagConfig:
    return RagConfig(corpus_path=Path("unused"), responses_path=Path("unused"))


def test_relevance_is_not_stance_and_conflicts_survive(source: Source) -> None:
    document = SearchResult(
        source=source,
        text="Paris is the capital. Paris is not the capital.",
        query="capital",
        rank=1,
        retrieval_score=100,
    )
    output = json.dumps(
        {
            "items": [
                {"span": "Paris is the capital.", "stance": "SUPPORT", "stance_score": 0.8},
                {"span": "Paris is not the capital.", "stance": "CONTRADICT", "stance_score": 0.9},
            ]
        }
    )
    result = asyncio.run(
        classify_evidence(
            "q",
            Claim(id="c", text="Paris is the capital"),
            document,
            settings(),
            FixtureModelProvider([output]),
        )
    )
    assert not result.errors
    assert [e.stance for e in result.items] == ["SUPPORT", "CONTRADICT"]
    assert result.items[1].retrieval_score == 100
    assert result.items[1].provenance.search_query == "capital"
    assert result.items[1].source == source
    assert result.usage.model_calls == 1
    ledger = EvidenceLedger()
    for item in result.items:
        ledger.add(item)
        ledger.add(item)
    assert len(ledger.items) == len(ledger.compact()) == 2


def test_unparseable_extraction_is_still_a_batch_error_and_retains_cost(source: Source) -> None:
    result = asyncio.run(
        classify_evidence(
            "q",
            Claim(id="c", text="claim"),
            SearchResult(source=source, text="original", query="query", rank=1),
            settings(),
            FixtureModelProvider(["not JSON"]),
        )
    )
    assert result.items == [] and result.errors
    assert result.usage.model_calls == 1 and result.trace


def extract(source: Source, document: str, spans: list[str]) -> EvidenceBatch:
    output = json.dumps(
        {"items": [{"span": s, "stance": "SUPPORT", "stance_score": 0.8} for s in spans]}
    )
    return asyncio.run(
        classify_evidence(
            "q",
            Claim(id="c", text="claim"),
            SearchResult(source=source, text=document, query="query", rank=1),
            settings(),
            FixtureModelProvider([output]),
        )
    )


def test_hallucinated_span_rejects_only_that_item_and_is_recorded(source: Source) -> None:
    result = extract(source, "Alpha holds. Beta holds.", ["invented", "Beta holds.", "   "])
    assert not result.errors
    assert [i.span for i in result.items] == ["Beta holds."]
    assert [(r.span, r.reason) for r in result.rejections] == [
        ("invented", "absent_from_source"),
        ("   ", "empty_span"),
    ]
    rejected = [e for e in result.trace if e.type == "EVIDENCE_SPAN_REJECTED"]
    assert len(rejected) == 2 and rejected[0].payload["span"] == "invented"
    assert result.usage.model_calls == 1  # the call is still paid for and accounted


def test_formatting_only_differences_align_to_the_exact_source_text(source: Source) -> None:
    document = "He served as\u00a0Acting Secretary \u2013 until 2009.  The \u201cDeputy\u201d role"
    result = extract(
        source,
        document,
        [
            "served as Acting Secretary - until 2009.",
            'The "Deputy" role',
            "served as Acting Secretary",
        ],
    )
    assert not result.rejections
    first, second, third = result.items
    assert first.span == "served as\u00a0Acting Secretary \u2013 until 2009."
    assert first.span in document and second.span in document and third.span in document
    assert first.metadata == {
        "alignment": "normalized",
        "model_span": "served as Acting Secretary - until 2009.",
    }
    assert third.metadata == {"alignment": "normalized", "model_span": "served as Acting Secretary"}
    assert second.span == "The \u201cDeputy\u201d role"


def test_exact_spans_keep_their_historical_identity(source: Source) -> None:
    result = extract(source, "Alpha holds.", ["Alpha holds."])
    assert result.items[0].metadata == {} and result.items[0].span == "Alpha holds."


@pytest.mark.parametrize(
    "span,document",
    [
        ("alpha holds", "Alpha holds."),  # case is never folded
        ("Alpha does not hold", "Alpha holds."),  # wording is never changed
        ("Alpha holds", "Alpha  or holds"),  # not contiguous in the source
    ],
)
def test_alignment_never_accepts_a_different_statement(span: str, document: str) -> None:
    assert align_span(span, document) is None


def test_alignment_maps_multi_character_expansions_back_to_original_offsets() -> None:
    document = "The \ufb01nal result was reported."  # 'ﬁ' ligature expands to two letters
    aligned = align_span("final result", document)
    assert aligned == ("\ufb01nal result", "normalized")
    assert aligned[0] in document


def test_compaction_preserves_both_sources(source: Source) -> None:
    second = source.model_copy(deep=True)
    second.id = "s2"
    second.uri = "fixture://second"
    search = FixtureSearchProvider(
        [
            CorpusDocument(source=source, text="A fact."),
            CorpusDocument(source=second, text="A fact."),
        ]
    )
    output = '{"items":[{"span":"A fact.","stance":"SUPPORT","stance_score":0.8}]}'
    result = asyncio.run(
        collect_evidence(
            "q",
            Claim(id="c", text="A fact"),
            "fact",
            2,
            settings(),
            search,
            FixtureModelProvider([output, output]),
        )
    )
    assert result.usage.search_calls == 1 and result.usage.model_calls == 2
    ledger = EvidenceLedger()
    for item in result.items:
        ledger.add(item)
    compact = ledger.compact()
    assert len(compact) == 1
    assert compact[0].source_ids == ["s1", "s2"]
    assert set(compact[0].evidence_ids) == {e.id for e in result.items}
    conflict = result.items[0].model_copy(deep=True)
    conflict.span = "changed"
    with pytest.raises(ValueError, match="cannot change"):
        ledger.add(conflict)


def test_empty_extraction_does_not_invent_neutral_evidence(source: Source) -> None:
    result = asyncio.run(
        classify_evidence(
            "q",
            Claim(id="c", text="claim"),
            SearchResult(source=source, text="unrelated", query="query", rank=1),
            settings(),
            FixtureModelProvider(['{"items":[]}']),
        )
    )
    assert result.items == [] and not result.errors
