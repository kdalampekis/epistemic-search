"""Safe YAML loading into explicit, validated run settings."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from epistemic_search.models import BudgetLimits, Count, Schema, Text


class RunConfig(Schema):
    schema_version: Literal[1] = 1
    run_id: Text
    seed: Count = 0
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    budget: BudgetLimits = Field(default_factory=BudgetLimits)


def load_config(path: Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
