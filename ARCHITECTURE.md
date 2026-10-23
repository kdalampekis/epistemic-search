# Architecture

## 1. Design principles

1. **Evidence before generation.**
2. **Unknown is not false.**
3. **Contradiction is first-class.**
4. **Formal reasoning operates over an extracted model, not raw prose.**
5. **The solver may prove derivability from the model, not real-world truth.**
6. **Retrieval is an action with cost.**
7. **The controller may stop without answering.**
8. **Every claim, evidence item, query, and decision is traceable.**
9. **Baselines and the proposed method must share retrieval/model budgets in experiments.**
10. **All model-facing components are provider-agnostic.**

## 2. Top-level architecture

```text
┌─────────────────────────────┐
│ Query Interface             │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Decomposition Engine        │
│ - candidate answers         │
│ - atomic premises           │
│ - dependency graph          │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Retrieval Engine            │
│ - search adapter            │
│ - local corpus adapter      │
│ - reranking                 │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Evidence Engine             │
│ - span extraction           │
│ - stance/NLI                │
│ - provenance                │
│ - deduplication             │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Belief Engine               │
│ - support                   │
│ - contradiction             │
│ - uncertainty               │
│ - calibration               │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Reasoning Engine            │
│ - proof graph               │
│ - sufficiency               │
│ - blockers                  │
│ - alternative hypotheses    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Epistemic Controller        │
│ ANSWER / SEARCH / ASK /     │
│ RESOLVE / ABSTAIN           │
└───────┬───────────┬─────────┘
        │           │
     search      terminal
        │           ▼
        └──────► Answer Engine
```

## 3. Core domain models

```python
class QueryCase:
    id: str
    question: str
    gold_answer: str | None
    answerable: bool | None
    metadata: dict


class Claim:
    id: str
    text: str
    normalized: str | None
    importance: float
    required_for: list[str]
    polarity: str


class ProofNode:
    id: str
    kind: "CLAIM" | "AND" | "OR" | "NOT" | "CONCLUSION"
    children: list[str]


class EvidenceItem:
    id: str
    claim_id: str
    source_id: str
    span: str
    stance: "SUPPORT" | "CONTRADICT" | "NEUTRAL"
    stance_score: float
    retrieval_score: float | None
    metadata: dict


class ClaimBelief:
    claim_id: str
    status: "SUPPORTED" | "CONTRADICTED" | "MIXED" | "UNKNOWN"
    support_score: float
    contradiction_score: float
    uncertainty: float
    calibrated: bool


class EpistemicState:
    query_id: str
    claims: list[Claim]
    proof_graph: list[ProofNode]
    evidence: list[EvidenceItem]
    beliefs: list[ClaimBelief]
    blockers: list[str]
    contradictions: list[str]
    budget: "BudgetState"
    trace: list["AgentEvent"]


class Decision:
    action: "ANSWER" | "SEARCH_MORE" | "RESOLVE_CONFLICT" | "ASK" | "ABSTAIN"
    target_claim_id: str | None
    rationale: str
    confidence: float | None
```

## 4. Provider boundaries

```python
class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...


class SearchProvider(Protocol):
    async def search(self, query: str, k: int) -> list[SearchResult]: ...
```

Possible search implementations:
- benchmark corpus;
- BM25;
- dense retrieval;
- hybrid retrieval;
- web-search API.

The controller must not depend directly on any vendor.

## 5. Decomposition engine

Responsibilities:

1. infer candidate answer structure;
2. generate answer-critical atomic premises;
3. generate logical dependencies;
4. preserve natural-language form;
5. assign stable IDs;
6. log prompt/model/version;
7. schema-validate every output.

Example:

```json
{
  "candidate_conclusion": "Company X may perform action Y",
  "premises": [
    {"id": "c1", "text": "Company X is subject to jurisdiction J"},
    {"id": "c2", "text": "Rule R applies to company type X"},
    {"id": "c3", "text": "No exception E applies"},
    {"id": "c4", "text": "Rule R is currently effective"}
  ],
  "logic": {
    "type": "AND",
    "children": ["c1", "c2", "c3", "c4"]
  }
}
```

## 6. Evidence engine

Relevance is not evidence stance.

```text
Search result
  ↓
Relevant span extraction
  ↓
Claim-specific stance classification
  ↓
SUPPORT / CONTRADICT / NEUTRAL
  ↓
Evidence ledger
```

