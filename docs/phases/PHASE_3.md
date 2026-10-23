# Phase 3 — Iterative relevance baseline

## Implementation and decisions

Added `method: iterative_rag`, validated `SEARCH_MORE` / `ANSWER` / `ABSTAIN`
model outputs, model-directed query rewriting, retained evidence context, and
finite `max_rounds`. Both baselines use the same execution code, providers,
answer/citation contract, usage ledger and evaluation protocol. Naive remains
one retrieval/model pass. Iterative decisions use a separate versioned prompt;
the generic grader is unchanged. No premise graph or proof policy exists.

Budgets now check cumulative usage across calls, reduce requested k to the
remaining document budget, reduce output allowances to remaining tokens, and
stop on round/call/document/token/cost/time limits. An async timeout bounds a
stalled call. Unknown usage from a canceled attempt remains explicit. Duplicate
retrieval is charged each time while identical source IDs share one context entry;
changing content under a source ID is rejected instead of silently merged.

## Tests and acceptance criteria

The loop is bounded and fully instrumented. Tests cover model-selected follow-up
queries; successful two-round answers; explicit abstention; round/search/model/
document limits; cumulative output allowance; invalid action combinations; timeout
cancellation; retained attempt costs; CLI integration; and unchanged naive tests.
Full suite: 73 passing tests. Locked install, lint, formatting, strict mypy,
pytest, iterative CLI, evaluation CLI, and distribution build are checked.

## Limitations

Token preflight still uses whitespace estimates. Actual provider overruns are
retained and marked budget-exhausted; remote monetary ceilings fail closed.
Timeout cancellation cannot guarantee the remote service stops billing.
Accumulating relevant evidence is not sufficiency reasoning. The fixture script
is not an agent-quality experiment, and no real-model comparative result exists.
The shared scorer remains `english-em-token-f1-v1`.

## Next dependency

Phase 4 — Premise decomposition: schema-constrained decomposition, versioned
prompts, cache, gold fixtures, graph validator, stable IDs and inspection CLI.
