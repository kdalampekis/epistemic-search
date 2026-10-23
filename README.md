# Epistemic Search

> **Premise-aware active retrieval with explicit belief states, contradiction handling, formal sufficiency checks, selective answering, and cost-aware search.**

**Repository name:** `epistemic-search`

**Working paper title:**  
**Epistemic Search: Premise-Aware Active Retrieval with Belief States, Formal Sufficiency Checks, and Selective Answering**

## 1. Research thesis

Most Retrieval-Augmented Generation (RAG) systems ask:

> What documents are relevant to this question?

This project asks a stronger question:

> **What must be known before this question can be responsibly answered, which of those requirements are currently supported, contradicted, or unknown, and what is the highest-value information action to take next?**

The system explicitly represents:

- the claims or premises required for an answer;
- the evidence supporting or contradicting each premise;
- uncertainty about each premise;
- logical dependencies between premises and candidate conclusions;
- the current blocking proof obligation(s);
- the expected value and cost of another retrieval action;
- a final decision among `ANSWER`, `SEARCH_MORE`, `ASK`, and `ABSTAIN`.

The target is not to build another web-scale search engine. The target is to build a **reasoning and control layer on top of retrieval**.

## 2. Core intuition

A standard RAG system often behaves like:

```text
Question
  ↓
Retrieve top-k
  ↓
Put retrieved text in context
  ↓
LLM generates answer
```

A more agentic system may repeat retrieval:

```text
Question
  ↓
Search
  ↓
Reason
  ↓
Search again
  ↓
Answer
```

Epistemic Search instead maintains an explicit state:

```text
Question
  ↓
Claim / premise decomposition
  ↓
Proof-obligation graph
  ↓
Retrieve evidence per unresolved premise
  ↓
Evidence ledger
  ├── SUPPORTED
  ├── CONTRADICTED
  ├── MIXED
  ├── UNKNOWN
  └── IRRELEVANT
  ↓
Probabilistic / calibrated belief state
  ↓
Formal sufficiency checker
  ↓
What blocks the conclusion?
  │
  ├── nothing → ANSWER
  ├── missing premise → SEARCH_MORE
  ├── conflicting premise → RESOLVE_CONFLICT
  ├── user-specific missing fact → ASK
  └── unresolved after budget → ABSTAIN
```

The search controller should prefer the action that resolves the most decision-critical uncertainty per unit cost.

## 3. Why this matters

A model can receive a large amount of context and still not have the one fact needed to justify a conclusion.

Example:

```text
Required:
C1 ∧ C2 ∧ C3 ∧ C4 → Conclusion

Current state:
C1 = SUPPORTED
C2 = SUPPORTED
C3 = UNKNOWN
C4 = SUPPORTED
```

The system should not respond by blindly loading more generic documents.

It should recognize:

```text
blocking_proof_obligation = C3
```

and search specifically for evidence about `C3`.

If `C3` remains unresolved, the correct behavior may be abstention.

## 4. Research contribution we are testing

This repository does **not** assume that premise-aware retrieval itself is novel.

Recent work already explores:
- adaptive retrieval;
- explicit sufficiency/gap judging;
- premise-directed active retrieval;
- uncertainty estimation;
- contradiction-aware RAG;
- symbolic reasoning with LLMs.

Our research question is whether combining the following in one controlled architecture provides measurable gains:

1. **Premise-level decomposition**
2. **Explicit evidence states**
3. **Calibrated or separately modeled epistemic uncertainty**
4. **Formal answer-sufficiency / proof-obligation checks**
5. **Contradiction as a first-class state**
6. **Value-of-information-driven retrieval**
7. **Selective answering / abstention**
8. **A token-, query-, latency-, and cost-aware stopping policy**

The intended contribution is therefore not “RAG with reasoning.”

It is:

> **Treating retrieval as finite-budget epistemic control over an explicit proof state.**

## 5. Scientific discipline

### 5.1 Formal derivability is not real-world truth

If an LLM extracts premises from natural language and a solver derives a conclusion, we can claim:

> The conclusion is derivable from the current extracted evidence model.

We must not claim:

> The real-world answer has been mathematically proven.

Extraction and evidence interpretation remain fallible.

### 5.2 Unknown is not false

`UNKNOWN` must never silently become `FALSE`.

### 5.3 Model confidence is not automatically probability

Raw LLM self-reported confidence must not be called calibrated probability.

If the project uses probabilities, calibration must be measured.

### 5.4 Abstention is an output, not a failure

The action space is:

```text
ANSWER
SEARCH_MORE
ASK
ABSTAIN
```

A correct abstention on insufficient evidence is a success.

## 6. What we are not building

For the first paper, do not build:

- a crawler;
- a web-scale index;
- a Perplexity-scale ranking engine;
- a new foundation model;
- a custom embedding model;
- a generic browser agent;
- a full knowledge graph of the Web.

