# Implementation status

Updated: 2026-10-24 (RV0 complete, RV1 infrastructure added).

| Phase | Status | Evidence |
| --- | --- | --- |
| 0 — Research repository foundation | Complete | [Implementation and checks](PHASE_0.md) |
| 1 — Naive RAG baseline | Complete | [Implementation and checks](PHASE_1.md) |
| 2 — Evaluation harness v1 | Complete | [Implementation and checks](PHASE_2.md) |
| 3 — Iterative relevance baseline | Complete | [Implementation and checks](PHASE_3.md) |
| 4 — Premise decomposition | Complete | [Implementation and checks](PHASE_4.md) |
| 5 — Evidence ledger | Complete | [Implementation and checks](PHASE_5.md) |
| 6 — Belief state v1 | Complete | [Implementation and checks](PHASE_6.md) |
| 7 — Structured sufficiency reasoner | Complete | [Implementation and checks](PHASE_7.md) |
| 8 — Premise-directed controller | Complete | [Implementation and checks](PHASE_8.md) |
| 9 — Targeted query generator | Complete | [Implementation and checks](PHASE_9.md) |
| 10 — Full Epistemic Search MVP | Complete | [Implementation and checks](PHASE_10.md) |
| 11 — Benchmark integrations | Complete | [Implementation and checks](PHASE_11.md) |
| 12 — Baseline parity | Complete | [Implementation and audited pilot](PHASE_12.md) |
| 13 — Abstention metrics | Complete | [Implementation and checks](PHASE_13.md) |
| 14 — Contradiction experiments | Complete | [Implementation and checks](PHASE_14.md) |
| 15 — Calibration | Complete (offline validation) | [Implementation and limits](PHASE_15.md) |
| 16 — Cost-aware controller | Complete | [Implementation and checks](PHASE_16.md) |
| 17 — Controlled benchmark transformations | Complete | [Implementation and checks](PHASE_17.md) |
| 18 — Optional formal backend | Complete | [Implementation and checks](PHASE_18.md) |
| 19 — Ablation runner | Complete | [Implementation and checks](PHASE_19.md) |
| 20 — Statistical analysis | Complete | [Implementation and checks](PHASE_20.md) |
| 21 — Failure analysis | Complete | [Implementation and checks](PHASE_21.md) |
| 22 — Demo dashboard | Complete | [Implementation and checks](PHASE_22.md) |
| 23 — Paper artifact generation | Complete | [Implementation and checks](PHASE_23.md) |
| 24 — Reproduction package | Complete | [Implementation and checks](PHASE_24.md) |
| 25 — Final technical report / paper | Complete | [Implementation and checks](PHASE_25.md) |

Phases 0 (`a6bd037`), 1 (`e8c030d`), and 2 (`93565cc`) were pushed; hosted CI passed.
Phase 3 (`03724e0`) was pushed with successful hosted CI. Naive/iterative baselines,
the common evaluation harness, structural premise decomposition and evidence ledger exist.
Phase 4 (`ee1a0a0`) was pushed with successful hosted CI.
Phase 5 (`018567e`) was pushed with successful hosted CI. Conservative belief
aggregation, a structured reasoner and a premise-directed policy exist.
Phase 7 (`c5f852a`) was pushed with successful hosted CI.
Phase 8 (`ed54560`) was pushed with successful hosted CI. Targeted query templates exist.
Phase 9 (`e322e4c`) was pushed with successful hosted CI. The MVP is integrated.
Phase 6 (`a815df2`) was pushed with successful hosted CI.
No real-model benchmark quality or novelty claims have been established.
Phase 10 (`b099c7c`) was pushed with successful hosted CI. Native benchmarks are integrated.
ConfRAG and benchmark sources were verified in Phase 11; the remaining literature
map still requires independent verification before novelty claims.

Phase 11 (`d8baae2`) was pushed with successful hosted CI. Phase 12 has five
implemented methods and a matched comparison runner. The revised strategy uses
Luna/medium with a $50 cumulative project cap and a $5 final Sol reserve. Local
credentials work; all 110 real pilot method-cases ran. The negative result and
$0.067952575 cumulative cost are audited. No full benchmark or Sol run follows.
Phase 12 (`196de1f`) was pushed with successful hosted CI (`40040967731`).
Phase 13 adds offline selective metrics and reanalyzes saved results at zero API
cost. Missing ranking/answerability data remain explicitly unknown; no full
benchmark or fresh model calls are needed for this phase.

