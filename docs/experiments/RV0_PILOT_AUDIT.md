# RV0 — Pilot failure audit

Date: 2026-10-24. Cost: **$0** (no API calls; no model, search or grader executed).
Part of the [research validation plan](../../RESEARCH_VALIDATION_PLAN.md).

RV0 asks one thing of the 110 saved Phase 12 method-cases: what can be *read off*
the traces and benchmark annotations without a semantic judgment? It does not
decide whether a premise was right, a stance correct, an abstention appropriate or
an answer true. Those fields exist in every record but are left blank and marked
`REQUIRES_MANUAL_REVIEW`. Therefore **this audit produces no failure
distribution** (`semantic_failure_distribution: null`), and nothing below is a
quality or novelty claim.

## What was run

```sh
uv run --locked epistemic-search audit-pilot configs/rv0_pilot_audit.yaml
```

The auditor re-reads the 15 saved runs (5 methods × HotpotQA, 2Wiki, ConfRAG),
checks that trace identity, status, usage and answer-presence agree with the saved
scores, checks the runs share a matched protocol per dataset, and verifies source
hashes before and after reading. It refuses to write into or beside a source run,
refuses to overwrite an earlier audit and refuses to import judgments. Output is
byte-identical across repeated runs. Source artifacts are unchanged.

Outputs (full set under `artifacts/rv0-pilot-audit/`, which is git-ignored; compact
copies in [docs/results/rv0/](../results/rv0/)):

| File | Content |
| --- | --- |
| `diagnostics.jsonl` | One record per method-case: `observations` (facts) and `human_judgments` (blank) kept separate. 110 records. Not committed (1.4 MB); hash is in `summary.json`. |
| `diagnostics.csv` | Flat table of outcome and mechanical counters per case |
| `documents.jsonl` | Retrieved documents referenced by key, with original text. Not committed. |
| `summary.json` | Aggregate mechanical statistics, source/output hashes, limitations |
| `manual_review_priority.jsonl` | All 22 questions in a mechanical review order |
| `rv1_annotation_template.jsonl` | Blank RV1 annotation records, bound to trace hashes (44 method-cases) |

Each diagnostic record covers the requested items: decomposition (claims, graph),
per-search retrieval (query, document keys and titles, rank, repeated-set flags),
raw extraction items with literal span checks, accepted evidence and its claim
assignment, stance, belief-state transitions replayed against current code,
structured-reasoner results replayed against current code, blocking obligations,
controller actions and rationales, generated targeted queries, and the final
decision. Premise-only has no stance/belief/formal stages; their absence is
recorded as intentional, not as missing data. Each question also links the matched
naive-RAG result so "would normal RAG have answered?" can be answered from the
actual run, not from a counterfactual.

## Mechanically observed facts

Sample: 10 HotpotQA + 10 2Wiki + 2 ConfRAG questions, five methods each. Nested
smoke cases are not extra observations. ConfRAG has no single-answer grade, so
its two questions are integration observations only. All counts below are descriptive
on **n = 22 questions** and carry no statistical support.

### Outcomes (as already audited in Phase 21)

| Method | Abstention | Mismatch | Budget stop | Execution error | Reference match | Ungraded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Closed-book | 0 | 11 | 0 | 1 | 8 | 2 |
| Naive RAG | 15 | 3 | 0 | 0 | 3 | 1 |
| Iterative RAG | 0 | 13 | 7 | 0 | 1 | 1 |
| Premise-only | 18 | 2 | 0 | 0 | 1 | 1 |
| Full Epistemic Search | 14 | 2 | 0 | 4 | 1 | 1 |

Abstention is an outcome, not an error, and a reference match is not proof of
correct reasoning.

### 1. Decomposition surface form (lexical flag only)

Premise-only and Full Epistemic Search share a byte-identical decomposition for all
22 questions, so both are bounded by it. Of its 80 premises, a fixed lexical check
(not a quality judgment) finds:

| Surface form | Premises |
| --- | ---: |
| Starts with a task verb (Identify, Determine, Establish, Resolve, …) | 28 |
| Ends with `?` | 7 |
| Starts with "Whether" | 6 |
| Other | 39 |

41 of 80 premises, in 13 of 22 questions, are phrased as a task, question or
"whether" clause instead of a checkable assertion. Several others restate the
question around an unresolved entity ("The crab type can be grown in a fishery").
Whether these are defective, unnecessary or merely stylistic is an RV1 judgment.

### 2. Retrieval and the controller's targeted queries

Every search returned exactly two documents (k = 2); the budget is 3 searches and 6
documents. Targeted query text is a deterministic concatenation (claim text +
original question + entities + a fixed suffix depending on evidence state), so the
same target in the same evidence state gives an identical query.

| Method | Questions with an exactly repeated query | Questions with a repeated document set |
| --- | ---: | ---: |
| Naive RAG | 0 | 0 |
| Iterative RAG | 3 | 5 |
| Premise-only | 17 | 18 |
| Full Epistemic Search | 14 | 14 |

