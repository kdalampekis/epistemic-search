"""Configuration validation and reproducible research commands."""

import asyncio
import json
from pathlib import Path
from typing import Literal

import httpx
import typer
import yaml

from epistemic_search.baseline import RunResult
from epistemic_search.benchmarks import BenchmarkDataset
from epistemic_search.campaign import estimate_campaign, run_campaign
from epistemic_search.config import load_config
from epistemic_search.dataset_setup import prepare_datasets
from epistemic_search.decomposition import DecompositionResult, decompose
from epistemic_search.evaluation import DatasetAdapter, JsonlDataset, evaluate, manifest
from epistemic_search.execution import configured_model, configured_spend, execute_case
from epistemic_search.models import QueryCase
from epistemic_search.parity import compare
from epistemic_search.tracing import configure_logging

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Epistemic Search research tools."""


@app.command("prepare-datasets")
def prepare_benchmarks(lock_path: Path, output_dir: Path) -> None:
    """Download pinned releases and verify checksums in a new directory."""
    try:
        with httpx.Client() as client:
            hashes = prepare_datasets(lock_path, output_dir, client)
    except (OSError, ValueError, httpx.HTTPError) as exc:
        typer.echo(f"Dataset setup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for name, digest in hashes.items():
        typer.echo(f"{digest}  {name}")


@app.command("validate-config")
def validate_config(path: Path) -> None:
    """Validate a YAML config and print its resolved JSON representation."""
    try:
        config = load_config(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Invalid config: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    logger = configure_logging(config.log_level)
    logger.info("Config validated: %s", config.run_id)
    typer.echo(config.model_dump_json(indent=2))


@app.command("run")
@app.command("run-naive")
def naive(config_path: Path, query_path: Path, output_path: Path) -> None:
    """Run one QueryCase JSON file; write answer, usage, and trace to a new JSON file."""
    try:
        config = load_config(config_path)
        case = QueryCase.model_validate_json(query_path.read_text(encoding="utf-8"))
        # Reserve the output before spending resources; never overwrite an earlier run.
        with output_path.open("x", encoding="utf-8") as output:
            result = asyncio.run(execute_case(case, config, config_path.parent))
            output.write(result.model_dump_json(indent=2) + "\n")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Run failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(result.model_dump_json(indent=2))
    if result.status != "completed":
        raise typer.Exit(code=1)


@app.command("evaluate")
def benchmark(config_path: Path) -> None:
    """Evaluate all JSONL cases with one shared metric protocol; retain failures."""
    try:
        config = load_config(config_path)
        if config.evaluation is None or config.rag is None:
            raise ValueError("evaluation and rag configuration are required")
        settings = config.evaluation
        spend = configured_spend(config.rag, config_path.parent)
        if spend and (reason := spend.stop_reason()):
            raise ValueError(reason)
        dataset: DatasetAdapter = (
            JsonlDataset(config_path.parent / settings.dataset_path)
            if settings.format == "jsonl"
            else BenchmarkDataset(settings, config_path.parent, config.seed)
        )

        async def runner(case: QueryCase) -> RunResult:
            documents = (
                dataset.documents(case.id) if isinstance(dataset, BenchmarkDataset) else None
            )
            return await execute_case(case, config, config_path.parent, documents)

        summary = asyncio.run(
            evaluate(
                dataset,
                runner,
                config_path.parent / settings.output_dir,
                manifest(config, config_path.parent),
                stop_requested=spend.stop_reason if spend else None,
            )
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Evaluation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(summary.model_dump_json(indent=2))
    if summary.errors or summary.stop_reason:
        raise typer.Exit(code=1)


@app.command("compare")
def compare_methods(config_path: Path) -> None:
    """Run five methods with shared inputs, budgets, models and metrics."""
    try:
        summaries = asyncio.run(compare(load_config(config_path), config_path.parent))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Comparison failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for method, summary in summaries.items():
        typer.echo(f"{method}: {summary.model_dump_json()}")
    if any(summary.errors or summary.stop_reason for summary in summaries.values()):
        raise typer.Exit(code=1)


@app.command("phase12")
def phase12(plan_path: Path, stage: str = "smoke", estimate_only: bool = False) -> None:
    """Estimate or run one small stage inside the cumulative project budget."""
    try:
        if stage not in {"smoke", "comparison"}:
            raise ValueError("stage must be smoke or comparison")
        selected: Literal["smoke", "comparison"] = "smoke" if stage == "smoke" else "comparison"
        typer.echo(json.dumps(estimate_campaign(plan_path, selected), indent=2))
        if estimate_only:
            return
        result = asyncio.run(run_campaign(plan_path, selected))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Phase 12 stopped: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, indent=2))
    if not result["complete"]:
        raise typer.Exit(code=1)


@app.command("decompose")
def inspect_decomposition(config_path: Path, query_path: Path, output_path: Path) -> None:
    """Generate or inspect a cached, structurally validated premise graph."""
    try:
        config = load_config(config_path)
        if config.rag is None or config.decomposition is None:
            raise ValueError("rag model and decomposition settings are required")
        case = QueryCase.model_validate_json(query_path.read_text(encoding="utf-8"))

        async def run() -> DecompositionResult:
            assert config.rag is not None and config.decomposition is not None
            async with httpx.AsyncClient() as client:
                model = configured_model(config.rag, config_path.parent, client)
                return await decompose(
                    case, config, model, config_path.parent / config.decomposition.cache_dir
                )

        with output_path.open("x", encoding="utf-8") as output:
            result = asyncio.run(run())
            output.write(result.model_dump_json(indent=2) + "\n")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Decomposition failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(result.model_dump_json(indent=2))
    if result.error is not None:
        raise typer.Exit(code=1)
