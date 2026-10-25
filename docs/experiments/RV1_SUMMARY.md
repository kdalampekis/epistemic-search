# RV1 research summary

Date: 2026-10-24. API cost of this step: **$0** (cumulative project spend unchanged at
$0.067952575). RV0 outputs are frozen and unmodified; RV2 has not started.

> **Disclosure.** All 22 annotation files were produced by **GPT-5.6 Sol**
> (`openai-gpt-5.6-sol-primary`) from the frozen RV0 traces, benchmark gold fields and the
> generated sheets. They are **model-assisted annotations, not independent human ground
> truth**, from a single assessor, with no second annotator and no human spot-check yet.
> The system under test used Luna, so the assessor and the system are from related model
> families. Everything below is a description of what that one assessor concluded.

## Validation and provenance

* `rv1-validate --require-complete`: 22/22 `COMPLETE`, 0 blank fields, every read-only
  context hash matching the committed manifest.
* One mechanical repair, no judgment touched: in `13_2wiki_a0b2a4ce0baf.yaml` the document id
  `4326252e2819` had been rewritten as `.inf` by a YAML 1.2 round trip (it reads as an
  exponent). It was restored to `'4326252e2819'` at the two positions where the committed
  blank file has it. The dumper now quotes such ids, with a test.
* The annotation diff is large because every judgment block changed; the hash check shows no
  `context` block did.
* Oracle attestation `authored_before_viewing_generated`: YES 18, NO 4 (cases 1, 2, 14, 15).
  A model that reads the whole file cannot be verified to have been blind, so even YES is
  self-reported.

## A. Observations supported by the completed annotations

Counts are over 22 questions (44 method-cases) and carry no statistical weight.

**Root cause (primary label).**

| Primary | Epistemic Search (22) | Premise-only (22) | Both (44) |
| --- | ---: | ---: | ---: |
| RETRIEVAL_ERROR | 7 | 12 | 19 |
| NO_IDENTIFIED_FAILURE | 3 | 4 | 7 |
| DECOMPOSITION_ERROR | 1 | 4 | 5 |
| STANCE_ERROR | 5 | 0 | 5 |
| EVIDENCE_EXTRACTION_ERROR | 4 | 0 | 4 |
| CONTROLLER_ERROR | 1 | 1 | 2 |
| UNCERTAIN | 1 | 1 | 2 |

Secondary labels: CONTROLLER_ERROR 14 (4 / 10), DECOMPOSITION 4, RETRIEVAL 4,
QUERY_GENERATION 2, ANSWER_GENERATION 1, FORMALIZATION 1, STANCE 1. The protocol's
"earliest sufficient stage" rule makes later stages such as the controller look smaller as
primary causes than they are as contributors. BELIEF_AGGREGATION and FORMALIZATION are never
primary.

**Outcomes as judged.** Epistemic Search: 14 abstentions (12 judged appropriate given the
evidence it had), 4 execution errors, 4 answers (3 correct, 1 wrong: case 17). Premise-only:
18 abstentions (15 appropriate), 4 answers (all judged correct). Three answers scored as
exact-match mismatches were judged semantically correct (cases 4, 8, 20).

**1. Decomposition.** Generated decompositions are judged semantically correct in 17/22 and
complete in 17/22, but 9/22 contain unnecessary premises, 5/22 miss required ones, and the
AND/OR structure matches in only 13/22. At premise level (80): 41 are not assertions (28
task verbs, 7 questions, 6 "whether" clauses), 65 necessary, 77 atomic, 77 well-formed. The
non-assertion judgments coincide exactly with the lexical flag, but the assessor saw that
flag, so this is not independent confirmation. Of the 13 questions containing a
non-assertion premise, 12 decompositions were still judged semantically correct.
Decomposition is primary for only 1/22 (Epistemic) and 4/22 (premise-only) cases.
*Assessment: phrasing alone is a weaker explanation than RV0 suggested; unbound entities,
unnecessary premises and missing dependency structure matter more.*

**2. Repeated queries / controller.** All 31 decisions followed by an exact repeat of an
earlier query (14 Epistemic, 17 premise-only) were judged not justified. 31 of 66
targeted rounds were not materially different from the previous one. Of the 10
`RESOLVE_CONFLICT` decisions, all 10 were judged inappropriate (they come from false
conflicts, below). Controller is primary in only 2/44 cases but secondary in 14.
*Assessment: the behaviour is real and undefended, but it is mostly a downstream amplifier
of retrieval and grounding failures, not the main cause.*

