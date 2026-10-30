# RV2-G: evidence-grounded decomposition (pre-registered)

Date: 2026-10-30. **Committed and pushed before any RV2-G model call.** No threshold, rule, prompt
or sample below is changed after a result is seen. This is a diagnostic go/no-go experiment, not
Epistemic Search v1.

## Frozen context (not modified or reinterpreted here)

* Original Epistemic Search: `NOT_PROMISING_IN_CURRENT_FORM` ([RV2_DECISION.md](RV2_DECISION.md)).
* Per-document stance / formal closure: dropped. Premise-state (M2 of RV2-E): no demonstrated value.
* Question-only generated premises: `NO_END_TO_END_SIGNAL` ([RV2-F](RV2_F_GENERATED_PREMISES.md):
  J 0.13, complete coverage 0.17, 30/30 structurally valid).
* Gold premises + whole-evidence sufficiency: strong positive control (RV2-F M0: J 0.93).

Not revived: per-document stance, belief masses, formal closure, Z3, premise-state M2, premise-directed
retrieval, contradiction machinery. `src/epistemic_search/grounded.py` contains none of them; a test
asserts the forbidden constructs do not appear in it.

## Hypothesis

> A decomposition generated before seeing evidence may operate at the wrong abstraction level. A
> decomposition grounded in the actual evidence may produce evidence-level proof obligations that
> preserve the strong sufficiency signal observed with oracle premises.

Mechanism observed in RV2-F: the generated premises were well formed but general or derived
("Burning gasoline or diesel releases pollutants into the atmosphere"), so verbatim leaf facts did not
resolve them and M1 abstained in 25 of 30 complete-evidence cases. RV2-G tests exactly one correction:
generate the structure from **question + the evidence actually available**, and make the structure
distinguish **evidence-level facts** (checked against the evidence) from **derived claims** (resolved
only by their dependencies).

## Ledger audit

[ledger_halt_audit.md](../results/rv2/rv2_g/ledger_halt_audit.md): no project or run halt, 0 pending,
all 3,561 charges settled; nothing to clear. The ledger is not bypassed; every request is reserved and
settled by it and the cap below is enforced by it.

## Data

* **EntailmentBank task 2, dev split only** (commit `daac2fdb7ab52ec3ef8f2953f59288c1edd7c2f0`);
  test is never read.
* **Fresh examples only.** Excluded: every id in the RV2-B, RV2-C, RV2-E and RV2-F samples
  (**89 distinct ids**; manifest in [exclusions.json](../results/rv2/rv2_g/exclusions.json)). RV2-A/D and the
  earlier pilots used other datasets, so no further EntailmentBank id was seen. Seen examples are never
  substituted back. `sample.json` records `overlap_with_excluded`, which must be empty.
* **Eligibility, fixed now: 2-6 gold leaves and a proof that converts to a valid graph** (no duplicate
  leaf text). **This is wider than RV2-F (3-5)**, and the reason is a supply constraint, not a choice
  from results: after RV2-F only 14 fresh three-leaf and no fresh four- or five-leaf dev examples remain;
  restricting to 3-5 leaves would give 14 examples and force `INCONCLUSIVE`. The fresh pool is
  2 leaves: 41, 3: 14, 6: 16 (7+: 27, not used).
* Deterministic sample: seed 20261029, namespaces `eb-g-<size>`, round-robin over sizes. **Target
  30 = 10 two-leaf + 10 three-leaf + 10 six-leaf** (ids in [sample.json](../results/rv2/rv2_g/sample.json),
  written before any call). If fewer than 30 are run, the first N of that same ordered list are used.
* **Target 30; minimum 24 completed** for all four systems and both conditions. Fewer -> `INCONCLUSIVE`.
  No extrapolation, no substitution.

### Conditions (no outside retrieval)

* **COMPLETE (C1):** exactly the gold leaves.
* **MISSING_ONE (C2):** the same pool minus exactly one leaf, chosen by the seeded rule
  `order_key(seed, "removed-leaf", ...)` over the gold proof tree's leaves. No distractors.

Every system receives the whole pool and can retrieve nothing else. COMPLETE and MISSING_ONE are paired
by original question. A two-leaf example's MISSING_ONE pool has a single document.

## Model and settings

`gpt-6-luna`, reasoning `medium`, model seed 42, sampling seed 20261029, the committed rate card
(0.10 / 0.01 / 0.125 / 0.50 USD per million tokens), serial calls, same output ceiling for all systems.
No Sol. Prompts are frozen in code (`premise-generation-v1`, `evidence-grounded-decomposition-v1`,
`sufficiency-judge-v1`, `sufficiency-answer-v1`) and are not edited after any result.

