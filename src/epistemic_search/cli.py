"""Configuration validation and reproducible research commands."""

import asyncio
from pathlib import Path

import typer
import yaml

from epistemic_search.config import load_config
from epistemic_search.execution import execute_case
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
