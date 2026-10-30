"""Safe YAML loading into explicit, validated run settings."""

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    model_serializer,
    model_validator,
)

from epistemic_search.models import (
    AcquisitionEstimate,
    AcquisitionPolicy,
    BudgetLimits,
    Count,
    Money,
    Schema,
    Text,
)


class ExperimentSpend(Schema):
    ledger_path: Path
    run_id: Text
    total_usd: Annotated[Money, Field(gt=0, le=50)] = Decimal(50)
    run_usd: Annotated[Money, Field(gt=0, le=50)]
    prior_spend_usd: Money = Decimal(0)
    validation_reserve_usd: Money = Decimal(5)
    stage: Literal["development", "smoke", "comparison", "validation"] = "development"

    @model_validator(mode="after")
    def valid_caps(self) -> Self:
        if self.prior_spend_usd + self.validation_reserve_usd > self.total_usd:
            raise ValueError("Prior spend and validation reserve exceed project cap")
        if self.run_usd > self.total_usd:
            raise ValueError("Run cap exceeds project cap")
        if self.stage == "validation" and self.run_usd > self.validation_reserve_usd:
            raise ValueError("Validation run exceeds the small final reserve")
        return self


class RagConfig(Schema):
    max_rounds: Annotated[int, Field(strict=True, gt=0)] = 3
    k: Annotated[int, Field(strict=True, gt=0)] = 3
    corpus_path: Path | None = None
    backend: Literal["fixture", "openai"] = "fixture"
    model: Text = "fixture-script-v1"
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    service_tier: Literal["default"] = "default"
    experiment_spend: ExperimentSpend | None = None
    responses_path: Path | None = None
    max_output_tokens: Annotated[int, Field(strict=True, gt=0)] = 512
    timeout_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 30
    input_usd_per_million: Money | None = None
    cached_input_usd_per_million: Money | None = None
    cache_write_usd_per_million: Money | None = None
    output_usd_per_million: Money | None = None

    @model_validator(mode="after")
    def validate_backend(self) -> Self:
        if self.backend == "fixture" and self.responses_path is None:
            raise ValueError("fixture backend requires responses_path")
        if self.backend == "openai" and self.model == "fixture-script-v1":
            raise ValueError("openai backend requires an explicit model identifier")
        if self.experiment_spend is not None:
            primary = self.model == "gpt-6-luna"
            validation = self.experiment_spend.stage == "validation"
            if self.backend != "openai" or self.model not in {"gpt-6-luna", "gpt-6.1-sol"}:
                raise ValueError("Research model must be Luna or validation-only Sol")
            if not primary and not validation:
                raise ValueError("Sol is reserved for the final validation subset")
            allowed = (
                {"low", "medium"} if self.experiment_spend.stage == "development" else {"medium"}
            )
            if self.reasoning_effort not in allowed:
                raise ValueError("Comparisons require medium; development permits low or medium")
            rates = ("0.10", "0.01", "0.125", "0.50") if primary else ("2", "0.1", "2.5", "10")
            if (
                self.input_usd_per_million,
                self.cached_input_usd_per_million,
                self.cache_write_usd_per_million,
                self.output_usd_per_million,
            ) != tuple(Decimal(x) for x in rates):
                raise ValueError("Research runs require the verified standard model rate card")
        return self


class EvaluationConfig(Schema):
    dataset_path: Path
    output_dir: Path
    dataset_name: Text
    split: Literal["train", "dev", "test"]
    format: Literal["jsonl", "hotpotqa", "2wikimultihopqa", "confrag", "controlled"] = "jsonl"
    aliases_path: Path | None = None
    snapshot_at: AwareDatetime | None = None
    limit: Annotated[int, Field(strict=True, gt=0)] | None = None

    @model_validator(mode="after")
    def native_requirements(self) -> Self:
        if self.format not in {"jsonl", "controlled"} and self.snapshot_at is None:
            raise ValueError("Native benchmarks require a recorded snapshot_at timestamp")
        if self.format == "2wikimultihopqa" and self.aliases_path is None:
            raise ValueError("2Wiki requires the release's id_aliases.json for answer scoring")
        if self.format in {"jsonl", "controlled"} and self.limit is not None:
            raise ValueError("limit is supported only for native benchmark adapters")
        return self


class DecompositionConfig(Schema):
    cache_dir: Path


class BeliefConfig(Schema):
    threshold: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] = 0.5


Method = Literal[
    "closed_book",
    "naive_rag",
    "iterative_rag",
    "premise_only",
    "premise_state",
    "sufficiency_check",
    "grounded_decomposition",
    "epistemic_search",
]


class ControllerConfig(Schema):
    policy: AcquisitionPolicy = "importance"
    default_estimate: AcquisitionEstimate = Field(default_factory=AcquisitionEstimate)
    estimates: dict[Text, AcquisitionEstimate] = Field(default_factory=dict)
    cost_unit: Literal["relative_work", "usd", "tokens"] = "relative_work"
    estimate_provenance: Text = "uniform-uninformative-default-v1"


class AblationConfig(Schema):
    use_premise_graph: StrictBool = True
    use_belief_state: StrictBool = True
    use_formal_sufficiency: StrictBool = True
    use_conflict_resolution: StrictBool = True
    use_cost_aware_controller: StrictBool = True
    allow_abstention: StrictBool = True
    compact_evidence: StrictBool = True

    @model_validator(mode="after")
    def single_intervention(self) -> Self:
        if sum(value is False for value in self.model_dump().values()) > 1:
            raise ValueError("Phase 19 supports one disabled component per ablation")
        return self


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
    controller: ControllerConfig = Field(default_factory=ControllerConfig)
    ablation: AblationConfig = Field(default_factory=AblationConfig)

    @model_serializer(mode="wrap")
    def serialize_config(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        values: dict[str, Any] = handler(self)
        # Preserve historical config hashes when the original policy is unchanged.
        if self.controller == ControllerConfig():
            values.pop("controller", None)
        if self.ablation == AblationConfig():
            values.pop("ablation", None)
        return values


def load_config(path: Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
