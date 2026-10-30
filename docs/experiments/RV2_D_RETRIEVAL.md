# RV2-D: retrieval only (HotpotQA and 2WikiMultiHopQA)

Date: 2026-10-30. Code: tag `epistemic-search-v1.1.1`. Plan and rule:
[RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md). Every case with its per-search
documents: [cases.jsonl](../results/rv2/rv2_d/cases.jsonl); summary and ledger:
[results.json](../results/rv2/rv2_d/results.json), [estimate.json](../results/rv2/rv2_d/estimate.json).

> **This experiment is partial.** The plan called for 144 questions (72 per dataset, chosen by the
> committed cost rule). It stopped after **46 questions with all four systems complete (23 per
> dataset)**, plus one partial question that is not scored. A model request failed mid-flight and
> the spend ledger, by design, halted the whole project ("API failure with uncertain charge;
> maximum reservation retained"; one $0.0021 reservation is still pending). I did not clear that
> halt. The 46 scored questions are an interleaved, type-balanced prefix of the committed sample,
> so they are a fair subset, but they are a third of what was planned.

## Design as run

Question pools come from the datasets' own distractor settings (10 paragraphs per question),
the 22 pilot questions are excluded, sampling is seeded (20261029) and stratified by question
type and interleaved so a prefix stays balanced. Same lexical retriever, k = 2, at most 3
searches and 6 documents, identical for every system. Systems: naive top-k; iterative
(model-written reformulations); premise-only and Epistemic Search (both premise-directed:
the target premise is chosen by the model or by the controller and the query is the premise
text plus the question). Retrieval is scored from the traces against the benchmark's supporting
facts, independent of answer quality. The parser was validated against the pilot's traces: it
reproduces RV0's independently computed pilot recall exactly (0.45 / 0.65 / 0.50 / 0.55).
Cost: **$0.0737** (cap $0.50), 511 settled generations.

## Results (46 questions; 95% interval on the contrast below)

| System | Gold-document recall | All gold retrieved | Mean searches | Gold found per search | Duplicate rate | Searches to all gold (never = 4) | Model calls | Cost (logical) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Naive top-k | 0.440 | 0.13 | 1.00 | 0.96 | 0.00 | 3.61 | 46 | $0.0038 |
| Iterative | **0.783** | **0.63** | 2.11 | 0.94 | 0.20 | **2.67** | 97 | $0.0112 |
| Premise-only | 0.467 | 0.13 | 2.00 | 0.61 | 0.40 | 3.61 | 138 | $0.0361 |
| Epistemic Search | 0.467 | 0.13 | 1.93 | 0.64 | 0.36 | 3.61 | 354 | $0.0370 |

Gold-supporting-fact recall equals document recall to within 0.002, because the retriever
returns whole paragraphs. By dataset (23 questions each): HotpotQA recall 0.37 / 0.70 / 0.39 / 0.39
and 2Wiki 0.51 / 0.87 / 0.54 / 0.54 for naive / iterative / premise-only / Epistemic Search.

**Pre-registered Q5** (best premise-directed recall minus best of naive/iterative, ≥ 0.10 with an
interval above zero, or equal recall with ≥ 25% fewer searches): gap **−0.315**, 95% CI
**[−0.402, −0.228]**; search ratio 0.95. **Verdict NO.** Premise-directed retrieval did not find
required evidence more efficiently; it found barely more than naive top-k and clearly less than
iterative retrieval, while repeating itself (36–40% duplicate documents).

## Why (from the traces)

Premise-only and Epistemic Search retrieve identical documents (same recall, 0.467) because both
build the next query by the same deterministic rule: the target premise text concatenated with
the whole original question. With a lexical retriever that mostly returns the same two
paragraphs again. The iterative baseline asks the model for a fresh query each time and gets
different documents. The controller that picks the target premise does not matter for retrieval
here, because it changes which premise is named, not what the query looks like. This is a
description of the traces, not a controlled test of query wording.

## Caveats

* 46 of 144 planned questions; the interval is wide in absolute terms but lies entirely below
  zero and far below the pre-registered +0.10 bar, so more questions are unlikely to reverse
  the sign. That is an expectation, not a measurement.
* Iterative RAG stopped on the budget in 13 of 46 questions and errored in 1 (counted in the
  denominators); its retrieval is read from the trace regardless of how it ended. Premise-only
  and Epistemic Search each errored on 2 questions (invalid generated graph in one, duplicate
  normalised claims in the other).
* Distractor-setting pools of 10 paragraphs and a lexical retriever only; nothing here says
  anything about open-corpus or dense retrieval.
* The retrieval comparison scores retrieval, not answers, so it does not show whether the
  better-retrieving system answers better.
