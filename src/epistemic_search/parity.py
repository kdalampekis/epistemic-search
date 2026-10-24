"""Five-method comparison from one immutable experimental configuration."""

import json
from pathlib import Path

from epistemic_search.baseline import RunResult
from epistemic_search.benchmarks import BenchmarkDataset, configured_dataset
from epistemic_search.config import DecompositionConfig, Method, RunConfig
from epistemic_search.controlled import ControlledDataset
from epistemic_search.decomposition import digest
from epistemic_search.evaluation import Summary, evaluate, manifest
from epistemic_search.execution import configured_spend, execute_case, local_api_key
from epistemic_search.models import QueryCase

METHODS: tuple[Method, ...] = (
    "closed_book",
    "naive_rag",
    "iterative_rag",
    "premise_only",
    "epistemic_search",
)


def comparison_configs(config: RunConfig, base_dir: Path) -> dict[Method, RunConfig]:
    if config.rag is None or config.evaluation is None:
        raise ValueError("Comparison requires rag and evaluation settings")
    for name in (
        "max_search_calls",
        "max_documents",
        "max_retrieved_tokens",
        "max_llm_calls",
        "max_total_llm_input_tokens",
        "max_total_llm_output_tokens",
    ):
        if getattr(config.budget, name) is None:
            raise ValueError(f"Comparison requires an explicit finite {name}")
    root = (base_dir / config.evaluation.output_dir).resolve()
    configs: dict[Method, RunConfig] = {}
    for method in METHODS:
        item = config.model_copy(deep=True)
        item.method = method
        item.run_id = config.run_id + "-" + method
        assert item.evaluation is not None
        item.evaluation.output_dir = root / method
        item.decomposition = DecompositionConfig(cache_dir=root / "cache" / method)
        configs[method] = item
    return configs


async def compare(config: RunConfig, base_dir: Path) -> dict[str, Summary]:
    configs = comparison_configs(config, base_dir)
    assert config.evaluation is not None and config.rag is not None
    if config.rag.backend == "openai" and not local_api_key(base_dir):
        raise ValueError("Set OPENAI_API_KEY locally before running a real-model comparison")
    spend = configured_spend(config.rag, base_dir)
    if spend and (reason := spend.stop_reason()):
        raise ValueError(reason)
    dataset = configured_dataset(config.evaluation, base_dir, config.seed)
    cases = dataset.load()
    root = (base_dir / config.evaluation.output_dir).resolve()
    # Validate all input hashes before reserving outputs or calling any model.
    manifests = {method: manifest(item, base_dir) for method, item in configs.items()}
    root.mkdir(parents=True, exist_ok=False)
    shared = {
        "protocol": "five-method-parity-v1",
        "base_config_hash": digest(config.model_dump(mode="json")),
        "budget_protocol": "shared-provider-guard-v2",
        "methods": list(METHODS),
        "seed": config.seed,
        "selected_case_ids": [c.id for c in cases],
        "dataset_hashes": manifests["naive_rag"]["input_hashes"],
        "metric_version": manifests["naive_rag"]["metric_version"],
        "retriever": manifests["naive_rag"]["retriever"],
        "retrieval_scope": manifests["naive_rag"]["retrieval_scope"],
        "model_settings": config.rag.model_dump(mode="json"),
        "budget": config.budget.model_dump(mode="json"),
        "cache_policy": (
            "exact-request model reuse; logical tokens/calls charged; physical spend separate"
            if spend
            else "cold-per-method-per-case; decomposition calls charged"
        ),
        "fixture_only": config.rag.backend == "fixture",
        "limitations": [
            "Matched ceilings, not equal realized usage; closed-book uses zero retrieval.",
            "Paid runs count exact API input; offline token counts are whitespace estimates.",
            "Cached outputs couple samples; cache-hit latency is not uncached model latency.",
            "Method-specific prompts/context policies differ; same answer model and graders.",
            "Remote sampling is not guaranteed deterministic; methods run in recorded order.",
        ],
    }
    (root / "comparison-manifest.json").write_text(json.dumps(shared, indent=2) + "\n")
    summaries: dict[str, Summary] = {}
    for method, item in configs.items():
        assert item.evaluation is not None
        run_manifest = {**manifests[method], "comparison_protocol": shared}

        async def runner(case: QueryCase, current: RunConfig = item) -> RunResult:
            case_config = current.model_copy(deep=True)
            assert case_config.decomposition is not None
            # Never reuse an earlier method's or another example's decomposition.
            case_config.decomposition.cache_dir /= digest(case.id)
            documents = (
                dataset.documents(case.id)
                if isinstance(dataset, (BenchmarkDataset, ControlledDataset))
                else None
            )
            return await execute_case(
                case,
                case_config,
                base_dir,
                documents,
                preserve_document_order=isinstance(dataset, ControlledDataset),
            )

        summaries[method] = await evaluate(
            dataset,
            runner,
            item.evaluation.output_dir,
            run_manifest,
            stop_requested=spend.stop_reason if spend else None,
        )
        # Keep completed methods reviewable if a later process is interrupted.
        (root / "comparison.json").write_text(
            json.dumps(
                {
                    "protocol": shared["protocol"],
                    "complete": len(summaries) == len(METHODS)
                    and all(s.stop_reason is None for s in summaries.values()),
                    "spending": spend.report() if spend else None,
                    "summaries": {
                        name: value.model_dump(mode="json") for name, value in summaries.items()
                    },
                },
                indent=2,
            )
            + "\n"
        )
        if spend and spend.stop_reason():
            break
    return summaries
