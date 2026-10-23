# Phase 4 — Premise decomposition

## Implementation and design

Added schema-constrained decomposition with versioned prompts, provider metadata,
usage/error retention, an atomic on-disk cache, content-derived claim/node IDs,
handwritten graph fixtures and a `decompose` inspection CLI. Draft model aliases
are rewritten to canonical IDs; reordered claims/children and renamed aliases
produce the same graph. Cache keys cover backend, model, question, prompt/schema,
seed and output allowance. Cache hits retain the originating response/usage while
the current call is explicitly charged zero.

The graph validator requires a single connected CONCLUSION root, valid claim and
child references, unique IDs, no cycles, correct operator arity, and exactly one
leaf per claim (shared leaves can have multiple parents). Every graph node must
be reachable from the conclusion. This is structural validation only.

## Tests and acceptance

All four criteria are covered: invalid graphs rejected; conclusion connected;
stable IDs; model/prompt recorded. Tests cover cycles, dangling references,
disconnected nodes, arity, duplicate IDs/text, missing claims, JSON round trips,
alias/order stability, cache usage and invalidation, invalid response accounting,
label isolation and CLI. Full suite: 84 tests. Locked install, ruff check/format,
strict mypy, pytest, decomposition CLI and distribution build pass.

## Known limitations

Semantic completeness and correctness still depend on the model; this phase
cannot certify them. Canonical IDs normalize case/Unicode/whitespace, not meaning.
A cache freezes a response for the keyed request; editing a fixture script alone
does not invalidate that request key (use a new model ID or clear the local cache).
Graphs are capped at 128 claims/512 nodes for inspection. No graph inference,
belief aggregation, stance classification or epistemic control is implemented.
Standalone decomposition uses its configured output allowance and timeout;
integration into shared run budgets belongs to Phase 10.

## Next dependency

Phase 5 — Evidence ledger: claim-specific span/stance extraction, provenance,
deduplication and compaction. Relevance must remain separate from stance.
