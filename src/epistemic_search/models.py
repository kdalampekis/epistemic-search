"""Validated data contracts; no retrieval, belief aggregation, or inference."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Count = Annotated[int, Field(strict=True, ge=0)]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Usage(Schema):
    """Per-call counts. None means API cost is unknown, never free.

    Context/retrieved tokens are separate views; do not add them to model tokens.
    Latency sums call durations; it is not parallel-run wall-clock time.
    """

    prompt_tokens: Count = 0
    completion_tokens: Count = 0
    cached_input_tokens: Count | None = 0
    cache_write_tokens: Count | None = 0
    reasoning_tokens: Count | None = 0
    model_cache_hits: Count = 0
    reused_cost_usd: Money = Decimal(0)
    api_calls: Count = 0
    preflight_calls: Count = 0
    retrieved_tokens: Count = 0
    context_tokens: Count = 0
    search_calls: Count = 0
    model_calls: Count = 0
    documents: Count = 0
    latency_seconds: Nonnegative = 0
    cost_usd: Money | None = None

    @property
    def total_llm_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class BudgetLimits(Schema):
    """None means unbounded; zero is a real zero budget."""

    max_search_calls: Count | None = None
    max_documents: Count | None = None
    max_retrieved_tokens: Count | None = None
    max_llm_calls: Count | None = None
    max_total_llm_input_tokens: Count | None = None
    max_total_llm_output_tokens: Count | None = None
    max_latency_seconds: Nonnegative | None = None
    max_cost_usd: Money | None = None


class BudgetState(Schema):
    limits: BudgetLimits = Field(default_factory=BudgetLimits)
    used: Usage = Field(default_factory=lambda: Usage(cost_usd=Decimal(0)))


class QueryCase(Schema):
    id: Text
    question: Text
    gold_answer: str | None = None
    answerable: bool | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Claim(Schema):
    id: Text
    text: Text
    normalized: Text | None = None
    importance: Score = 1.0
    required_for: list[Text] = Field(default_factory=list)
    polarity: Literal["POSITIVE", "NEGATIVE"] = "POSITIVE"


class ProofNode(Schema):
    """Graph syntax only; graph validation and evaluation belong to later phases."""

    id: Text
    kind: Literal["CLAIM", "AND", "OR", "NOT", "CONCLUSION"]
    children: list[Text] = Field(default_factory=list)
    claim_id: Text | None = None


class Source(Schema):
    id: Text
    uri: Text
    title: Text
    retrieved_at: AwareDatetime
    source_type: Literal["web", "corpus", "benchmark"]


class EvidenceProvenance(Schema):
    search_query: Text
    rank: Annotated[int, Field(strict=True, ge=1)]
    extraction_model: Text
    prompt_version: Text
    duplication_group: Text | None = None


class EvidenceItem(Schema):
    id: Text
    claim_id: Text
    source: Source
    # Preserve the exact extracted span, including its whitespace.
    span: Annotated[str, Field(min_length=1)]
    stance: Literal["SUPPORT", "CONTRADICT", "NEUTRAL"]
    stance_score: Score
    retrieval_score: Annotated[float, Field(allow_inf_nan=False)] | None = None
    provenance: EvidenceProvenance
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class BeliefStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ClaimBelief(Schema):
    """Scores are heuristic; the schema itself does not establish calibration."""

    claim_id: Text
    status: BeliefStatus = BeliefStatus.UNKNOWN
    support_score: Score = 0.0
    contradiction_score: Score = 0.0
    uncertainty: Score = 1.0
    calibrated: bool = False
    evidence_ids: list[Text] = Field(default_factory=list)


AcquisitionPolicy = Literal["importance", "random", "uncertainty", "voi"]


class AcquisitionEstimate(Schema):
    retrievability: Score = 1
    cost: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 1


class AcquisitionRanking(Schema):
    policy: AcquisitionPolicy
    seed: Count
    step: Count
    context_id: str
    cost_unit: Literal["relative_work", "usd", "tokens"]
    estimate_provenance: Text
    scores: dict[str, Nonnegative]
    estimates: dict[str, AcquisitionEstimate]
    criticality: dict[str, Score]
    uncertainty: dict[str, Score]


class Decision(Schema):
    action: Literal["ANSWER", "SEARCH_MORE", "RESOLVE_CONFLICT", "ASK", "ABSTAIN"]
    target_claim_id: Text | None = None
    blocking_claims: list[Text] = Field(default_factory=list)
    rationale: Text
    confidence: Score | None = Field(
        default=None, description="Uncalibrated score, not probability"
    )
    acquisition: AcquisitionRanking | None = None


class AgentEvent(Schema):
    id: Text
    query_id: Text
    type: Text
    timestamp: AwareDatetime
    component: Text
    usage: Usage
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class EpistemicState(Schema):
    query_id: Text
    claims: list[Claim] = Field(default_factory=list)
    proof_graph: list[ProofNode] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    beliefs: list[ClaimBelief] = Field(default_factory=list)
    blockers: list[Text] = Field(default_factory=list)
    contradictions: list[Text] = Field(default_factory=list)
    budget: BudgetState = Field(default_factory=BudgetState)
    trace: list[AgentEvent] = Field(default_factory=list)
