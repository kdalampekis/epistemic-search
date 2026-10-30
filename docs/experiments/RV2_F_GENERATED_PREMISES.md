# RV2-F: generated-premise sufficiency (pre-registered)

Date: 2026-10-30. **Committed and pushed before any RV2-F model call.** No threshold, rule, prompt or
sample below is changed after a result is seen. Follows the RV2 decision
([RV2_DECISION.md](RV2_DECISION.md): `NOT_PROMISING_IN_CURRENT_FORM`) and the pivot test
([RV2_E_PIVOT.md](RV2_E_PIVOT.md): `PREMISE_ONLY_SUFFICES`). This is the last, narrow go/no-go test
of the one surviving idea.

## Question and hypothesis

Premise-only sufficiency checking separated complete from incomplete evidence (J 0.87-0.89) in
RV2-C and RV2-E, **but always with gold premises** (EntailmentBank leaf facts). RV2-B showed that
model-generated structure was the weak link (28% invalid graphs; valid ones stated derived claims).

> **H.** A single generation of required premises from the question alone, followed by a
> whole-evidence-set check of each premise (ANSWER iff every premise is RESOLVED, else ABSTAIN),
> keeps enough of the gold-premise separation to be worth building on.

Pipeline under test, and nothing more: `question -> generated premises -> per-premise
RESOLVED/UNRESOLVED judged from the whole evidence set -> ANSWER iff all RESOLVED else ABSTAIN`.
The implementation (`src/epistemic_search/sufficiency.py`) contains no per-document stance, evidence
ledger, belief aggregation, formal closure, conflict state, retrieval controller, query generator,
or solver; a test asserts those constructs do not appear in it. `premise_state.py` (M2) and the
original architecture are untouched.

## Ledger audit (done first)

[ledger_halt_audit.md](../results/rv2/rv2_f/ledger_halt_audit.md): the RV2-E halt was a cancelled
in-flight request (`9ed25a3b...`, $0.00210525, `rv2-e-pivot-v1`); outcome genuinely uncertain. It
was settled at the reserved maximum (the conservative, spend-safe direction), the halt cleared
under the ledger's own policy with a backup taken, no historical record deleted, and the ledger
verified read-only afterwards. The ledger is not bypassed in RV2-F: every request is reserved and
settled by it and the run cap below is enforced by it.

## Data

* **EntailmentBank task 2, dev split only** (commit `daac2fdb7ab52ec3ef8f2953f59288c1edd7c2f0`).
  The test split is never read.
* **Fresh examples only.** Excluded: every id in the RV2-B, RV2-C and RV2-E samples (59 distinct
  ids; manifest in [sample.json](../results/rv2/rv2_f/sample.json) under `excluded_seen_ids`), and
  by construction every earlier development/pilot example (those are other datasets). Seen examples
  are never substituted back in. The sample file records `overlap_with_excluded` and it must be empty.
* Eligibility: 3-5 gold leaves and a proof that converts to a valid graph (no duplicate leaf text).
  No distractor requirement (no distractors are used).
* Deterministic sample: seed 20261029, namespaces `eb-f-3/4/5`, round-robin over leaf counts.
  **Fresh pool: 30 three-leaf and 14 four-leaf; no five-leaf example remains**, so the 30-example
  target is 16 three-leaf + 14 four-leaf (stored in `sample.json`, which was written before any call).
  If fewer than 30 are run, the first N of that same ordered list are used.
* **Target 30; minimum 24 completed.** Fewer than 24 examples completed for all four systems and both
  conditions -> `INCONCLUSIVE`. No extrapolation, no substitution.

### Conditions (no outside retrieval)

* **COMPLETE (C1):** the pool is exactly the gold leaves.
* **MISSING_ONE (C2):** the same pool minus exactly one leaf, chosen by the seeded rule
  `order_key(seed, "removed-leaf", ...)` (deterministic per example).

Every system receives the whole pool for every query and can retrieve nothing else. COMPLETE and
MISSING_ONE are paired by original question.

## Model and settings

`gpt-6-luna`, reasoning `medium`, model seed 42, sampling seed 20261029, the committed rate card
(0.10 / 0.01 / 0.125 / 0.50 USD per million tokens), serial calls, same output ceiling for all
systems. No Sol. Prompts are frozen in the committed code (`premise-generation-v1`,
`sufficiency-judge-v1`, `sufficiency-answer-v1`) and are not edited after any result.