**3. Retrieval.** Retrieved documents contained what the round needed in 30 of 110 rounds
(27%). The original-question search succeeded for 7/22 questions. Across all rounds,
Epistemic Search reached needed information for 10/22 questions and premise-only for 7/22.
Targeted rounds succeeded 9/29 (Epistemic) and 7/37 (premise-only), so targeted retrieval
was not better than the first search. Queries were judged appropriate for their target in 54
of 66 targeted rounds, and the missing information was judged retrievable from the corpus in
70 of 76 applicable rounds (6 unsure). Benchmark gold titles were present in 71 rounds and
absent in 32. *Assessment: retrieval is the largest single bucket (19/44), and the corpus is
not the limit.*

**4. Extraction and strict span validation.** Of 195 extraction batches, 45 had decisive
evidence in the document and **none of the 45 was missed**; all 66 empty batches were
judged correctly empty. All six spans that failed strict validation (four from an NBSP-type
mismatch, two non-verbatim) were judged faithful in meaning; none entered the ledger.
In two of the four execution errors (cases 3 and 4) the discarded evidence was SUPPORT and
sufficient on its own; in case 4 premise-only answered correctly. *Assessment: the
abort-on-first-bad-span policy destroyed valid evidence; extraction recall itself looks good.*

**5. Stance and grounding.** 164 extracted items are 125 distinct (case, premise, span,
stance) tuples, because repeated searches re-extract the same document. The assessor's stance
was NEUTRAL 102, SUPPORT 45, UNSURE 17 and **CONTRADICT 0** at item level.

| System stance → assessor stance | Items (164 raw) | Distinct (125) |
| --- | ---: | ---: |
| SUPPORT → NEUTRAL | 27 | 21 |
| CONTRADICT → NEUTRAL | 13 | 5 |
| CONTRADICT → SUPPORT | 3 | 1 |
| NEUTRAL → SUPPORT | 4 | 3 |
| CONTRADICT → UNSURE | 4 | 4 |
| Disagreement among determinate | 47 / 147 (32%) | 30 / 108 (28%) |

Item-level counts overstate the problem because of duplication; the distinct figures are the
better ones. 79 of 125 distinct items were judged not to address their assigned premise.
Stance error rates are similar for assertion and non-assertion premises (14/53 vs 16/55),
so premise phrasing does not explain them.

**Are "contradictions" really grounding errors?** In this sample, yes. No true
contradiction exists in the annotated data, yet the system produced 20 CONTRADICT items (10
distinct spans). Five distinct spans were NEUTRAL (different event, entity, office or
unrelated fact: the 2012 Orange Bowl against the 2015 game, case 5; Hugler's other job
titles and an unrelated Noonan, case 8; a freight-use sentence against "ceased operating",
case 7; Boston's tree gift against a donor premise, case 6), one was SUPPORT (a placeholder
premise "director is D_A" with "directed by Leslie Goodwins", case 11), and four were UNSURE
(a "whether" premise that cannot be true or false, ConfRAG case 2). The five cases that
triggered `RESOLVE_CONFLICT` (5, 6, 7, 8, 11) are exactly these. The same grounding failure
appears on the SUPPORT side: in case 17 a wrong parent–child relation was accepted as
support and the system answered "George I" instead of "Louis V". **Consequence for
evaluation:** because the pilot contains no true contradiction, it cannot say anything
about contradiction detection (that needs RV6).

**6. Belief and formal layers.** Of 47 belief states the assessor judged the claim status
justified in 27 and unjustified in 20 (43%), and the formal conclusion appropriate in 37
and not in 10. These errors trace to the evidence layer; neither stage is a primary cause.

**7. Oracle decompositions.** 22 exported: logic AND 19, OTHER 3 (cases 2 and 21, ConfRAG
without a reference answer; case 12, below). 19 convert to `ProofGraph`, and **16 are both
convertible and attested as authored before viewing**. Oracles have 71 claims against 80
generated premises (generated more in 8 cases, fewer in 7, equal in 7).

## B. Likely implementation defects (correctable without changing the hypothesis)

1. **Strict span validation aborts the whole case on one bad span** (4/22 execution errors;
   all faithful; 2 lost sufficient SUPPORT). Normalise (Unicode, NBSP, dashes, quotes) with
   offsets mapped back to the original text, and reject the single item instead of the case.
2. **No no-progress guard.** An exact repeated query with unchanged state cannot help
   (31/31 unjustified). A guard should stop or move to another blocker. Choosing better
   queries is a modelling change, not a defect fix.
3. **Duplicate extraction on repeated documents** inflates item counts (164 raw vs 125
   distinct items); whether it adds cost is unmeasured because the pilot used a model-output cache.
