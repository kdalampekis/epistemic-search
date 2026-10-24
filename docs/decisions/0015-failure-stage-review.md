# ADR 0015 — Failure symptoms, stages and reviewed causes

Date: 2026-10-24. Status: accepted.

The offline failure inspector consumes existing labels, scores and traces. It
renders every executed case as Markdown and standalone HTML, with question,
evaluator-only gold/answerability, final output, resource use, evidence state and
a collapsible full event timeline. Raw text is escaped in HTML, Markdown fences
expand around embedded backticks, paths stay inside their run directory, and
reports need no network, scripts or provider credentials.

Use the ten categories in `ARCHITECTURE.md` without inventing automatic semantic
ground truth. Direct error events identify an observed failing stage. A wrong
final answer gets a provisional `ANSWER_GENERATION_ERROR` output-symptom label;
its upstream cause or benchmark ambiguity remains unresolved. These are explicitly
different classification bases and all automatic primary labels need review.
Each execution error or reference mismatch receives one primary hypothesis.

Abstention, budget stop and ungraded output are separate outcomes, not automatic
failures. Matching a reference likewise does not validate the reasoning chain.
The classifier does not diagnose stance, belief, calibration or semantic
formalization errors without independent annotation. A frontier-limit failure is
an observed formal-stage failure, not proof that the underlying semantics are bad.

Manual judgments can set any taxonomy primary and optional distinct secondary
categories. They must name the run and case, bind to the exact trace SHA-256,
and record assessor, protocol and rationale. Missing/stale/duplicate annotations
are rejected before report creation. Reviewed labels replace provisional labels
without changing saved model outputs or answer grading. A manual annotation may
also flag a reference-matching case when independent inspection finds a problem.

Aggregate counts distinguish outcomes, provisional categories and manual labels;
source hashes and planned/executed inventories preserve partial runs. Outputs
cannot overwrite earlier reports. This workflow supports human review but does
not pretend that automated stage localization is a causal failure analysis.