## Systems (exactly four)

| ID | System | Notes |
| --- | --- | --- |
| B0 | naive RAG | One search with the question over the pool, one cited answer or abstention. |
| B1 | iterative RAG | The existing simple iterative baseline (model-written follow-up queries, at most 3 rounds), against the same given pool; no new retrieval is possible. |
| M0 | gold-premise premise-only | Positive control. Premises = the gold leaf facts. One judge call returns RESOLVED/UNRESOLVED per premise from the whole evidence set; ANSWER iff all RESOLVED. No per-document stance, no formal closure. |
| M1 | generated-premise premise-only | Premises generated **once per question** from the question text alone, **stored, and reused verbatim in both conditions.** The generator never sees the proof tree, the decomposition, the gold leaves, the removed leaf, or the condition label. Same judge as M0. |

M1 generation format: `{"premises":[{"id":"p1","assertion":"..."}],"logic":"AND"}`, declarative
assertions, 1-8 premises. **No manual repair. No semantic retry.** A generation that does not parse /
validate is recorded as unusable and is **not retried** (the existing provider infrastructure has no
deterministic serialization retry for this call, so none is used). An example with unusable
generation makes M1 ABSTAIN in both conditions (`NO_USABLE_PREMISES`, no judge call) and **stays in
every denominator**.

### What counts as ANSWER

For M0 and M1 the decision is the sufficiency check itself: ANSWER iff every premise is RESOLVED
(each RESOLVED verdict must cite supplied evidence ids; verdicts that are malformed or ungrounded are
errors, never answers). The answer text is produced afterwards from the cited evidence and **never
changes the decision**. For B0/B1 the decision is whether the system returns an answer rather than
abstaining. A request or schema error counts as "no answer". `UNKNOWN` is never treated as `FALSE`:
an abstention is a statement about insufficiency of evidence, not about the claim.

## Metrics

Primary: **J = answer rate on COMPLETE - answer rate on MISSING_ONE**, per system.

Secondary: complete coverage (answer rate on COMPLETE); missing-evidence false-answer rate (answer
rate on MISSING_ONE); abstention rate; strict J on final non-null answers; answer exact match and
normalized (SQuAD) match **reported separately** among complete-evidence answers (a weak proxy
for free-text science answers; no verdict uses answer text); model calls, prompt/completion tokens,
latency, logical and new-API cost; M1 generation failure rate.

M1 diagnostics (deterministic only; **no LLM judge of premise correctness**): number of premises,
structural validity (parses, 1-8 premises, unique ids, non-empty assertions, `AND`), duplicate-premise
rate, non-assertion rate by surface-form syntax flags, proof-graph conversion success, generation
tokens and cost.

Statistics: paired seeded bootstrap over questions (10,000 resamples) for J per system and for
M1 - B0, M1 - B1, M1 - best baseline, M1 - M0, and M0 - best baseline, 95% intervals.

## Decision rule (fixed now)

Let M1 be the generated-premise system, m0 the gold-premise control, and `best` =
max(J(B0), J(B1)) (the best **non-premise** baseline).

M1 is **viable** only if **all** hold:

* **A.** M1 complete coverage >= 0.90.
* **B.** J(M1) >= 0.65.
* **C.** J(M1) - best >= +0.25, **or** the bootstrap 95% interval of J(M1) - best has a lower bound
  above 0 **and** the point estimate is >= +0.20.
* **D.** J(M1) >= 0.75 x J(M0).
* **E.** At least 90% of the M1 examples are structurally usable without repair.

Definitions used by the classification:

* **M0 strong:** M0 complete coverage >= 0.90 **and** J(M0) >= 0.65 **and** J(M0) - best >= +0.25.
* **No-signal flags** (any one set means M1 is not meaningfully better than the baselines):
  J(M1) - best < +0.10; or M1 complete coverage < 0.75; or J(M1) < 0.40.

Final classification (exactly one):

| Class | When |
| --- | --- |
| `INCONCLUSIVE` | Fewer than 24 completed fresh examples, dataset corruption, infrastructure failure, or an unrecoverable API/ledger failure. **Not** for disappointing results. |
| `PROMISING_COMPONENT` | A, B, C, D and E all hold. |
| `ORACLE_DEPENDENT` | M1 not viable, M0 strong, and no no-signal flag is set (M1 keeps partial signal but materially falls short of the bar). |
| `NO_END_TO_END_SIGNAL` | Otherwise: M1 not viable and either a no-signal flag is set (not better than baselines / poor complete coverage / weak separation) or the positive control M0 is not strong. |

