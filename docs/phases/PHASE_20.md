# Phase 20 — Statistical analysis

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 19 commit `3f9ee96` passed CI `40084386967` before work began.

## Implementation and design

Added offline analysis of saved matched runs: question-cluster percentile
bootstrap intervals, paired cluster sign-flip tests, Holm-adjusted p-values and
mean/median/p90 resource distributions. Reference differences use paired scores;
controlled families stay together. Insufficient groups and missing outcomes
produce explicit unavailable results. Failures remain in denominators.

Reports validate inventories, hashes, grader/model/effort/retrieval/budget parity
and saved summary consistency. They preserve source hashes, analysis config,
statistical conventions, cache caveats and incomplete-cost counts. Partial runs
are refused rather than silently restricted. See
[ADR 0014](../decisions/0014-paired-statistical-analysis.md).

## Tests and acceptance

All four acceptance items are implemented: bootstrap CIs, paired tests, cost
distributions and reproducible comparison reports. Tests cover unequal cluster
sizes, exact sign-flip probabilities, seeded Monte Carlo with nonzero p-values,
Holm correction, linear quantiles, degenerate/single-group intervals, unknown
costs, failure retention, deterministic replay and incompatible artifact rejection.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`uv run --locked --extra formal --extra benchmarks pytest -q`, and `uv build`
pass: **276 tests**, **59 typed files**. CI runs the one-group fixture analysis,
which correctly declines inferential intervals/tests rather than fabricating power.

```sh
uv run --locked epistemic-search analyze-comparison configs/statistics_fixture.yaml
uv run --locked epistemic-search analyze-comparison configs/statistics_hotpotqa.yaml
uv run --locked epistemic-search analyze-comparison configs/statistics_2wikimultihopqa.yaml
uv run --locked epistemic-search analyze-comparison configs/statistics_confrag.yaml
```

Commands create new outputs and refuse overwrite. To reproduce committed reports,
use a fresh checkout without those generated report paths or choose a new output
path (which changes the recorded config hash).

## Observed results and limitations

Reanalyzed all five saved Phase 12 methods separately for 10 HotpotQA, 10 2Wiki
and two ConfRAG examples, without further API calls. Reports:
[HotpotQA](../results/phase20_hotpotqa_pilot.json),
[2Wiki](../results/phase20_2wikimultihopqa_pilot.json),
[ConfRAG](../results/phase20_confrag_pilot.json).

The full method has no Holm-adjusted advantage over naive RAG on this pilot.
Closed-book exceeds naive RAG in 2Wiki coverage and F1 under the within-dataset
adjustment. This is an unfavorable result for the retrieval pipeline, not grounds
to hide failed cases or scale the benchmark. The ConfRAG adapter has no answer
EM/F1 labels; those comparisons remain unavailable. Coverage is not answer safety.

The samples are small, some bootstrap intervals are degenerate, and cache reuse
means there are no independent model replicates. Marginal percentile intervals
and exact paired tests can disagree on exclusion/rejection in tiny samples; both
are retained. Cross-dataset multiplicity is not adjusted. No superiority or
generalization claim follows, and these results were not used to tune test labels.

Additional research API spend: **$0**; cumulative remains **$0.067952575**.
After push and successful CI: **Phase 21 — Failure analysis**.
