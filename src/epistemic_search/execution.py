"""Construct configured providers at the application boundary."""

import os
from pathlib import Path

import httpx

from epistemic_search.adapters import (
    FixtureModelProvider,
    FixtureSearchProvider,
    OpenAIModelProvider,
)
from epistemic_search.baseline import RunResult, run_baseline
from epistemic_search.config import RunConfig
from epistemic_search.models import QueryCase
from epistemic_search.providers import ModelProvider


async def execute_case(case: QueryCase, config: RunConfig, base_dir: Path) -> RunResult:
    if config.rag is None:
        raise ValueError("rag configuration is required")
    search = FixtureSearchProvider.from_path(base_dir / config.rag.corpus_path)
    async with httpx.AsyncClient() as client:
        model: ModelProvider
        if config.rag.backend == "fixture":
            assert config.rag.responses_path is not None
            model = FixtureModelProvider.from_path(base_dir / config.rag.responses_path)
        else:
            model = OpenAIModelProvider(client, os.environ.get("OPENAI_API_KEY", ""), config.rag)
        return await run_baseline(case, config, search, model)
