"""Construct configured providers at the application boundary."""

import os
import shlex
from pathlib import Path

import httpx

from epistemic_search.adapters import (
    CorpusDocument,
    FixtureModelProvider,
    FixtureSearchProvider,
    OpenAIModelProvider,
)
from epistemic_search.baseline import RunResult
from epistemic_search.comparators import run_comparator, run_guarded_baseline
from epistemic_search.config import RagConfig, RunConfig
from epistemic_search.engine import run_epistemic
from epistemic_search.models import QueryCase
from epistemic_search.providers import ModelProvider
from epistemic_search.spending import SpendLedger


def local_api_key(base_dir: Path) -> str:
    """Read only the requested key in memory; never mutate environment or files."""
    if key := os.environ.get("OPENAI_API_KEY"):
        return key
    root = base_dir.parent if (base_dir.parent / "pyproject.toml").exists() else base_dir
    path = root / ".env"
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        name, separator, value = line.removeprefix("export ").partition("=")
        if separator and name.strip() == "OPENAI_API_KEY":
            try:
                parts = shlex.split(value, comments=True)
            except ValueError:
                raise ValueError("Invalid OPENAI_API_KEY quoting in .env") from None
            if len(parts) > 1:
                raise ValueError("Invalid OPENAI_API_KEY assignment in .env")
            return parts[0] if parts else ""
    return ""


def configured_spend(config: RagConfig, base_dir: Path) -> SpendLedger | None:
    if config.experiment_spend is None:
        if config.backend == "openai":
            raise ValueError("Paid research calls require project and per-run budget settings")
        return None
    settings = config.experiment_spend.model_copy(deep=True)
    settings.ledger_path = (base_dir / settings.ledger_path).resolve()
    return SpendLedger(settings)


def configured_model(config: RagConfig, base_dir: Path, client: httpx.AsyncClient) -> ModelProvider:
    if config.backend == "fixture":
        assert config.responses_path is not None
        return FixtureModelProvider.from_path(base_dir / config.responses_path)
    if config.experiment_spend is None:
        raise ValueError("Paid research calls require project and per-run budget settings")
    resolved = config.model_copy(deep=True)
    if resolved.experiment_spend is not None:
        resolved.experiment_spend.ledger_path = (
            base_dir / resolved.experiment_spend.ledger_path
        ).resolve()
    return OpenAIModelProvider(client, local_api_key(base_dir), resolved)


async def execute_case(
    case: QueryCase,
    config: RunConfig,
    base_dir: Path,
    documents: list[CorpusDocument] | None = None,
    *,
    preserve_document_order: bool = False,
) -> RunResult:
    if config.rag is None:
        raise ValueError("rag configuration is required")
    if config.method == "closed_book":
        search = FixtureSearchProvider([])
    elif documents is not None:
        search = FixtureSearchProvider(documents, preserve_document_order=preserve_document_order)
    elif config.rag.corpus_path is not None:
        search = FixtureSearchProvider.from_path(base_dir / config.rag.corpus_path)
    else:
        raise ValueError("A corpus_path or explicit benchmark document pool is required")
    async with httpx.AsyncClient() as client:
        model = configured_model(config.rag, base_dir, client)
        if config.method in {"closed_book", "premise_only"}:
            if config.method == "premise_only" and config.decomposition is None:
                raise ValueError("premise_only requires decomposition cache settings")
            return await run_comparator(
                case,
                config,
                search,
                model,
                base_dir / config.decomposition.cache_dir if config.decomposition else base_dir,
            )
        if config.method == "epistemic_search":
            if config.decomposition is None:
                raise ValueError("epistemic_search requires decomposition cache settings")
            return await run_epistemic(
                case, config, search, model, base_dir / config.decomposition.cache_dir
            )
        return await run_guarded_baseline(case, config, search, model)
