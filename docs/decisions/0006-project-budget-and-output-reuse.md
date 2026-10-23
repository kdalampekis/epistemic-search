# ADR 0006 — Project budget and exact-request reuse

Accepted 2026-10-23 during Phase 12. Supersedes the cold model-output policy in
ADR 0005 for paid research and the earlier Sol-primary/$50-per-phase plan.

The current **entire project** API allowance is $50. Luna/medium is the primary
experimental setting; low is permitted only in separately labelled development
runs. Sol is limited to a later final validation cohort. Astra is excluded.
Reserve $5 for that final cohort; this is part of the $50, not extra funding.

All application-created paid providers require `experiment_spend`. Every paid
config must point at the same persistent `artifacts/research/spending.sqlite3`.
Do not delete, relocate to an empty ledger, or reset it between phases. Configure
`prior_spend_usd` before first use for known expenditure outside this runner.
Current initialization is zero because no earlier paid research calls were made
by this implementation. This ledger cannot observe other applications' bills.

SQLite transactions serialize generation reservations. Before each generation,
Responses input-token counting measures the complete input including its schema.
The runner reserves all input at the verified 30-minute cache-write rate plus
all permitted output (including reasoning) at the output rate. Requests use the
standard tier, global endpoint, no tools, no truncation and at most 100,000 input
tokens. Settlement uses nonoverlapping ordinary/cached/write input categories;
reasoning tokens are a subset of output, not an additional charge. Unexpected
usage/tier/TTL contracts stop execution. The cap covers estimated standard API
token charges, not taxes, external spending or an undocumented provider tariff.
The non-generative count endpoint is tracked separately and has no token charge
in this rate-card calculation.

A pending request survives crashes with its maximum charge reserved. Unknown
billing, cancellation or a provider contract mismatch blocks further generation
until audited; there is no automatic retry or speculative release. Per-run
exhaustion stops that run and retains partial artifacts without marking all
future project runs unusable. Project and per-run caps persist across restarts.

Exact model requests are cached in the same database, keyed by complete API
payload, model, reasoning, schema, output allowance, prompt version and recorded
replicate seed. Credentials are neither part of the key nor persisted. Reuse
retains original logical model-call/input/output counts for the shared method
budgets. `model_cache_hits` identifies reuse; `cost_usd`, `api_calls` and current
latency count physical work, while `reused_cost_usd` and `original_usage` retain
the reused computation. Provider-side cached inputs are a separate concept.
Use ledger usage for actual paid-token totals, not the sum of logical token
counts from replayed responses. This coupling reduces stochastic preprocessing
differences; it does not provide independent model replicates. Different seeds
partition reuse but are not a remote sampling-seed guarantee.

Decomposition artifact caches remain isolated per method/example so they cannot
bypass logical charging. Deterministic local retrieval caches repeated queries
within an immutable per-case corpus, retaining logical search/document counts.
There is no external search API charge. Cache-hit latency is not evidence of
uncached architecture speed. Compare physical spend and logical work separately.

The campaign runs one explicit small stage at a time. A hashed smoke audit is
required before the 22-case diagnostic pilot. Unknown accounting/provider
failures block it; retained model-output validation failures may justify a
negative diagnostic experiment after inspection. No failures are dropped and no
validation rule is relaxed to make smoke outputs succeed. There is no automatic
full-benchmark stage. Further scaling requires a documented informative result,
a new cost estimate and remaining project funds.

Sources, verified 2026-10-23:
- [Luna model and standard pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Sol model and standard pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [Exact input-token counting](https://developers.openai.com/api/docs/guides/token-counting)
- [Prompt caching and write accounting](https://developers.openai.com/api/docs/guides/prompt-caching)