Store:
- source;
- search query;
- retrieval rank;
- exact span;
- stance model;
- timestamp;
- freshness metadata where available;
- deduplication group.

Conflicting evidence must coexist in the ledger.

## 7. Belief engine

First version should be interpretable.

```text
support = aggregate(weights of SUPPORT evidence)
contradiction = aggregate(weights of CONTRADICT evidence)

if both low:
  UNKNOWN
elif support high and contradiction low:
  SUPPORTED
elif contradiction high and support low:
  CONTRADICTED
else:
  MIXED
```

Later compare:
- calibrated NLI aggregation;
- logistic evidence aggregation;
- Bayesian approximations with explicit assumptions;
- semantic entropy as auxiliary uncertainty;
- learned aggregation.

Never label uncalibrated values “probabilities.”

## 8. Reasoning engine

### 8.1 Minimal proof graph

Support:
- `AND`
- `OR`
- `NOT`
- atomic claims

Example policy:

```text
AND:
  SUPPORTED if all children SUPPORTED
  CONTRADICTED if any required child CONTRADICTED
  UNKNOWN/MIXED otherwise
```

### 8.2 Blocking proof obligations

Given a conclusion, return the unresolved frontier that blocks derivation.

This output drives retrieval.

### 8.3 Optional symbolic backend

Later add:
- Datalog-like rules;
- Z3/SMT for explicitly structured subsets.

Do not force arbitrary open-domain text into SMT merely for novelty.

## 9. Controller

Rule baseline:

```text
if conclusion sufficient:
    ANSWER
elif critical contradiction exists and budget remains:
    RESOLVE_CONFLICT
elif blocker exists and budget remains:
    SEARCH_MORE(blocker)
else:
    ABSTAIN
```

Cost-aware variant:

```text
score(action) =
  expected_information_gain
  * decision_criticality
  * estimated_retrievability
  / expected_cost
```

Potential costs:
- search calls;
- documents;
- retrieved tokens;
- LLM input tokens;
- latency;
- dollar cost.

## 10. Query generation

Targeted query generation receives:
- original question;
- target claim;
- entities;
- temporal scope;
- current evidence;
- conflict direction if resolving a contradiction.

Example:

```text
Generic:
"California company X action Y"

Targeted:
"2026 California statute exception E company type X action Y"
```

## 11. Answer engine

The final generator receives:
- resolved conclusion state;
- compact decisive evidence;
- unresolved caveats;
- citations.

It should not receive every retrieved document by default.

## 12. Trace model

Every run must be replayable.

```yaml
query_id: q_001
events:
  - type: DECOMPOSE
  - type: SEARCH
    target_claim: c1
    query: ...
  - type: EVIDENCE_ADDED
    evidence_id: e1
  - type: BELIEF_UPDATE
    claim: c1
    from: UNKNOWN
    to: SUPPORTED
  - type: SEARCH
    target_claim: c3
  - type: DECISION
    action: ABSTAIN
    reason: unresolved_required_premise
```

## 13. Token/cost accounting

Instrument:
- prompt tokens/component;
- completion tokens/component;
- retrieved text tokens;
- final context tokens;
- total tokens;
- search calls;
- model calls;
- wall-clock latency;
- estimated API cost.

Token efficiency is a primary research outcome.

## 14. Failure taxonomy

```text
DECOMPOSITION_ERROR
RETRIEVAL_ERROR
EVIDENCE_EXTRACTION_ERROR
STANCE_ERROR
BELIEF_AGGREGATION_ERROR
FORMALIZATION_ERROR
CONTROLLER_ERROR
ANSWER_GENERATION_ERROR
CALIBRATION_ERROR
BENCHMARK_AMBIGUITY
```

Each failed example should receive one primary and optional secondary category.

## 15. Reproducibility

- no committed API keys;
- `.env.example`;
- prompt versioning;
- model identifiers;
- dataset hashes;
- config-driven runs;
- cached immutable retrieval for ablations;
- fixed seeds where possible;
- all experiments tied to git commit.

## Current project budget boundary

Paid provider calls are governed by a persistent SQLite ledger shared across
phases, with separate run caps, exact input-token preflight and conservative
charge reservations. Domain logic consumes logical usage; exact-request reuse
records physical spend separately. No API key is serialized. The current
$50-total Luna-primary policy and its limitations are specified in
[ADR 0006](docs/decisions/0006-project-budget-and-output-reuse.md).
