# ADR 0002 — Evaluation protocol v1

Status: accepted for Phase 2.

All methods use the same `english-em-token-f1-v1` scoring implementation. It
lowercases, removes ASCII punctuation and English articles, and normalizes
whitespace. EM compares normalized strings; token F1 uses multiset overlap.
This generic English scorer is not claimed to reproduce any dataset's official
scorer. Dataset-specific protocols, if required in Phase 11, must be separately
versioned and applied equally to all methods.

EM/F1 denominators include every example with a non-null `gold_answer`, including
failed runs, budget exhaustion, and abstentions (zero score). Unlabelled cases
remain in coverage and cost totals but are excluded from answer-quality means.
No labelled cases means unknown quality (`null`), not zero quality. Coverage is
the number of completed, non-null answers divided by ALL cases. Answerability
labels do not silently turn abstention into an EM match; selective metrics are
scheduled for Phase 13.

The harness passes only IDs and questions to methods, stripping all labels and
metadata. It rejects duplicate IDs/malformed datasets before provider calls.
Every case produces a trace file and a JSONL score row. Unexpected exceptions
remain failed cases with explicitly incomplete usage. Aggregate counts are lower
bounds when incomplete usage exists; unknown costs propagate to unknown totals.

Output directories must be new. Trace filenames use ordinal indices, never
query IDs. Manifest hashes cover resolved config, dataset, corpus, and fixture
script, and record commit/dirty state, metric version and package versions.
Fixture results are explicitly marked as smoke tests, never scientific evidence.