Phase 13 (`dfa9dba`) was pushed with successful hosted CI (`40063077390`).
Phase 14 evaluates the saved ConfRAG pilot without API calls, records a detection
miss and source-cluster coverage, and separates independent safety judgments
from internal conflict states. No quality claim or benchmark scaling follows.

Phase 14 (`eb9f73f`) was pushed with successful hosted CI (`40063561539`).
Phase 15 implements paired calibration measurement and fitting, validated only
on explicit fixtures. Missing aligned real scores/labels preclude empirical
calibration claims; the controller still uses uncalibrated heuristic beliefs.

Phase 15 (`e6eec78`) was pushed with successful hosted CI (`40064049865`).
Phase 16 adds four logged acquisition policies under shared constraints; the
original default and historical config hashes remain intact. Validation is offline.

Phase 16 (`0fc1b65`) was pushed with successful hosted CI (`40064451187`).
Phase 17 adds deterministic, grouped context interventions, preserved grading and
explicit provenance. All validation is offline; semantic claims still need review.

Phase 17 (`53e0056`) was pushed with successful hosted CI (`40083318221`).
Phase 18 adds optional Boolean SMT and an instrumented generative/graph/SMT
comparison. Classical and graph semantics remain explicit; validation is offline.

Phase 18 (`581cf0b`) was pushed with successful hosted CI (`40083718154`).
Phase 19 implements seven bounded ablation paths and matched result tables,
including explicit dependent-component removal. Only offline fixtures were run.

Phase 19 (`3f9ee96`) was pushed with successful hosted CI (`40084386967`).
Phase 20 reanalyzes the saved pilot with paired tests, clustered bootstrap and
cost summaries. Negative results and missing ConfRAG answer metrics are retained.

Phase 20 (`ea9b15b`) was pushed with successful hosted CI (`40115519622`).
Phase 21 renders all 110 saved pilot traces and records provisional failure-stage
categories, with manual trace-bound annotation support and no new API calls.

Phase 21 (`fe5b3b4`) was pushed with successful hosted CI (`40116134085`).
Phase 22 adds a standalone local dashboard with event-by-event graph, evidence,
state, decision and resource playback. All validation is offline.

Phase 22 (`f074144`) was pushed with successful hosted CI (`40117208034`).
Phase 23 generates paper tables, figures, dataset inventories and outcome-stratified
trace excerpts from validated saved runs, keeping scripted ablations separate.

Phase 23 (`3a82b3a`) was pushed with successful hosted CI (`40128622872`).
Phase 24 adds a credential-free, checksummed local reproduction archive and
clean-checkout fixture/saved-result reproduction commands.

Phase 24 (`949dad1`) was pushed with successful hosted CI (`40128999926`).
The clean local reproduction archive was built and verified. Phase 25 delivers a
six-page report, result-bound rendering and a narrowed literature/claim audit.
No further implementation phase is specified; scientific validation remains open.

Phase 25 (`052a498`) was pushed with successful hosted CI (`40129599742`),
including the independent offline reproduction job. **All specified implementation
phases 0–25 are complete.** This is not a claim that the research hypotheses were
confirmed: real calibration, causal ablations, independent semantic review and
stronger-model transfer remain unvalidated. No Phase 26 or benchmark scaling is
authorized by the roadmap itself. See the technical report for the next research
decision and the unchanged $50 cumulative API boundary.

## Scientific validation (post-roadmap)

Implementation is finished; no Phase 26 exists. Remaining work is organised as
research-validation experiments in [RESEARCH_VALIDATION_PLAN.md](../../RESEARCH_VALIDATION_PLAN.md).

