# RV2-C: controlled epistemic-state experiment (sufficiency under missing evidence)

Date: 2026-10-30. Code: tag `epistemic-search-v1.1.1` plus the opt-in oracle-structure hook.
Plan and decision rule (committed before any call): [RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md).
All cases, with gold, pool composition, answers, decisions, blockers, tokens, calls, latency and
cost: [results.json](../results/rv2/rv2_c/results.json), [cases_oracle.jsonl](../results/rv2/rv2_c/cases_oracle.jsonl),
[estimate.json](../results/rv2/rv2_c/estimate.json).

## Design as run

EntailmentBank dev (task 2), **27 examples** (9 each with 3, 4 and 5 leaves; chosen by the
committed rule, which allowed 9 per size because the planning cost fit 80% of the cap), seed
20261029. Four evidence conditions per example: **C1** all gold leaves, **C2** one leaf removed,
**C3** C2 plus the 4 highest-relevance dataset distractors, **C4** C1 plus the same distractors.
Every system gets the whole pool for every query and can retrieve nothing outside it. Systems:
closed-book (pool-independent), naive RAG given the pool, premise-only given the **gold proof
graph**, Epistemic Search given the **gold proof graph**. 108 cases per system (closed-book: 27).
Model `gpt-6-luna`, reasoning `medium`, seed 42. Run cost **$0.0478 new API spend** (cap $0.50);
no error stopped the run and the cap was not reached.

## Results (pre-registered metrics)

J = answer rate when the evidence is complete (C1∪C4) minus answer rate when it is incomplete
(C2∪C3). A system that always answers has J ≈ 0; a perfect sufficiency detector has J = 1.

| System | Answer rate C1 / C2 / C3 / C4 | Coverage on complete | Unsupported-answer rate | **J** |
| --- | --- | ---: | ---: | ---: |
| Closed-book | 0.96 in every condition (ignores the pool) | 0.963 | 0.963 | 0.00 |
| Naive RAG (pool given) | 0.96 / 0.96 / 0.93 / 0.96 | 0.963 | **0.944** | 0.019 |
| Premise-only (gold graph) | 0.96 / **0.04 / 0.15** / 1.00 | **0.981** | **0.093** | **0.889** |
| Epistemic Search (gold graph) | 0.96 / **0.33 / 0.37** / 0.93 | 0.944 | **0.352** | **0.593** |

* Epistemic Search separates complete from incomplete evidence far better than naive RAG or
  closed-book (J 0.59 against 0.02), and it does **not** get there by abstaining everywhere
  (it answers 94% of complete cases).
* Premise-only, given the same gold graph, separates them **better** (J 0.89), and it is not
  trivially cautious either (it answers 98% of complete cases).
* Premise-only had 1 error out of 108 cases (a duplicate citation in its output), counted as no
  answer. Epistemic Search had none.

### Pre-registered questions

| Q | Result | Verdict |
| --- | --- | --- |
| Q1 gold structure and evidence → behaves correctly | coverage on complete 0.944 (≥ 0.80 met); answer-hit rate 0.118 (needs ≥ 0.70) | **UNDETERMINED** (see the answer-matching caveat) |
| Q2 detects insufficiency better than simpler baselines | ΔJ = J(ES) − max(J(premise-only), J(naive)) = **−0.296**, 95% CI **[−0.463, −0.130]** | **NO** |
| Q3 distractors do not cause false closure | ES answer rate in C3 0.370; best baseline 0.148 | **NO** |
| Depth (for the architecture criterion) | J 0.615 for depth ≤ 2 (13 examples), 0.571 for depth ≥ 3 (14 examples) | not triggered |

Q2 is not a near miss and not noise: the whole interval is below zero, so on this data
Epistemic Search is reliably **worse** than premise-only at telling sufficient from
insufficient evidence.

## Why: the formal state closes too easily

Epistemic Search answered in 19 of the 54 missing-leaf cases. In **all 19** the removed leaf's
claim had been judged SUPPORTED by the stance step (it closes a premise when any single
document supports it). The supporting document was **another gold leaf** of the same proof in
15 cases and a high-relevance distractor in 4. EntailmentBank leaves overlap in meaning, and a
distractor chosen for relevance can paraphrase a leaf, so a claim is often "supported" by text
that is not the leaf the gold proof requires. The premise-only baseline reads the same premises
and the whole evidence set and decides what is still unresolved; it answered only 5 of the same
54 cases (4 of them also answered by Epistemic Search).

The Epistemic Search stop on complete evidence is rare (3 of 54 complete cases, in 2 examples,
all `NO_PROGRESS`). It localizes the blocker exactly (the removed leaf is the only unresolved
premise) in 64.8% of missing-leaf cases, and the formal state is complete in 94.4% of
complete-evidence cases. Results do not depend materially on proof size (coverage 0.89–1.00 and
unsupported rate 0.33–0.39 across 3, 4 and 5 leaves).

## Cost

| System | Logical model calls | Logical cost | New API cost (cache reuse from RV2-B) |
| --- | ---: | ---: | ---: |
| Closed-book | 27 | $0.0013 | – |
| Naive RAG | 108 | $0.0087 | $0.0087 |
| Premise-only | 157 | $0.0205 | $0.0152 |
| Epistemic Search | 2,711 | **$0.1986** | $0.0230 |

Epistemic Search makes about 17 times as many model calls and costs about ten times as much
(logical cost) as premise-only for a lower J. Most of its calls are one extraction per
(premise, document) pair. (The new-API figure for it is low only because RV2-B had already paid
for most of the identical requests.)

## Limits that bear on how to read this

1. **The ground truth for C2/C3 is imperfect.** The gold proof says the removed leaf is
   required, but because leaves overlap in meaning, a defensible reading can sometimes support
   the claim from what remains. This favours stricter systems on J. It does not rescue
   Epistemic Search from Q2, because premise-only is judged on the same ground truth and is
   not abstaining indiscriminately (98% coverage on complete evidence), but it means "false
   answer" in C2/C3 is "answer not supported by the gold proof", not "provably wrong".
2. **C3 uses the hardest distractors** (highest dataset relevance), a deliberate stress test.
   Q3 is the least robust of the three questions.
3. **Answer matching is weak.** The systems' answers are correct paraphrases of gold sentences
   but token-F1 ≥ 0.5 marks most as misses (hit rate 0.12 for Epistemic Search, 0.21 for
   premise-only, 0.44 for naive RAG). This is why Q1 is UNDETERMINED rather than YES; coverage and J, which carry the
   verdict, do not use answer text. `selective_risk` in `results.json` mixes in these misses and
   should not be read.
4. **Both structured systems were given the oracle graph.** This is the most favourable setting
   for Epistemic Search, so its shortfall here is not attributable to decomposition or
   retrieval; RV2-B shows the generated front end is worse.
5. 27 examples; the intervals above are bootstrap intervals over examples (10,000 resamples).
