# ADR 0014 — Paired saved-run inference with question clusters

Date: 2026-10-24. Status: accepted.

Analyze immutable scored examples; do not regrade answers or call a model. Require
complete matched case/label inventories, the same grader/data/retriever/model/
effort/seed/resource ceilings, valid config hashes and summaries consistent with
their scored rows. Partial runs are rejected rather than silently intersected.
Errors and abstentions retain their original zero answer scores. Unknown metrics
and costs remain missing with explicit counts.

The estimand is the mean across scored examples. Question `group_id` determines
resampling units, defaulting to the original case ID for native datasets. All
variants in a group travel together. Draw the same number of groups with
replacement and compute the example-weighted mean of each resulting sample;
unequal group sizes can change the resampled example count. For comparisons,
bootstrap paired per-example differences, never independent method draws.
Use two-sided percentile intervals and linear-interpolated quantiles with a
declared seed and repetition count. Return no interval with fewer than two groups;
flag degenerate distributions. Percentile intervals are an explicitly simple,
potentially poorly covered small-sample estimate, not guaranteed coverage.
The resampling/percentile convention follows the
[SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html);
the implementation uses only the standard library and samples whole groups.

Paired tests flip method labels jointly within each question group. Use absolute
mean difference as the two-sided statistic, counting ties within relative/absolute
tolerance `1e-12 * max(1, observed absolute sum)`. Enumerate all `2^G` assignments
through 16 groups; otherwise sample signs and use `(extreme + 1)/(draws + 1)`.
This tests exchangeability of method labels within independent groups, not
arbitrary equality of means without assumptions. The paired sampling and
Monte Carlo correction are described in
[SciPy's permutation-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).
Our absolute-tail convention is recorded explicitly. With singleton groups and
binary exact-match outcomes, this also gives the exact paired discordance test.

Holm adjustment covers all available method-versus-reference tests across
coverage, exact match and F1 within one report. No cross-dataset or cross-report
correction is implied. Confidence intervals are marginal, not simultaneous.
See the [R p.adjust reference](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html).

Report mean, median, p90, known count, unknown count and observed totals for
tokens, model/search/API calls, cache hits, physical estimated cost and wall time.
Cached requests are not independent replicates, and their latency is not uncached
latency. Recorded source hashes make reports reproducible; no model sampling
uncertainty beyond the saved executions is estimated. Keep datasets separate.

Small pilot intervals can exclude zero while the paired test does not reject;
the procedures have different finite-sample behavior. Report both without
choosing whichever appears favorable. These analyses are exploratory and cannot
establish the architecture's general superiority.
