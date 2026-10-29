"""Shared RV2 execution settings: Luna/medium through the persistent spend ledger.

Every experiment gets its own run id and hard cap inside the same $50 project policy as the
pilot, so caps are enforced by the ledger on every request, not by this module's good intent.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from epistemic_search.config import (
    DecompositionConfig,
    ExperimentSpend,
    RagConfig,
    RunConfig,
)
from epistemic_search.models import BudgetLimits
from epistemic_search.spending import SpendLedger

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"  # local_api_key looks for ../.env relative to this
LEDGER = ROOT / "artifacts" / "research" / "spending.sqlite3"
MODEL = "gpt-6-luna"
SEED = 42
SAMPLING_SEED = 20261029


def rag_config(
    run_id: str,
    cap_usd: str,
    *,
    k: int = 2,
    max_rounds: int = 3,
    max_output_tokens: int = 4096,
    timeout_seconds: float = 180,
) -> RagConfig:
    return RagConfig(
        backend="openai",
        model=MODEL,
        reasoning_effort="medium",
        k=k,
        max_rounds=max_rounds,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        input_usd_per_million=Decimal("0.10"),
        cached_input_usd_per_million=Decimal("0.01"),
        cache_write_usd_per_million=Decimal("0.125"),
        output_usd_per_million=Decimal("0.50"),
        experiment_spend=ExperimentSpend(
            ledger_path=LEDGER,
            run_id=run_id,
            total_usd=Decimal(50),
            run_usd=Decimal(cap_usd),
            prior_spend_usd=Decimal(0),
            validation_reserve_usd=Decimal(5),
            stage="development",
        ),
    )


def run_config(
    method: str,
    run_id: str,
    rag: RagConfig,
    budget: BudgetLimits,
    cache_dir: Path | None = None,
) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        seed=SEED,
        method=method,
        budget=budget,
        rag=rag,
        decomposition=DecompositionConfig(cache_dir=cache_dir) if cache_dir else None,
    )


def ledger_report(rag: RagConfig) -> dict[str, object]:
    assert rag.experiment_spend is not None
    return SpendLedger(rag.experiment_spend).report()


def write_new_json(path: Path, value: Any) -> None:
    """Results are evidence: never silently replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str))
        stream.write("\n")