## Systems (exactly four)

| ID | System | Notes |
| --- | --- | --- |
| B0 | naive RAG | One search with the question over the pool, one cited answer or abstention. No decomposition. |
| B1 | question-only premise-only | The RV2-F M1 architecture **unchanged and not improved**: premises generated once per question from the question alone, reused in both conditions, whole-evidence RESOLVED/UNRESOLVED judge, ANSWER iff all RESOLVED. Negative control. |
| M0 | gold-premise premise-only | Positive control: gold leaf facts as premises, same judge. |
| M2 | evidence-grounded decomposition | The system under test (below). |

### M2

1. **Decompose (one call per condition).** The model sees only `{question, evidence}` where evidence is
   the sources actually present in that condition. It never sees the gold proof tree, the removed
   leaf's identity, the condition label, any benchmark metadata, or any evidence not present (a test
   asserts the prompt payload is exactly question + present evidence). Output schema:
   `evidence_facts[{id, assertion, supported_by:[source ids]}]`,
   `derived_claims[{id, assertion, depends_on:[ids]}]`, `required_for_answer:[ids]`. The prompt asks the
   model to list **every elementary fact the answer requires, whether or not the evidence provides it**,
   with `supported_by: []` when none of the supplied evidence does, and to write derived claims for
   conclusions that follow from combining facts. It is not told how many leaves exist.
2. **Structural check (deterministic).** Usable iff it parses against the schema, ids are unique,
   every `supported_by` id is a supplied source, every `depends_on` and `required_for_answer` id
   exists, and derived claims have dependencies and no cycles. Anything else is recorded as unusable;
   M2 ABSTAINs (`NO_USABLE_DECOMPOSITION`, no judge call), the example **stays in every denominator**.
   There is no repair and no retry.
3. **Judge evidence facts.** One call with the same `sufficiency-judge-v1` prompt as B1/M0: every
   evidence fact is judged RESOLVED/UNRESOLVED from the WHOLE evidence set (a RESOLVED verdict must
   cite supplied sources). The decomposer's `supported_by` is **not** shown to the judge and is not a
   verdict.
4. **Resolve (deterministic).** A derived claim is resolved iff every dependency is resolved.
   **ANSWER iff every node in `required_for_answer` is resolved**, else ABSTAIN. The answer text is
   produced afterwards from the supplied evidence and never changes the decision.

Errors (request failures, malformed or ungrounded verdicts) count as no answer and are never repaired.
`UNKNOWN` is never treated as `FALSE`.

## Metrics

Primary: **J = answer rate on COMPLETE - answer rate on MISSING_ONE**, per system, using the
sufficiency decision (B0: whether it returns an answer). Secondary: complete coverage; missing-evidence
false-answer rate; abstention rate; strict J on final non-null answers; answer exact and normalized match
reported separately (weak proxy, no verdict uses them); calls, tokens, latency, logical and new-API cost.

M2 deterministic structure statistics (no LLM judge): evidence facts and derived claims per example,
graph depth, required nodes, compression ratio (required evidence facts / evidence sentences),
duplicate-claim count, malformed rate, dangling-reference decompositions, decomposition size, facts with
no cited support, facts whose cited support the judge rejected, share of required nodes that are
evidence facts, and `required == all evidence` (a *degenerate-copy* flag, reported by condition, never an
automatic failure; with leaf-only pools it is expected in COMPLETE, whereas in MISSING_ONE it means the
decomposer only described what it saw).

**Diagnostic for every M2 case without a final answer** (mechanical, no model judge), by condition:
`STRUCTURAL_ERROR` (no usable decomposition, or an unusable judgment), `EVIDENCE_FACT` (a required
evidence fact is unresolved), `DERIVED_CLAIM` (all required evidence facts resolved but a required
derived claim is not, because a non-required dependency is unresolved), `ANSWER_GENERATION_FAILURE`
(decision ANSWER but no final answer). The unresolved required node ids are stored per case.

Statistics: paired seeded bootstrap over questions (10,000 resamples), 95% intervals for J per system and
for M2 - B1, M2 - B0, M2 - M0 (also M0 - B1).

## Decision rule (fixed now)

M2 is **promising** only if **all** hold:

* **A.** M2 complete coverage >= 0.90.
* **B.** J(M2) >= 0.65.
* **C.** J(M2) - J(B1) >= +0.30.
* **D.** J(M2) >= 0.70 x J(M0).
* **E.** >= 90% of M2 decompositions (all conditions of completed examples) parse and are structurally
  usable without repair.
