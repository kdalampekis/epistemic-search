# Codex Build Specification

## Project

`epistemic-search`

## Goal

Build a reproducible research system for premise-aware active retrieval and selective answering.

Do **not** implement the entire architecture at once.

## Proposed stack

- Python 3.12+
- uv
- Pydantic v2
- Typer
- pytest
- ruff
- pyright or mypy
- httpx
- numpy/pandas for evaluation
- networkx only if useful
- optional `z3-solver` in a later phase
- provider SDKs behind adapters

## Repository structure

```text
epistemic-search/
├── AGENTS.md
├── README.md
├── RESEARCH_PROPOSAL.md
├── ARCHITECTURE.md
├── EXPERIMENT_PLAN.md
├── LITERATURE_MAP.md
├── PAPER_PLAN.md
├── PERPLEXITY_POSITIONING.md
├── CODEX_BUILD_SPEC.md
├── CODEX_START_PROMPT.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── configs/
├── src/
│   └── epistemic_search/
│       ├── models/
│       ├── providers/
│       ├── decomposition/
│       ├── retrieval/
│       ├── evidence/
│       ├── belief/
│       ├── reasoning/
│       ├── controller/
│       ├── answering/
│       ├── evaluation/
│       ├── tracing/
│       └── cli/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/
├── notebooks/
├── docs/
│   ├── decisions/
│   ├── phases/
│   ├── experiments/
│   └── results/
└── artifacts/
```

# Phase 0 — Research repository foundation

## Objective
Create the minimal high-quality research scaffold.

## Implement
- package structure;
- Pydantic core schemas:
  - `QueryCase`
  - `Claim`
  - `ProofNode`
  - `EvidenceItem`
  - `ClaimBelief`
  - `EpistemicState`
  - `BudgetState`
  - `Decision`
  - `AgentEvent`;
- provider protocols:
  - `ModelProvider`
  - `SearchProvider`;
- config loading;
- structured logging;
- token/cost accounting interfaces;
- simple CLI;
- tests;
- CI;
- `docs/phases/STATUS.md`.

## Acceptance criteria
- install succeeds;
- lint passes;
- typecheck passes;
- tests pass;
- schemas round-trip through JSON;
- no external API required for tests;
- mocks exist for both provider interfaces.

Do not implement retrieval or LLM decomposition yet.

---

# Phase 1 — Naive RAG baseline

## Objective
Establish the baseline before building the proposed method.

## Implement

```text
Question
→ SearchProvider
→ top-k documents
→ answer ModelProvider
→ answer + citations
```

Add:
- configurable `k`;
- token accounting;
- search-call accounting;
- trace output;
- fixture corpus retriever.

## Acceptance criteria
- end-to-end with fake providers;
- optional real provider via configuration;
- trace contains all costs;
- deterministic fixture run.

---

# Phase 2 — Evaluation harness v1

## Objective
Make evaluation first-class early.

## Implement
- dataset adapter protocol;
- JSONL benchmark runner;
- exact match/F1;
- answer coverage;
- search calls;
- retrieved tokens;
- LLM tokens;
- latency/cost;
- per-example traces;
- aggregate JSON/CSV outputs.

---

# Phase 3 — Iterative relevance baseline

## Objective
Create a fair agentic RAG baseline.

```text
question
→ search
→ evidence
→ model decides search_more or answer
→ repeat until budget
```

No premise graph.

Must be bounded and fully instrumented.

---

# Phase 4 — Premise decomposition

## Objective
Convert questions into explicit answer-critical claims and dependency graphs.

## Implement
- schema-constrained decomposition;
- prompt versioning;
- cache;
- fixture/gold cases;
- validator;
- inspection CLI.

## Acceptance criteria
- invalid graphs rejected;
- conclusion connected to premises;
- stable IDs;
- model/prompt recorded.

---

# Phase 5 — Evidence ledger

## Objective
Retrieve and classify evidence claim-by-claim.

## Implement
- span extraction;
- claim-specific stance:
  - SUPPORT
  - CONTRADICT
  - NEUTRAL;
- provenance;
- deduplication;
- evidence compaction.

Relevance must not equal stance.

---

# Phase 6 — Belief state v1

## Objective
Aggregate evidence without hiding disagreement.

Statuses:
- SUPPORTED
- CONTRADICTED
- MIXED
- UNKNOWN

Do not call scores calibrated probabilities.

Synthetic tests must cover:
- no evidence;
- support only;
- contradiction only;
- mixed evidence;
- duplicates.

---

# Phase 7 — Structured sufficiency reasoner

## Objective
Determine whether current claim states are sufficient for a conclusion.

Implement:
- AND / OR / NOT;
- recursive evaluation;
- blocker extraction;
- unresolved minimal frontier;
- derivation trace.

