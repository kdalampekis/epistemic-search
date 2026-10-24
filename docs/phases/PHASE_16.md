# Phase 16 — Cost-aware controller

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 15 commit `e6eec78` passed CI `40064049865` before work began.

## Implementation

Added configurable random, importance, uncertainty and approximate-VOI acquisition
ranking through the existing `choose_action` interface. Shared frontier,
conflict priority, sufficiency and budget logic are preserved. Acquisition
decisions record candidates, scores, estimation inputs, provenance and seed/round.
The full engine passes its config and case/round identity into the controller.

The historical importance policy remains the default. Nondefault settings are
serialized; exact historical defaults preserve prior config hashes. No prompt,
grader, provider or paid-output cache key changed. See
[ADR 0010](../decisions/0010-acquisition-policies.md) for the heuristic's definition.

## Tests and acceptance

All four requested policies exist and share one action interface. Tests cover
ranking changes from uncertainty/cost, exact heuristic values, stable random
replay despite input reordering, identical conflict/budget rules, terminal
sufficiency, invalid estimates and historical config serialization. All four MVP
scenarios run under each policy with the same expected outcomes and usage.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`pytest -q`, and `uv build` passed: **231 tests**, **50 typed files**.

```sh
uv run --locked epistemic-search evaluate configs/voi_fixture.yaml
```

This offline smoke explicitly acquires a missing premise before answering:
2 searches, 5 scripted model calls, 0 HTTP/API calls, $0. The trace contains the
VOI inputs and selected target. CI includes this smoke. Historical ConfRAG
config validation and the Phase 14 result report still reproduce exactly.

## Limitations and next dependency

There is no measured information gain, learned retrievability, global repair-plan
optimization or demonstrated cost advantage. Uniform estimates can make policies
equivalent; fixture success is not evidence of model quality. Calibration remains
unvalidated on real predictions. Additional research API spend: **$0**; cumulative
spend remains **$0.067952575**. No benchmark scaling follows automatically.

After push and successful CI: **Phase 17 — Controlled benchmark transformations**.
Keep transformation labels/metadata outside model-visible context and preserve
the original question groups for split separation.
