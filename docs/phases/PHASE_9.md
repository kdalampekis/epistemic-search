# Phase 9 — Targeted query generator

## Implementation and decisions

Added validated query context and deterministic templates that prioritize the
target premise while retaining original question, entities, temporal constraints,
current target evidence, conflict state and required stance. Generated queries
are always returned with an AgentEvent containing version, full query and inputs,
and explicit zero external-call cost. Conflict queries request independent evidence
for and against rather than assuming that the desired stance is true.

Templates preserve negation/dates and normalize only whitespace/duplicate complete
parts. Dates are never invented. No LLM call or external search is performed here.
Current evidence informs independent-verification/conflict mode and is referenced
by ID in the trace; entire source passages are not stuffed into search text.

## Tests and acceptance

All Phase 9 inputs and query logging are implemented. Tests cover deterministic
output, retained entities/dates/negation, required stance, target-only evidence,
conflict wording, zero usage and missing temporal scope. Full suite: 136 tests.
Required checks: locked install, lint/format, strict mypy, pytest and build.

## Limitations and next dependency

These are interpretable baseline templates, not optimized queries or a demonstrated
retrieval improvement. Entity/time extraction is caller-supplied. No provider-specific
query rewriting or value-of-information selection. Next: **Phase 10 — Full Epistemic
Search MVP**, integrating the components with shared budgets and fixture scenarios.
