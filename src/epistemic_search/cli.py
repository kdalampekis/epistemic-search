"""Configuration validation and reproducible research commands."""

import asyncio
import json
from pathlib import Path
from typing import Literal

import httpx
import typer
import yaml

from epistemic_search.ablations import run_ablations
from epistemic_search.baseline import RunResult
from epistemic_search.benchmarks import BenchmarkDataset, configured_dataset
from epistemic_search.calibration import run_calibration
from epistemic_search.campaign import estimate_campaign, run_campaign
from epistemic_search.config import load_config
from epistemic_search.conflicts import analyze_conflicts
from epistemic_search.controlled import ControlledDataset, generate_transformations
from epistemic_search.dataset_setup import prepare_datasets
from epistemic_search.decomposition import DecompositionResult, decompose
from epistemic_search.evaluation import evaluate, manifest
from epistemic_search.execution import configured_model, configured_spend, execute_case
from epistemic_search.formal import compare_formal
from epistemic_search.models import QueryCase
from epistemic_search.parity import compare
from epistemic_search.selective import analyze_saved_run
from epistemic_search.statistics import analyze_comparison
from epistemic_search.tracing import configure_logging

app = typer.Typer(no_args_is_help=True)


@app.command("analyze-comparison")
def comparison_statistics(config_path: Path) -> None:
    """Bootstrap paired saved scores and summarize costs without model calls."""
    try:
        report = analyze_comparison(config_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Statistical analysis failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Analyzed {len(report['runs'])} matched runs; additional API cost $0")


@app.command("ablate")
def ablate(plan_path: Path) -> None:
    """Run matched one-switch ablations and generate CSV/Markdown tables."""
    try:
        summaries = asyncio.run(run_ablations(plan_path))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Ablation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {name: value.model_dump(mode="json") for name, value in summaries.items()}, indent=2
        )
    )


@app.command("compare-formal")
def formal_comparison(config_path: Path) -> None:
    """Compare supplied Boolean graphs with SMT and a schema-validated model judge."""
    try:
        report = asyncio.run(compare_formal(config_path))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Formal comparison failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2))
    if report["stop_reason"] or report["generative_errors"] or report["graph_errors"]:
        raise typer.Exit(code=1)


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
        dataset = configured_dataset(settings, config_path.parent, config.seed)

        async def runner(case: QueryCase) -> RunResult:
            documents = (
                dataset.documents(case.id)
                if isinstance(dataset, (BenchmarkDataset, ControlledDataset))
                else None
            )
            return await execute_case(
                case,
                config,
                config_path.parent,
                documents,
                preserve_document_order=isinstance(dataset, ControlledDataset),
            )

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


@app.command("selective")
def selective(run_dir: Path, output_path: Path, scores_path: Path | None = None) -> None:
    """Analyze saved evaluation outputs without model calls or new grading."""
    try:
        report = analyze_saved_run(run_dir, scores_path)
        with output_path.open("x", encoding="utf-8") as output:
            output.write(report.model_dump_json(indent=2) + "\n")
    except (OSError, ValueError) as exc:
        typer.echo(f"Selective analysis failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(report.model_dump_json(indent=2))


@app.command("conflicts")
def conflicts(run_dir: Path, output_path: Path, judgments_path: Path | None = None) -> None:
    """Audit saved ConfRAG detection/retrieval and optional independent safety labels."""
    try:
        report = analyze_conflicts(run_dir, judgments_path)
        with output_path.open("x", encoding="utf-8") as output:
            output.write(report.model_dump_json(indent=2) + "\n")
    except (OSError, ValueError, KeyError) as exc:
        typer.echo(f"Conflict analysis failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(report.model_dump_json(indent=2))


@app.command("calibrate")
def calibrate(config_path: Path) -> None:
    """Compare score families offline with disjoint calibration/evaluation groups."""
    try:
        report = run_calibration(config_path)
    except (OSError, ValueError) as exc:
        typer.echo(f"Calibration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(report.model_dump_json(indent=2))


@app.command("transform")
def transform_benchmark(config_path: Path) -> None:
    """Generate declared evidence interventions offline, retaining base groups."""
    try:
        report = generate_transformations(config_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Transformation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2))
