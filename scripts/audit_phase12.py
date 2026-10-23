"""Audit existing Phase 12 artifacts and reproduce the compact committed report.

Run from the repository root: uv run --locked python scripts/audit_phase12.py
No HTTP POST is permitted during this audit, including the completed-run replay.
"""

import asyncio
import hashlib
import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from epistemic_search.campaign import load_plan, run_campaign
from epistemic_search.decomposition import digest
from epistemic_search.execution import configured_spend
from epistemic_search.parity import METHODS


def main() -> None:
    runs = load_plan(Path("configs/phase12.yaml"))
    records = []
    total = Decimal(0)
    physical_calls = cache_hits = api_calls = 0
    for path, config in runs:
        assert config.evaluation and config.rag and config.rag.experiment_spend
        root = (path.parent / config.evaluation.output_dir).resolve()
        report = json.loads((root / "comparison.json").read_text())
        common = json.loads((root / "comparison-manifest.json").read_text())
        assert report["complete"] and set(report["summaries"]) == set(METHODS)
        trace_hashes = {}
        errors = []
        for method, summary in report["summaries"].items():
            assert summary["examples"] == config.evaluation.limit
            assert summary["incomplete_usage_examples"] == summary["unknown_cost_examples"] == 0
            manifest = json.loads((root / method / "manifest.json").read_text())
            assert manifest["selected_case_ids"] == common["selected_case_ids"]
            assert manifest["metric_version"] == common["metric_version"]
            usage = summary["usage"]
            total += Decimal(usage["cost_usd"])
            cache_hits += usage["model_cache_hits"]
            physical_calls += usage["model_calls"] - usage["model_cache_hits"]
            api_calls += usage["api_calls"]
            for trace_path in sorted((root / method / "traces").glob("*.json")):
                trace = json.loads(trace_path.read_text())
                usage = trace["usage"]
                for key, limit in [
                    ("model_calls", config.budget.max_llm_calls),
                    ("prompt_tokens", config.budget.max_total_llm_input_tokens),
                    ("completion_tokens", config.budget.max_total_llm_output_tokens),
                    ("search_calls", config.budget.max_search_calls),
                ]:
                    assert limit is not None and usage[key] <= limit
                trace_hashes[str(trace_path.relative_to(root))] = hashlib.sha256(
                    trace_path.read_bytes()
                ).hexdigest()
                if trace["status"] == "error":
                    errors.append(
                        {
                            "method": method,
                            "query_id": trace["query_id"],
                            "error": trace["error"],
                            "usage": usage,
                        }
                    )
                for event in trace["trace"]:
                    if event["type"] == "MODEL":
                        response = event["payload"]["response"]
                        assert response["model"] == "gpt-6-luna"
                        assert response["metadata"]["reasoning_effort"] == "medium"
        records.append(
            {
                "run_id": config.run_id,
                "stage": config.rag.experiment_spend.stage,
                "report_hash": digest(report),
                "selected_case_ids": common["selected_case_ids"],
                "dataset_hashes": common["dataset_hashes"],
                "metric_version": common["metric_version"],
                "summaries": report["summaries"],
                "trace_hashes": trace_hashes,
                "errors": errors,
            }
        )
    last_path, last = runs[-1]
    assert last.rag
    ledger = configured_spend(last.rag, last_path.parent)
    assert ledger
    with sqlite3.connect(ledger.settings.ledger_path) as db:
        rows = db.execute("SELECT reserved,actual,state FROM charges").fetchall()
    assert all(
        state == "settled" and Decimal(actual) <= Decimal(reserved)
        for reserved, actual, state in rows
    )
    assert sum((Decimal(actual) for _, actual, _ in rows), Decimal(0)) == total
    assert len(rows) == physical_calls
    before = ledger.report()["generation_attempts"]
    with patch("httpx.AsyncClient.post", side_effect=AssertionError("Audit forbids API calls")):
        replay = asyncio.run(run_campaign(Path("configs/phase12.yaml"), "comparison"))
    assert replay["complete"] and ledger.report()["generation_attempts"] == before
    output = {
        "model": "gpt-6-luna",
        "reasoning_effort": "medium",
        "stage_policy": "3 smoke cases then 22 diagnostic cases; no further scaling",
        "cumulative_project_cost_usd": str(total),
        "physical_generation_calls": physical_calls,
        "api_calls": api_calls,
        "model_cache_hits": cache_hits,
        "spending": ledger.report(),
        "replay_new_generation_calls": 0,
        "runs": records,
        "source_hashes": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path("src/epistemic_search").glob("*.py"))
        },
        "source_note": (
            "Model, prompts, retrieval and scoring fixed before smoke. Later edits add reporting, "
            "campaign validation and budget protections; no prompt/scorer tuning. Execution "
            "manifests record the prior commit and a dirty worktree. This audit is committed "
            "with the final Phase 12 implementation."
        ),
    }
    target = Path("docs/results/phase12_luna_pilot.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: output[k]
                for k in (
                    "cumulative_project_cost_usd",
                    "physical_generation_calls",
                    "api_calls",
                    "model_cache_hits",
                    "replay_new_generation_calls",
                )
            },
            indent=2,
        )
    )
    for record in records:
        if record["stage"] == "comparison":
            print(record["run_id"])
            for method, summary in record["summaries"].items():
                print(
                    method,
                    {
                        k: summary[k]
                        for k in (
                            "exact_match",
                            "token_f1",
                            "coverage",
                            "errors",
                            "budget_exhausted",
                        )
                    },
                )


if __name__ == "__main__":
    main()
