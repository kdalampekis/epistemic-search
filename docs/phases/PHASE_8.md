# Phase 8 — Premise-directed controller

## Implementation and decisions

The deterministic controller consumes the validated proof graph, beliefs and
budget, and returns a Decision plus the reasoner's trace. Supported roots yield
ANSWER. Structurally impossible roots abstain. Otherwise the selected minimal
frontier supplies acquisition targets; conflicting/opposing evidence is resolved
first, then unknown claims, ordered by importance and stable ID. Already-satisfied
obligations and irrelevant OR-branch conflicts do not trigger retrieval.

Acquisition checks account for already-used and reserved search/document/token/
model/latency/cost resources. Unknown monetary usage/reservations fail closed when
a monetary limit is configured. Every abstention includes blocking claim IDs.
No API calls or evidence updates occur inside this pure policy.

## Tests and acceptance

Tests cover resolved-claim exclusion, mixed/opposite-state conflict priority,
all zero resource limits, used-plus-reserved allowance, unknown/zero monetary
costs, supported conclusions with no acquisition budget, and irrelevant OR
conflicts. All Phase 8 criteria are covered. Full suite: 133 tests. Required
checks: locked install, lint/format, strict mypy, pytest and build.

## Limitations and next dependency

Reservations must be supplied conservatively by execution; remote realized costs
may differ. ANSWER is a logical authorization; any model call to render it still
needs its own execution budget (Phase 10). No value-of-information optimization
yet. Next: **Phase 9 — Targeted query generator**.
