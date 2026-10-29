import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from epistemic_search.decomposition import ProofGraph
from epistemic_search.rv2_adapters import (
    ControlledCase,
    EBExample,
    controlled_conditions,
    eb_proof_graph,
    load_entailmentbank,
    load_scifact_pairs,
    load_vitaminc,
    parse_proof,
    sample_eb,
    sample_stratified,
    sample_vitaminc,
    strategyqa_audit,
)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def vrow(case: str, claim: str, evidence: str, label: str, n: int) -> dict[str, str]:
    return {
        "unique_id": f"{case}_{n}",
        "case_id": case,
        "wiki_revision_id": "1",
        "label": label,
        "claim": claim,
        "evidence": evidence,
        "page": "p",
        "revision_type": "real",
    }


def vitaminc_fixture(tmp_path: Path) -> Path:
    rows = []
    for i, (a, b) in enumerate(
        [("SUPPORTS", "REFUTES"), ("SUPPORTS", "NOT ENOUGH INFO"), ("REFUTES", "NOT ENOUGH INFO")]
        * 4
    ):
        rows += [
            vrow(f"c{i}", f"claim {i}", f"before {i}", a, 1),
            vrow(f"c{i}", f"claim {i}", f"after {i}", b, 2),
        ]
    path = tmp_path / "dev.jsonl"
    write_jsonl(path, rows)
    return path


def test_vitaminc_vocabulary_is_checked_and_pairs_are_balanced(tmp_path: Path) -> None:
    path = vitaminc_fixture(tmp_path)
    rows = load_vitaminc(path)
    sample = sample_vitaminc(rows, 6, seed=3)
    assert len(sample) == 12 and len({e.group for e in sample}) == 6
    assert {e.gold for e in sample} == {"SUPPORT", "CONTRADICT", "NEUTRAL"}
    assert [e.id for e in sample] == [
        e.id for e in sample_vitaminc(list(reversed(rows)), 6, seed=3)
    ]
    assert sample != sample_vitaminc(rows, 6, seed=4)
    bad = tmp_path / "bad.jsonl"
    write_jsonl(bad, [vrow("x", "c", "e", "MAYBE", 1)])
    with pytest.raises(ValueError, match="Unmapped VitaminC labels"):
        load_vitaminc(bad)


def test_scifact_uses_official_neutral_class_and_refuses_test(tmp_path: Path) -> None:
    base = tmp_path / "data"
    write_jsonl(
        base / "corpus.jsonl",
        [
            {"doc_id": 1, "title": "T1", "abstract": ["a1.", "a2."], "structured": False},
            {"doc_id": 2, "title": "T2", "abstract": ["b1."], "structured": False},
        ],
    )
    write_jsonl(
        base / "claims_dev.jsonl",
        [
            {
                "id": 10,
                "claim": "sup",
                "evidence": {"1": [{"sentences": [0], "label": "SUPPORT"}]},
                "cited_doc_ids": [1],
            },
            {
                "id": 11,
                "claim": "con",
                "evidence": {"2": [{"sentences": [0], "label": "CONTRADICT"}]},
                "cited_doc_ids": [2],
            },
            {"id": 12, "claim": "nei", "evidence": {}, "cited_doc_ids": [1]},
        ],
    )
    pairs = load_scifact_pairs(tmp_path, "dev")
    assert {p.source_label: p.gold for p in pairs} == {
        "SUPPORT": "SUPPORT",
        "CONTRADICT": "CONTRADICT",
        "NEI": "NEUTRAL",
    }
    assert pairs[0].evidence == "T1. a1. a2."
    with pytest.raises(ValueError, match="never used"):
        load_scifact_pairs(tmp_path, "test")
    assert len(sample_stratified(pairs, 3, 0, "x")) == 3


def eb_record(
    rid: str, proof: str, triples: dict[str, str], distractors: list[str]
) -> dict[str, object]:
    return {
        "id": rid,
        "question": "Q?",
        "answer": "A",
        "hypothesis": "H",
        "proof": proof,
        "depth_of_proof": 2,
        "meta": {
            "triples": triples,
            "distractors": distractors,
            "distractors_relevance": [float(10 - i) for i in range(len(distractors))],
            "intermediate_conclusions": {"int1": "i1"},
        },
    }


