# Phase 22 — Demo dashboard

Status: **complete**, pushed as `f074144`; hosted CI `40117208034` passed.
Phase 21 commit `fe5b3b4` passed CI `40116134085` before work began.

## Implementation and design

Added `dashboard.py`, bundled native JS/CSS, fixture/pilot YAML configs and the
`dashboard` CLI. Standalone local HTML displays the question, premise graph,
evidence with provenance, beliefs, blockers, next decision/query, cumulative
resources and recorded final answer/abstention. Search and event playback work
without a server or external assets. See [ADR 0016](../decisions/0016-offline-dashboard.md).

## Tests and acceptance

All eight requested views are present. Tests check no future evidence leakage,
resource conservation, complete case inclusion, CSP hashes, escaped untrusted
text, trace path confinement and overwrite refusal. All **287 tests** pass;
ruff lint/format, mypy (**63 files**) and wheel/sdist builds pass. CI builds the
fixture dashboard after fixture evaluations. Wheel inspection includes JS/CSS.

A headless installed Chrome smoke via ephemeral Playwright validated all 110
pilot cases, filtering (including empty results), case selection, event stepping,
1440px desktop and 390px mobile layouts, no page errors and no HTTP(S) requests.
Both layouts were visually inspected. The original smoke assertion expected
lowercase rendered metadata; CSS intentionally uppercases it. The assertion was
corrected to be case-insensitive; no application defect was hidden.

```sh
uv run --locked epistemic-search dashboard configs/dashboard_fixture.yaml
uv run --locked epistemic-search dashboard configs/dashboard_pilot.yaml
```

Open `artifacts/dashboard-pilot/index.html` for all saved pilot cases. Generated
HTML and source/renderer hashes remain local artifacts, not benchmark evidence.

## Limitations and next dependency

Complete saved runs only; Phase 21 reports remain available for partial runs.
Graph width scrolls within its panel on small screens. Final wall time includes
cache effects; logical calls and physical API calls/cost remain distinct. No
live execution, new grading, model calls or benchmark scaling occurred.
Additional API spend: **$0**; cumulative remains **$0.067952575**.

After push and successful CI: **Phase 23 — Paper artifact generation**.
