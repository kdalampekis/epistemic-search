# Phase 19 — Ablation runner

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 18 commit `581cf0b` passed CI `40083718154` before work began.

## Implementation and design

Implemented all seven requested switches, a one-switch-at-a-time runner and
incremental JSON, CSV and Markdown comparisons. Shared configs keep model/effort,
data, grader, retrieval and resource ceilings matched. Nondefault switches appear
in configs and traces; unchanged defaults preserve historic config hashes.

The engine now supports generative control without formal sufficiency, ordinary
queries without conflict-resolution templates, importance instead of VOI,
bounded forced answers and full-document answer context. Removal of graph or
belief prerequisites uses the existing iterative/premise-only comparators and
records the dependent components removed. This scope is explicit in every
comparison manifest; see [ADR 0013](../decisions/0013-ablation-semantics.md).

## Tests and acceptance

All switches have actual execution paths. Tests verify matched manifests and
tables, schema validation, absence of gold leakage, omitted formal calls, retained
MIXED states, changed conflict queries, changed VOI ranking, raw-context exposure,
forced-answer failures and hard-budget enforcement. A test caught and fixed an
automatic conflict-query fallback that initially made that intervention inert.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`uv run --locked --extra formal --extra benchmarks pytest -q`, and `uv build`
pass: **263 tests**, **57 typed files**. Existing MVP scenarios and five-method
comparisons still pass. CI includes the new offline command:

```sh
uv run --locked epistemic-search ablate configs/ablation_fixture.yaml
```

The reference and seven variants each execute one scripted example without
errors: **28 scripted model calls**, eight searches, zero API calls and $0.
All answer matches are fixture behavior, not model-quality measurements.

## Negative observation, limitations and next dependency

On this tiny context, compact evidence metadata uses more input tokens than raw
document presentation (reference 264 versus no-compaction 249 whitespace-estimated
input tokens). Compaction does not automatically save tokens. No empirical
advantage is claimed. Some policy changes are inactive on this easy CLI fixture;
separate deterministic tests activate them.

Single-switch removal can remove dependent operations; this is not an isolated
causal effect for those variants. Factorial interactions and paired statistical
analysis are not implemented in this phase. Forced answering cannot override
hard budgets or guarantee a valid answer. No paid benchmark or scaling occurred.
Additional research API spend: **$0**; cumulative remains **$0.067952575**.

After push and successful CI: **Phase 20 — Statistical analysis**.
