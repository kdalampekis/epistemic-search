# RV2 decision

Date: 2026-10-30. Produced mechanically by `epistemic-search rv2-decision` from the four result
files under the rule committed before any model call
([RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md)); output in
[decision.json](../results/rv2/decision.json).

## Classification: `NOT_PROMISING_IN_CURRENT_FORM`

Rule that fired: **2, Q2 = NO.** With gold proof structure and gold evidence in a controlled
missing-evidence test, Epistemic Search separated complete from incomplete evidence
**significantly worse than a simpler baseline** that is given the same gold premises. The gold
upper bound failed, so by the pre-registered rule retrieval and decomposition are not blamed.

**What this classification does and does not say.**

* It is a statement about the architecture *in its current form* (per-document stance, formal
  closure of a premise when one document supports it, query built from premise plus question).
* It is **not** a finding that premise-aware reasoning has no value. In the same experiment the
  premise-only baseline, which uses the very same gold premises, did best (see below). The
  evidence points at the formal-state machinery, not at the premise idea.
* It does not say the idea cannot work. It says this implementation did not beat a cheaper
  alternative on the experiment designed to favour it.

## The five go/no-go questions

| Q | Answer | Evidence |
| --- | --- | --- |
| Q1. With gold structure and gold evidence, does Epistemic Search behave correctly? | **Partly.** It reaches the right proof state when evidence is complete (answers 94%, proof completed in 94%) but also answers in 35% of missing-leaf cases. Formally `UNDETERMINED`: the answer-matching proxy (token-F1) scored correct paraphrases as misses (hit rate 0.12). | RV2-C |
| Q2. Does it detect a removed leaf better than simpler baselines? | **No, the reverse.** J = 0.59 against 0.89 for premise-only (ΔJ = −0.30, 95% CI [−0.46, −0.13]). It beats naive RAG and closed-book (J 0.02 and 0.00). | RV2-C |
| Q3. Do distractors avoid false closure? | **No.** It answers 37% of C3 cases against 15% for the best baseline. | RV2-C |
| Q4. Does oracle structure beat generated structure? | **Yes, by a lot.** J 0.44 against 0.06 (0.46 against 0.08 on the 13 examples with a valid generated graph). 28% of generated graphs fail structural validation. | RV2-B |
| Q5. Does premise-directed retrieval find evidence more efficiently? | **No.** Gold-document recall 0.47 against 0.78 for iterative, and about equal to naive top-k (0.44). | RV2-D (partial) |
| Stance component works? | **Yes on matched pairs** (macro-F1 0.82; false-CONTRADICT 1.5% and 4.5%). It cannot test the mismatched-evidence failure RV1 found. | RV2-A |

## The twelve items

1. **Datasets and versions.** VitaminC `vitaminc.zip` (SHA-256 `49d82dc1…`); SciFact release
   `data.tar.gz` (`11c62128…`); EntailmentBank commit `daac2fdb7ab52ec3ef8f2953f59288c1edd7c2f0`
   (dataset v2); StrategyQA `strategyqa_dataset.zip` (`4911d85e…`, audit only); HotpotQA dev
   distractor, Hugging Face revision `1908d6af…` (the canonical host no longer resolves);
   2WikiMultiHopQA `data_ids_april7.zip` (`95df2bf5…`). HoVer not used. Manifests:
   `data/manifests/`.
2. **Sample sizes.** RV2-A 100 + 100 items. RV2-B and RV2-C: 18 and 27 EntailmentBank dev
   examples × 4 conditions. RV2-D: 46 of 144 planned questions (23 per dataset). Seed 20261029;
   model seed 42.
3. **Gold metrics.** See [RV2_A](RV2_A_STANCE.md), [RV2_B](RV2_B_ORACLE_STRUCTURE.md),
   [RV2_C](RV2_C_EPISTEMIC_STATE.md), [RV2_D](RV2_D_RETRIEVAL.md); every per-item prediction and
   metric is in `docs/results/rv2/`.
4. **API spend.** **$0.2344 of the $1.50 RV2 cap** (A $0.0268, B $0.0862, C $0.0478, D $0.0737
   including a $0.0021 reservation held by the halt). Whole project $0.3024 of $50. No Sol.
