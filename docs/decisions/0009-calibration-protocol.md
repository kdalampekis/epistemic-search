# ADR 0009 — Paired calibration with separated question groups

Status: accepted for Phase 15. Protocol: `paired-binary-calibration-v1`.

## Scope

Measure three supplied score families for the **same fixed candidate and binary
correctness event**: raw/self-reported confidence, NLI-derived score, and evidence
aggregation. Compare a fourth family obtained by fitting a histogram map to
the NLI score. A score protocol must explain how its value relates to the declared
event. Entailment of a source sentence and real-world answer correctness are
different events; their labels cannot be silently interchanged.

Scores must lie in [0,1], but this range alone does not make them probabilities.
Applying calibration metrics to raw heuristic scores is a diagnostic comparison,
not certification. The domain belief model remains uncalibrated; this phase does
not switch `ClaimBelief.calibrated` on or change controller thresholds.

## Metrics and fit

For binary correctness y and score s, binary Brier = mean((s-y)^2), without
the factor of two used by a two-class-vector convention. ECE is the sum of bin
fractions times abs(mean score - observed correctness). Reliability curve data
retain each bin's count, interval, mean score and correctness. Empty bins have
null means, not zero accuracy. These are empirical statistics, not proofs of
calibration. See [Guo et al., ICML 2017](https://proceedings.mlr.press/v70/guo17a.html)
for ECE, reliability diagrams and post-processing calibration.

Both metric and fit bins are fixed-width and configured before evaluation.
Intervals are [j/B, (j+1)/B), with 1 included in the final bin. This left-inclusive
boundary convention is versioned explicitly. The fit uses Laplace-smoothed
binary frequency (positive_count + 1)/(bin_count + 2). An empty fit bin uses the
similarly smoothed global calibration-split frequency. Record counts, positives,
estimates and fit candidate IDs. Histogram calibration need not preserve ranking
or improve held-out metrics; sparse bins are a material limitation.

## Leakage and missing-data boundaries

- Candidate IDs must be unique. Related candidates, methods and transformed
  versions of one question must share `group_id`; groups cannot cross the two
  splits. The tool can check supplied IDs, not detect hidden semantic duplicates.
- Fit reads only calibration-split candidates with known labels and NLI scores.
  No evaluation labels enter fitting, bin selection or smoothing selection.
  Changing evaluation labels cannot change the fitted model; tested explicitly.
- All four evaluated families use exactly the same evaluation candidates with
  all three raw scores and known correctness. Every excluded evaluation row
  retains its ID and reasons. Report total versus analyzed denominators.
- Failed/absent candidates have no invented correctness. Missing labels do not
  become false labels. No usable fit or paired evaluation yields unavailable
  results, not zero Brier/ECE. Do not compare conditional subsets as if they
  represented all examples or all methods.
- `event_definition`, `label_protocol`, score protocols, fixture status and input/
  config/evaluator hashes accompany the serialized fit and report. Provider
  usage remains in the original prediction artifacts; offline analysis costs $0.

## Current experimental limit

The shipped four-family comparison is explicitly **fixture-only**. The real Luna
pilot lacks aligned self-confidence, NLI and evidence-aggregation scores for the
same candidates, and lacks gold premise-level stance labels. Neither raw
stance confidence nor max evidence support is silently assigned answer-level
probability semantics. No real calibration-improvement claim is available.

Before a real comparison, freeze the event, score-generation protocols and
question-group split; collect labels independent of scores; retain call costs;
then fit once and report all predeclared metrics on the untouched evaluation
groups. No paid pilot is launched merely to fill this roadmap entry. Optional
semantic entropy is omitted because extra sampled generations are not justified
by current results or budget priorities.
