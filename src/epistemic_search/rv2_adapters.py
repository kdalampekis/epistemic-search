"""RV2 adapters: load locally cached external gold datasets and sample them deterministically.

No network and no model here. Every sample is a pure function of (data, seed), selected by a
SHA-256 ordering that does not look at labels except where a stratum is named explicitly.
Labels are mapped explicitly; nothing is silently dropped.
"""

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import Field

from epistemic_search.decomposition import DecompositionDraft, DraftClaim, DraftNode, ProofGraph
from epistemic_search.models import Schema, Text

Stance = Literal["SUPPORT", "CONTRADICT", "NEUTRAL"]
VITAMINC_LABELS = {"SUPPORTS": "SUPPORT", "REFUTES": "CONTRADICT", "NOT ENOUGH INFO": "NEUTRAL"}
SCIFACT_LABELS = {"SUPPORT": "SUPPORT", "CONTRADICT": "CONTRADICT", "NEI": "NEUTRAL"}


def order_key(seed: int, namespace: str, identifier: str) -> str:
    return hashlib.sha256(f"{seed}:{namespace}:{identifier}".encode()).hexdigest()


def pick[T](items: list[T], key: Callable[[T], str], seed: int, namespace: str, n: int) -> list[T]:
    """First ``n`` items in seeded hash order; stable under input reordering."""
    return sorted(items, key=lambda item: order_key(seed, namespace, key(item)))[:n]


class StanceExample(Schema):
    id: Text
    dataset: Text
    claim: Text
    evidence: Text
    gold: Stance
    source_label: Text
    group: str | None = None  # contrastive pair / claim identifier


# ---------------------------------------------------------------- VitaminC