All 14 Full Epistemic Search abstentions (14 of 22) ran three searches, repeated an
exact query and a document set, and ended with the controller rationale
"Acquisition budget unavailable: search_calls, documents". Of the 47 recorded belief
updates, **19 left every claim belief exactly unchanged**; all 19 are in the 14
abstaining questions, and every abstaining question has at least one. This is a
candidate no-progress loop, not yet a verdict: whether a different query would have
helped is a judgment.

Retrieval of benchmark-annotated supporting titles (HotpotQA + 2Wiki, n = 20 per
method; exact normalised title match; a **proxy**, because retrieving a supporting
title does not establish that decisive evidence was extracted or understood):

| Method | Mean fraction of gold titles retrieved | All gold titles retrieved | No gold title retrieved |
| --- | ---: | ---: | ---: |
| Naive RAG | 0.413 | 3 / 20 | 6 / 20 |
| Iterative RAG | 0.738 | 10 / 20 | 1 / 20 |
| Premise-only | 0.438 | 4 / 20 | 6 / 20 |
| Full Epistemic Search | 0.463 | 4 / 20 | 5 / 20 |

Only 2 of the 14 Epistemic Search abstentions retrieved all gold titles. By dataset
(n = 10 each) 2Wiki recall is 0.375 for naive, premise-only and Epistemic Search
against 0.825 for iterative; HotpotQA is 0.45 / 0.65 / 0.50 / 0.55
(naive / iterative / premise-only / Epistemic).

### 3. Evidence extraction

* 195 extraction batches in Full Epistemic Search; **66 (34%) returned no items**.
  Whether those were correct non-matches or missed evidence is unknown.
* 135 accepted evidence items: 67 NEUTRAL, 57 SUPPORT, 11 CONTRADICT. Stance
  correctness is unreviewed.
* **Span-contract violations: 6 spans in 4 questions**, which are exactly the four
  execution errors, because one rejected span aborts the case. Strict validation was
  not changed. Four of the six spans (two questions, one ConfRAG, one HotpotQA) match the
  source text once a non-breaking space is replaced; two (one 2Wiki, one HotpotQA) do
  not match even after whitespace normalisation. Normalisation is a diagnostic only;
  no evidence was repaired.

### 4. Belief aggregation and structured reasoner

All 47 recorded belief updates and 47 structured-reasoner results reproduce exactly
when replayed through the current code (0 mismatches). This shows the deterministic
code is consistent with its recorded outputs; it says nothing about whether the
claims, stances or formal model are semantically right.

## Highest-priority examples for manual annotation

Order is mechanical, not a ranking of importance: more execution errors, then
candidate contract violations, then reasoner conflicts, then repeated document sets
(summed over the two audited methods), then dataset and ID. **Because only 22
questions exist, RV1 should annotate all 22**; the order sets annotation sequence,
not a subset, so the sample is not cherry-picked. The first eight:

| Rank | Dataset | Question ID (prefix) | Why it ranks first |
| ---: | --- | --- | --- |
| 1 | 2Wiki | 2bf61f5808… | Epistemic execution error; span absent even after normalisation |
| 2 | ConfRAG | 1105 | Execution error; three NBSP-only span mismatches |
| 3 | HotpotQA | 5a7363ec55… | Execution error; one NBSP-only mismatch |
| 4 | HotpotQA | 5a8a5c0d55… | Execution error; span absent after normalisation; premise-only answered |
| 5 | HotpotQA | 5ae63b2255… | Abstention with a conflict; four repeated document sets across the two methods |
| 6 | HotpotQA | 5a7fb17655… | Abstention; all gold titles retrieved yet abstained |
| 7 | HotpotQA | 5a86eee855… | Abstention with a conflict; repeated document sets |
| 8 | HotpotQA | 5a7b3ec955… | Abstention with conflict; premise-only answered |

The full ordered list is in
[manual_review_priority.jsonl](../results/rv0/manual_review_priority.jsonl).

## Proposed RV1 protocol (not started)

RV1 requires a human assessor; none is recorded and none is simulated. No LLM judge
is used for semantic labels.

1. **Scope and bias control.** Annotate all 22 questions (44 audited method-cases,
   decomposition once per question since both methods share it). Use the priority
   order as sequence only. Record assessor and date. Pilot data are development
   data after this step; see the plan's dev/test rule.
2. **Three passes, to limit hindsight.**
   A: decomposition, seeing only question and gold answer / supporting facts.
   B: each extracted item, seeing claim, source document and span, not system
   outcome. C: stage attribution, with the full trace.
3. **Per premise:** necessary, correct, atomic, complete (question-level), dependency
   correct, each yes / no / unsure. Also record whether the claim is a checkable
   assertion (to compare with the lexical flag).
4. **Per extracted item:** gold stance (SUPPORT / CONTRADICT / NEUTRAL), whether the
   assignment to the claim is correct, whether it is decisive, with a short
   rationale. Items the extractor missed are recorded in
   `missing_premise_descriptions` or a free-text note.
5. **Per question:** retrieval success and whether decisive evidence was in the
   retrieved text (using `documents.jsonl`); whether belief aggregation and the
   formal result were semantically right given the *assessor's* stances; whether
   the controller action and targeted query were reasonable; whether ABSTAIN or
   ANSWER was appropriate; whether the answer is correct (independent of exact
   match).
