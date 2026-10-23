# ADR 0005 — Five-method parity protocol

Accepted for the Phase 12 implementation. Paid budgeting and model-output
reuse are updated by [ADR 0006](0006-project-budget-and-output-reuse.md).
The cold artifact-cache discussion below remains the fixture protocol.

The `compare` command derives five runs from one config: closed-book, naive RAG,
iterative relevance, premise-only and full Epistemic Search. It requires explicit
finite search/document/retrieved-token/model/input/output ceilings. Models,
provider settings, seeds, retrieval pool, top-k, round cap, dataset subset and
scorer are shared. Different realized consumption is reported, not equalized.
Closed-book deliberately uses no retrieval. All failures remain in denominators.

Premise-only reuses the full system's decomposition model/prompt and deterministic
targeted-query generator. Its generative judge selects an unresolved premise or
answers/abstains from cumulative retrieved context. It does not run stance
extraction, belief aggregation, graph propagation or formal sufficiency checking.
It is an implemented comparator, not a reproduction claim about any cited paper.

Closed-book uses `MemoryAnswer`, which has no citations. `RunResult` accepts this
schema only for method `closed_book`. Retrieval methods still require `Answer`
with citation validation. Fabricated source IDs are never used to make a
closed-book output pass the cited-answer schema.

## Budgets and accounting

The application boundary now wraps naive/iterative provider calls with the same
`RunAccounting` guards used by both new comparators and the MVP. Existing baseline
policy logic retains its own internal stopping checks; its internal totals are
not added to the wrapper ledger. The returned trace uses the wrapper's provider
records and a separate context-token view, so every call is counted once.
Low-level legacy baseline functions retain their existing interface and tests;
configured CLI/evaluation/comparison execution uses the shared guard protocol.

`shared-provider-guard-v2` caps each requested output allowance to the remaining
cumulative output budget for every method. Provider-reported overruns and failed
attempts remain charged. Prompt preflight still uses whitespace estimates; it
cannot promise a hard remote token ceiling. Unknown monetary cost remains null;
a configured hard dollar ceiling still fails closed without preflight costing.
The full controller may conservatively abstain earlier than a generator; that is
part of the recorded method policy, not a different budget ceiling.

## Reproducibility and cache policy

Each comparison requires a new output root. Each method/example uses a separate
cold decomposition cache; preprocessing calls are included in its usage. This
also prevents repeated questions with distinct IDs from receiving free cached
work. Cold runs do not guarantee identical remote decompositions: sampling may
remain stochastic despite recording the seed. Remote API cache behavior is
reported by the provider and is distinct from local decomposition caching.

A common manifest records method order, model settings, raw/alias/script hashes,
selected IDs, ceilings, retrieval scope and scoring protocol. Per-method results
are retained incrementally; `comparison.json.complete` means all methods ran,
not that every example succeeded or the research hypothesis was supported.
Only `fixture_only: false` runs can contribute real-model research observations.
No paired significance tests, ablation switch matrix or selective metrics are
introduced here; those remain in their scheduled phases.