* **F.** Not abstention-only: complete coverage satisfies A (high J from refusing almost everything
  does not count).

**STRONG_SIGNAL** (reported separately; does not change the classification): complete coverage >= 0.95
and J >= 0.75.

Classification (exactly one):

| Class | When |
| --- | --- |
| `INCONCLUSIVE` | Fewer than 24 completed fresh examples, data/infrastructure failure, or unrecoverable ledger/API failure. Never for disappointing results. |
| `EVIDENCE_GROUNDED_SIGNAL` | A-F all hold. |
| `PARTIAL_SIGNAL` | Not all of A-F hold, **and** M2 substantially beats B1 (J(M2) - J(B1) >= +0.20 with the bootstrap 95% lower bound above 0) **and** the signal is non-degenerate (complete coverage >= 0.50 and J(M2) >= 0.40). Every failed threshold is reported. |
| `NO_SIGNAL` | Otherwise: M2 does not materially outperform B1, or J remains weak, or complete coverage remains poor. |

The partition is exhaustive and mechanical (`decision.json`). Boundary behaviour is unit-tested
(coverage 27/30 passes, 26/30 fails; J retention exactly 0.70; recovery +0.27 fails C; 23 completed
examples -> INCONCLUSIVE; 24 -> classified).

## Interpretation rules

* **NO_SIGNAL:** stop this direction. No other decomposition architecture, better premise prompts, larger
  models, chain-of-thought variants, additional proof representations, more EntailmentBank experiments or
  retrieval redesign is proposed. The result is archived and the direction is closed.
* **PARTIAL_SIGNAL:** nothing continues automatically. I report the exact failed threshold, effect size,
  interval, observed failure mechanism and an effort estimate for one next experiment, and wait for approval.
* **EVIDENCE_GROUNDED_SIGNAL:** nothing is scaled and nothing is built automatically. I may only
  *propose* an "Evidence-Grounded Proof Search" architecture (acquire evidence first, then construct the
  proof state from what is known; target missing relations with a second retrieval) and wait for approval.
* RV3 is not started in any case.

## Cost estimate and hard cap

Hard cap **$0.30** for run id `rv2-g-evidence-grounded-v1` (the $50 project cap is unchanged), enforced by
the ledger on every request. Planning estimate from RV2-F (30 examples, four systems, $0.033) plus one extra
decomposition call and one judge call per M2 case: roughly **$0.06-0.12** for 30 examples. `epistemic-search
rv2-g estimate` runs the first sample example in full first (kept as data); the committed rule picks **30
examples if probe cost x 30 x 2 is within 80% of the cap, else 24; never fewer**, and stops and asks if even
24 would exceed the cap. Any ledger refusal or halt stops the run; incomplete examples are not completed by
substitution, and a halt is audited, not bypassed.

## Outputs

`docs/results/rv2/rv2_g/`: `exclusions.json`, `sample.json`, `estimate.json`, `cases.jsonl` (every system,
example, condition), `generated_premises.jsonl` (B1 generations, raw), `decompositions.jsonl` (every M2
decomposition, raw response and structure, failures included, never edited), `metrics.json`,
`decision.json`, `ledger_halt_audit.md`. All examples and failures are kept.

## What this cannot show (disclosed in advance)

* **Leaf-only pools are the most favourable evidence setting.** No distractors and no retrieval step;
  success here does not show the idea works with realistic retrieval or noisy evidence.
* **Evidence-conditioned decomposition can see the shape of the gold answer in the pool.** M2 reads the
  same sentences the gold proof was built from, in the COMPLETE condition. A positive result there partly
  measures how well it reads the supplied sentences, which the hypothesis intends, but is not a test of
  open-ended reasoning.
* **The gap must be noticed, not copied.** If the decomposer only describes the evidence it sees, M2 will
  answer in MISSING_ONE and J will be near 0; that failure is reported, not rescued.
* **MISSING_ONE ground truth is imperfect**: EntailmentBank leaves can overlap in meaning (see RV2-C), and
  a two-leaf pool with one document left is a very small test of "missing".
* The sample mixes two-, three- and six-leaf proofs; the 2-leaf stratum is easy and the 6-leaf stratum is
  hard, and 10 questions per stratum is too few for per-stratum conclusions. Strata are reported
  descriptively only.
* Answer text is a weak proxy; no verdict uses it. One dataset, 24-30 examples; intervals are over questions.
