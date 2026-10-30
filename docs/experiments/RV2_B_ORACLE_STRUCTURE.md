# RV2-B: oracle proof structure versus generated structure

Date: 2026-10-29. Code: tag `epistemic-search-v1.1.1` plus the opt-in oracle-structure hook (see
[RV2_V1_1_FREEZE.md](RV2_V1_1_FREEZE.md) for why v1.1.1). Plan:
[RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md). Results with every case:
[results.json](../results/rv2/rv2_b/results.json), [cases_oracle.jsonl](../results/rv2/rv2_b/cases_oracle.jsonl),
[cases_generated.jsonl](../results/rv2/rv2_b/cases_generated.jsonl). A superseded v1.1 probe is kept in
`docs/results/rv2/rv2_b_superseded_probe_v1_1/`.

## 1. Convertibility (offline, $0)

| Dataset | Examples | Fully convertible | Partial | Not convertible |
| --- | ---: | ---: | ---: | ---: |
| EntailmentBank dev | 187 | **187** (166 trees, 21 sharing a node) | 0 | 0 |
| StrategyQA train | 2,290 | **0** | 2,290 (gold facts only, no usable proof logic) | 0 |

StrategyQA's decompositions are sub-questions with `#n` back-references (6,671 of 6,720
steps end in `?`), so nothing was forced into the claim graph and **no model was run on it**.
The pipeline's graph keeps leaf claims only, so EntailmentBank's intermediate-conclusion text
is dropped even though the adapter preserves it. All of this is in
[RV2_DATASET_AUDIT.md](RV2_DATASET_AUDIT.md).

## 2. Causal substitution on EntailmentBank

Epistemic Search, identical downstream processing, with the **gold proof graph** (oracle) versus
the structure **Luna generates from the question**. 18 dev examples (6 each with 3, 4 and 5
leaves), four evidence conditions each, 72 cases per arm, same cases in both arms. Conditions:
C1 all gold leaves, C2 one leaf removed, C3 C2 plus 4 distractors, C4 C1 plus the same 4
distractors; every system receives the whole pool and can retrieve nothing outside it.
Run cost **$0.0862 new API spend** (cap $0.25); 1,793 and 1,088 logical model calls.

| | Oracle structure | Generated structure |
| --- | ---: | ---: |
| Answer rate C1 / C2 / C3 / C4 | 0.94 / 0.44 / 0.50 / 0.89 | 0.28 / 0.22 / 0.28 / 0.33 |
| Coverage on complete (C1∪C4) | **0.917** | 0.306 |
| Unsupported-answer rate (C2∪C3) | **0.472** | 0.250 |
| **J** = coverage − unsupported rate | **0.444** | 0.056 |
| Errors (invalid graph) | 0 | **20 of 72 cases** |
| Proof completion on complete (no unresolved premise) | 0.917 | 0.583 |
| Mean unresolved premises C1 / C2 / C3 / C4 | 0.11 / 0.56 / 0.50 / 0.17 | 0.78 / 1.00 / 0.78 / 0.56 |
| Answer hit (token-F1 ≥ 0.5) among complete answers | 0.18 | 0.45 |
| No-progress stops | 22 | 32 |

**Pre-registered Q4 (oracle J − generated J ≥ 0.20): J gap = 0.389, verdict YES.**

Two things sit inside that YES and must be read with it:

* **Invalid generated graphs.** In 5 of 18 examples (28%) the model's graph failed the
  pipeline's structural validation (for example a `claim_id` on the CONCLUSION node), which is
  an error in all four conditions. Those count as no answer, as pre-registered, so they inflate
  the gap. Restricting to the **13 examples with a valid generated graph** (a secondary
  analysis, not used for the verdict): J is 0.077 generated against 0.462 oracle, a gap of
  **0.385**. So the gap is not an artifact of broken graphs.
* **Why valid generated graphs do badly.** With a valid generated graph and the complete
  evidence (C1), Epistemic Search answered only 5 of 13 examples and abstained in the other 8
  by `NO_PROGRESS`. The generated premises are derived statements ("the expanding ice exerts
  pressure on the rock"), not the leaf facts. The stance step judges one claim against one
  document, so a premise that follows from two facts is not supported by either document and
  stays open. The oracle premises are the leaf facts themselves, which a single document can
  support. This is a mismatch between what the premises assert and what a per-document stance
  can establish, not a retrieval problem.

## 3. The oracle arm is not clean either

With the gold structure and gold evidence the system **does** reach the right proof state when
the evidence is complete (proof completed in 91.7% of C1/C4 cases), but it answered in 17 of the
36 cases where a leaf was removed. In **all 17** the claim for the removed leaf had been judged
SUPPORTED. Reading the evidence behind them:

| Document that supported the removed leaf's claim | Cases |
| --- | ---: |
| Another **gold leaf** of the same proof | 13 |
| A distractor (a near-paraphrase) | 4 |

Examples: the removed claim "different solids are combined physically" is supported by the
retained leaf "solids are combined physically"; "a mixture is made of two or more substances
combined together" by a leaf about "combined rice cereal and marshmallows together".
EntailmentBank leaves overlap in meaning, so removing one often does not make its claim
underivable from the rest. These judgments look defensible, not like hallucination. The
consequence is a validity limit on C2/C3 as ground truth that I did not anticipate when
pre-registering them (I anticipated it for C3 distractors only): **a share of the "unsupported
answers" are answers the remaining text can arguably support.** The pre-registered metrics are
reported as defined; this diagnostic is what keeps them from being over-read. When the stance
step had no supporting document at all, the system did stop: blocker localization (the removed
leaf is the only unresolved premise) is 0.528 overall.

Answer matching is weak: the system's answers are correct paraphrases ("the water would expand
as it freezes, likely causing the rock to break apart") of gold sentences ("the rocks would
break into smaller pieces"), so token-F1 ≥ 0.5 marks most as misses (hit rate 0.18). The
coverage and J measures do not depend on answer text. The proxy is only used where the plan
says it is.

## 4. What this does and does not say

* **Supports:** explicit gold structure plus complete evidence is what makes Epistemic Search
  behave (coverage 0.92, proof completed); the generated front end cannot yet supply that
  structure (28% invalid, and the valid ones are statements a single document cannot support).
  Oracle structure materially improves the system (Q4 = YES by both the pre-registered and the
  conditional measure).
* **Does not establish:** that oracle-structure Epistemic Search detects insufficiency better
  than simpler systems. That is RV2-C's comparison, and the 47% unsupported-answer rate above
  is the number it must be set against.
* **Caveats:** 18 examples; answers are free text, so answer matching is weak; generated
  blocker localization is 0 by construction (its claims are not leaf texts, so it cannot be
  mapped) and is not evidence of failure; the generated-arm structure invalidity is a property
  of this Luna prompt, which was not tuned.
