# RV2 — diagnostic validation plan (SUPERSEDED_BEFORE_ANNOTATION)

> **Superseded 2026-10-29.** The manual RV2-0 path below was never run; see
> [rv2/SUPERSEDED.md](rv2/SUPERSEDED.md) and
> [RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md). Kept as history.

Date: 2026-10-24. Cumulative project API spend at this point: **$0.067952575**. RV0 and
RV1 are frozen. The 22 pilot questions are development data, so nothing here is a
claim-bearing evaluation. RV1 was annotated by GPT-5.6 Sol (model-assisted, not independent
human ground truth) and RV2-0 exists to test whether those labels can be trusted.

Purpose: decide whether the negative pilot is explained mainly by implementation defects,
retrieval, automatic decomposition, evidence grounding, the downstream belief/formal/controller
layers, or the premise-aware hypothesis itself. Budget target: under $1 of additional spend.

## Sequence and gates

| Step | What | Cost cap | Gate |
| --- | --- | ---: | --- |
| RV2-0 | Blind human spot-check of RV1 labels: 30 stance items and 5 cases | $0 | **Human approval required** before RV2-1 |
| RV2-1 | Two defect fixes only, frozen as `epistemic-search-v1.1` | $0 | After RV2-0 approval |
| RV2-2 | Re-run the 22 development questions, `epistemic_search` and `premise_only`, same Luna settings | **$0.25** hard | Estimate first |
| RV2-3 | 2×2 oracle diagnostic on the usable oracle subset | **$0.75** hard | Estimate first |
| Gate | Report which explanation is best supported; stop | — | Explicit approval to continue |
| RV2-4 | Entity/event-grounded stance extraction | — | Only if RV2-3 justifies it |

RV2-2 plus RV2-3 must not exceed a cumulative **$1** without explicit approval. Do not start
RV3, do not spend the Sol reserve, and do not broaden the architecture beyond the two v1.1
fixes before the gate.

## RV2-1: the only two changes

1. **Robust span validation.** Offset-preserving normalization may repair formatting-only
   differences. A span that still cannot be aligned rejects that evidence item only, not the
   question, and the rejection is recorded in the trace. Hallucinated spans must not be
   silently accepted.
2. **No-progress guard.** If the proposed query equals the previous query, the retrieved
   document set is unchanged, and the belief state is unchanged, emit a deterministic
   `NO_PROGRESS` outcome and stop repeating. The query-generation policy is not modified.

## RV2-3: the 2×2

| | Retrieved documents | Gold supporting-document pool |
| --- | --- | --- |
| Generated decomposition | A | B |
| Oracle decomposition | C | D |

Only oracle cases that are convertible to the proof representation and eligible under the
recorded attestation rules; anything excluded is listed, never silently dropped. Reported per
cell: answer accuracy and coverage, abstention rate, search/model calls, token cost, stance
accuracy against RV1 where measurable, unresolved blockers, execution failures.

Reading: A→B isolates retrieval under fixed decomposition; A→C isolates decomposition under
ordinary retrieval; C→D shows the downstream architecture with stronger inputs. **If D stays
poor, that is evidence against the current premise-aware downstream hypothesis.**

## Metrics

Exact Match is unchanged. A separate secondary normalized/semantic-equivalence metric is
added for every method identically and never replaces or retroactively changes Exact Match.

## Decision gate after RV2-3

Report which is best supported: (A) retrieval, (B) automatic decomposition, (C) evidence
grounding/stance, (D) downstream belief/formal/controller, (E) the premise-aware hypothesis
adds no useful signal, (F) inconclusive. Propose RV2-4 only if improving grounding would test
the hypothesis more cleanly. Then propose an RV3 design on fresh, disjoint questions and stop.

## Status

* RV2-0: `SUPERSEDED_BEFORE_ANNOTATION` (no labels collected, no API calls).
* RV2-1 to RV2-3 of this plan: replaced by the external-gold plan.
