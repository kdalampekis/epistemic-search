# RV2-E: pivot validation of the simpler architecture

Date: 2026-10-30. Plan and decision rule, committed before any call:
[RV2_E_PIVOT_PLAN.md](RV2_E_PIVOT_PLAN.md). Code: tag `epistemic-search-v1.1.1` plus
`premise_state` (commit `8e54f40`). All cases:
[cases_given.jsonl](../results/rv2/rv2_e/cases_given.jsonl),
[cases_lexical.jsonl](../results/rv2/rv2_e/cases_lexical.jsonl),
[results.json](../results/rv2/rv2_e/results.json), [estimate.json](../results/rv2/rv2_e/estimate.json).

## Outcome (pre-registered rule): `PREMISE_ONLY_SUFFICES`

Premise-only **replicated strongly** on fresh examples. Premise-state (M2) **missed its
viability bar by one threshold** (coverage on complete evidence 0.889 against the required 0.90)
and did not beat premise-only on the sufficiency measure. Under the rule committed in advance
that is a loss for M2: **keep premise-only as a small component; no architecture beyond it is
supported.** A statistically supported advantage for M2 in the secondary search setting did not
change the outcome because the rule requires M2 to be viable first.

## Run

27 EntailmentBank dev examples never used in RV2-B/C (the planned 32; the run stopped, see
"Interruption"), four systems, E-A (whole pool given, conditions C1–C4) for 27 examples and E-B
(evidence found by search in the full 25-sentence context, R1/R2) for 26. The 27 examples exceed
the committed minimum of 24. Gold premises were given to M1 and M2. Model `gpt-6-luna`, medium,
seed 42. **New API spend $0.0939** (cap $0.50), 724 settled generations.

### E-A, the deciding experiment (27 examples, 108 cases per system)

| System | Answer rate C1 / C2 / C3 / C4 | Coverage on complete | Unsupported-answer rate | **J** | Model calls | Logical cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| B0 naive RAG | 0.93 / 0.81 / 0.78 / 0.89 | 0.907 | 0.796 | **0.111** | 108 | $0.0081 |
| B1 iterative RAG | 0.96 / 0.85 / 0.81 / 0.89 | 0.926 | 0.833 | **0.093** | 134 | $0.0117 |
| M1 premise-only | 0.96 / 0.11 / 0.07 / 0.96 | **0.963** | 0.093 | **0.870** | 157 | $0.0217 |
| M2 premise-state | 0.89 / 0.00 / 0.07 / 0.89 | 0.889 | **0.037** | 0.852 | 214 | $0.0313 |

| Rule | Result |
| --- | --- |
| R0: at least 24 complete examples | **27**, met |
| R1: premise-only viable (J ≥ 0.75, coverage ≥ 0.90, ≥ 0.50 above the best baseline) | J 0.870, coverage 0.963, margin 0.759, **holds** |
| R2: premise-state viable (same) | J 0.852 ✓, margin 0.741 ✓, coverage **0.889 < 0.90**, **fails** |
| R3(i): ΔJ(M2 − M1) ≥ 0.05, interval above 0 | −0.019, 95% CI [−0.167, +0.130], **no** |
| R3(ii): E-B leaf-recall gain ≥ 0.10, interval above 0, cost ≤ 1.5× | +0.140, CI [+0.061, +0.228], cost ratio 1.44, **yes** |

R2 fails by 0.011 on a single threshold (48 of 54 complete cases answered against the 49 or more
needed). I am reporting it as the failure it is under the committed rule, not rounding it.

### E-B (evidence must be found by search), 26 examples

| System | Answer rate R1 (complete) / R2 (missing) | J | Required-leaf recall in R1 | Mean searches | Logical cost |
| --- | --- | ---: | ---: | ---: | ---: |
| B0 naive RAG | 0.42 / 0.38 | 0.04 | 0.231 | 1.0 | $0.003 |
| B1 iterative RAG | 0.62 / 0.62 | 0.00 | 0.297 | 2.0 | $0.008 |
| M1 premise-only | 0.50 / 0.23 | 0.27 | 0.655 | 2.6 | $0.026 |
| M2 premise-state | 0.38 / 0.12 | 0.27 | **0.795** | 2.8 | $0.026 |

M2 finds the required leaves significantly more often than M1 (+0.14), and both find far more
than the baselines. With the full 25-sentence context neither answers much when everything is
present (0.38 to 0.50) because they do not always retrieve every leaf within six documents.

## Post-hoc diagnostics (not used for the verdict)

* **All six of M2's refusals on complete evidence are the answer step, not the sufficiency
  judgment.** In those cases (3 examples × C1, C4) M2 judged **every premise RESOLVED** and then
  its answer call, which sees only the cited evidence, returned `null`. Over all 54 complete
  cases M2's state said "all resolved" 54 times. Taking the state alone as the decision,
  post hoc, M2 would score coverage 1.00 and unsupported 0.074 (4 of 54), J 0.926. That is a
  different system from the one pre-registered and was found after seeing the data, so it is
  only an indication of where M2's shortfall comes from and must be tested on fresh data
  before it is believed.
* **M2 is stricter than M1** (it answered 0 of 27 C2 cases against 3 of 27) and pays for it in
  coverage. The two have statistically indistinguishable J.
* **Two M2 errors** (both on one example, C2/C3) are the model returning a RESOLVED/CONFLICTING
  premise without evidence ids, rejected by the schema; they count as no answer.

## Interpretation

* **Premise-aware sufficiency judgment replicates.** Given gold premises, both premise systems
  separate complete from incomplete evidence (J ≈ 0.85–0.87) where naive and iterative RAG
  essentially do not (J ≈ 0.1), on 27 new examples. This confirms the RV2-C finding.
* **Making the unresolved-premise state explicit did not improve sufficiency detection.** The
  explicit state matched premise-only on J, was stricter, and cost 1.4 times as much.
* **It may help search, with caveats.** M2's recall advantage in E-B is statistically
  supported but is confounded two ways: M2's query is the premise text alone while M1's adds
  the whole question, and the oracle premises are the leaf sentences verbatim, so a premise-text
  query finds its leaf almost by construction. This is an upper bound for perfect premises,
  not evidence about real questions, where RV2-D found premise-directed retrieval much weaker
  than iterative retrieval.
* **Still untested:** premise-only or premise-state with *generated* premises on this kind of
  data. RV2-B showed generated structure is the weak link (28% invalid, derived claims), so
  everything positive here depends on obtaining good premises.

## Interruption and the ledger

The run stopped after 646 of 768 planned rows with a second ledger halt ("Cancelled API attempt;
any pending maximum charge remains reserved", one pending reservation). A request was cancelled
in flight, most likely a model call that exceeded its time limit, the same family of failure as
RV2-D. The minimum of 24 complete examples had already been reached, so I did **not** ask to
clear it or resume. **The halt is in force again.** The first halt's clearance is documented in
[ledger_halt_audit.md](../results/rv2/ledger_halt_audit.md).
