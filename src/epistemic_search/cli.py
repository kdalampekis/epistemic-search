"""Foundation CLI. No research method is run in Phase 0."""

from pathlib import Path

import typer
import yaml

from epistemic_search.config import load_config
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
