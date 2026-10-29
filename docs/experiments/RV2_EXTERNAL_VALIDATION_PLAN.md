# RV2 external-gold validation plan (pre-registered)

Date: 2026-10-29. Committed **before any RV2 model call**. Supersedes the manual path in
[RV2_PLAN.md](RV2_PLAN.md) (`SUPERSEDED_BEFORE_ANNOTATION`). No manual labeling by the user
is needed anywhere; wherever an official gold label exists it is the label, and no model
judges correctness. Cumulative project spend before RV2: **$0.067952575** of the $50 cap.
Datasets and their limits: [RV2_DATASET_AUDIT.md](RV2_DATASET_AUDIT.md).

**Purpose.** A go/no-go decision, not more experiments: after isolating each component, is
Epistemic Search promising enough to justify RV3?

| Question | Experiment | Data |
| --- | --- | --- |
| Does the evidence stance component work? | RV2-A | VitaminC, SciFact |
| Does explicit oracle proof structure help downstream? | RV2-B | EntailmentBank (StrategyQA audit only) |
| Can the controller tell sufficient from insufficient evidence? | RV2-C | EntailmentBank |
| Does premise-directed retrieval recover required evidence more efficiently? | RV2-D | HotpotQA, 2Wiki |

## Fixed settings

* **Model:** `gpt-6-luna`, reasoning `medium`, standard rate card, as in Phase 12. No Sol.
  Every compared system uses the identical model, effort, seed (42), token ceilings and call
  ceilings.
* **Code under test:** tag `epistemic-search-v1.1` (two defect fixes only, below).
* **Sampling seed:** 20261029. Every sample is a function of (data, seed) and is saved with
  its ids. Samples extend as prefixes, so a larger N never changes earlier items.
* **Budget:** hard caps enforced by the persistent spend ledger, one run id per experiment:
  RV2-A $0.25, RV2-B $0.25, RV2-C $0.50, RV2-D $0.50, **total $1.50**. Before each experiment
  the cost is estimated from measured per-call cost on two designated probe items; the
  estimate and the sample size it implies are logged first. If an experiment already answers
  its question negatively the remaining budget is not spent.
* **Negative results are kept.** Failed, aborted and over-cap cases stay in the denominators
  and are reported.

## v1.1 (frozen before any experiment)

1. **Span handling.** An extracted span is aligned to the source by an offset-preserving
   canonical form (Unicode spaces and whitespace runs, dashes, curly quotes). If it aligns,
   the evidence stores the **exact original substring**; the model's raw span is kept in the
   item's metadata. If it does not, **that item alone is rejected and the rejection is
   recorded in the trace**; the question continues. Nothing that is not in the document can
   enter the ledger.
2. **No-progress guard.** Before issuing a search, if the proposed query equals the previous
   query, the last search returned no document not already seen, and the epistemic state is
   unchanged by that search, emit `NO_PROGRESS` and stop acquiring. Premise-only has no
   belief state, so its "state" is its chosen target premise. Query generation is unchanged.

An opt-in way to supply an oracle proof graph through the case is added after the tag, as
experiment harness; with no oracle supplied the code path is byte-for-byte the tagged one.

## RV2-A: stance against gold labels

Input is the gold claim and the gold evidence only: no retrieval, controller or answer
generation. The system under test is the current stance component (`classify_evidence`
followed by the deterministic `aggregate_beliefs`). Prediction: `SUPPORTED→SUPPORT`,
`CONTRADICTED→CONTRADICT`, `UNKNOWN→NEUTRAL` (no extracted evidence or neutral only),
`MIXED` kept as its own predicted outcome and counted as an error for every gold class.

* **Samples:** VitaminC dev, 50 contrastive pairs = 100 items (34 C / 33 N / 33 S); SciFact
  dev, 100 (claim, cited abstract) pairs (34 / 33 / 33).
* **Metrics:** accuracy, macro-F1, per-class precision/recall/F1, confusion matrix,
  false-CONTRADICT rate (share of non-CONTRADICT items predicted CONTRADICT), CONTRADICT
  precision, false-SUPPORT rate; for SciFact also the two-way SUPPORT/CONTRADICT subscore;
  for VitaminC the pair metrics: both members correct, and predictions differ when the gold
  labels differ.
* **Stance works** if VitaminC macro-F1 ≥ 0.70 **and** false-CONTRADICT rate ≤ 0.10 on both
  datasets. Otherwise the stance front end is a limiting factor.

## RV2-B: oracle structure

1. **Convertibility (offline, $0):** EntailmentBank dev and StrategyQA train classified as
   fully / partially / not convertible by the rules in the audit. Only cleanly convertible
   examples enter model runs.
2. **Causal substitution (EntailmentBank):** Epistemic Search with the **generated**
   decomposition versus the **oracle** proof graph, downstream processing identical, on the
   same examples and the same four evidence conditions as RV2-C. The oracle arm is the
   RV2-C Epistemic Search run and is not paid for twice. If the estimate exceeds the cap,
   the generated arm runs on the largest prefix of the sample that fits and the oracle arm
   is compared on that prefix only.

## RV2-C: controlled epistemic state (the decisive experiment)

* **Sample:** EntailmentBank dev task 2, examples whose proof converts, with 3, 4 or 5
  leaves, in seeded order; initially 6 per size (18 total), raised in steps of 3 per
  size while the cost estimate stays within 80% of the cap, to at most 30.
* **Four conditions per example** (all deterministic given the seed):

  | | Evidence pool | Expected behaviour |
  | --- | --- | --- |
  | C1 | all gold leaves | ANSWER |
  | C2 | one required leaf removed (seeded choice) | do not behave as if sufficient |
  | C3 | C2 pool + the 4 highest-relevance dataset distractors | distractors do not substitute |
  | C4 | all leaves + the same 4 distractors | ANSWER |

