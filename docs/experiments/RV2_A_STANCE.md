# RV2-A: the stance component against official gold labels

Date: 2026-10-29. Code: tag `epistemic-search-v1.1`. Plan: [RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md)
(committed before any call). Machine-readable results, every prediction, gold label, token
count, latency and cost: [results.json](../results/rv2/rv2_a/results.json) and
[estimate.json](../results/rv2/rv2_a/estimate.json).

## What was tested

The gold claim and the gold evidence go in; no retrieval, controller or answer generation.
The system is exactly the pipeline's stance path: the Luna evidence-extraction prompt
(`classify_evidence`) followed by the deterministic `aggregate_beliefs` (threshold 0.5).
`SUPPORTED→SUPPORT`, `CONTRADICTED→CONTRADICT`, `UNKNOWN→NEUTRAL`; `MIXED` is kept as its own
outcome and counted wrong for every gold class. Model `gpt-6-luna`, reasoning `medium`,
seed 42, sampling seed 20261029.

| Dataset | Split | Items | Gold labels |
| --- | --- | ---: | --- |
| VitaminC | dev | 100 (50 contrastive pairs) | 34 CONTRADICT / 33 NEUTRAL / 33 SUPPORT |
| SciFact | dev | 100 (claim, cited abstract) pairs | 34 / 33 / 33; `NEI` → NEUTRAL |

## Results

All 200 items ran. 0 model errors; 6 hallucinated or unalignable spans were rejected
item-by-item (v1.1) and none aborted a case.

| | VitaminC | SciFact |
| --- | ---: | ---: |
| Accuracy (95% CI) | **0.81** (0.74–0.88) | **0.82** (0.74–0.89) |
| Macro-F1 (95% CI) | **0.815** (0.735–0.883) | **0.836** (0.760–0.904) |
| SUPPORT precision / recall / F1 | 0.789 / 0.909 / 0.845 | 0.806 / 0.879 / 0.841 |
| CONTRADICT precision / recall / F1 | **0.963** / 0.765 / 0.852 | **0.903** / 0.824 / 0.862 |
| NEUTRAL precision / recall / F1 | 0.735 / 0.758 / 0.746 | 0.862 / 0.758 / 0.806 |
| **False-CONTRADICT rate** (95% CI) | **0.015** (0.00–0.053) | **0.045** (0.00–0.105) |
| False-SUPPORT rate | 0.119 | 0.104 |
| Predicted MIXED (counted wrong) | 1 | 4 |
| Two-way SUPPORT/CONTRADICT accuracy | 0.836 (n = 67) | 0.851 (n = 67) |

Confusion matrices (rows gold, columns predicted):

| VitaminC | SUPPORT | CONTRADICT | NEUTRAL | MIXED |
| --- | ---: | ---: | ---: | ---: |
| SUPPORT | 30 | 0 | 3 | 0 |
| CONTRADICT | 2 | 26 | 6 | 0 |
| NEUTRAL | 6 | 1 | 25 | 1 |

| SciFact | SUPPORT | CONTRADICT | NEUTRAL | MIXED |
| --- | ---: | ---: | ---: | ---: |
| SUPPORT | 29 | 0 | 3 | 1 |
| CONTRADICT | 2 | 28 | 1 | 3 |
| NEUTRAL | 5 | 3 | 25 | 0 |

**Contrastive pairs (VitaminC, 50 pairs, same claim and minimally different evidence with
different gold labels):** both members correct in **64%**; the two predictions differ in
**82%**; both wrong in 2%. So when the evidence changes the verdict, the component usually
notices (82%) and gets both sides right in about two thirds of pairs. The (two-way) macro-F1
fields in `results.json` include the empty NEUTRAL class and are not meaningful; the
accuracy and per-class figures above are the ones to read.

Cost: **$0.0266 of new API spend** for 200 calls (cap $0.25; estimate $0.022), 82,064 prompt
and 37,274 completion tokens, about 5.6 s per call including the token pre-count.

## Pre-registered verdict

The rule was: works if VitaminC macro-F1 ≥ 0.70 **and** false-CONTRADICT ≤ 0.10 on both
datasets. All three checks pass (0.815; 0.015; 0.045), the run is complete, and the verdict
is **stance works**. The interval caveat is real: the upper bound of the SciFact
false-CONTRADICT rate is 0.105, so a ≤ 0.10 claim is supported by the point estimate, not
by the whole interval.

## What this does and does not show

* **It shows** that the extraction-plus-aggregation stance path is competent on a claim paired
  with evidence that is about that claim, on two unrelated gold benchmarks: roughly 82%
  accurate, very rarely asserting a contradiction that is not there, and mostly sensitive to
  small evidence changes.
* **It does not test the failure RV1 reported.** RV1 found the pilot's false contradictions
  came from evidence about a *different* game, person or office being compared with the
  premise. Every gold pair here is topically matched by construction, so this experiment
  cannot expose that kind of grounding failure, and the pass should not be read as
  contradicting RV1. The two are consistent: stance on matched evidence is good; stance on
  mismatched retrieved text was the problem. Whether to build entity/event grounding is a
  question for the final decision gate, not something this result settles.
* **Where it errs.** Numeric and comparative inference (VitaminC `SUPPORTS`/`REFUTES` that
  need arithmetic, such as "over 11 million" against "less than 12 million", often come back
  NEUTRAL), and absence claims. 6 of 34 VitaminC CONTRADICT items were called NEUTRAL, and 6 of
  33 NEUTRAL items were called SUPPORT.
* **Label caveat.** All three SciFact false CONTRADICTs are `NEI` pairs whose abstract
  discusses the claim's subject (for example, depletion of Scribble blocking transformation
  against a claim that downregulation prevents it). `NEI` in SciFact means annotators marked no
  rationale in that abstract, so some of these may be correct readings the label is
  conservative about. They are scored as errors anyway.
* **Sample.** 100 items per dataset; intervals are wide. The VitaminC sample is a designed
  mix of pair types, not its natural distribution, and one third of VitaminC dev is
  synthetic (FEVER-derived).

No negative result was hidden: the weaker cells (NEUTRAL precision 0.735 on VitaminC;
SUPPORT→NEUTRAL misses; pair `both_correct` of 64%) are reported above.
