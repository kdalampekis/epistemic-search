# Phase 14 — Contradiction experiments

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 13 commit `dfa9dba` passed CI run `40063077390` before this phase began.

## Implementation and acceptance

- ConfRAG evaluation: `conflicts.py` and CLI analyze native corpus conflict labels,
  retrieved/cited viewpoint coverage, missing detector outputs and failures.
- Contradiction detection: evaluate existing thresholded MIXED beliefs against
  corpus labels, with precision/recall/F1, explicit unknowns and an all-positive
  detection denominator. No different grader is applied to baseline prose.
- Conflict trace: `CONFLICT` events link mixed claims to both evidence stances and
  provenance. Historical belief events remain analyzable without paid replay.
- Conflict-specific search: existing controller/query behavior is retained;
  tests verify execution and blocking after further one-sided evidence. The
  evaluator counts actual attempts and keeps failed-search costs unknown.
- Unsafe-answer metric: independent, trace-bound judgments produce a rate with
  explicit denominator; internal conflict violations are separately labelled.

Protocol and exclusions: [ADR 0008](../decisions/0008-conflict-evaluation.md).
This is project-specific contradiction evaluation on ConfRAG, not reproduction
of its structured NMI/answer/reason coverage tasks. No model prompt changed.

## Checks

`uv run --locked ruff check .`, `ruff format --check .`,
`mypy src tests scripts/analyze_phase14.py`, `pytest -q`, and `uv build` passed.
**200 tests passed**; mypy checked **49 files** including the reproduction script.
Tests cover mixed-source provenance, persistent conflict, executed versus merely
planned search, failed attempts, missing predictions, confusion denominators,
unsafe judgment consistency, label isolation, CLI overwrite refusal, trace hashes
and source/path validation. No test uses a real provider.

Reproduce the saved pilot analysis from the repository root with a new output:

```sh
uv run --locked python scripts/analyze_phase14.py configs/confrag_comparison.yaml phase14.json
```

The script validates the executed comparison config and matched example IDs,
then records input/evaluator hashes. It never invokes a model or search provider.

## Results and limitations

[Saved report](../results/phase14_conflict_pilot.json): all five methods, both
preselected ConfRAG pilot examples, **zero additional API calls/cost**. Total
research API spending remains **$0.067952575**.

Case 88 is corpus-labelled contradictory. Full Epistemic Search answered without
detecting conflict and retrieved sources from only one of two viewpoint clusters
(coverage 0.5). This is one end-to-end detection false negative. Its second case
failed extraction and has unknown detection. The other methods have no explicit
detector output, so their detector classification metrics are unavailable.
Premise-only retrieval covered both clusters for case 88 but cited just one;
source coverage alone establishes neither understanding nor answer correctness.

All methods have unknown independent unsafe-answer rates because no independent
safety adjudication exists. The full system's internal no-conflict state cannot
serve as its own gold safety label. No comparative reliability or significance
claim is supported, and the two-case diagnostic does not justify scaling.

## Next dependency

After push and successful CI: **Phase 15 — Calibration**. Implement measurement
and held-out calibration with offline tests first. Do not convert heuristic
evidence scores into calibrated probabilities by renaming them.
