# ADR 0011 — Declared, grouped evidence interventions

Date: 2026-10-24. Status: accepted.

Controlled examples bundle a query, its documents, an original question group and
the original versioned answer grader. This makes context transformations usable
by all five methods without changing their prompts or answer evaluation. The
`controlled` JSONL format is separate from native benchmark adapters. Existing
native annotations remain historical labels, not automatically updated gold
supporting facts, viewpoint clusters or contradiction judgments.

Each YAML plan emits the base and independent variants for missing premises,
contradiction, irrelevant context, redundant paraphrases, exact repetitions,
order and freshness conflicts. Authors supply semantic additions explicitly;
the generator neither negates arbitrary text nor claims to verify contradiction.
Targets, document hashes, source mappings, seed and presentation order are recorded.
Synthetic additions receive synthetic URIs. Repetitions retain their original URI
and exact text, so they are not presented as independently sourced corroboration.
Evidence dates must occur in the supplied text; retrieval timestamps are preserved.

Gold reference answers stay unchanged. Missing, contradictory and freshness
variants reset answerability to unknown unless an independently attributed label
is supplied. Exact match therefore measures retention of the original reference,
not newly established truth or safety. In particular, an undated question with
dated conflicting context needs human review before substantive conclusions.
Families must stay together in any downstream train/dev/test split. This generator
does not perform splitting or assert that two input families are independent.

All transformation labels and gold answers remain evaluator-only. Case IDs are
opaque hashes. `controlled` runs use the existing lexical top-k membership, then
present selected documents in declared corpus order; the manifest records this
retrieval variant and search traces preserve lexical ranks. Thus order changes
reach prompts without secretly changing membership. Documents outside top-k do
not reach the model; inspect traces before claiming an intervention was observed.
Other interventions can intentionally change membership and token counts.

The fixture plan is a software check, not a benchmark result. No automatic model
calls, semantic rewrites, inferred answerability labels or large runs are added.
