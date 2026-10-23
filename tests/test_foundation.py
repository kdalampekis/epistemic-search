import io
import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from epistemic_search.accounting import UsageLedger, UsageRecorder
from epistemic_search.cli import app
from epistemic_search.config import load_config
from epistemic_search.models import AgentEvent, Usage
from epistemic_search.tracing import configure_logging


def test_accounting_preserves_components_unknown_costs_and_snapshots(event: AgentEvent) -> None:
    ledger = UsageLedger()
    recorder: UsageRecorder = ledger
    assert ledger.total().cost_usd == Decimal(0)
    recorder.record(event)
    event.usage.prompt_tokens = 100
    assert ledger.total().prompt_tokens == 10
    assert ledger.total().total_llm_tokens == 14
    assert ledger.total().cost_usd == Decimal("0.001")
    search = event.model_copy(deep=True)
    search.id = "event-2"
    search.component = "search"
    search.usage = Usage(search_calls=1, retrieved_tokens=20, documents=2, latency_seconds=0.5)
    recorder.record(search)
    total = ledger.total()
    assert total.cost_usd is None
    assert total.search_calls == 1
    assert total.model_calls == 1
    assert total.documents == 2
    assert total.retrieved_tokens == 20
    assert total.context_tokens == 6
    assert total.latency_seconds == 0.75
    assert ledger.total("answering").cost_usd == Decimal("0.001")
    assert ledger.total("absent").prompt_tokens == 0


def test_config_and_cli() -> None:
    path = Path("configs/foundation.yaml")
    config = load_config(path)
    assert config.seed == 42
    assert config.budget.max_cost_usd == Decimal("1.00")
    result = CliRunner().invoke(app, ["validate-config", str(path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == config.model_dump(mode="json")
    assert json.loads(result.stderr)["level"] == "INFO"


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[]",
        "run_id: test\nseed: -1",
        "run_id: test\nsead: 42",
        "run_id: test\nbudget:\n  max_search_calls: -1",
        "run_id: [",
        "!!python/object/apply:os.getpid []",
    ],
)
def test_invalid_config_fails_cleanly(tmp_path: Path, content: str) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(content)
    with pytest.raises((ValidationError, yaml.YAMLError)):
        load_config(path)
    result = CliRunner().invoke(app, ["validate-config", str(path)])
    assert result.exit_code == 1
    assert "Invalid config:" in result.stderr


def test_cli_missing_file_and_help(tmp_path: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["--help"]).exit_code == 0
    result = runner.invoke(app, ["validate-config", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 1
    assert "Invalid config:" in result.stderr


def test_structured_logging_preserves_event_and_does_not_duplicate(event: AgentEvent) -> None:
    stream = io.StringIO()
    configure_logging(stream=stream)
    logger = configure_logging(stream=stream)
    logger.info("Evidence event\nwith newline", extra={"event": event})
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == event.model_dump(mode="json")
    assert payload["message"] == "Evidence event\nwith newline"
    assert payload["level"] == "INFO"
    try:
        raise ValueError("fixture error")
    except ValueError:
        logger.exception("Failure")
    assert "ValueError: fixture error" in json.loads(stream.getvalue().splitlines()[1])["exception"]
