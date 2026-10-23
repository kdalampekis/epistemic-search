# Phase 7 — Structured sufficiency reasoner

## Implementation and decisions

Added recursive AND/OR/NOT/CONCLUSION evaluation, derivation trace, blocker
extraction and exact inclusion-minimal repair frontiers with a deterministic
smallest frontier. Missing beliefs remain UNKNOWN; NOT preserves UNKNOWN/MIXED.
The result explicitly limits its scope to derivability from the extracted model.
[ADR 0003](../decisions/0003-sufficiency-semantics.md) defines the truth-state rules.

Repair obligations retain desired stances and combine complete consistent
assignments before comparing with current beliefs. This handles shared premises,
negation and dependencies where changing one claim could break another branch.
Structurally unsatisfiable positive conclusions are distinguished from missing
evidence. Enumeration limits fail explicitly; partial frontiers are never reported
as exact. Already-supported conclusions avoid unnecessary frontier enumeration.

## Tests and acceptance

All Phase 7 deliverables are implemented. Tests cover state propagation, negation,
missing beliefs, exact blockers, OR alternatives, irrelevant conflicts, globally
minimal shared-premise frontiers, limit failures, `A AND NOT A` in every belief
state, and checking that suggested repairs actually establish the root across
all 16 two-claim belief combinations. Full suite: 120 tests. Locked install,
lint/format, strict typing, pytest and package build are required checks.

## Limitations and next dependencies

The semantics are conservative engineered rules, not calibrated beliefs or proof
of real-world facts. The exact frontier can grow exponentially; limits raise
errors. Repairability does not mean a search can find the desired evidence.
No epistemic controller exists yet. Next: **Phase 8 — Premise-directed controller**.
