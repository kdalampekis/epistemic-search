"""Configuration validation and reproducible research commands."""

import asyncio
from pathlib import Path

import httpx
import typer
import yaml

from epistemic_search.baseline import RunResult
from epistemic_search.config import load_config
from epistemic_search.decomposition import DecompositionResult, decompose
from epistemic_search.evaluation import JsonlDataset, evaluate, manifest
from epistemic_search.execution import configured_model, execute_case
from epistemic_search.models import QueryCase
from epistemic_search.tracing import configure_logging

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Epistemic Search research tools."""


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

        async def runner(case: QueryCase) -> RunResult:
            return await execute_case(case, config, config_path.parent)

        summary = asyncio.run(
            evaluate(
                JsonlDataset(config_path.parent / settings.dataset_path),
                runner,
                config_path.parent / settings.output_dir,
                manifest(config, config_path.parent),
            )
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"Evaluation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(summary.model_dump_json(indent=2))
    if summary.errors:
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