def eb_fixture(tmp_path: Path) -> Path:
    triples = {f"sent{i}": f"fact {i}" for i in range(1, 9)}
    tree = eb_record(
        "t1",
        "sent1 & sent2 -> int1: i1; int1 & sent3 -> hypothesis;",
        triples,
        ["sent4", "sent5", "sent6", "sent7"],
    )
    shared = eb_record(
        "t2",
        "sent1 & sent2 -> int1: i1; int1 & sent2 & sent3 -> hypothesis;",
        triples,
        ["sent4", "sent5", "sent6", "sent7"],
    )
    dup = eb_record(
        "t3",
        "sent1 & sent2 -> hypothesis;",
        {**triples, "sent2": "FACT 1"},
        ["sent4", "sent5", "sent6", "sent7"],
    )
    write_jsonl(tmp_path / "data/public_dataset/v/dataset/task_2/dev.jsonl", [tree, shared, dup])
    return tmp_path


def test_entailment_trees_convert_with_explicit_reasons(tmp_path: Path) -> None:
    examples = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path), "dev")}
    graph, reason = eb_proof_graph(examples["t1"])
    assert isinstance(graph, ProofGraph) and reason is None
    assert {n.kind for n in graph.nodes} == {"CLAIM", "AND", "CONCLUSION"} and len(
        graph.claims
    ) == 3
    assert eb_proof_graph(examples["t2"])[0] is not None  # shared leaf: a DAG, still valid
    assert eb_proof_graph(examples["t3"]) == (None, "duplicate leaf text")
    assert examples["t1"].distractors[0][2] > examples["t1"].distractors[-1][2]
    with pytest.raises(ValueError, match="untouched"):
        load_entailmentbank(tmp_path, "test")
    with pytest.raises(ValueError, match="Malformed"):
        parse_proof("sent1 sent2;")
    with pytest.raises(ValueError, match="hypothesis"):
        parse_proof("sent1 & sent2 -> int1;")


def test_controlled_conditions_have_the_specified_composition(tmp_path: Path) -> None:
    ex = {e.id: e for e in load_entailmentbank(eb_fixture(tmp_path), "dev")}["t1"]
    cases = {c.condition: c for c in controlled_conditions(ex, seed=1)}
    roles = {k: sorted(d.role for d in c.docs) for k, c in cases.items()}
    assert roles["C1"] == ["leaf"] * 3 and roles["C4"] == ["distractor"] * 4 + ["leaf"] * 3
    assert roles["C2"] == ["leaf"] * 2 and roles["C3"] == ["distractor"] * 4 + ["leaf"] * 2
    removed = cases["C2"].removed_leaf
    assert removed and cases["C3"].removed_leaf == removed and cases["C1"].removed_leaf is None

    def leaf_texts(case: ControlledCase) -> set[str]:
        return {d.text for d in case.docs if d.role == "leaf"}

    assert ex.leaves[removed] not in leaf_texts(cases["C2"])
    assert leaf_texts(cases["C1"]) == leaf_texts(cases["C4"]) == set(ex.leaves.values())
    assert all(d.key.startswith("doc") for c in cases.values() for d in c.docs)
    assert cases == {c.condition: c for c in controlled_conditions(ex, seed=1)}
    assert controlled_conditions(ex, seed=2)[1].removed_leaf is not None


def test_sample_eb_only_takes_convertible_examples_with_enough_distractors(tmp_path: Path) -> None:
    examples = load_entailmentbank(eb_fixture(tmp_path), "dev")
    picked = sample_eb(examples, per_size=5, sizes=(3,), seed=0)
    assert {e.id for e in picked} == {"t1", "t2"}  # t3 has duplicate leaf text and 2 leaves
    short = EBExample(
        id="s",
        question="q",
        answer="a",
        hypothesis="h",
        leaves={},
        intermediates={},
        steps=[],
        depth=1,
    )
    assert sample_eb([short], 1, (3,), 0) == []


def test_strategyqa_classes_never_invent_structure() -> None:
    rows: list[dict[str, object]] = [
        {
            "decomposition": ["Who was born first?", "Is #1 before #2?"],
            "facts": ["a"],
            "answer": True,
        },
        {"decomposition": ["Aristotle lived before laptops."], "facts": [], "answer": False},
        {"decomposition": ["Is X?"], "facts": [], "answer": False},
    ]
    audit = strategyqa_audit(rows)
    assert audit["classes"] == {"PARTIAL_FACTS_ONLY": 1, "FULL": 1, "NONE": 1}
    assert audit["steps_that_are_questions"] == 3 and audit["steps_with_back_references"] == 1
