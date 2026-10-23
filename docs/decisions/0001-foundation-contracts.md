# ADR 0001 — Phase 0 data and provider contracts

Status: accepted for Phase 0 (2026-10-23).

## Context

The architecture sketches a search provider returning a bare result list and
evidence referring to a source ID. Phase 0 also requires accounting and preserved
provenance. A bare list cannot carry the cost of an empty search, and an ID alone
cannot round-trip source provenance without a separate source store.

## Decision

- Keep both providers asynchronous and vendor-neutral. Return `SearchResponse`
  with results and per-call `Usage` instead of a bare list. Model responses also
  require usage. Adapters must report actual counts, including failed calls when
  they incur usage; failure reporting will be implemented with real adapters.
- Embed a typed `Source` and `EvidenceProvenance` in each evidence item. Preserve
  exact spans, source URI, timezone-aware retrieval time, query/rank, extraction
  model and prompt version. Fixture sources may use non-HTTP URIs.
- Use `Decimal` USD amounts. Unknown cost is `None`; explicit zero means free.
  Summing any unknown cost yields an unknown total. Counts must be nonnegative
  integers; scores must be finite. Support and contradiction scores remain
  independent heuristic scores, not probabilities.
- Keep retrieved/context tokens separate from prompt/completion tokens to avoid
  double-counting. Summed call latency is not elapsed run wall-clock time.
- Carry JSON Schema in model requests and use `ModelResponse.parse(schema)` to
  validate structured output before domain use. Provider JSON mode alone is
  insufficient validation. Text responses remain available for later baselines.
- Use flat modules while the scaffold is small. Add subsystem packages when
  their scheduled phases implement behavior; no empty future engines.

## Consequences and limits

Consumers must access `SearchResponse.results`; adapters must supply usage even
when results are empty. Embedded provenance duplicates a little data but needs
no external store to interpret a serialized evidence item. `UsageLedger` records
each call event once at the caller's direction; it does not deduplicate events.
The `calibrated` flag is metadata, not evidence that calibration was evaluated.
Graph connectivity, semantic consistency, budget enforcement, retry accounting,
provider-specific token measurement and run replay belong to later phases.
