# Phase 13 — Abstention metrics

Status: **complete**. Commit `dfa9dba` pushed; hosted CI `40063077390` passed.
Phase 12 commit `196de1f` passed hosted CI run `40040967731` before work began.

## Implementation and decisions

Added `selective.py` and the offline `selective` CLI. Implemented coverage,
selective EM risk, risk-coverage curve data, discrete AURC and abstention
precision/recall/F1. Existing answer scores are reused without changing any
method's grader. The report retains errors, budget stops, explicit denominators,
source hashes and partial-run status. See [ADR 0007](../decisions/0007-selective-metrics.md).

Tied ranking scores use analytical expected-prefix loss under uniform tie order,
so input order cannot alter AURC. No zero-risk value is assigned at zero coverage.
Null represents missing correctness/answerability labels or missing ranking
scores/counterfactual predictions. Errors never earn correct-abstention credit.

## Tests and acceptance

All six required metrics are implemented and exercised with deterministic data:
- hand-calculated prefix risks and AURC, including all-correct/all-wrong endpoints;
- equal/mixed-score tie permutations;
- abstention confusion counts including crashes and budget stops;
- no-answer and missing-label denominators;
- invalid IDs/scores/statuses and inconsistent saved-run metadata;
- saved-run CLI integration, overwrite refusal and partial evaluation analysis.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`pytest -q` and `uv build` are the required checks. Current tests: **195 passed**;
mypy: **46 files**. CI includes an offline selective-analysis CLI smoke.

## Saved pilot analysis and limitations

Reanalyzed all 15 dataset/method groups from Phase 12 at **zero additional API
cost**. [Results](../results/phase13_selective_pilot.json) record the source hashes.
Total project API spend remains **$0.067952575**. Hotpot naive RAG has coverage
0.60 and selective EM risk 0.50; full Epistemic Search has coverage 0.20 and risk
0.50. These operating points do not support a reliability improvement claim.
They are small samples at different coverages, not a matched-coverage study.

The pilot contains no ranking scores or evidence-answerability labels. Therefore
real AURC and abstention classification metrics remain null. ConfRAG has no
single-answer correctness labels, so its selective EM risk is also null. The
curve/AURC implementation is validated on fixtures; no real curve is fabricated.
Collecting candidate predictions/confidence and calibration is a later phase,
not a reason to repeat paid Phase 12 calls now.

## Next dependency

After this phase's push and successful CI: **Phase 14 — Contradiction experiments**.
Use native ConfRAG annotations, saved traces and offline tests first; any new
model pilot must obey the same cumulative project ledger and scaling policy.
