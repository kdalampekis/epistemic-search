# epistemic-search v1.1 (frozen before any RV2 model call)

Date: 2026-10-29. Exactly two defect fixes from the RV0/RV1 findings, nothing else. Tag:
`epistemic-search-v1.1`. Plan: [RV2_EXTERNAL_VALIDATION_PLAN.md](RV2_EXTERNAL_VALIDATION_PLAN.md).

## Fix A: span handling (`evidence.py`)

Before: one extracted span that was not an exact substring raised an error for the whole
question (4 of 22 pilot Epistemic Search cases).

Now `align_span` maps the model's span onto the source through an offset-preserving canonical
form: Unicode spaces and whitespace runs collapse to one space, dashes and curly quotes are
straightened, characters are NFKC-normalized one at a time. Case and wording are never
changed. If the folded span occurs in the folded source, the evidence stores the **exact
original substring** (so every stored span is a true substring of its document) and keeps
the model's raw span in `metadata.model_span`. Otherwise **only that item** is dropped, as a
`SpanRejection` in the batch, an `EVIDENCE_SPAN_REJECTED` trace event and the `rejections`
list of the `EVIDENCE_ADDED` event. An unparseable response is still a batch error. Spans that
were already exact keep their previous evidence ids and metadata.

### Offline replay on the six spans the pilot rejected (no API call)

| Case | Span (start) | v1.1 |
| --- | --- | --- |
| ConfRAG 1105 (3 spans) | "N.W.A's seminal classic…", "The fascination…", "The rumor is…" | repaired (NBSP) |
| HotpotQA 5a7363ec | "a group of desert coral islets 60 miles west of Key West, Florida" | repaired (NBSP) |
| 2Wiki 2bf61f58 | "the lovely documentary series is made by the director Marc Sinden" | **rejected**: a paraphrase, not in the source |
| HotpotQA 5a8a5c0d | "Elsie Audrey Mossom (3 September 1920, Preston – 1 September 2009, Hastings)… Later in 1935, she turned on the Blackpool Illuminations…" | **rejected**: it splices two non-adjacent sentences and the second half is not what follows the first in the source |

So the fix repairs the four formatting-only failures and still refuses the two non-verbatim
ones. The RV1 annotation judged those two "faithful in meaning"; the strict rule does not
accept them, deliberately, so no hallucinated or composed text can enter the ledger.

## Fix B: no-progress guard (`engine.py`, `comparators.py`)

Before a next search would be issued, if all three hold:

1. the proposed query equals the query of the previous search,
2. the previous search returned no document not already seen, and
3. the previous search left the epistemic state unchanged (belief snapshot before == after),

the run emits `NO_PROGRESS` and stops acquiring, abstaining with the rationale
`NO_PROGRESS: repeated query, no new documents, state unchanged` (status `completed`, not an
error). In the ablation that forbids abstention the existing forced-answer path is used.
Premise-only has no belief state, so condition 3 is "the model selected the same target
premise again". **Query generation is unchanged.** Iterative RAG is untouched.

## What is not changed

Prompts, thresholds, belief aggregation, the formal reasoner, query generation, the
controller, budgets and the scorers. With a clean span and productive searches the code path
and the evidence ids are identical to v1.

## Tests

`tests/test_evidence.py` (alignment, mixed batches, nothing different accepted, offsets across
a ligature), `tests/test_engine.py` (the question continues past a hallucinated span; an NBSP
difference is repaired to the exact source text; the guard stops a stuck loop after 2 searches
instead of 5; it does not fire when a search makes progress), and
`tests/test_no_progress_premise_only.py` (same loop stopped; no firing while documents are
new). One older test encoded the abort-on-bad-span behaviour and was replaced on purpose.
