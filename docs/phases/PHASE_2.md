# Phase 2 — Evaluation harness v1

## Implementation

Added dataset adapter protocol and validated JSONL loader; shared EM/token-F1
and answer coverage; method-independent async runner; all-case JSONL outputs and
individual JSON traces; aggregate JSON/CSV with tokens, calls, documents, latency,
decimal costs, missing-cost/incomplete-usage counts; reproducibility manifest;
config-driven `evaluate` CLI and smoke dataset.

## Design decisions

[ADR 0002](../decisions/0002-evaluation-protocol.md) freezes normalization,
denominators, failure accounting and label isolation. Scoring is centralized and
never varies by method. Provider failures cannot silently remove a case or become
a zero-cost success. Unknown costs stay unknown. Configured budgets apply per case.

## Validation and acceptance

All Phase 2 deliverables are implemented. Tests cover EM/F1 including repeated
tokens and empty strings, duplicate/malformed datasets, no label leakage, failed
cases, abstentions, unlabelled denominators, budget exhaustion, artifact retention,
overwrite refusal, config-driven CLI, input hashing and known negative smoke cases.
Full suite: 61 tests. Required commands: locked install, ruff check/format, mypy,
pytest, `epistemic-search evaluate configs/evaluation_fixture.yaml`, and build.

## Limitations

Generic English single-reference scoring is not an official benchmark scorer.
No citation entailment grading or selective-risk/calibration metrics yet. All
cases are loaded for validation before execution; this is suitable for initial
research datasets, not streaming web-scale evaluation. Unexpected exceptions may
hide already-incurred usage, which is explicitly marked incomplete. Token estimates
and remote budget caveats from Phase 1 still apply. No real-model quality study run.

## Next dependency

Phase 3 — Iterative relevance baseline: bounded search/model loop with the same
providers, budget accounting, answer contract and evaluation harness, no premises.