* **Pool access:** every method receives the entire controlled pool for every query (a fixed
  provider that always returns the whole pool, in seeded order, with neutral document keys).
  Nothing can be retrieved from outside it. This removes retrieval as a confound; that is the
  point of the experiment.
* **Systems:** closed-book (pool-independent, run once per example), naive evidence-given
  RAG, premise-only (given the oracle graph), Epistemic Search (given the oracle graph).
* **Definitions.** ANSWER is a non-null answer; everything else is no answer (errors and
  budget stops are counted separately but are not answers). *Coverage on complete* =
  answer rate in C1∪C4. *Unsupported-answer rate* = answer rate in C2∪C3 (an answer when the
  gold proof is incomplete, whether or not the string happens to be right). **J = coverage on
  complete − unsupported-answer rate.** *Answer hit* = SQuAD-normalized token-F1 against the
  gold answer ≥ 0.5 (a deterministic proxy; raw F1 is also stored). *Selective risk* = (unsupported
  answers + non-hit answers in C1∪C4) / answers. *Blocker localization* = on C2/C3 the final
  unresolved set is exactly the removed leaf's claim (Epistemic Search only).
* **Also reported:** abstention rate, proof-completion accuracy (C1/C4 final state has no
  unresolved obligation), unresolved-required-premise count, distractor robustness (C4 vs C1
  coverage, C3 vs C2 answer rate), tokens, calls, latency, cost.

## RV2-D: retrieval only

HotpotQA dev distractor and 2Wiki dev, the 22 pilot questions excluded. HotpotQA: 24 bridge
+ 24 comparison; 2Wiki: 12 of each of its four types (96 questions total), raised by the same
cost rule. Same corpus (the question's own paragraph pool), same lexical retriever, k = 2, at
most 3 searches and 6 documents for every system. Systems: naive top-k, iterative,
premise-only (premise-directed, target chosen by the model), Epistemic Search (premise-directed,
target chosen by the controller). Retrieval is scored from the traces, independently of answer
quality.

* **Metrics:** gold-document recall, gold-supporting-fact recall (a fact counts as recovered
  when its paragraph is, since retrieval returns whole paragraphs), required-evidence coverage
  (all gold titles retrieved), useful unique evidence per search, duplicate retrieval rate,
  searches to recover all gold evidence (censored at 3 and reported as such), retrieval
  tokens and cost.

## Pre-registered decision rule

Uncertainty: 95% paired bootstrap over examples, 10,000 resamples, seed 20261029. A "YES"
needs the point estimate **and** the interval condition; "NO" needs the stated bound;
anything else is undetermined.

| Q | Statement | YES if | NO if |
| --- | --- | --- | --- |
| Q1 | With gold structure and gold evidence ES behaves correctly | ES coverage on complete ≥ 0.80 and answer-hit rate among its complete-condition answers ≥ 0.70 | coverage on complete < 0.60 |
| Q2 | ES detects insufficiency better than simpler baselines | J(ES) − max(J(premise-only), J(naive)) ≥ 0.20, CI lower bound > 0, ES coverage on complete ≥ 0.60 | difference ≤ 0.05, or ES coverage on complete < 0.50 |
| Q3 | Distractors do not cause false closure | ES answer rate in C3 ≤ 0.25 and ≥ 0.20 below the best baseline's | otherwise |
| Q4 | Oracle structure materially beats generated | J(oracle ES) − J(generated ES) ≥ 0.20 (same examples) | < 0.20 |
| Q5 | Premise-directed retrieval is more efficient | best premise-directed gold-document recall − best of naive/iterative ≥ 0.10 with CI lower bound > 0, or equal recall with ≥ 25% fewer searches | difference ≤ 0.02 |
| Stance | RV2-A rule above | works | does not work |

**Classification, evaluated in order, exactly one result:**

1. `INCONCLUSIVE` if RV2-C could not complete: fewer than 12 examples with all four
   conditions for Epistemic Search (cap, error rate or data).
2. `NOT_PROMISING_IN_CURRENT_FORM` if Q1 = NO, or Q2 = NO (this includes safety achieved only
   by near-universal abstention: ES coverage on complete < 0.50). If the gold upper bound
   fails, retrieval and decomposition are **not** blamed.
3. If Q2 = YES:
   * `ARCHITECTURE_REVISION_NEEDED` if ES-oracle J on proofs of depth ≥ 3 is below half of
     its J on depth ≤ 2 (nested dependencies are not handled; needs at least 5 examples in
     each group, otherwise this criterion is undetermined);
   * else `PROMISING_BUT_FRONTEND_LIMITED` if Q4 = YES, or Stance = does not work;
   * else `PROMISING`.
4. Otherwise (Q2 undetermined) `INCONCLUSIVE`.

Q3 and Q5 are reported as additional signals and do not change the class. **StrategyQA's
non-convertibility is reported as a scope limitation and deliberately does not trigger a
class**: it reflects what the dataset's annotations can express, and no experiment was run on
it. If RV2-A shows systematic stance-grounding failure, a grounded-stance design is proposed
at the decision gate and **not implemented without approval**.

## Outputs

`docs/experiments/RV2_{A_STANCE,B_ORACLE_STRUCTURE,C_EPISTEMIC_STATE,D_RETRIEVAL,DECISION}.md`
and `docs/results/rv2/`, with, for every experiment: config, seed, model, reasoning setting,
dataset and split, sample ids, per-item predictions, gold labels, metrics, tokens, calls,
latency, cost. Each stage is committed and pushed separately. RV3 is not started.
