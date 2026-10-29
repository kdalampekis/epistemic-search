"""RV2 final decision: read the four result files, apply the committed rule, write the verdict.

No judgment enters here. If an input is missing the class is INCONCLUSIVE, never a guess.
"""

import json
from pathlib import Path
from typing import Any

from epistemic_search.rv2_analysis import classify
from epistemic_search.rv2_run import ROOT, write_new_json

RESULTS = Path("docs/results/rv2")


def load(root: Path, name: str) -> dict[str, Any] | None:
    path = root / RESULTS / name / "results.json"
    return json.loads(path.read_text()) if path.exists() else None


def decide(root: Path = ROOT) -> dict[str, Any]:
    a, b, c, d = (load(root, n) for n in ("rv2_a", "rv2_b", "rv2_c", "rv2_d"))
    inputs = {
        "RV2-A": a is not None,
        "RV2-B": b is not None,
        "RV2-C": c is not None,
        "RV2-D": d is not None,
    }
    stance = a["verdict"]["stance_works"] if a else None
    c_metrics = c["metrics"] if c else {}
    b_metrics = b["metrics"] if b else {}
    es_examples = int(c_metrics.get("complete_examples", 0))
    q = {
        "Q1_gold_structure_and_evidence_behaves_correctly": c_metrics.get("Q1"),
        "Q2_detects_insufficiency_better_than_baselines": c_metrics.get("Q2"),
        "Q3_distractors_do_not_cause_false_closure": c_metrics.get("Q3"),
        "Q4_oracle_structure_materially_beats_generated": b_metrics.get("Q4"),
        "Q5_premise_directed_retrieval_more_efficient": (d or {}).get("metrics", {}).get("Q5"),
        "stance": {"works": stance},
    }

    def verdict(key: str) -> Any:
        return (q[key] or {}).get("verdict", "UNDETERMINED")

    result = classify(
        es_examples,
        verdict("Q1_gold_structure_and_evidence_behaves_correctly"),
        verdict("Q2_detects_insufficiency_better_than_baselines"),
        c_metrics.get("depth", {}),
        verdict("Q4_oracle_structure_materially_beats_generated"),
        stance,
    )
    if not all(inputs.values()):
        result = {
            "class": "INCONCLUSIVE",
            "rule": f"missing inputs: {[k for k, v in inputs.items() if not v]}",
        }
    return {
        "rule_source": "docs/experiments/RV2_EXTERNAL_VALIDATION_PLAN.md (pre-registered)",
        "inputs_present": inputs,
        "complete_epistemic_search_examples": es_examples,
        "questions": q,
        "classification": result,
    }


def write(root: Path = ROOT) -> dict[str, Any]:
    decision = decide(root)
    write_new_json(root / RESULTS / "decision.json", decision)
    return decision
