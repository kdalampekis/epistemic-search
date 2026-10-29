"""RV2 dataset audit: facts measured from the local files, written as deterministic JSON."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from epistemic_search.rv2_adapters import (
    VITAMINC_LABELS,
    eb_proof_graph,
    load_entailmentbank,
    load_scifact_pairs,
    load_vitaminc,
    sample_eb,
    sample_stratified,
    sample_vitaminc,
    strategyqa_audit,
    vitaminc_pairs,
)

SEED = 20261029


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sizes(counter: Counter[Any]) -> dict[str, int]:
    return {str(k): v for k, v in sorted(counter.items(), key=lambda kv: str(kv[0]))}


def audit_scifact(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("train", "dev", "test"):
        rows = jsonl(root / "data" / f"claims_{split}.jsonl")
        out[split] = {"claims": len(rows), "labeled": "evidence" in rows[0]}
    for split in ("train", "dev"):
        pairs = load_scifact_pairs(root, split)
        out[split]["claim_document_pairs"] = len(pairs)
        out[split]["pair_labels"] = sizes(Counter(p.source_label for p in pairs))
    dev = load_scifact_pairs(root, "dev")
    out["sample"] = sizes(Counter(e.gold for e in sample_stratified(dev, 100, SEED, "scifact-dev")))
    return out


def audit_vitaminc(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"label_mapping": VITAMINC_LABELS}
    for split in ("train", "dev", "test"):
        rows = load_vitaminc(root / "vitaminc" / f"{split}.jsonl")
        entry: dict[str, Any] = {
            "rows": len(rows),
            "labels": sizes(Counter(r["label"] for r in rows)),
            "revision_types": sizes(Counter(r["revision_type"] for r in rows)),
        }
        if split == "dev":
            kinds = Counter(
                "".join(sorted(VITAMINC_LABELS[r["label"]][0] for r in pair))
                for pair in vitaminc_pairs(rows)
            )
            entry["contrastive_pairs_by_type"] = sizes(kinds)
            sample = sample_vitaminc(rows, 50, SEED)
            entry["sample"] = {
                "items": len(sample),
                "labels": sizes(Counter(e.gold for e in sample)),
                "pairs": len({e.group for e in sample}),
            }
        out[split] = entry
    return out


def audit_strategyqa(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("train", "train_filtered", "test"):
        rows = json.loads((root / f"strategyqa_{name}.json").read_text(encoding="utf-8"))
        out[name] = {"examples": len(rows), "fields": sorted(rows[0])}
    out["train_structure"] = strategyqa_audit(
        json.loads((root / "strategyqa_train.json").read_text(encoding="utf-8"))
    )
    return out


def audit_entailmentbank(root: Path) -> dict[str, Any]:
    examples = load_entailmentbank(root, "dev")
    convertible = reasons = shared = 0
    for ex in examples:
        graph, why = eb_proof_graph(ex)
        convertible += graph is not None
        reasons += why is not None
        if graph:
            parents = Counter(c for n in graph.nodes for c in n.children)
            shared += any(v > 1 for v in parents.values())
    sample = sample_eb(examples, 6, (3, 4, 5), SEED)
    return {
        "dev_examples": len(examples),
        "leaves": sizes(Counter(len(e.leaves) for e in examples)),
        "depth": sizes(Counter(e.depth for e in examples)),
        "distractors_available": sizes(Counter(min(len(e.distractors), 20) for e in examples)),
        "fully_convertible": convertible,
        "not_convertible": reasons,
        "convertible_with_shared_nodes": shared,
        "sample_for_controlled_experiments": {
            "examples": len(sample),
            "by_leaf_count": sizes(Counter(len(e.leaves) for e in sample)),
        },
    }


def audit_multihop(root: Path) -> dict[str, Any]:
    hotpot = json.loads((root / "hotpotqa" / "hotpot_dev_distractor.json").read_text())
    wiki = json.loads((root / "2wikimultihop" / "dev.json").read_text())

    def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "examples": len(rows),
            "types": sizes(Counter(r["type"] for r in rows)),
            "paragraphs_per_question": sizes(Counter(len(r["context"]) for r in rows)),
            "gold_titles": sizes(Counter(len({t for t, _ in r["supporting_facts"]}) for r in rows)),
        }

    return {"hotpotqa_dev_distractor": summary(hotpot), "2wikimultihop_dev": summary(wiki)}


def audit_datasets(data_root: Path, manifests: Path) -> dict[str, Any]:
    versions = {
        p.stem: yaml.safe_load(p.read_text())["version_or_commit"]
        for p in sorted(manifests.glob("*.yaml"))
    }
    return {
        "seed": SEED,
        "versions": versions,
        "scifact": audit_scifact(data_root / "scifact"),
        "vitaminc": audit_vitaminc(data_root / "vitaminc"),
        "strategyqa": audit_strategyqa(data_root / "strategyqa"),
        "entailmentbank": audit_entailmentbank(data_root / "entailmentbank"),
        "multihop": audit_multihop(data_root),
        "hover": "not used (see data/manifests/hover.yaml)",
    }
