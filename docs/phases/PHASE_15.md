# Phase 15 — Calibration

Status: **complete** (implementation and offline validation). Commit `e6eec78`
pushed; CI `40064049865` passed. A real-model calibration comparison
remains unavailable without aligned scores and independent labels.
Phase 14 commit `eb9f73f` passed CI `40063561539` before work began.

## Implementation and decisions

`calibration.py` implements binary Brier, ECE, reliability curve data, a fitted
histogram calibration map, and a paired four-family comparison: raw confidence,
NLI score, calibrated NLI and evidence aggregation. The CLI reads a YAML config
and schema-validated scored candidates. No provider calls or new dependencies.
See [ADR 0009](../decisions/0009-calibration-protocol.md).

Calibration and evaluation groups must be disjoint; shared-question variants
cannot cross the boundary. Fixed bin counts and smoothing are not tuned on
evaluation labels. Reports retain errors, missing scores/labels, fit IDs,
reliability-bin counts and input/code hashes. An absent fit or comparable sample
produces explicit unavailability. Domain heuristic scores remain uncalibrated.

## Acceptance and tests

All three required metrics and four nonoptional comparison families are
implemented. Optional semantic entropy is intentionally omitted. Tests include
hand-calculated Brier/ECE, endpoints/empty bins, invalid scores, smoothed fit,
serialization, group leakage and duplicate IDs, fit independence from evaluation
labels, paired denominators, unknown-data handling and CLI overwrite protection.
CI includes the offline calibration CLI smoke.

Required checks: `uv run --locked ruff check .`, `ruff format --check .`,
`mypy src tests`, `pytest -q`, and `uv build` passed. **212 tests passed**;
mypy checked **50 files**.

## Fixture experiment and limitations

```sh
uv run --locked epistemic-search calibrate configs/calibration_fixture.yaml
```

Four calibration candidates, seven evaluation rows, four paired candidates;
one unknown label, one failed execution and one missing score are reported.
[Committed fixture output](../results/phase15_fixture_calibration.json).
The synthetic histogram result has lower ECE but worse Brier than raw NLI scores;
no improvement is assumed or hidden. These numbers are software validation only.

The Luna pilot cannot support the four-family comparison: scores concern
different events and some were never collected. Do not reinterpret extraction
confidence as answer correctness or fit on test labels. Real calibration results
remain an explicitly unresolved research limitation; this phase establishes the
measurement and fitting protocol, not empirical calibration quality.
Additional API calls/cost: **0**. Project API total: **$0.067952575**.

## Next dependency

After push and successful CI: **Phase 16 — Cost-aware controller**. Keep the
existing rule policy as the default; implement and test alternative acquisition
policies under shared budgets. Treat information-value estimates as heuristics
unless separately calibrated. Real calibrated beliefs remain unavailable.
