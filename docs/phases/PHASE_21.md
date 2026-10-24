# Phase 21 — Failure analysis

Status: **complete**, pushed as `fe5b3b4`; hosted CI `40116134085` passed.
Phase 20 commit `ea9b15b` passed CI `40115519622` before work began.

## Implementation and design

Added an offline trace viewer, taxonomy classifier, Markdown/HTML example reports
and aggregate inventories. Each executed case remains visible, including errors,
abstentions, budget stops and ungraded answers. Reports show original evidence,
belief/graph state, decisions, usage and expandable event payloads.

Classification distinguishes observable failure stages, provisional output
symptoms and manual judgments. Automatic labels require review; manual judgments
bind assessor/protocol/rationale to exact trace hashes. Abstention is never
automatically treated as a failure. See
[ADR 0015](../decisions/0015-failure-stage-review.md).

## Tests and acceptance

All requested outputs exist: trace viewer, failure classifier using the project
taxonomy, and per-example Markdown/HTML. Tests cover all-case inclusion, output
symptoms versus extraction errors, neutral treatment of abstention/budget stops,
manual provenance and stale-hash rejection, invalid categories, safe rendering
of untrusted source text, path confinement, trace identity validation and overwrite
refusal. Reports require no scripts or network assets.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`uv run --locked --extra formal --extra benchmarks pytest -q`, and `uv build`
pass: **283 tests**, **61 typed files**. CI includes the fixture viewer.

```sh
uv run --locked epistemic-search analyze-failures configs/failures_fixture.yaml
uv run --locked epistemic-search analyze-failures configs/failures_pilot.yaml
```

Open `artifacts/failure-pilot/index.html` locally for all 110 saved pilot traces.
The generated aggregate is copied without editing to
[phase21_failure_pilot.json](../results/phase21_failure_pilot.json).

## Observations, limitations and next dependency

All 110 pilot method-cases were inspected: 14 reference matches, 31 mismatches,
five execution errors, 47 abstentions, seven budget stops and six ungraded answers.
Four execution failures occur during exact-span extraction and one during answer
generation. Including output mismatches, 36 primary hypotheses require review;
no independent human judgments are claimed. Counts are observable outcomes,
not verified causal failure rates or evidence that abstention was inappropriate.

HTML is a static inspection artifact with native disclosure controls, not the
Phase 22 dashboard. No model calls, prompt tuning or benchmark scaling occurred.
Additional research API spend: **$0**; cumulative remains **$0.067952575**.

After push and successful CI: **Phase 22 — Demo dashboard**.
