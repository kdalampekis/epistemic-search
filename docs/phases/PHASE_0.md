# Phase 0 — Research repository foundation

Date: 2026-10-23.

## Implementation

- Python 3.12 src-layout package, uv lockfile, Typer entry point, ruff, strict mypy,
  pytest, and GitHub Actions checks.
- All nine required Pydantic v2 schemas: `QueryCase`, `Claim`, `ProofNode`,
  `EvidenceItem`, `ClaimBelief`, `EpistemicState`, `BudgetState`, `Decision`,
  `AgentEvent`. Supporting source, provenance, budget, and usage contracts.
- Async `ModelProvider` and `SearchProvider` protocols, validated request/response
  schemas, structured-output parsing, and offline mocks of both protocols.
- YAML config validation and a `validate-config` CLI with resolved JSON output.
- JSON-line logging, event payloads, component-level token/search/document/cost
  accounting, and a recorder protocol.

## Design decisions

[ADR 0001](../decisions/0001-foundation-contracts.md) records the search response
envelope, embedded evidence provenance, cost semantics, and compact module layout.

`UNKNOWN` is a distinct enum state and never a Boolean. Scores are bounded,
finite, and explicitly uncalibrated by default. Source timestamps require a
timezone; evidence spans retain whitespace. Costs use decimal USD values;
missing cost information propagates as unknown. Empty searches still carry usage.
Budget limits permit explicit zero and distinguish it from unbounded (`None`).

## Validation and acceptance criteria

| Criterion | Result |
| --- | --- |
| Installation succeeds | `uv sync --locked --python 3.12` |
| Lint and format pass | `uv run --locked ruff check .`; `uv run --locked ruff format --check .` |
| Type checking passes | `uv run --locked mypy src tests` |
| Tests pass | `uv run --locked pytest`: 32 passed |
| Core schemas round-trip JSON | All nine core schemas and provider contracts exercised |
| No API required by tests | Tests use local fixtures and async protocol mocks |
| Mocks for both providers | `tests/test_providers.py`, including empty search results |
| CLI works | `uv run --locked epistemic-search validate-config configs/foundation.yaml` |
| Distribution builds | `uv build` produces wheel and sdist |

Tests cover score/count/cost validation, timezone requirements, provenance,
unknown-state semantics, independent defaults, invalid structured model output,
safe YAML rejection, CLI errors, usage snapshots, unknown costs, and JSON logs.
The first mypy run flagged a redundant enum comparison after type narrowing;
that assertion was removed and the checks rerun. No experimental results were
produced. Hosted CI has been configured but has not run remotely.

## Known limitations

- Schemas encode data contracts, not semantic truth. Graph connectivity and
  logical consistency checks are deferred to Phase 4; inference to Phase 7.
- The calibration flag does not certify calibration; evaluation is Phase 15.
- Providers must fill usage correctly; real adapter/retry/error accounting is
  not implemented. Structured response consumers must call `parse(schema)`.
- The ledger expects each call once; repeated event recording double-counts.
  Summed call durations are not parallel-run wall-clock latency.
- Budget enforcement belongs to execution/controller phases. Defaults do not
  constitute a production budget policy.
- No baseline, benchmark, external API adapter, or empirical method comparison
  exists yet. The supplied literature map still needs independent verification.
- Local checks use Python 3.12; compatibility with later Python versions is not
  independently tested. Reproducible runs should use the lockfile and this version.

## Next dependencies and exact recommended prompt

Phase 1 depends on these provider contracts and usage schemas. Use:

> Read AGENTS.md and its required documents in order, then
> docs/phases/PHASE_0.md and docs/decisions/0001-foundation-contracts.md.
> Implement **Phase 1 — Naive RAG baseline only** from CODEX_BUILD_SPEC.md.
> Add question → SearchProvider → configurable top-k documents → ModelProvider
> answer with citations, a deterministic fixture corpus retriever, complete
> token/search/cost trace output, and an optional real provider through config.
> Use SearchResponse.results and SearchResponse.usage, preserve source provenance,
> and schema-validate structured model outputs. Keep tests offline with fake
> providers. Do not implement Phase 2 or premise decomposition, belief aggregation,
> formal reasoning, or the proposed controller. Run install, lint, typecheck and
> tests; update STATUS.md and write PHASE_1.md. Report files changed, commands,
> acceptance criteria, limitations, and the exact next recommended phase.
