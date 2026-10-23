# Research strategy under the $50 total budget

Effective 2026-10-23. This supersedes the earlier Phase 12 Sol-primary plan.
The aim is experimental information per dollar, not benchmark volume.

- Total project API cap: **$50**, including all phases and failures.
- Primary model: **gpt-6-luna / medium** through Responses API, identically
  configured for every method. Low is allowed for separate simple development
  work, never silently mixed into the main comparison.
- Final robustness reserve: **$5 within the $50**, for a small Sol/medium subset
  after the architecture and findings stabilize. No Sol run is scheduled now.
- No GPT-6 Astra. No extra budget assumed.
- Tests use fixtures/mocks; small development examples precede experiments.
- Before any experiment expected above $1, publish its assumptions, token/API
  estimate and conservative bound. The estimator prints both a planning scenario
  and the configured token-ceiling bound, without assuming cache savings.
- Retain failed cases, exact request reuse and cost reservations. Never rerun
  identical paid requests just to obtain a nicer result.

## Phase 12 sequence

Seed 42 selects examples using the existing label-independent native adapter.
First: one smoke example from each of HotpotQA, 2Wiki and ConfRAG, all five
methods. Per-dataset run cap $0.25. Planning scenario $0.0354375 total;
configured token-ceiling bound $0.43326.

Second: the preregistered diagnostic pilot of 10 HotpotQA + 10 2Wiki + 2 ConfRAG
examples, each with all five methods (110 method-examples). Per-dataset caps
$2/$2/$0.50. Planning scenario $0.259875; token-ceiling bound $3.17724.
The scenario assumes 3 calls per method-example, each 1,500 input and 1,200
output/reasoning tokens; it is not an empirical prediction. Exact identical
smoke requests can be reused. Smoke examples are nested in the larger seeded
subset and are not additional independent observations.

Freeze prompts, corpus/retriever, reasoning settings, caps and scorer across
methods. Keep smoke and pilot outputs distinct and record overlap. ConfRAG has
no single-answer EM/F1: these two examples are integration observations only;
contradiction metrics remain Phase 14. No full benchmark follows automatically.
A negative or inconclusive pilot can satisfy integration acceptance without
supporting the research hypothesis or justifying larger spend.

## Commands

```sh
uv run --locked epistemic-search phase12 configs/phase12.yaml --stage smoke --estimate-only
uv run --locked epistemic-search phase12 configs/phase12.yaml --stage smoke
# Inspect traces and record the report hashes in phase12_smoke_audit.json.
uv run --locked epistemic-search phase12 configs/phase12.yaml --stage comparison --estimate-only
uv run --locked epistemic-search phase12 configs/phase12.yaml --stage comparison
```

The CLI reads only OPENAI_API_KEY from the environment or the local ignored
`.env`, in memory. Never put it in `.env.example`. Completed matching artifacts
are reused; partial or changed artifacts require inspection and are never
overwritten. Project/run caps and cumulative reservations live in the shared
SQLite file, independent of output directories. See
[ADR 0006](../decisions/0006-project-budget-and-output-reuse.md) for physical versus
logical accounting, crash handling and pricing limitations.
