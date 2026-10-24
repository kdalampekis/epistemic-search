# ADR 0007 — Selective metrics with explicit missing data

Accepted for Phase 13. This is a separate, offline analysis of saved scores;
original answer graders, prompts and Phase 12 results are unchanged.

## Operating point

Coverage is answered/executed examples, retaining errors and budget stops in
the denominator. Selective EM risk is the fraction of answered examples with
EM zero. It is null if no answers exist or any answered example lacks a
correctness label. This measures answer correctness, not citation grounding.

Abstention is the positive class; gold positive means `answerable: false` for
the available evidence. A non-answer from a completed run or budget stop counts
as withholding. A crashed/error run cannot receive true-positive abstention
credit; on a gold-unanswerable case it contributes a false negative. Error and
budget-stop counts are also reported separately. Answerability is never inferred
from the presence of a QA gold answer. Unknown answerability labels are excluded
only from these classification counts, with the labelled denominator explicit.

Precision = TP/(TP+FP), recall = TP/(TP+FN), and F1 = 2TP/(2TP+FP+FN).
A zero denominator produces null, not a fabricated zero or perfect result.
Budget-induced withholding does not by itself establish semantic awareness.

## Curves and AURC

The standard empirical AURC averages the selective risk at all ranked prefixes;
coverage is prefix size divided by sample size. See Section 3.1, equation 27 of
[Franc, Prusa and Voracek, JMLR 2023](https://www.jmlr.org/papers/volume24/21-0048/21-0048.pdf).

Our version `selective-em-uniform-ties-v1` ranks higher scores first and uses
**expected loss under a uniform ordering within equal-score groups**. Thus
permuting tied inputs cannot improve the result through label-based ordering.
A point that partially accepts a tied group describes randomized tie selection,
not a realizable deterministic score threshold. Its tie fraction is recorded.
At zero coverage, risk is null. AURC is the mean of the N nonempty prefix risks;
there is no trapezoidal interpolation from a fictitious zero-risk origin.
Scores are ranking statistics, not automatically calibrated probabilities.

Full AURC requires a candidate prediction, correctness label and ranking score
for every example. An abstention/error supplies no counterfactual answer; its
ordinary QA penalty is not invented as such a candidate's loss. The offline
CLI therefore leaves the curve/AURC unavailable when predictions or scores are
missing. It never fabricates ranks from gold labels, case order or answerability.
The pure `risk_coverage` function supports fully scored candidate sets; fixtures
verify exact hand-computed values and tie behavior. Confidence collection and
calibration remain Phase 15, and artifact plotting remains Phase 23.

## Saved-run interface

`selective RUN_DIR OUTPUT_JSON [--scores-path SCORES_JSON]` reads existing
`examples.jsonl`, evaluator-only `labels.jsonl`, `manifest.json` and `summary.json`.
A score file has `source` (a named scoring protocol) and `scores` (ID to finite
number). Unknown IDs and inconsistent counts/metric versions are rejected.
The analysis records source hashes, planned/executed counts and any original
stop reason. Existing output files cannot be overwritten. No provider, API key,
new grading or paid call is involved.
