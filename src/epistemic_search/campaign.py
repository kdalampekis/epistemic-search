"""Small preregistered Phase 12 stages; no automatic scaling to benchmarks."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from epistemic_search.config import RunConfig, load_config
from epistemic_search.decomposition import digest
from epistemic_search.evaluation import Summary, manifest
from epistemic_search.execution import local_api_key
from epistemic_search.models import Schema, Text
from epistemic_search.parity import METHODS, compare
from epistemic_search.spending import SpendLedger


class Phase12Plan(Schema):
    smoke: list[Path] = Field(min_length=1)
    comparison: list[Path] = Field(min_length=1)
    smoke_audit: Path | None = None


class SmokeAudit(Schema):
    informative: bool
    rationale: Text
    comparison_report_hashes: dict[str, str]


def verify_smoke_audit(path: Path, runs: list[tuple[Path, RunConfig]]) -> None:
    plan = Phase12Plan.model_validate(yaml.safe_load(path.read_text()))
    if plan.smoke_audit is None:
        raise ValueError("Comparison requires a recorded smoke audit before scaling")
    audit = SmokeAudit.model_validate_json((path.parent / plan.smoke_audit).read_text())
    if not audit.informative:
        raise ValueError("Smoke audit does not justify the comparison pilot")
    expected = {}
    for config_path, config in runs:
        assert config.rag and config.rag.experiment_spend and config.evaluation
        if config.rag.experiment_spend.stage != "smoke":
            continue
        root = config_path.parent / config.evaluation.output_dir
        report = json.loads((root / "comparison.json").read_text())
        expected[config.run_id] = digest(report)
        for trace_path in root.glob("*/traces/*.json"):
            trace = json.loads(trace_path.read_text())
            if any(e["type"] in {"MODEL_ERROR", "SEARCH_ERROR"} for e in trace["trace"]):
                raise ValueError("Provider failures must be resolved before scaling")
    if audit.comparison_report_hashes != expected:
        raise ValueError("Smoke audit does not match the current complete smoke reports")


def load_plan(path: Path) -> list[tuple[Path, RunConfig]]:
    plan = Phase12Plan.model_validate(yaml.safe_load(path.read_text()))
    runs: list[tuple[Path, RunConfig]] = []
    ledger_path: Path | None = None
    outputs: set[Path] = set()
    run_ids: set[str] = set()
    policy: dict[str, object] | None = None
    for stage, paths in [("smoke", plan.smoke), ("comparison", plan.comparison)]:
        for relative in paths:
            config_path = (path.parent / relative).resolve()
            config = load_config(config_path)
            if (
                config.rag is None
                or config.rag.experiment_spend is None
                or config.evaluation is None
            ):
                raise ValueError(
                    "Each campaign run requires primary model, spending and evaluation settings"
                )
            settings = config.rag.experiment_spend
            if settings.stage != stage:
                raise ValueError("Run spending stage does not match the campaign stage")
            current_ledger = (config_path.parent / settings.ledger_path).resolve()
            if ledger_path is not None and current_ledger != ledger_path:
                raise ValueError("All Phase 12 runs must share one persistent budget ledger")
            ledger_path = current_ledger
            if settings.run_id in run_ids:
                raise ValueError("Campaign spending run IDs must be distinct")
            run_ids.add(settings.run_id)
            current_policy: dict[str, object] = {
                "rag": config.rag.model_dump(mode="json", exclude={"experiment_spend"}),
                "budget": config.budget.model_dump(mode="json"),
                "project_policy": settings.model_dump(
                    mode="json", exclude={"run_id", "run_usd", "stage"}
                ),
            }
            if policy is not None and current_policy != policy:
                raise ValueError(
                    "All runs must use identical primary model/reasoning/retrieval settings"
                )
            policy = current_policy
            output = (config_path.parent / config.evaluation.output_dir).resolve()
            if output in outputs:
                raise ValueError("Campaign output directories must be distinct")
            outputs.add(output)
            runs.append((config_path, config))
    return runs


def estimate_campaign(path: Path, stage: Literal["smoke", "comparison"]) -> dict[str, object]:
    estimates = []
    runs = load_plan(path)
    first = runs[0][1]
    assert first.rag and first.rag.experiment_spend
    for config_path, config in runs:
        assert config.rag and config.rag.experiment_spend and config.evaluation
        if config.rag.experiment_spend.stage != stage:
            continue
        n = config.evaluation.limit
        b = config.budget
        if (
            n is None
            or b.max_total_llm_input_tokens is None
            or b.max_total_llm_output_tokens is None
        ):
            raise ValueError("Pilot estimation requires finite example and token limits")
        assert config.rag.cache_write_usd_per_million and config.rag.output_usd_per_million
        cells = n * len(METHODS)
        worst = (
            cells
            * (
                Decimal(b.max_total_llm_input_tokens) * config.rag.cache_write_usd_per_million
                + Decimal(b.max_total_llm_output_tokens) * config.rag.output_usd_per_million
            )
            / Decimal(1_000_000)
        )
        # Planning scenario, not an empirically measured expectation; no cache savings assumed.
        scenario = (
            cells
            * 3
            * (
                1500 * config.rag.cache_write_usd_per_million
                + 1200 * config.rag.output_usd_per_million
            )
            / Decimal(1_000_000)
        )
        estimates.append(
            {
                "config": str(config_path),
                "examples": n,
                "method_examples": cells,
                "planning_scenario_usd": str(scenario),
                "token_ceiling_cost_usd": str(worst),
                "maximum_input_tokens": cells * b.max_total_llm_input_tokens,
                "maximum_output_tokens": cells * b.max_total_llm_output_tokens,
                "run_cap_usd": str(config.rag.experiment_spend.run_usd),
            }
        )
    return {
        "stage": stage,
        "runs": estimates,
        "scenario_assumption": (
            "3 calls per method-example; 1500 input + 1200 output per call; no cache hits"
        ),
        "project_cap_usd": str(first.rag.experiment_spend.total_usd),
        "automatic_scaling": False,
    }


async def run_campaign(
    path: Path, stage: Literal["smoke", "comparison"] = "smoke"
) -> dict[str, object]:
    runs = load_plan(path)
    if stage == "comparison":
        verify_smoke_audit(path, runs)
    if not local_api_key(path.parent):
        raise ValueError("OPENAI_API_KEY is not configured; no paid calls made")
    first_path, first = runs[0]
    assert first.rag and first.rag.experiment_spend
    settings = first.rag.experiment_spend.model_copy(deep=True)
    settings.ledger_path = (first_path.parent / settings.ledger_path).resolve()
    ledger = SpendLedger(settings)
    # Validate every data/script path before the first provider call.
    for config_path, config in runs:
        manifest(config, config_path.parent)
    outcomes: dict[str, object] = {}
    for config_path, config in runs:
        assert config.rag and config.rag.experiment_spend and config.evaluation
        run_stage = config.rag.experiment_spend.stage
        if stage == "smoke" and run_stage != "smoke":
            continue
        settings = config.rag.experiment_spend.model_copy(deep=True)
        settings.ledger_path = (config_path.parent / settings.ledger_path).resolve()
        ledger = SpendLedger(settings)
        if reason := ledger.stop_reason():
            return {
                "complete": False,
                "runs": outcomes,
                "spending": ledger.report(),
                "reason": reason,
            }
        root = config_path.parent / config.evaluation.output_dir
        if root.exists():
            report = json.loads((root / "comparison.json").read_text())
            prior = json.loads((root / "comparison-manifest.json").read_text())
            if not report["complete"] or prior.get("base_config_hash") != digest(
                config.model_dump(mode="json")
            ):
                raise ValueError(
                    "Existing run is partial or has different config; inspect it before retry"
                )
            if prior["dataset_hashes"] != manifest(config, config_path.parent)["input_hashes"]:
                raise ValueError("Existing run input hashes differ; cannot reuse results")
            summaries = {
                name: Summary.model_validate(value) for name, value in report["summaries"].items()
            }
        else:
            if stage == "comparison" and run_stage == "smoke":
                raise ValueError("Run and audit the smoke stage before the comparison pilot")
            summaries = await compare(config, config_path.parent)
        complete = set(summaries) == set(METHODS) and all(
            s.stop_reason is None for s in summaries.values()
        )
        outcomes[config.run_id] = {"complete": complete, "output_dir": str(root)}
        if not complete:
            return {"complete": False, "runs": outcomes, "spending": ledger.report()}
        if run_stage == "smoke" and any(
            s.incomplete_usage_examples or (s.errors and stage == "smoke")
            for s in summaries.values()
        ):
            raise ValueError(
                "Smoke has failed cases or incomplete accounting; larger comparison not started"
            )
    return {"complete": True, "runs": outcomes, "spending": ledger.report()}
