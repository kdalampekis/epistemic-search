"""Construct configured providers at the application boundary."""

import os
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


def configured_model(config: RagConfig, base_dir: Path, client: httpx.AsyncClient) -> ModelProvider:
    if config.backend == "fixture":
        assert config.responses_path is not None
        return FixtureModelProvider.from_path(base_dir / config.responses_path)
    return OpenAIModelProvider(client, os.environ.get("OPENAI_API_KEY", ""), config)


async def execute_case(
    case: QueryCase,
    config: RunConfig,
    base_dir: Path,
    documents: list[CorpusDocument] | None = None,
) -> RunResult:
    if config.rag is None:
        raise ValueError("rag configuration is required")
    if config.method == "closed_book":
        search = FixtureSearchProvider([])
    elif documents is not None:
        search = FixtureSearchProvider(documents)
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
