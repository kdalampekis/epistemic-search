# Phase 24 — Reproduction package

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 23 commit `3a82b3a` passed CI `40128622872` before work began.

## Implementation and decisions

Added `reproduction.py`, bundle/verify CLI commands, `scripts/reproduce_offline.py`
and [REPRODUCING.md](../../REPRODUCING.md). The archive contains source, YAML
configs/seeds, uv.lock, existing dataset acquisition CLI/lock, prompt construction
code, actual saved requests, model metadata and full run manifests/scores/traces.
Explicitly excluded credentials, environment files, caches, mutable spend ledger
and full benchmark downloads. See [ADR 0018](../decisions/0018-offline-reproduction-package.md).

## Tests and acceptance

All seven required package categories are present. Three new tests cover repeatable
archive bytes, complete metadata/trace inclusion, credential exclusion, overwrite
refusal, symlink refusal and rejection of modified/extra/traversal members.
Lint/format, mypy (**68 files including the reproduction driver**), all-extra pytest
(**294 tests**) and build pass. CI adds an independent fresh-checkout job running
all fixture reproduction steps and archive verification.

A preview archive was verified and extracted into two separate temporary trees.
Each installed the locked dependencies into a new venv. Saved mode reproduced all
118 method-cases (110 pilot plus eight separate scripted ablations) and matched
all numerical tables and statistical comparisons exactly. Fresh fixture mode
completed all twelve commands, including formal/calibration/control/ablation,
dashboard and paper artifacts, without model API calls. A release archive is
built again from the clean committed checkout after hosted CI passes.

## Limitations and next dependency

Dependency installation and fresh dataset downloads need network/cache. A source
clone alone omits raw pilot traces; use the local archive for saved-run replay.
Remote model aliases/seeds do not guarantee future identical generations.
Fixture timestamps/paths and cross-platform figure rendering may differ. Archive
creation is not publication or an independent scientific replication.
Additional API spend **$0**; cumulative remains **$0.067952575**.

After push and successful CI: **Phase 25 — Final technical report / paper**.
