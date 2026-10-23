# Phase 5 — Evidence ledger

## Implementation and decisions

Added claim-specific retrieval and schema-validated exact-span extraction with
SUPPORT/CONTRADICT/NEUTRAL stances. Relevance scores remain separate. Every item
retains source URI/time/title, claim, query/rank, exact span, extraction model and
prompt version. Extraction rejects spans absent from the source. Empty extraction
stays empty; it is not manufactured negative evidence.

The ledger ignores identical repeated IDs, rejects ID reuse with changed content,
and preserves distinct provenance. Text compaction groups identical normalized
spans per claim/stance while retaining every evidence ID and source ID. Opposing
stances never collapse. Normalized-span duplication groups will support conservative
aggregation in Phase 6. All calls, invalid outputs, and provider failures retain
usage/traces; partial extraction failures remain explicit alongside successes.

## Tests and acceptance

All listed Phase 5 deliverables are implemented. Tests cover high retrieval
relevance with contradiction, coexistence of support/contradiction, exact source
span validation, invalid JSON, retained failed-call usage, duplicate IDs, changed
provenance rejection, multiple-source compaction, empty extraction and end-to-end
fixture retrieval/classification. Full suite: 89 tests. Required locked install,
lint/format, strict typing, tests and distribution build pass.

## Limitations

Stance scores are uncalibrated and extraction remains fallible. Exact substring
checking establishes source membership, not semantic correctness. Deduplication
is conservative exact normalized-span grouping, not semantic paraphrase detection.
Standalone extraction has per-call timeout/output limits; shared run-budget
integration is Phase 10. No belief aggregation or sufficiency reasoning exists yet.

## Next dependency

Phase 6 — Belief state v1: separate support/contradiction aggregation, UNKNOWN,
MIXED and duplicate-aware synthetic tests; no probability/calibration claims.
