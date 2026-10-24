"""One-component-at-a-time comparisons with explicit dependency-removal scope."""

import csv
import io
import json
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Field, model_validator

from epistemic_search.baseline import RunResult
from epistemic_search.benchmarks import BenchmarkDataset, configured_dataset
from epistemic_search.config import AblationConfig, DecompositionConfig, RunConfig, load_config
from epistemic_search.controlled import ControlledDataset
from epistemic_search.decomposition import digest
from epistemic_search.evaluation import Summary, evaluate, file_hash, manifest
from epistemic_search.execution import configured_spend, execute_case, local_api_key
from epistemic_search.models import QueryCase, Schema
from epistemic_search.parity import comparison_configs

Switch = Literal[
    "use_premise_graph",
    "use_belief_state",
    "use_formal_sufficiency",
    "use_conflict_resolution",
    "use_cost_aware_controller",
    "allow_abstention",
    "compact_evidence",
]
EFFECTS = {
    "reference": "Unablated epistemic engine with configured VOI acquisition.",
    "use_premise_graph": (
        "Use iterative relevance baseline: removes decomposition and downstream "
        "evidence-state/formal/VOI control; raw context."
    ),
    "use_belief_state": (
        "Use premise-only baseline: retains decomposition, replaces belief/formal/conflict/VOI "
        "control with a model judge; raw context."
    ),
    "use_formal_sufficiency": (
        "Retain evidence/beliefs; replace proof sufficiency and frontier/VOI target selection "
        "with a generative controller."
    ),
    "use_conflict_resolution": (
        "Retain MIXED and conservative sufficiency; replace conflict-resolution actions/queries "
        "with ordinary targeted search."
    ),
    "use_cost_aware_controller": (
        "Replace VOI with importance; preserve frontier, conflict priority and hard budgets."
    ),
    "allow_abstention": (
        "Attempt a cited best answer at policy abstention or round limit; hard budget/errors "
        "still stop, null outputs remain failures."
    ),
    "compact_evidence": (
        "Supply full retrieved document text to the final answer model; "
        "retain extracted ledger and control policy."
    ),
}