| Experiment | Status | Evidence |
| --- | --- | --- |
| RV0 — Pilot failure audit | Complete (offline, $0; mechanical facts only) | [RV0 report](../experiments/RV0_PILOT_AUDIT.md), [results](../results/rv0/) |
| RV1 — Semantic annotation (primary assessor: GPT-5.6 Sol; **model-assisted, not independent human ground truth**) | Complete and validated: 22 of 22 questions; aggregated | [Summary](../experiments/RV1_SUMMARY.md), [protocol](../experiments/RV1_ANNOTATION_PROTOCOL.md), `annotations/rv1/primary/`, [results](../results/rv1/) |
| RV2 — External-gold validation | **Complete (RV2-D partial: 46/144 questions, ledger halt).** Decision: **`NOT_PROMISING_IN_CURRENT_FORM`** (Q2 = NO: with gold structure and evidence Epistemic Search detects a missing leaf worse than premise-only, J 0.59 vs 0.89). Spend $0.2344 of $1.50. RV3 not started | [Decision](../experiments/RV2_DECISION.md), [plan](../experiments/RV2_EXTERNAL_VALIDATION_PLAN.md), [audit](../experiments/RV2_DATASET_AUDIT.md), [A](../experiments/RV2_A_STANCE.md), [B](../experiments/RV2_B_ORACLE_STRUCTURE.md), [C](../experiments/RV2_C_EPISTEMIC_STATE.md), [D](../experiments/RV2_D_RETRIEVAL.md) |
| RV3–RV10 | Not started | Gated by RV2 and the plan's decision gates |

RV0 produced no semantic failure distribution: 0 annotations, 0 API calls,
cumulative research spend unchanged at $0.067952575. It records candidate
bottlenecks (premise phrasing, repeated targeted queries ending in budget
abstention, supporting-title recall, single-span aborts) without deciding whether
any is an implementation defect or a failure of the hypothesis. No claim about the
research hypothesis follows.

RV0 was committed as `919e86d` before any RV1 work and is frozen. RV1 provides a
validated annotation schema (`rv1-init`, `rv1-validate`, `rv1-aggregate`,
`rv1-add-assessor`), blank files for all 22 pilot questions, an oracle-decomposition
export that converts to the pipeline's `ProofGraph`, and agreement tooling for a second
assessor.

The primary RV1 annotations (`openai-gpt-5.6-sol-primary`) were produced by GPT-5.6 Sol and are
model-assisted, not independent human ground truth; no repository API call was made. They
validate (one file needed a mechanical YAML quoting repair, no judgment edited) and
aggregate. See the [RV1 summary](../experiments/RV1_SUMMARY.md) for the failure
distribution and its caveats. A human spot-check has not been done. The 22 pilot questions
are development data and cannot serve as a test set. RV2 has not started.

## RV2-E (pivot validation of the simpler architecture): complete

Result under the pre-registered rule: **`PREMISE_ONLY_SUFFICES`**. Premise-only replicated on 27
fresh EntailmentBank examples (J 0.87 vs 0.09-0.11 for naive and iterative RAG). Premise-state
(per-premise status judged from the whole evidence set, fixed controller) missed its viability
bar on coverage (0.889 vs 0.90) and did not beat premise-only on J (delta -0.02, 95% CI
[-0.17, +0.13]); it showed a supported but confounded search-recall advantage in the secondary
setting. New spend $0.0939. See [RV2-E](../experiments/RV2_E_PIVOT.md) and
[plan](../experiments/RV2_E_PIVOT_PLAN.md). The ledger is halted again (cancelled in-flight
request); not cleared.

## RV2-F (generated-premise sufficiency): complete

Result under the pre-registered rule: **`NO_END_TO_END_SIGNAL`; the mandatory stop rule fired.**
30 fresh EntailmentBank examples, all four systems. J: gold-premise premise-only 0.93, generated-premise
premise-only 0.13 (coverage 0.17), naive RAG 0.20, iterative RAG 0.27. Generated premises were
well-formed (30/30 structurally usable) but insufficiently resolvable from the evidence. Spend $0.0327.
The project stops; no RV3. See [RV2-F](../experiments/RV2_F_GENERATED_PREMISES.md) (pre-registration
and results) and the [ledger audit](../results/rv2/rv2_f/ledger_halt_audit.md).

## RV2-G (evidence-grounded decomposition): complete

Result under the pre-registered rule: **`NO_SIGNAL`; the direction is closed.** 30 fresh EntailmentBank
examples, all four systems. J: gold premises 1.00, evidence-grounded M2 0.37 (complete coverage 0.57),
naive RAG 0.40, question-only premises 0.00. M2 beat question-only premises by +0.37 [0.17, 0.57] but not
naive RAG, and fell 0.63 below the gold control; it missed the `PARTIAL_SIGNAL` bar (J >= 0.40) by 0.033.
All 13 complete-evidence abstentions were required evidence facts the decomposer itself had cited no source
for. Spend $0.0699. See [RV2-G](../experiments/RV2_G_EVIDENCE_GROUNDED_DECOMPOSITION.md) and the
[ledger audit](../results/rv2/rv2_g/ledger_halt_audit.md). No RV3.
