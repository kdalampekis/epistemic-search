# RV2-E: pivot validation of the simpler architecture (pre-registered)

Date: 2026-10-30. Committed **before any RV2-E model call**. Follows the RV2 decision
([RV2_DECISION.md](RV2_DECISION.md): `NOT_PROMISING_IN_CURRENT_FORM`). This is the one last,
narrow test of the surviving idea suggested by that result; if it loses, the project stops.

## Why this test

RV2-C showed that premise-only, given the gold premises, separated complete from incomplete
evidence far better than the formal per-document design (J 0.89 against 0.59) at a tenth of the
cost. RV2-E asks whether that holds on **examples never used before**, and whether making the
unresolved-premise state explicit adds anything to premise-only.

Not included, deliberately: per-document stance, an evidence ledger, belief mass, formal
closure, and the "supporting document must be new to the premise" patch (it treats a symptom of
the per-document design rather than replacing it).

## Systems (same model, effort, seed, ceilings for all)

| ID | System | What it does |
| --- | --- | --- |
| B0 | `naive_rag` | One search with the question, one cited answer or abstention. |
| B1 | `iterative_rag` | Model-written follow-up queries, up to 3 searches. |
| M1 | `premise_only` | The RV2-C comparator, unchanged: the model sees the premises and all retrieved evidence and itself picks ANSWER / SEARCH_MORE / ABSTAIN. |
| M2 | `premise_state` (new, `src/epistemic_search/premise_state.py`) | One structured call per round returns, for **every** premise, `RESOLVED`, `UNRESOLVED` or `CONFLICTING`, judged from the **whole** evidence set, citing the source ids relied on. A fixed controller: all resolved → answer from the cited evidence; else SEARCH for the first unresolved premise (the **premise text alone is the query**), or RESOLVE_CONFLICT; stop with `NO_PROGRESS` on a repeated query / no new documents and no state change; else abstain at the round limit. |

M1 and M2 receive the **gold premises** (EntailmentBank leaf facts as the oracle graph), as in
RV2-C. This isolates sufficiency judgment and control. It does **not** test the generated
front end, which RV2-B showed to be unreliable (28% invalid graphs; valid ones state derived
claims). A positive result here is therefore conditional on obtaining good premises.

The prompts (`premise-state-v1`, `premise-state-answer-v1`) are frozen in the committed code
and will not be edited after any result is seen. The estimate probe uses a fresh example and
is kept as data.

## Data

EntailmentBank dev (task 2), convertible proofs with 3 to 5 leaves and at least 4 distractors,
**excluding every example used in RV2-B/C** (27). Fresh candidates by leaf count: 42, 26, 8.
Seeded (20261029, namespace `eb-pivot-<size>`), round-robin over sizes. Size by the committed
rule: the largest per-size in (12, 8, 4) whose planning cost, from a one-example probe, is at
most 80% of the cap, giving 32 (12/12/8), 24 (8/8/8) or 12 examples.

* **E-A (primary, sufficiency).** The RV2-C conditions: C1 all leaves, C2 one leaf removed
  (seeded), C3 C2 plus the 4 highest-relevance distractors, C4 C1 plus them. Every system
  receives the whole pool; nothing outside it can be retrieved.
* **E-B (secondary, search).** The dataset's full 25-sentence context, retrieved with the
  standard lexical retriever, k = 2, at most 3 searches and 6 documents (the RV2-D ceilings).
  R1 = every leaf present among all distractors; R2 = R1 without the removed leaf. Systems
  must find what they need.

## Metrics

E-A as in RV2-C: coverage on complete (C1∪C4), unsupported-answer rate (C2∪C3), **J** = the
first minus the second, model calls, tokens, logical cost. E-B: answer rate in R1/R2, J,
**required-leaf recall in R1** (share of gold leaves retrieved), searches, cost. Uncertainty:
seeded paired bootstrap over examples, 10,000 resamples. Answer text is not used in any
verdict.

## Decision rule (fixed now)

Let J(·) and coverage be from E-A over examples complete for all four systems.

* **R0 validity.** At least 24 complete examples. Otherwise `INCONCLUSIVE`.
* **R1 premise-only replicates.** J(M1) ≥ 0.75 and coverage(M1) ≥ 0.90 and
  J(M1) − max(J(B0), J(B1)) ≥ 0.50.
* **R2 premise-state is viable.** The same three conditions for M2.
* **R3 premise-state adds value over premise-only** if either
  (i) J(M2) − J(M1) ≥ 0.05 with the bootstrap interval's lower bound above 0, or
  (ii) E-B required-leaf recall in R1, M2 − M1 ≥ 0.10 with lower bound above 0, **and**
  logical cost(M2) ≤ 1.5 × cost(M1).

| Outcome | When |
| --- | --- |
| `PIVOT_VALIDATED` | R0, R1, R2 and R3 |
| `PREMISE_ONLY_SUFFICES` | R0 and R1 hold but M2 is not viable or adds nothing: keep premise-only as a small component, drop the rest |
| `STOP` | R1 fails: the RV2-C result did not replicate; stop the project |
| `INCONCLUSIVE` | R0 fails |

"If it loses we stop" means: `STOP`, or `PREMISE_ONLY_SUFFICES` (no architecture beyond
premise-only is supported). Only `PIVOT_VALIDATED` supports continuing with M2.

## What this cannot show

* **Oracle premises are verbatim leaf sentences**, so in E-B a query made from a premise's text
  retrieves that leaf almost by construction. E-B is an upper bound for premise-targeted
  search with perfect premises, not evidence about real questions (RV2-D found the opposite
  for generated premises with a different query rule).
* **The C2/C3 ground truth is imperfect** (EntailmentBank leaves overlap in meaning; see
  RV2-C). It favours strict systems for every system alike.
* One dataset, grade-school science; 24–32 examples; free-text answers (not scored).
* It says nothing about the generated front end, and nothing about the pilot's
  mismatched-evidence grounding failures.

## Budget and the ledger halt

Hard cap **$0.50** under run id `rv2-e-pivot-v1`, enforced by the persistent ledger; estimate
first, then run; expected spend is well under the cap. The project-wide ledger is currently
**halted** by the RV2-D uncertain-charge failure. Running RV2-E requires an explicit human
decision to clear that halt; I have not cleared it. RV2-D is not resumed (46 of 144 questions;
its verdict is already far outside the bar).