class AblationPlan(Schema):
    run_config_path: Path
    output_dir: Path
    switches: Annotated[list[Switch], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_switches(self) -> Self:
        if len(set(self.switches)) != len(self.switches):
            raise ValueError("Ablation switches must be unique")
        return self


def variant_configs(config: RunConfig, root: Path, switches: list[Switch]) -> dict[str, RunConfig]:
    comparison_configs(config, root)  # Reuse finite matched-budget validation, without execution.
    if config.method != "epistemic_search" or config.ablation != AblationConfig():
        raise ValueError("Ablations need an unablated epistemic_search reference")
    if config.controller.policy != "voi":
        raise ValueError("Ablation reference must explicitly enable the VOI policy")
    if not switches or len(set(switches)) != len(switches):
        raise ValueError("Ablation switches must be nonempty and unique")
    variants = {}
    for name in ["reference", *switches]:
        item = config.model_copy(deep=True)
        if name != "reference":
            item.ablation = AblationConfig.model_validate({name: False})
        item.run_id += "-" + name
        assert item.evaluation
        item.evaluation.output_dir = root / name
        item.decomposition = DecompositionConfig(cache_dir=root / "cache" / name)
        variants[name] = item
    return variants


def write_tables(root: Path, summaries: dict[str, Summary]) -> None:
    rows = []
    for name, summary in summaries.items():
        usage = summary.usage
        rows.append(
            {
                "variant": name,
                "examples": summary.examples,
                "planned": summary.planned_examples,
                "errors": summary.errors,
                "incomplete_usage_examples": summary.incomplete_usage_examples,
                "unknown_cost_examples": summary.unknown_cost_examples,
                "budget_exhausted": summary.budget_exhausted,
                "coverage": summary.coverage,
                "exact_match": summary.exact_match,
                "token_f1": summary.token_f1,
                "input_tokens": usage.prompt_tokens,
                "cached_input_tokens": usage.cached_input_tokens,
                "output_tokens": usage.completion_tokens,
                "reasoning_tokens": usage.reasoning_tokens,
                "model_calls": usage.model_calls,
                "search_calls": usage.search_calls,
                "api_calls": usage.api_calls,
                "cache_hits": usage.model_cache_hits,
                "estimated_cost_usd": usage.cost_usd,
                "wall_seconds": summary.wall_seconds,
                "partial": summary.stop_reason is not None
                or summary.examples != summary.planned_examples,
            }
        )
    if not rows:
        return
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (root / "table.csv").write_text(stream.getvalue())
    headers = [
        "variant",
        "examples",
        "planned",
        "errors",
        "coverage",
        "exact_match",
        "token_f1",
        "model_calls",
        "search_calls",
        "estimated_cost_usd",
        "partial",
    ]
    markdown = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    markdown.extend(
        "| " + " | ".join(str(row[key]) if row[key] is not None else "NA" for key in headers) + " |"
        for row in rows
    )
    (root / "table.md").write_text("\n".join(markdown) + "\n")


async def run_ablations(plan_path: Path) -> dict[str, Summary]:
    plan = AblationPlan.model_validate(yaml.safe_load(plan_path.read_text()))
    config_path = plan_path.parent / plan.run_config_path
    config = load_config(config_path)
    root = (plan_path.parent / plan.output_dir).resolve()
    variants = variant_configs(config, root, plan.switches)
    assert config.rag and config.evaluation
    if config.rag.backend == "openai" and not local_api_key(config_path.parent):
        raise ValueError("Set OPENAI_API_KEY locally before a paid ablation")
    spend = configured_spend(config.rag, config_path.parent)
    if spend and (reason := spend.stop_reason()):
        raise ValueError(reason)
    dataset = configured_dataset(config.evaluation, config_path.parent, config.seed)
    cases = dataset.load()
    manifests = {name: manifest(item, config_path.parent) for name, item in variants.items()}
    shared = {
        "protocol": "one-switch-ablation-v1",
        "plan_sha256": file_hash(plan_path),
        "run_config_sha256": file_hash(config_path),
        "variants": list(variants),
        "selected_case_ids": [c.id for c in cases],
        "effects": {name: EFFECTS[name] for name in variants},
        "fixture_only": config.rag.backend == "fixture",
        "matched": [
            "model",
            "reasoning_effort",
            "seed",
            "dataset",
            "grader",
            "retriever",
            "budget_caps",
        ],
        "limitations": [
            "Matched ceilings, not equal realized resource usage.",
            "Removing prerequisite components also removes dependent control; see effects.",
            "Interventions may be inactive; inspect traces before attributing effects.",
            "Variant order is recorded; exact-request cache reuse couples results and latency.",
            "Incomplete runs and model failures stay in reports; no automatic benchmark scaling.",
        ],
    }
    root.mkdir(parents=True, exist_ok=False)
    (root / "ablation-manifest.json").write_text(json.dumps(shared, indent=2) + "\n")
    summaries: dict[str, Summary] = {}
    for name, item in variants.items():
        assert item.evaluation

        async def runner(case: QueryCase, current: RunConfig = item) -> RunResult:
            current = current.model_copy(deep=True)
            assert current.decomposition
            current.decomposition.cache_dir /= digest(case.id)
            documents = (
                dataset.documents(case.id)
                if isinstance(dataset, (BenchmarkDataset, ControlledDataset))
                else None
            )
            return await execute_case(
                case,
                current,
                config_path.parent,
                documents,
                preserve_document_order=isinstance(dataset, ControlledDataset),
            )

        summaries[name] = await evaluate(
            dataset,
            runner,
            item.evaluation.output_dir,
            {**manifests[name], "ablation_protocol": shared},
            stop_requested=spend.stop_reason if spend else None,
        )
        write_tables(root, summaries)
        (root / "comparison.json").write_text(
            json.dumps(
                {
                    "protocol": shared["protocol"],
                    "complete": len(summaries) == len(variants)
                    and all(s.stop_reason is None for s in summaries.values()),
                    "spending": spend.report() if spend else None,
                    "summaries": {n: s.model_dump(mode="json") for n, s in summaries.items()},
                },
                indent=2,
            )
            + "\n"
        )
        if spend and spend.stop_reason():
            break
    return summaries