5. **What failed.** Epistemic Search's sufficiency detection (Q2, Q3); the generated front end
   (28% invalid graphs; valid ones state derived claims a single document cannot support);
   premise-directed retrieval (Q5); the answer-matching proxy (a measurement failure, not a
   system one).
6. **What worked.** The stance component on matched pairs; Epistemic Search over naive RAG
   and closed-book on missing evidence; the premise-only baseline given gold premises; the
   no-progress and span fixes (v1.1) doing what they were meant to; the cost caps.
7. **Oracle structure.** Large improvement over the model-generated structure (Q4), and the
   system reaches complete proofs with it. It still answers when a leaf is missing.
8. **Gold evidence.** With complete gold evidence the system answers 94% and closes the proof
   in 94% of cases; the answers are semantically right but not token-matching.
9. **Required evidence removed.** Epistemic Search still answered 35% of the time. In all 19
   RV2-C cases (and 17 of 17 in RV2-B) the removed leaf's claim had been judged supported, by
   another gold leaf in 15 of 19 and by a paraphrase distractor in 4.
10. **Retrieval efficiency.** Premise-directed retrieval did not beat naive top-k and was far
    below iterative retrieval (Q5 = NO), at 3–10 times the model calls.
11. **Classification.** `NOT_PROMISING_IN_CURRENT_FORM`.
12. **Is RV3 justified?** **Not as originally conceived.** A fresh-question benchmark
    comparison of the current Epistemic Search against baselines is not scientifically
    justified: the controlled upper bound already shows it losing to a simpler system, and
    scaling would spend money to confirm that. What the evidence does support is a narrow,
    cheap follow-up on a different question; see the options below.

## What the results point at (not yet tested)

These are hypotheses suggested by the traces. None was implemented, and none is claimed.

1. **Premise closure by a single document is too permissive.** It closes a premise when any one
   document supports it, which lets overlapping text stand in for a required fact. The premise-only
   baseline, which judges the whole evidence set against the premises, did far better. Test the
   premise-only variant, or a closure rule that requires the supporting document to be
   *new* to that premise, as the candidate core.
2. **The premise-to-query rule wastes searches.** Premise text plus the whole question returns
   the same paragraphs again (36–40% duplicates). Model-written queries do better.
3. **The generated front end needs claims one document can settle** (28% were invalid; valid
   ones were derived statements). The oracle result says structure is worth getting right.

No grounded-stance architecture (an RV2-E) is proposed or built: RV2-A did not show systematic
stance errors on matched evidence, so it does not point there. RV1's mismatched-evidence finding
remains open and untested by RV2.

## Disclosures and limits

* **v1.1.1.** The no-progress guard in tag `v1.1` compared query-hashed evidence ids and did not
  fire when it should. I corrected it as tag `v1.1.1` (the `v1.1` tag was not moved), after
  seeing it in a probe. RV2-A ran on v1.1 and is unaffected; RV2-B/C/D ran on v1.1.1. The
  correction changes search counts and stop reasons, not any answer or abstain outcome. The
  superseded probe files are kept.
* **RV2-D is partial** (46 of 144 questions) because of the ledger halt described there; the
  halt is still in force and I have not cleared it.
* **The C2/C3 ground truth is imperfect.** EntailmentBank leaves overlap in meaning, so some
  "answers without the leaf" are defensible. This favours strict systems on J. It does not
  change Q2, because premise-only is judged on the same truth and answers 98% of complete cases.
* **Answer matching is a token-F1 proxy.** Coverage and J, which carry the verdicts, do not use
  answer text.
* **Small samples.** 27 and 46 examples; the key intervals exclude zero, but the figures should
  be read as large effects on small data.
* **RV1 is model-assisted** (GPT-5.6 Sol) and was not human-verified; RV2 does not depend on it.
* Not done: StrategyQA (not convertible; no model run), HoVer, any grounded-stance work, RV3.

## Options for you

1. **Stop here** and treat the architecture as negative in its current form.
2. **A small, cheap follow-up (about $0.4–0.5 estimated, since fresh examples cannot reuse the cache):** replicate RV2-C on fresh
   EntailmentBank examples comparing premise-only against a closure variant of Epistemic Search
   that requires the supporting document to be new to that premise. It would test hypothesis 1
   only and needs your approval for any implementation.
3. **Resume RV2-D** to 144 questions. It needs a human decision to clear the ledger halt (see
   the report); the expected cost is about $0.2.