This partition is exhaustive and the inputs are computed mechanically by `epistemic-search rv2-f run`
(`decision.json`). Boundary behaviour is unit-tested (coverage 27/30 passes and 26/30 fails;
23 completed examples -> INCONCLUSIVE; 24 -> classified).

## Mandatory stop rule

* `ORACLE_DEPENDENT` or `NO_END_TO_END_SIGNAL` -> **the research project stops.** Premise-only is
  archived as a component result. No further controller, formal representation, query-generation,
  premise-state variant, stance system, M2 repair, or EntailmentBank experiment is proposed, and RV3
  is not started.
* `PROMISING_COMPONENT` -> only a fresh **RV3 design** may be proposed (untouched realistic multi-hop
  QA/retrieval questions; naive RAG, iterative RAG, generated-premise premise-only; matched model,
  retrieval and token budgets; selective risk/coverage; a missing-evidence controlled subset). It is
  not run without explicit approval.
* `INCONCLUSIVE` follows the infrastructure/sample rules above and is not a pass.

## Cost estimate and hard cap

Hard cap **$0.40** for run id `rv2-f-generated-premises-v1` (enforced by the persistent ledger on
every request; the $50 project cap is unchanged). Pre-run planning estimate from the RV2-C/E per-case
costs: roughly **$0.05-0.15** for 30 examples (naive and iterative RAG cost well under a cent per
case; the sufficiency system is two or three short calls per case plus one generation per question).
`epistemic-search rv2-f estimate` runs one example first (kept as data), and the committed rule
chooses **30 examples if the projected cost is within 80% of the cap, otherwise 24 (never fewer)**;
if even 24 cannot fit, the run stops and I ask. Stop rule for spend: any ledger refusal or halt stops
the run; incomplete examples are not completed by substitution, and a halt is audited, not bypassed.

## Outputs

`docs/results/rv2/rv2_f/`: `sample.json`, `cases.jsonl` (every system, example, condition, with the
premises used), `generated_premises.jsonl` (raw responses and flags, failures included),
`results.json`, `estimate.json`, `decision.json`, `ledger_halt_audit.md`. All examples and failures are
kept; nothing is filtered.

## What this cannot show (disclosed in advance)

* **Leaf-only pools are the most favourable evidence setting.** There are no distractors and no
  retrieval step; success here does not show the idea works on realistic retrieval.
* **Generated premises need not equal the gold leaves.** If a generated premise set does not
  require the removed leaf, M1 may rightly answer in MISSING_ONE and J will be capped below 1 through
  no fault of the judge; equally, overlapping leaves make the MISSING_ONE ground truth imperfect (see
  RV2-C). Both effects penalize M1 relative to M0 in D and are accepted.
* **Answer text is a weak proxy** (free-text science answers); the verdict never uses it.
* One dataset (grade-school science), 24-30 examples; intervals are over examples.
* A fresh pool without five-leaf examples (16 + 14 sample); a different dataset or more complex
  questions may behave differently.

---

# Results (appended after the run; everything above is the unchanged pre-registration)

Pre-registration commit `313fd5c`. Files: [results.json](../results/rv2/rv2_f/results.json),
[decision.json](../results/rv2/rv2_f/decision.json), [cases.jsonl](../results/rv2/rv2_f/cases.jsonl),
[generated_premises.jsonl](../results/rv2/rv2_f/generated_premises.jsonl),
[estimate.json](../results/rv2/rv2_f/estimate.json). Estimate probe: 1 example, $0.0011, so the
committed rule chose 30 examples. **30 of 30 examples completed for all four systems and both
conditions** (240 case rows, 30 generations); no ledger halt, no cap reached.
Run spend **$0.0327** of the $0.40 cap (probe included); no Sol.

## Classification: `NO_END_TO_END_SIGNAL`. The mandatory stop rule fired.

Sample: 16 three-leaf + 14 four-leaf fresh dev examples; the 59 ids used in RV2-B/C/E were
excluded and the overlap is empty.

