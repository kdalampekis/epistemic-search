# Phase 12 — Baseline parity

Status: **complete**, committed/pushed as `196de1f`; hosted CI `40040967731` passed.
Phase 11 commit `d8baae2` and the offline checkpoint `1e44d3b` passed hosted CI.

## Implementation

Closed-book, naive top-k, iterative relevance, premise-directed without
belief/formal reasoning, and full Epistemic Search run through the same provider
guards. A single configuration fixes the model, reasoning, retriever, seed,
example subset, ceilings and scorer. All structured model outputs are validated;
all failures remain in the evaluation denominator. Closed-book has an uncited
output schema and never searches. Premise-only shares decomposition and targeted
query generation but uses a generative sufficiency judge.

The user's revised strategy makes **Luna/medium primary and $50 the total project
allowance**, replacing the earlier Sol-primary/per-phase plan. Added:

- `spending.py`: persistent SQLite per-run/project reservations, protected $5
  final-validation reserve, retained crash/unknown charges, and settled usage.
- `campaign.py`: small explicit smoke/pilot stages, cost estimates, hash-bound
  smoke audit, exact completed-artifact reuse and no automatic full benchmark.
- Provider exact input-token preflight, configured reasoning, standard tier,
  cached/write/reasoning token accounting, API-call counts and output reuse.
- Logical token/call charging on reuse, with actual API spend and cache hits
  separately visible. Local retrieval caches identical queries per corpus.
- Read-only local `.env` support; no credentials are serialized. A duplicate key
  in the tracked `.env.example` was removed; `.env` remained unchanged and ignored.
- Partial evaluation summaries record planned versus executed cases and a stop
  reason when the project/run cap prevents another call.

[ADR 0005](../decisions/0005-baseline-parity.md) defines the method boundary;
[ADR 0006](../decisions/0006-project-budget-and-output-reuse.md) updates paid cache
and budget semantics. No prompts, answer graders or evidence-validation rules
were tuned during this pilot.

## Validation

- Offline five-method fixture: all methods execute, with logical model counts
  1/1/1/2/4 and search counts 0/1/1/1/1. No quality claims from scripted output.
- Native benchmark adapters were validated in Phase 11; actual downloads and
  checksums remain under ignored `artifacts/benchmarks`.
- Tests include guard parity, label isolation, schema/provenance validation,
  restart/concurrency/unknown-charge behavior, cap exhaustion, physical versus
  logical cache use, cache-key replicate separation, local key loading,
  smoke-audit tampering and partial-output preservation.
- `uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
  `pytest -q`, `uv build`, and validation of all 18 YAML configs were run.
  Current suite: 185 tests passed; mypy: 44 files.

## Real-model observations

The smoke ran one seeded example from each benchmark through all five methods.
All 42 physical generations settled below their reservations: **$0.016803625**.
HotpotQA and 2Wiki had no execution errors. ConfRAG full-system extraction
returned a non-verbatim span, which was rejected; this negative case remains.
There were no provider errors or incomplete usage records in the smoke.
[The audit](../experiments/phase12_smoke_audit.json) records why this supports a
small diagnostic pilot despite that model failure, not a larger benchmark.

The pilot uses 10 HotpotQA, 10 2Wiki and 2 ConfRAG cases, five methods each.
The estimate was reported before execution: planning scenario $0.259875;
conservative token-ceiling bound $3.17724, with per-run caps $2/$2/$0.50.
See [research budget strategy](../experiments/research_budget.md).

All 110 pilot method-cases completed, with five retained model/extraction errors
and seven budget stops. Total smoke + pilot cost: **$0.067952575**, from 278
physical generations / 556 HTTP calls and 177 local model-cache hits. Full audit
reconciled costs, confirmed limits/model parity and replayed completed artifacts
with HTTP disabled and zero new generations. See the
[negative pilot report](../experiments/phase12_pilot.md) and
[compact audited results](../results/phase12_luna_pilot.json).

The full method did not improve EM on either ten-case QA subset. No larger
benchmark or Sol validation is justified now; no positive hypothesis claim is made.

## Limitations and next dependency

Matched ceilings do not imply identical realized work. The retriever is lexical
overlap over per-question supplied context, not a web-scale search engine.
Cached outputs couple runs; cache-hit latency cannot establish uncached speed.
The small development subset cannot establish significance or novelty, and
ConfRAG has no single-answer EM/F1. Formal sufficiency means derivability from
extracted claims, not proof of real-world truth. Provider alias sampling remains
stochastic; original outputs and source hashes must be retained.

The matched real-model execution acceptance criterion is met, including failure
retention and reproducible configs. The commit/push and CI gate passed; proceed to
**Phase 13 — Abstention metrics**, using
saved results and offline tests without new model calls.
