"""Safe YAML loading into explicit, validated run settings."""

from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import AwareDatetime, Field, model_validator

from epistemic_search.models import BudgetLimits, Count, Money, Schema, Text


class RagConfig(Schema):
    max_rounds: Annotated[int, Field(strict=True, gt=0)] = 3
    k: Annotated[int, Field(strict=True, gt=0)] = 3
    corpus_path: Path | None = None
    backend: Literal["fixture", "openai"] = "fixture"
    model: Text = "fixture-script-v1"
    responses_path: Path | None = None
    max_output_tokens: Annotated[int, Field(strict=True, gt=0)] = 512
    timeout_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 30
    input_usd_per_million: Money | None = None
    cached_input_usd_per_million: Money | None = None
    output_usd_per_million: Money | None = None

    @model_validator(mode="after")
    def validate_backend(self) -> Self:
        if self.backend == "fixture" and self.responses_path is None:
            raise ValueError("fixture backend requires responses_path")
        if self.backend == "openai" and self.model == "fixture-script-v1":
            raise ValueError("openai backend requires an explicit model identifier")
        return self


class EvaluationConfig(Schema):
    dataset_path: Path
    output_dir: Path
    dataset_name: Text
    split: Literal["train", "dev", "test"]
    format: Literal["jsonl", "hotpotqa", "2wikimultihopqa", "confrag"] = "jsonl"
    aliases_path: Path | None = None
    snapshot_at: AwareDatetime | None = None
    limit: Annotated[int, Field(strict=True, gt=0)] | None = None

    @model_validator(mode="after")
    def native_requirements(self) -> Self:
        if self.format != "jsonl" and self.snapshot_at is None:
            raise ValueError("Native benchmarks require a recorded snapshot_at timestamp")
        if self.format == "2wikimultihopqa" and self.aliases_path is None:
            raise ValueError("2Wiki requires the release's id_aliases.json for answer scoring")
        if self.format == "jsonl" and self.limit is not None:
            raise ValueError("limit is supported only for native benchmark adapters")
        return self


class DecompositionConfig(Schema):
    cache_dir: Path


class BeliefConfig(Schema):
    threshold: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] = 0.5


Method = Literal["closed_book", "naive_rag", "iterative_rag", "premise_only", "epistemic_search"]


class RunConfig(Schema):
    schema_version: Literal[1] = 1
    run_id: Text
    seed: Count = 0
    method: Method = "naive_rag"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    budget: BudgetLimits = Field(default_factory=BudgetLimits)
    rag: RagConfig | None = None
    evaluation: EvaluationConfig | None = None
    decomposition: DecompositionConfig | None = None
    belief: BeliefConfig = Field(default_factory=BeliefConfig)


def load_config(path: Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
