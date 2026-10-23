import asyncio
import json
from pathlib import Path

import pytest

from epistemic_search.adapters import CorpusDocument, FixtureModelProvider, FixtureSearchProvider
from epistemic_search.config import RagConfig
from epistemic_search.evidence import EvidenceLedger, classify_evidence, collect_evidence
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


@pytest.mark.parametrize(
    "text", ["not JSON", '{"items":[{"span":"invented","stance":"SUPPORT","stance_score":1}]}']
)
def test_invalid_extraction_retains_cost(source: Source, text: str) -> None:
    result = asyncio.run(
        classify_evidence(
            "q",
            Claim(id="c", text="claim"),
            SearchResult(source=source, text="original", query="query", rank=1),
            settings(),
            FixtureModelProvider([text]),
        )
    )
    assert result.items == [] and result.errors
    assert result.usage.model_calls == 1 and result.trace


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
