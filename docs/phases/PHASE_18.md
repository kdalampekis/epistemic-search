# Phase 18 — Optional formal backend

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 17 commit `53e0056` passed CI `40083318221` before work began.

## Implementation and design

Added optional `z3-solver` dependency, a validated Boolean graph translator and
classical entailment checks. Consistency is checked before entailment so conflicting
assumptions cannot prove arbitrary conclusions. Unknown evidence stays unconstrained.
The solver records version, replayable queries, verdicts, timeouts and CPU latency.

The new `compare-formal` command compares a schema-validated generative judge,
the existing proof graph and Z3 on identical supplied structures. It records
incremental per-case results, errors, all model usage, project spending when
configured, source/config hashes and separate semantic labels. Gold/provenance
remain outside the judge prompt. See [ADR 0012](../decisions/0012-optional-boolean-smt.md).

## Tests and acceptance

All three requested methods are implemented and compared on an explicitly
structured subset. No open-domain text is translated into SMT. Tests include
truth-table enumeration, unknown versus false, consistency before entailment,
SMT-query replay, malformed graphs/beliefs, absent optional dependency, solver
unknown, schema-invalid model outputs, label isolation and zero-call budgets.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`uv run --locked --extra formal --extra benchmarks pytest -q`, and `uv build`
pass: **254 tests**, **54 typed files**. CI tests the optional extra separately.

```sh
uv run --locked --extra formal epistemic-search compare-formal configs/formal_fixture.yaml
```

Eight hand-authored fixtures complete with zero errors, eight scripted model
calls, zero searches, zero API calls and $0. All methods match their separately
declared fixture oracles. Two cases differ in sufficient/not-sufficient between
graph and SMT: excluded middle and an irrelevant conflicting OR branch.
The impossible conjunction also differs in status (graph UNKNOWN, SMT refuted).
These are documented semantic differences, not experimental wins or hidden failures.

## Limitations and next dependency

Only the Boolean fragment is supported. Belief extraction/thresholding is held
fixed; no calibrated probabilities, world-truth guarantees, measured real-model
advantage or full-controller SMT replacement is claimed. Solver timeouts apply
per check (at most three); saved wall time includes overhead. The scripted judge
is a test double, and empirical generative-versus-formal quality remains untested.

Additional research API spend: **$0**; cumulative remains **$0.067952575**.
After push and successful CI: **Phase 19 — Ablation runner**.