4. **Reporting:** exact match alone penalises semantically correct answers (3 cases). Add a
   second metric for every method equally; do not replace the existing one.

## C. Failures that may indicate a weakness of the premise-aware hypothesis

These cannot be settled on this evidence; each needs a test that separates it from
implementation.

1. **Flat conjunctions of unbound premises cannot drive bridge-question retrieval.**
   "The crab type is known for sweet flesh" has no bound entity (case 15); structure matches
   in only 13/22; targeted queries returned the same document sets and were no better than
   the first search.
2. **The evidence layer adds failure modes** that premise-only does not have (stance 5,
   extraction 4 of 22 primary) without earlier benefit on this sample (premise-only 4 answers
   all correct; Epistemic 3 of 4). This is a statement about the current implementation, not
   proof the idea fails.
3. **Premise-versus-span stance is under-specified.** Without entity/event grounding it
   produces false conflicts that consume the budget. Whether a grounded design fixes it is
   an open modelling question, not a settled defect.

## D. Benchmark and label-quality issues

* **Case 12** (2Wiki, Time Out of Mind): the question asks for a place of birth and the
  reference answer is "Israeli"; the gold page says only "Israeli-American". Both methods
  are UNCERTAIN, and the oracle is OTHER.
* **ConfRAG cases 2 and 21:** no reference answer; their oracles are assessor-authored
  structure, not ground truth.
* **Exact-match strictness:** "Elsie Audrey Mossom" vs "Audrey Mossom", "Retina Display" vs
  "Retina", and a long form of "Secretary of Labor" (cases 4, 8, 20).
* The pilot has no true contradiction, so conflict handling is unevaluated.

## E. Unresolved

* How much would an independent human change these labels? Cases the findings lean on most
  are 5, 6, 8, 12 and 17; a human should check them, plus a stratified sample of about 30
  stance items, before labels drive code.
* Did the assessor anchor on the lexical flag and on the system's stance shown in context?
* Would oracle decomposition help, and does retrieval remain the bottleneck regardless?
* Does k = 2 lexical retrieval, rather than premise-directed querying, explain the gap to
  iterative RAG (gold-title recall 0.74 vs 0.46)? Iterative RAG was not annotated.
* Does a grounded stance check remove the false conflicts without losing true ones?
* Anything about calibration, contradiction detection, or stronger models.

## Proposed RV2 (not started)

Principle: fix defects, test one modelling change at a time, never tune on a test set; the 22
questions stay development data and RV3 uses fresh disjoint questions.

**RV2-0 (free, before any change).** Human spot-check of the five cases above and about 30
stance items; record agreement with the Sol labels. If agreement is poor, stop and revisit RV1.

**RV2-1 Defect fixes** (code, offline tests, replay with HTTP disabled): span repair with
non-fatal item rejection (B1) and a no-progress guard (B2), nothing else. Freeze as
`epistemic-search-v1.1`. Report the unchanged v1 results alongside.

**RV2-2 Re-run the 22 development questions** with v1.1 for Epistemic Search and
premise-only. Compare outcome types against v1. Descriptive only.

**RV2-3 Diagnostic 2×2 on the development set:** {generated, oracle decomposition} ×
{retrieved, gold-document pool}, Epistemic Search, on the 16 blind convertible oracles. It
separates decomposition from retrieval from downstream reasoning. Flat AND oracles do not
encode bridge dependencies, so this under-tests hypothesis C1; say so in the report.

**RV2-4 One modelling candidate, labelled as such:** entity/event-grounded stance
extraction, scored first offline against the annotated distinct items (only after RV2-0
confirms the labels) and then in the development re-run. No claim from it.

**Estimated API cost.** Using the logged pilot costs (Epistemic Search about $0.0008 per
question, 10 model calls; premise-only about $0.0009), the expected total is about
**$0.10**. Using the project's conservative token-ceiling bound ($0.029 per method-case),
the ceiling is about **$3**: RV2-2 $1.3, RV2-3 $1.4 (48 runs), RV2-4 $0.2. Cumulative
spend would stay below about $3.1 of the $50 cap. Per `research_budget.md`, publish the
estimate and bound before running anything above $1.

**Should an oracle-decomposition experiment precede any larger benchmark?** Yes. It is
cheap, it separates the two readings (premise-aware reasoning does not help, versus it helps
but automatic premise extraction is poor), and retrieval being the largest bucket means it
must be crossed with gold documents or it will mislead. But treat it as a development
diagnostic on contaminated, single-assessor data. The first claim-bearing comparison is RV3
on fresh questions with closed-book, naive, iterative, premise-only and Epistemic Search.

No novelty or hypothesis-confirmation claim follows from any of this.
