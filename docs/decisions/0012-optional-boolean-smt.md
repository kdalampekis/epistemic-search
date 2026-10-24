# ADR 0012 — Optional Boolean SMT comparison

Date: 2026-10-24. Status: accepted.

The optional `formal` extra supplies Z3. The first supported fragment is an
explicitly authored, validated AND/OR/NOT proof graph with atomic belief states.
There is no automatic prose-to-SMT conversion, numeric theory, quantification,
temporal reasoning or claim that the input captures the real world. Claim IDs
are independent atoms; wording and the claim polarity field do not add hidden
constraints. Inputs carry formalization provenance and question-group IDs.

SUPPORTED asserts an atom, CONTRADICTED asserts its negation, UNKNOWN adds no
constraint, and MIXED asserts both. Check assumption consistency first. An
inconsistent theory returns `inconsistent`, never a sufficient answer. Otherwise
test assumptions with the negated conclusion, then with the conclusion: unsat
establishes entailment/refutation respectively; two satisfiable queries leave the
answer undetermined. Solver `unknown` is separate from epistemic uncertainty and
never counts as sufficient. Each check has a configured timeout; record the Z3
version, exact SMT queries, results and timing. The API follows the solver's
[official programming guide](https://z3prover.github.io/papers/programmingz3.html).

This classical semantics deliberately differs from conservative graph propagation.
For example, excluded middle is classically entailed with an unknown atom, while
the proof graph remains UNKNOWN. Any MIXED assumption makes the classical theory
inconsistent, even when graph propagation can answer through an independent OR
branch. Reports retain these differences, not silently equate the methods or
grade them against one mislabeled oracle. Graph labels and classical labels are
separate; the generative judge receives the same classical task as Z3.

The standalone comparison uses the existing provider boundary, schema validation,
budget guard, exact paid-output cache and cumulative spending ledger. The
generative prompt receives only graph and beliefs, never expected labels,
provenance or the other methods' results. It makes one bounded call per case,
retains errors, and stores incremental results and full accounting. Deterministic
methods have zero model/search usage, with CPU latency separately recorded.

The comparison does not replace the full controller's conservative sufficiency
policy. Scripted fixture success verifies implementation, not model capability
or superiority of formal inference. A real comparison needs separately reviewed
structured data, matched model/effort, a cost estimate and the existing $50
project cap; it is not automatically scheduled by this implementation phase.