| System | COMPLETE answer rate | MISSING_ONE answer rate | **J** | 95% CI of J | Errors |
| --- | ---: | ---: | ---: | --- | ---: |
| B0 naive RAG | 0.867 | 0.667 | 0.200 | [0.00, 0.40] | 0 |
| B1 iterative RAG | 0.933 | 0.667 | 0.267 | [0.13, 0.43] | 12 (11 round-limit stops, 1 uncited source) |
| M0 gold premises | **1.000** | 0.067 | **0.933** | [0.83, 1.00] | 0 |
| M1 generated premises | **0.167** | 0.033 | **0.133** | [0.00, 0.30] | 1 (ungrounded verdict) |

Paired differences in J (95% bootstrap): M1 - B0 -0.07 [-0.30, +0.17]; M1 - B1 -0.13 [-0.37, +0.10];
M1 - best baseline -0.13 [-0.37, +0.10]; **M1 - M0 -0.80 [-0.97, -0.60]**; M0 - best baseline
+0.67 [+0.50, +0.83].

### Viability of M1 (all five required)

| Condition | Result |
| --- | --- |
| A complete coverage >= 0.90 | **fail** (0.167) |
| B J >= 0.65 | **fail** (0.133) |
| C advantage over the best baseline >= +0.25 (or CI > 0 and >= +0.20) | **fail** (-0.133) |
| D J(M1) >= 0.75 x J(M0) | **fail** (0.133 vs 0.700 required) |
| E >= 90% structurally usable | pass (30/30) |

M0 was strong (coverage 1.00, J 0.93, +0.67 over the best baseline), and all three no-signal flags
were set (delta over baselines < 0.10, M1 coverage < 0.75, J < 0.40). By the fixed partition that is
`NO_END_TO_END_SIGNAL`, not `ORACLE_DEPENDENT`.

### Generated-premise diagnostics (deterministic flags only)

Structurally usable 30/30 (100%); generation failures 0; mean 2.23 premises per question against
3.47 gold leaves; duplicate-premise rate 0.0; non-assertion rate 0.0; proof-graph conversion 30/30;
generation cost $0.0052 (16,894 tokens). **The generated premises are well-formed. They fail on
sufficiency, not on format.** M1 abstained in 90% of all cases and in 25 of 30 COMPLETE cases:
generated premises are general or derived statements (for example, "Burning gasoline or diesel
releases pollutants into the atmosphere"), which the verbatim leaf facts of the pool do not state
or entail on their own, so they stay UNRESOLVED even when the evidence is complete. No LLM judged
whether a premise is semantically correct, so this is a reading of the pattern, not a measured
premise-quality figure.

### Answer text, cost

Answer match among complete-evidence answers is a weak proxy: exact match B0 0.19, B1 0.04, M0 0.11,
M1 0.00; normalized match 0.50, 0.21, 0.36, 0.40 (small, differently sized denominators; no verdict
uses them). Logical cost for all 60 cases per system: B0 $0.004, B1 $0.006, M0 $0.009, M1 $0.010
(including $0.0052 generation). Calls: 60, 82, 92, 66.

### Degradation from gold to generated premises

COMPLETE answer rate 1.000 -> 0.167; MISSING_ONE answer rate 0.067 -> 0.033; **J 0.933 -> 0.133
(-0.80)**. M1's low false-answer rate on MISSING_ONE is not discrimination; it is blanket
abstention.

### Disclosures and limits

* B1's 11 round-limit stops are the existing iterative baseline's behaviour under the same 3-round
  ceiling (counted as no answer, as pre-registered). Even if all 12 B1 errors were answers, its J could
  rise by at most 0.2 and could not make M1 viable.
* One M1 case errored on an ungrounded judge verdict (RESOLVED without citing evidence) and is counted
  as no answer, as pre-registered; it was not repaired.
* Leaf-only pools make the gold premises' verbatim match unusually easy for M0; M1 premises need not
  match the leaves. Both effects are inherent to the pre-registered design and were disclosed in
  advance. The result does not show that no better premise generator exists; it shows this
  single-pass question-only generator does not preserve the signal.
* 30 examples on one dataset; sample-level intervals are over questions.

## Answer to the go/no-go question

**No.** Automatic premise generation did not preserve the premise-only sufficiency signal: J fell
from 0.93 with gold premises to 0.13 with generated premises, no better than naive RAG. The
mandatory stop rule fires: the research project stops here and premise-only is archived as a
component result that works only given good premises.