6. **Attribution.** Primary category is the earliest stage whose failure would by
   itself explain the outcome; list others as secondary. Allowed:
   `DECOMPOSITION_ERROR`, `RETRIEVAL_ERROR`, `EVIDENCE_EXTRACTION_ERROR`,
   `STANCE_ERROR`, `BELIEF_AGGREGATION_ERROR`, `FORMALIZATION_ERROR`,
   `CONTROLLER_ERROR`, `ANSWER_GENERATION_ERROR`, `APPROPRIATE_ABSTENTION`,
   `UNKNOWN_REQUIRES_HUMAN_REVIEW`. Use UNKNOWN rather than guessing. Note the
   Phase 21 taxonomy differs (it has `CALIBRATION_ERROR`, `BENCHMARK_AMBIGUITY`
   instead of the last two), so RV1 needs its own small importer/aggregator; RV0
   deliberately has none.
7. **Reliability.** The annotator re-labels at least 20% of questions after at least a
   week without looking at earlier labels and reports agreement. A second human is
   preferable; with n = 22, report counts, not percentages implying precision.
8. **Freeze.** No code, prompt or threshold changes during RV1. Annotations bind to
   `trace_sha256`; stale annotations are rejected.
9. **Defect vs. hypothesis adjudication (for RV2).** Label each confirmed problem as
   a *specification defect* (system contradicts its own contract), a *design
   limitation* (works as designed but the design is the issue), or a *hypothesis
   failure*. Only the first class is fixed in RV2.

## Provisional answer

*What are the leading candidate bottlenecks in the current Epistemic Search pipeline,
and what evidence would we need to determine whether they are implementation defects
or failures of the research hypothesis?*

These are candidates ranked by mechanical prominence, **not** established causes.

1. **Decomposition quality (shared by both premise methods).** 41 of 80 premises
   are task, question or "whether" phrasings. If RV1 finds most are not checkable
   assertions, that points to a decomposer prompt/schema defect. If even well-formed
   assertions cannot be written without first resolving a bridge entity
   (premises that depend on unknown intermediate entities), that would be a design
   limitation of premise-first retrieval. *Evidence needed:* RV1 premise labels;
   afterwards an oracle-decomposition comparison on the same questions.
2. **Controller and query generation.** All 14 abstentions follow an exactly repeated
   query and document set until the 3-search / 6-document budget ends, and
   recall of supporting titles is below the iterative baseline. This could be a
   missing no-repeat guard (defect) or evidence that claim-text queries are
   inherently poor retrieval queries (hypothesis-level). *Evidence needed:* whether
   belief state really did not change, whether reasonable alternative queries
   would have found the gold documents, and the RV5 ablation of premise-directed
   against plain retrieval.
3. **Retrieval coverage.** Mean supporting-title recall of 0.46 (Epistemic) against
   0.74 (iterative) under equal per-search depth. *Evidence needed:* RV1 judgment of
   whether decisive evidence was in the retrieved text, separating retriever limits
   from query formulation.
4. **Extraction contract.** Four of 22 full-system cases ended in an execution error
   from a single rejected span; two are non-breaking-space mismatches, which would
   be a normalisation defect, while two are non-verbatim spans, which reflect model
   reliability and the choice to abort the case on one bad item. *Evidence needed:*
   RV1 confirmation that the spans were otherwise correct, and a policy decision
   in RV2 about rejection handling; the 34% empty batches also need review.
5. **Stance and assignment.** Unassessable mechanically; priority examples (for
   instance a HotpotQA conflict case with a comparison premise receiving
   SUPPORT/CONTRADICT items about a different person) should be reviewed first.
   *Evidence needed:* RV1 gold stances.
6. **Belief aggregation and formal reasoner.** Lowest mechanical priority: replay
   shows no inconsistency with current code. A semantic fault would still surface
   through bullets 1 and 5, so this stage cannot be cleared until RV1.

The pilot also shows closed-book matching or exceeding every retrieval-based method
(equal HotpotQA EM to naive RAG, higher F1, and higher 2Wiki EM), which makes a
context-pool or grading limitation worth checking in RV1 before attributing anything
to the architecture.

## Limitations of RV0

* Mechanical agreement is not independent semantic validation.
* Counts come from 22 questions chosen by a seeded draw; no inference follows.
* The surface-form flag and gold-title recall are proxies and can be wrong in both
  directions (for example an acceptable assertion starting with a task verb, or
  a relevant document with a non-annotated title).
* "Unchanged belief" means the recorded claim beliefs are identical before and after
  an update; it does not say which search caused it.
* Nothing here supports or refutes the research hypothesis.

## Reproduce

```sh
uv run --locked epistemic-search audit-pilot configs/rv0_pilot_audit.yaml
uv run --locked pytest tests/test_pilot_audit.py
```

Requires the saved Phase 12 artifacts under `artifacts/phase12/`; the output
directory must not already exist. No credentials or network access are needed.
