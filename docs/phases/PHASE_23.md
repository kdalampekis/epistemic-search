# Phase 23 — Paper artifact generation

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 22 commit `f074144` passed CI `40117208034` before work began.

## Implementation and decisions

Added `paper_artifacts.py`, CLI, YAML plans and the optional locked `paper` extra.
Reused the unchanged statistical analysis through an optional output path.
Generated tables (CSV/Markdown/LaTeX), plots (SVG/PDF/PNG), dataset summaries,
separate ablation tables with intervention provenance, and seeded selected trace
excerpts. Inputs, full case inventory and outputs carry hashes. See
[ADR 0017](../decisions/0017-generated-paper-artifacts.md).

The committed `docs/paper/generated` contains all 110 real pilot method-cases and
eight scripted ablation method-cases in separate groups. No scores are pooled.
The three real reports reproduce Phase 20 metrics, resources and comparisons
exactly. Missing ConfRAG answer labels remain NA; fixture ablations establish no
model-quality result. Excerpts retain errors and abstention outcomes.

## Tests and acceptance

All five artifact categories exist. Four new tests cover score conservation,
all-case inventory, outcome selection, exact repeated exports, file hashes,
overwrite refusal, trace mismatch rejection before publication, intervention
provenance and missing-value/LaTeX handling. Ruff lint/format, mypy (**65 files**),
all-extra pytest (**291 tests**) and build pass. CI tests and generates the fixture
package. Figures were visually inspected; missing-score axis margins were fixed.

```sh
uv run --locked --extra paper epistemic-search paper-artifacts configs/paper_fixture.yaml
uv run --locked --extra paper epistemic-search paper-artifacts configs/paper_pilot.yaml
```

## Limitations and next dependency

Small exploratory samples, unstable/degenerate intervals, no independent model
replicates, no real ablation study and no calibration/unsafe-answer ground truth.
Selected traces are outcome-stratified illustrations, not representative rates.
Figure bytes are reproducible within the locked environment; fonts/platforms can
change rendering. Scientific conclusions remain negative or unresolved.
No paid calls or scaling: additional API spend **$0**, cumulative **$0.067952575**.

After push and successful CI: **Phase 24 — Reproduction package**.