`UNKNOWN` must propagate correctly.

---

# Phase 8 — Premise-directed controller

Policy v1:

```text
if sufficient:
  ANSWER
elif contradiction and budget:
  RESOLVE_CONFLICT
elif blocker and budget:
  SEARCH_MORE(blocker)
else:
  ABSTAIN
```

Acceptance:
- no unnecessary resolved-claim searches;
- budget respected;
- abstention returns blocking claims.

---

# Phase 9 — Targeted query generator

Inputs:
- original question;
- target claim;
- entities;
- temporal scope;
- current evidence;
- conflict state.

Log all generated queries.

---

# Phase 10 — Full Epistemic Search MVP

Integrate:

```text
decompose
→ retrieve
→ evidence
→ belief
→ reason
→ controller
→ repeat
→ answer/abstain
```

Fixture cases:

A. all evidence found → ANSWER  
B. missing premise → targeted search → ANSWER  
C. still missing → ABSTAIN  
D. contradiction → conflict-resolution search

---

# Phase 11 — Benchmark integrations

First:
1. HotpotQA
2. 2WikiMultiHopQA
3. ConfRAG

Keep dataset setup reproducible.

---

# Phase 12 — Baseline parity

Run:
- closed-book;
- naive top-k;
- iterative relevance;
- premise-directed without belief/formal;
- full system.

Use matched:
- answer model;
- retriever;
- budgets;
- evaluation.

---

# Phase 13 — Abstention metrics

Implement:
- coverage;
- selective risk;
- risk-coverage curves;
- AURC;
- abstention precision/recall/F1.

---

# Phase 14 — Contradiction experiments

Add:
- ConfRAG evaluation;
- contradiction detection;
- conflict trace;
- conflict-specific search;
- unsafe-answer metric.

---

# Phase 15 — Calibration

Compare:
- self-reported/raw confidence;
- NLI score;
- calibrated NLI;
- evidence aggregation;
- optional semantic entropy.

Implement:
- ECE;
- Brier;
- reliability curves.

---

# Phase 16 — Cost-aware controller

Policies:
- random unresolved;
- importance first;
- uncertainty first;
- approximate value-of-information.

All share the same action interface.

---

# Phase 17 — Controlled benchmark transformations

Generate:
- missing premise;
- contradiction;
- irrelevant/redundant context;
- repeated evidence;
- order manipulation;
- freshness conflicts.

Record transformation metadata.

---

# Phase 18 — Optional formal backend

Add `z3-solver` for structured subsets.

Compare:
- generative sufficiency judge;
- proof graph;
- SMT where valid.

Do not force open-domain text into SMT.

---

# Phase 19 — Ablation runner

Config switches:

```yaml
use_premise_graph: true
use_belief_state: true
use_formal_sufficiency: true
use_conflict_resolution: true
use_cost_aware_controller: true
allow_abstention: true
compact_evidence: true
```

Generate comparable result tables.

---

# Phase 20 — Statistical analysis

Implement:
- bootstrap CIs;
- paired tests where appropriate;
- cost distribution summaries;
- comparison reports.

---

# Phase 21 — Failure analysis

Create:
- trace viewer;
- failure classifier;
- Markdown/HTML example reports.

Use the taxonomy in `ARCHITECTURE.md`.

---

# Phase 22 — Demo dashboard

Local UI showing:
- question;
- premise graph;
- evidence;
- belief states;
- blockers;
- next action/query;
- budget/tokens;
- final answer/abstention.

The UI is not the scientific contribution.

---

# Phase 23 — Paper artifact generation

Scripts generate:
- tables;
- plots;
- dataset summaries;
- ablation tables;
- selected traces.

Never manually copy result numbers into paper artifacts.

---

# Phase 24 — Reproduction package

Add:
- configs;
- seeds;
- lockfile;
- dataset scripts;
- prompts;
- model metadata;
- result manifests.

---

# Phase 25 — Final technical report / paper

Use `PAPER_PLAN.md`.

Only make claims supported by experimental results.

---

# Recommended order

```text
P0 Foundation
 ↓
P1 Naive baseline
 ↓
P2 Evaluation harness
 ↓
P3 Iterative baseline
 ↓
P4 Premise decomposition
 ↓
P5 Evidence ledger
 ↓
P6 Belief state
 ↓
P7 Sufficiency reasoner
 ↓
P8 Controller
 ↓
P9 Targeted search
 ↓
P10 MVP
 ↓
P11–P14 Real benchmarks
 ↓
P15–P20 Research experiments
 ↓
P21–P25 Demo + paper
```

## Important implementation rule

Do not rush into the proposed method before the baselines and evaluation harness exist.

A research repository without trustworthy baselines is not useful.
