# Phase 25 — Final technical report / paper

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 24 commit `949dad1` passed CI `40128999926` before work began.

## Deliverables and decisions

Delivered a six-page [technical report](../paper/REPORT.pdf), with
[Markdown](../paper/REPORT.md), printable HTML and a prose template. It follows
PAPER_PLAN.md: motivation, related work, method, setup, main tables, failure/cost
analysis, ablation scope, limitations, ethics, reproduction and research next steps.
The title reflects the actual negative pilot rather than promised superiority.

`scripts/render_report.py` includes generated tables and JSON scalar values,
checks local references and records source/output hashes. Tests cover automatic
value updates, deterministic rendering, missing-value handling, HTML escaping,
unresolved-token rejection and source confinement. PDF provenance binds HTML,
Chromium version and exported bytes. No empirical values were hand-transcribed.
The reproduction allowlist now includes the new HTML report format.

The primary-source literature audit verifies the cited high-level descriptions,
adds the canonical LINC entry and records additional overlap with ECR, DeepControl
and evidence-obligation PGR. Claims are narrowed to an implementation, reproducible
pilot and negative observations; architectural priority is not established.
README, the paper plan and fellowship positioning distinguish delivered evidence
from original aspirations. The repository remains private and no submission was sent.

## Acceptance and checks

The requested report exists with only bounded, source-linked claims. All result
numbers bind to saved artifacts; fixture ablations are labelled, real calibration
and Sol validation are absent, and the pilot importance policy is distinguished
from later VOI and SMT capabilities. Failed cases and ungraded ConfRAG metrics
remain visible. The literature review is targeted, not an exhaustive priority proof.

Ruff lint/format, mypy (**70 files including both reproduction/report drivers**),
all-extra pytest (**296 tests**), report freshness checking and builds pass. CI
checks the report and independently reproduces offline fixtures. Browser checks
verified all four tables and the image; PDF text/rendering checks found six
nonempty pages, and representative pages were visually inspected.

```sh
uv run --locked --extra paper python scripts/render_report.py
uv run --locked --extra paper python scripts/render_report.py --check
uv run --locked --all-extras pytest -q
```

## Unresolved scientific risks and next step

The software roadmap is delivered; the hypotheses are not confirmed. The sample
is small, exact-span extraction can fail, coverage is low, a conflict was missed,
and independent answerability/safety/calibration labels are unavailable. Real
ablations, stronger-model transfer and full-text closest-system comparisons are
still needed before a novelty or superiority submission.

No additional paid experiment was run: added spend **$0**, total **$0.067952575**
against the **$50 project cap**. The reserved Sol subset was not consumed.

**Exact next phase: none in CODEX_BUILD_SPEC.md (0–25 delivered).** The recommended
next research task is independent semantic annotation and a separately specified,
small development-only diagnostic study, followed by scaling only if informative.
Do not invent Phase 26 or automatically run a larger benchmark.
