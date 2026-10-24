"""Reproduce the Phase 14 offline report from a completed comparison config."""

import json
from pathlib import Path

import typer

from epistemic_search.config import load_config
from epistemic_search.conflicts import analyze_conflicts
from epistemic_search.decomposition import digest
from epistemic_search.evaluation import file_hash
from epistemic_search.parity import METHODS


def main(config_path: Path, output_path: Path) -> None:
    config = load_config(config_path)
    if config.evaluation is None or config.evaluation.format != "confrag" or config.rag is None:
        raise ValueError("Expected a ConfRAG comparison config")
    root = config_path.parent / config.evaluation.output_dir
    common_path = root / "comparison-manifest.json"
    common = json.loads(common_path.read_text())
    if common["base_config_hash"] != digest(config.model_dump(mode="json")):
        raise ValueError("Config differs from the executed comparison")
    if common["model_settings"] != config.rag.model_dump(mode="json"):
        raise ValueError("Model settings differ from the executed comparison")
    reports = {}
    for method in METHODS:
        report = analyze_conflicts(root / method)
        if [c.query_id for c in report.cases] != common["selected_case_ids"]:
            raise ValueError("Matched, fully executed case sets required for this pilot report")
        reports[method] = report.model_dump(mode="json")
    payload = {
        "analysis": "Phase 14 offline ConfRAG diagnostics",
        "model": config.rag.model,
        "reasoning_effort": config.rag.reasoning_effort,
        "additional_api_calls": 0,
        "additional_api_cost_usd": "0",
        "config_sha256": file_hash(config_path),
        "comparison_manifest_sha256": file_hash(common_path),
        "source_hashes": {
            str(p): file_hash(p)
            for p in [
                Path("scripts/analyze_phase14.py"),
                Path("src/epistemic_search/conflicts.py"),
                Path("src/epistemic_search/belief.py"),
                Path("src/epistemic_search/benchmarks.py"),
            ]
        },
        "reports": reports,
        "limitations": [
            "Two diagnostic examples; no significance or comparative reliability claim.",
            "Corpus-level conflict labels do not label the actually retrieved subset.",
            "Source-cluster coverage is not semantic answer/reason coverage or NMI.",
            "Absent detector outputs and independent safety judgments remain unknown.",
            "Internal conflict freedom does not establish real-world safety or truth.",
        ],
    }
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, indent=2) + "\n")
    typer.echo(f"Wrote {len(reports)} method reports; additional API cost $0")


if __name__ == "__main__":
    typer.run(main)
