# Research validation plan

Status: adopted 2026-10-24. Implementation phases 0–25 are complete and **no
Phase 26 will be created**. The repository is now an experimental instrument; the
open question is whether the architecture buys anything, which component buys
what, under which conditions, and at what cost.

The Phase 12 Luna pilot (110 method-cases, $0.067952575) did **not** support a
superiority claim for full Epistemic Search. That negative result stays on record
([pilot](docs/experiments/phase12_pilot.md)). Real calibration, causal ablations,
independent semantic review and stronger-model transfer remain unvalidated.

Work is organised as numbered **experiments (RV0–RV10)**, not implementation
phases. An experiment may change code only where its own section permits it.

## Rules that apply to every experiment

1. Diagnose before modifying. No prompt, threshold, controller or retrieval change
   is made on the strength of RV0 alone.
2. **Implementation defect vs. failed hypothesis.** A behaviour that violates the
   system's own specification (for example a text-normalisation mismatch that
   rejects a correct span) is a defect and may be fixed in RV2. A system that
   works as specified but adds cost without improving answers is a negative
   scientific result: record it, do not tune until it wins.
3. **Dev/test discipline.** The 22 pilot questions are spent as development
   evidence. Fixes may be inspected against them, but every claim-bearing run
   (RV3 onward) draws new, seeded questions disjoint from the pilot and from any
   set used for tuning. After RV2 the method is frozen as `epistemic-search-v1`;
   prompts and thresholds do not change after a test set is observed.
4. **Matched protocol.** Same questions, model, reasoning effort, retriever,
   retrieval budget, grader and call ceilings for every method, with disclosure of
   any unavoidable asymmetry. Closed-book scored highest in the pilot, so RV3/RV4
   should include it as a low-cost control rather than omit it.
5. Report Pareto trade-offs (quality against tokens/searches/cost), not a single
   accuracy number. Unknown never means false; heuristic scores are not
   probabilities; negative results go into experiment notes.
6. Spend is staged: estimate, run, inspect, then decide whether the next spend is
   justified. Anything expected above $1 follows the estimate-first rule in
   [research_budget.md](docs/experiments/research_budget.md).

## Experiments

| ID | Experiment | Cost | Decision gate |
| --- | --- | ---: | --- |
| RV0 | Pilot failure audit: mechanical facts from the 110 saved cases | $0 | **Done**; see [RV0 report](docs/experiments/RV0_PILOT_AUDIT.md) |
| RV1 | Manual semantic annotation of decomposition, evidence stance and failure attribution | $0 | Needs a human assessor; yields the first real failure distribution |
| RV2 | Fix confirmed implementation defects only; freeze `epistemic-search-v1` | small | Only defects shown by RV1/RV0 evidence; no hypothesis-tuning |
| RV3 | Small controlled validation: ~50 new questions (HotpotQA, 2Wiki, contradiction/insufficient) × matched methods | ≈ $2 | **Stop** if no interesting signal; do not scale |
| RV4 | Main Luna experiment at larger N, quality-vs-cost Pareto figure | ≈ $5 | Only if RV3 is promising |
| RV5 | Real-model causal ablations using the Phase 19 runner | ≈ $5 | Identifies which component earns its cost |
| RV6 | Contradiction experiment (A and ¬A): detection F1, answer accuracy, unsafe-answer rate | shared ≈ $3 | Compare against both-in-context baseline |
| RV7 | Missing-premise experiment (A∧B∧C with C removed, plus distractors) | shared with RV6 | Does it name C as missing, search for it, abstain when absent? |
| RV8 | Statistics: paired bootstrap, CIs, McNemar where valid, risk–coverage | $0 | Phase 20 machinery on RV3–RV7 data |
| RV9 | Stronger-model transfer on ~20–30 representative questions, iterative vs. Epistemic | ≈ $5 (the existing Sol reserve) | Does any effect survive a stronger model? |
| RV10 | Paper decision: claims limited to what RV1–RV9 support | $0 | May conclude the idea is partly or wholly unsupported |

The dollar figures are planning allocations inside the existing **$50 cumulative
cap** (about $30 left unallocated as reserve); they are not commitments and each
is subject to its gate.

## RV0 and RV1 in one paragraph

RV0 records only what can be read off saved traces and benchmark annotations; it
labels nothing as a semantic error. RV1 is where a human decides whether the
decomposition was right, whether each stance was right and which stage failed,
using the template RV0 generated. RV2 does not start until RV1 is complete.