def load_vitaminc(path: Path) -> list[dict[str, str]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    vocabulary = {r["label"] for r in rows}
    if not vocabulary <= set(VITAMINC_LABELS):
        raise ValueError(f"Unmapped VitaminC labels: {sorted(vocabulary - set(VITAMINC_LABELS))}")
    return rows


def vitaminc_pairs(rows: list[dict[str, str]]) -> list[tuple[dict[str, str], dict[str, str]]]:
    """Same claim, two different evidence texts, different labels: a contrastive pair.

    Each pair is oriented by unique_id so the result does not depend on input row order.
    """
    by_claim: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_claim.setdefault((row["case_id"], row["claim"]), []).append(row)
    pairs = []
    for group in by_claim.values():
        group = sorted(group, key=lambda r: r["unique_id"])
        for i, first in enumerate(group):
            for second in group[i + 1 :]:
                if first["label"] != second["label"] and first["evidence"] != second["evidence"]:
                    pairs.append((first, second))
    return pairs


def sample_vitaminc(rows: list[dict[str, str]], n_pairs: int, seed: int) -> list[StanceExample]:
    """n_pairs contrastive pairs, split as evenly as possible over S/R, S/N and R/N pair types.

    One pair per case so items are not nested; labels follow from the pair types.
    """
    kinds: dict[str, list[tuple[dict[str, str], dict[str, str]]]] = {}
    seen_cases: set[str] = set()
    pairs = vitaminc_pairs(rows)
    for first, second in sorted(
        pairs, key=lambda p: order_key(seed, "vitaminc-pair", p[0]["unique_id"])
    ):
        if first["case_id"] in seen_cases:
            continue
        seen_cases.add(first["case_id"])
        kind = "".join(sorted(VITAMINC_LABELS[r["label"]][0] for r in (first, second)))
        kinds.setdefault(kind, []).append((first, second))
    wanted = sorted(kinds)
    if len(wanted) != 3:
        raise ValueError(f"Expected three contrastive pair types, found {wanted}")
    quota = {k: n_pairs // 3 + (i < n_pairs % 3) for i, k in enumerate(wanted)}
    chosen = [p for k in wanted for p in kinds[k][: quota[k]]]
    out = []
    for first, second in chosen:
        group = f"{first['case_id']}:{hashlib.sha256(first['claim'].encode()).hexdigest()[:8]}"
        for row in (first, second):
            out.append(
                StanceExample(
                    id=row["unique_id"],
                    dataset="vitaminc",
                    claim=row["claim"],
                    evidence=row["evidence"],
                    gold=VITAMINC_LABELS[row["label"]],
                    source_label=row["label"],
                    group=group,
                )
            )
    return sorted(out, key=lambda e: (e.group or "", e.id))


# ---------------------------------------------------------------- SciFact


def load_scifact_pairs(root: Path, split: str) -> list[StanceExample]:
    """Every (claim, cited abstract) pair with its official document-level label.

    SUPPORT/CONTRADICT come from the annotated rationale; NEI is the official label of a claim
    whose cited abstract has no rationale. The test split has no labels and is refused.
    """
    if split == "test":
        raise ValueError("SciFact test labels are not public; it is never used")
    base = root / "data"
    corpus = {}
    for line in (base / "corpus.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        corpus[int(doc["doc_id"])] = doc
    out = []
    for line in (base / f"claims_{split}.jsonl").read_text(encoding="utf-8").splitlines():
        claim = json.loads(line)
        labels = {int(d): evs[0]["label"] for d, evs in claim["evidence"].items()}
        for doc_id in claim["cited_doc_ids"]:
            doc_id = int(doc_id)
            label = labels.get(doc_id, "NEI")
            doc = corpus[doc_id]
            out.append(
                StanceExample(
                    id=f"scifact-{split}-{claim['id']}-{doc_id}",
                    dataset="scifact",
                    claim=claim["claim"],
                    evidence=doc["title"] + ". " + " ".join(doc["abstract"]),
                    gold=SCIFACT_LABELS[label],
                    source_label=label,
                    group=f"{claim['id']}",
                )
            )
    return out


def sample_stratified(
    examples: list[StanceExample], n: int, seed: int, namespace: str
) -> list[StanceExample]:
    by_label: dict[str, list[StanceExample]] = {}
    for e in examples:
        by_label.setdefault(e.gold, []).append(e)
    labels = sorted(by_label)
    quota = {k: n // len(labels) + (i < n % len(labels)) for i, k in enumerate(labels)}
    chosen: list[StanceExample] = []
    for label in labels:
        chosen += pick(by_label[label], lambda e: e.id, seed, namespace, quota[label])
    return sorted(chosen, key=lambda e: e.id)


# ---------------------------------------------------------------- EntailmentBank


class EBExample(Schema):
    id: Text
    question: Text
    answer: Text
    hypothesis: Text
    leaves: dict[str, str]  # sentence id -> text, only gold leaves
    intermediates: dict[str, str]
    steps: list[tuple[list[str], str]]  # premises -> conclusion id
    distractors: list[tuple[str, str, float]] = Field(default_factory=list)  # id, text, relevance
    depth: int


def parse_proof(proof: str) -> list[tuple[list[str], str]]:
    steps = []
    for raw in proof.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        left, arrow, right = raw.partition("->")
        if not arrow:
            raise ValueError(f"Malformed proof step: {raw!r}")
        premises = [p.strip() for p in left.split("&")]
        conclusion = right.split(":")[0].strip()
        if not conclusion or any(not p for p in premises):
            raise ValueError(f"Malformed proof step: {raw!r}")
        steps.append((premises, conclusion))
    if not steps or steps[-1][1] != "hypothesis":
        raise ValueError("Proof does not end in the hypothesis")
    return steps


def load_entailmentbank(root: Path, split: str) -> list[EBExample]:
    """Join task_2 (full pool with distractors); leaves are the sentences the proof cites."""
    if split == "test":
        raise ValueError("EntailmentBank test is untouched in RV2")
    base = next((root / "data" / "public_dataset").glob("*/dataset"))
    out = []
    for line in (base / "task_2" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        steps = parse_proof(r["proof"])
        triples: dict[str, str] = r["meta"]["triples"]
        cited = [p for premises, _ in steps for p in premises if p.startswith("sent")]
        if not set(cited) <= set(triples):
            raise ValueError(f"Inconsistent leaves in {r['id']}")
        relevance = dict(
            zip(r["meta"]["distractors"], r["meta"]["distractors_relevance"], strict=True)
        )
        out.append(
            EBExample(
                id=r["id"],
                question=r["question"],
                answer=r["answer"],
                hypothesis=r["hypothesis"],
                leaves={s: triples[s] for s in dict.fromkeys(cited)},
                intermediates=r["meta"]["intermediate_conclusions"],
                steps=steps,
                distractors=sorted(
                    ((d, triples[d], float(relevance[d])) for d in r["meta"]["distractors"]),
                    key=lambda t: (-t[2], t[0]),
                ),
                depth=int(r["depth_of_proof"]),
            )
        )
    return out


def eb_proof_graph(ex: EBExample) -> tuple[ProofGraph | None, str | None]:
    """Convert a gold entailment tree to the pipeline's ProofGraph, or say exactly why not.

    Leaves become CLAIM nodes (their sentence text is the claim), each step an AND over its
    premises, intermediate conclusions are the AND nodes (no claim of their own), and the
    hypothesis is the CONCLUSION root.
    """
    texts = list(ex.leaves.values())
    if len({" ".join(t.casefold().split()) for t in texts}) != len(texts):
        return None, "duplicate leaf text"
    claims = [DraftClaim(id=s, text=t, polarity="POSITIVE") for s, t in ex.leaves.items()]
    nodes = [DraftNode(id=f"leaf_{s}", kind="CLAIM", children=[], claim_id=s) for s in ex.leaves]
    handle = {s: f"leaf_{s}" for s in ex.leaves}
    for index, (premises, conclusion) in enumerate(ex.steps):
        try:
            children = [handle[p] for p in premises]
        except KeyError as exc:
            return None, f"step cites {exc.args[0]} before it is derived"
        if len(set(children)) != len(children):
            return None, "repeated premise within a step"
        if len(children) == 1:
            handle[conclusion] = children[0]
            continue
        node = f"step_{index}"
        nodes.append(DraftNode(id=node, kind="AND", children=children, claim_id=None))
        handle[conclusion] = node
    top = handle["hypothesis"]
    nodes.append(DraftNode(id="root", kind="CONCLUSION", children=[top], claim_id=None))
    try:
        draft = DecompositionDraft(claims=claims, nodes=nodes, conclusion_id="root")
        return draft.graph(), None
    except ValueError as exc:
        return None, str(exc).splitlines()[0]


class PoolDoc(Schema):
    key: Text  # neutral identifier; never reveals leaf/distractor role
    text: Text
    role: Literal["leaf", "distractor"]
    leaf_id: str | None = None


class ControlledCase(Schema):
    example_id: Text
    condition: Literal["C1", "C2", "C3", "C4"]
    removed_leaf: str | None
    docs: list[PoolDoc]


CONDITIONS = {
    "C1": "complete proof",
    "C2": "one required leaf removed",
    "C3": "one leaf removed + distractors",
    "C4": "complete proof + distractors",
}


def controlled_conditions(ex: EBExample, seed: int, n_distractors: int = 4) -> list[ControlledCase]:
    """The four deterministic evidence conditions for one example.

    The removed leaf and the document order depend only on (seed, id); distractors are the
    dataset's own highest-relevance distractors, so they are the most confusable ones.
    """
    removed = min(ex.leaves, key=lambda s: order_key(seed, "removed-leaf", f"{ex.id}:{s}"))
    leaf_docs = {
        s: PoolDoc(key="unassigned", text=t, role="leaf", leaf_id=s) for s, t in ex.leaves.items()
    }
    distractors = [
        PoolDoc(key="unassigned", text=t, role="distractor", leaf_id=d)
        for d, t, _ in ex.distractors[:n_distractors]
    ]
    if len(distractors) < n_distractors:
        raise ValueError(f"{ex.id}: fewer than {n_distractors} distractors")
    plan: dict[str, tuple[list[PoolDoc], str | None]] = {
        "C1": (list(leaf_docs.values()), None),
        "C2": ([d for s, d in leaf_docs.items() if s != removed], removed),
        "C3": ([d for s, d in leaf_docs.items() if s != removed] + distractors, removed),
        "C4": (list(leaf_docs.values()) + distractors, None),
    }
    cases = []
    for name, (docs, gone) in plan.items():
        ordered = sorted(docs, key=lambda d: order_key(seed, f"order-{name}", f"{ex.id}:{d.text}"))
        cases.append(
            ControlledCase(
                example_id=ex.id,
                condition=name,
                removed_leaf=gone,
                docs=[d.model_copy(update={"key": f"doc{i + 1}"}) for i, d in enumerate(ordered)],
            )
        )
    return cases


def sample_eb(
    examples: list[EBExample], per_size: int, sizes: tuple[int, ...], seed: int
) -> list[EBExample]:
    """``per_size`` examples for each leaf count in ``sizes`` that convert cleanly."""
    chosen: list[EBExample] = []
    for size in sizes:
        pool = [
            e
            for e in examples
            if len(e.leaves) == size
            and eb_proof_graph(e)[0] is not None
            and len(e.distractors) >= 4
        ]
        chosen += pick(pool, lambda e: e.id, seed, f"eb-{size}", per_size)
    return chosen


# ---------------------------------------------------------------- StrategyQA


def strategyqa_audit(rows: list[dict[str, object]]) -> dict[str, object]:
    """Classify gold structure by what can be mapped without inventing anything.

    FULL: every decomposition step is a declarative assertion with no ``#n`` back-reference.
    PARTIAL_FACTS_ONLY: gold facts exist but the decomposition steps are questions, so the
    dependency/logic cannot be mapped (and the answer polarity is not a conjunction of facts).
    NONE: nothing mappable.
    """
    classes: Counter[str] = Counter()
    steps_total = steps_questions = refs = 0
    for row in rows:
        steps = [str(s) for s in row.get("decomposition", [])]  # type: ignore[attr-defined]
        steps_total += len(steps)
        steps_questions += sum(s.strip().endswith("?") for s in steps)
        refs += sum("#" in s for s in steps)
        declarative = steps and all(not s.strip().endswith("?") and "#" not in s for s in steps)
        if declarative:
            classes["FULL"] += 1
        elif row.get("facts"):
            classes["PARTIAL_FACTS_ONLY"] += 1
        else:
            classes["NONE"] += 1
    return {
        "examples": len(rows),
        "classes": dict(classes),
        "decomposition_steps": steps_total,
        "steps_that_are_questions": steps_questions,
        "steps_with_back_references": refs,
        "answer_true": sum(bool(r.get("answer")) for r in rows),
    }