Use an existing retrieval/search backend.

The contribution lives in the **controller, evidence model, reasoning layer, and evaluation**.

## 7. Target outcome

The strongest result would look like:

> At matched search and model budgets, Epistemic Search improves answer accuracy and selective reliability while reducing unnecessary retrieved/context tokens, and detects contradictions/missing evidence more reliably than standard and iterative RAG baselines.

A particularly compelling result would be a Pareto improvement:

```text
higher answer quality
+
better abstention
+
better contradiction handling
+
fewer context tokens
```

## 8. Repository map

```text
epistemic-search/
├── README.md
├── AGENTS.md
├── RESEARCH_PROPOSAL.md
├── ARCHITECTURE.md
├── EXPERIMENT_PLAN.md
├── LITERATURE_MAP.md
├── PAPER_PLAN.md
├── PERPLEXITY_POSITIONING.md
├── CODEX_BUILD_SPEC.md
├── CODEX_START_PROMPT.md
├── docs/
│   ├── decisions/
│   ├── phases/
│   ├── experiments/
│   └── results/
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
├── configs/
├── scripts/
├── notebooks/
└── artifacts/
```

## 9. Start here

Codex / Claude Code should read, in order:

1. `AGENTS.md`
2. `RESEARCH_PROPOSAL.md`
3. `ARCHITECTURE.md`
4. `EXPERIMENT_PLAN.md`
5. `LITERATURE_MAP.md`
6. `CODEX_BUILD_SPEC.md`

Then follow `docs/phases/STATUS.md`, completing and pushing each phase before the next.

## 10. Phase 0 quickstart

The foundation and naive baseline are implemented. See [phase status](docs/phases/STATUS.md) and the
[Phase 0 report](docs/phases/PHASE_0.md).

Install with Python 3.12 and uv:

```sh
uv sync --locked --python 3.12
uv run --locked epistemic-search validate-config configs/foundation.yaml
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
uv run --locked pytest
uv build
```

Tests and the config CLI require no API keys or network access after dependency
installation. The CLI prints resolved config JSON to stdout and structured logs
to stderr. Configuration rejects unknown fields and invalid budgets. A seed is
recorded for future methods; it does not guarantee determinism of remote models.

Current code lives in small modules under `src/epistemic_search/`: `models`,
`providers`, `config`, `accounting`, `tracing`, and `cli`. The larger repository
map above is the planned layout as later phases add functionality. Provider mocks
are in `tests/test_providers.py`. Next: **Phase 7 — Structured sufficiency reasoner**.

## 11. Naive RAG baseline

```sh
uv run epistemic-search run-naive configs/naive_fixture.yaml tests/fixtures/query.json run.json
```

This offline smoke run uses lexical fixture retrieval and scripted model output.
It tests integration, not answer quality. `run.json` contains the answer, cited
sources, provenance, requests/responses, accounting, and errors. Existing output
files are never overwritten. Corpus/script paths are relative to the YAML file.

For a real model, set `OPENAI_API_KEY` and use `configs/naive_openai.yaml` with a
model snapshot available to your account. Unconfigured prices mean unknown cost.
Tests need no keys. See [Phase 1](docs/phases/PHASE_1.md) for estimation/budget limits.

## 12. Evaluation harness

```sh
uv run epistemic-search evaluate configs/evaluation_fixture.yaml
```

Creates a new `artifacts/evaluation-fixture/` directory containing a manifest,
per-example traces and JSONL scores, and JSON/CSV summaries. All cases remain in
the outputs, including failures. EM/F1 use labelled cases; coverage uses all cases.
Unknown costs remain null. See [the scoring protocol](docs/decisions/0002-evaluation-protocol.md).
The bundled two-case smoke run deliberately includes a wrong scripted answer;
it makes no model-quality claim. Change `evaluation.output_dir` for another run.

## 13. Iterative relevance baseline

```sh
uv run epistemic-search run configs/iterative_fixture.yaml tests/fixtures/query.json iterative.json
uv run epistemic-search evaluate configs/iterative_fixture.yaml
```

`method: iterative_rag` enables model-directed follow-up searches, bounded by
`rag.max_rounds` and cumulative budgets. It shares provider/accounting/grading
code with `naive_rag`. [Phase 3](docs/phases/PHASE_3.md) documents the limits.

## 14. Premise graph inspection

```sh
uv run epistemic-search decompose configs/decomposition_fixture.yaml tests/fixtures/decomposition_query.json graph.json
```

Validates the model's graph, assigns stable IDs, and saves request/model/usage
metadata. Repeat with a new output filename to inspect a cache hit. Structural
validity does not establish that the premises are true or complete. Details:
[Phase 4](docs/phases/PHASE_4.md).
