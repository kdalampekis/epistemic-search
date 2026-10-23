# Phase 12 Luna pilot — negative diagnostic result

Date: 2026-10-23. All five methods used `gpt-6-luna`, reasoning `medium`, the same
lexical retriever/provided-context pools, seed, token/search ceilings and native
answer graders. No prompts or graders changed after observing outcomes.

The three-case smoke preceded a fixed pilot of 10 HotpotQA, 10 2Wiki and 2
ConfRAG cases. Smoke cases are nested in the pilot; they are not independent
extra observations. All **110 pilot method-cases** ran. Five model/extraction
errors and seven retrieval-round budget stops remain in their denominators.
ConfRAG has no single-answer EM/F1; those two cases test integration only.

| Method | Hotpot EM | Hotpot F1 | Hotpot coverage | 2Wiki EM | 2Wiki F1 | 2Wiki coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Closed-book | 0.30 | 0.537 | 0.90 | 0.50 | 0.775 | 1.00 |
| Naive RAG | 0.30 | 0.462 | 0.60 | 0.00 | 0.000 | 0.00 |
| Iterative RAG | 0.10 | 0.319 | 0.70 | 0.00 | 0.226 | 0.70 |
| Premise-only | 0.10 | 0.207 | 0.30 | 0.00 | 0.000 | 0.00 |
| Full Epistemic Search | 0.10 | 0.167 | 0.20 | 0.00 | 0.060 | 0.10 |

These small development samples **do not support an improvement claim** for the
full architecture. Closed-book's higher scores do not establish groundedness;
its memory answers have no citations. No significance or novelty claim follows.

Known failures: one closed-book Hotpot response consumed its 4,096-token output
allowance entirely as reasoning and produced no parsed answer. Four pilot
full-system cases rejected extracted spans absent from the exact source text
(two Hotpot, one 2Wiki, one ConfRAG). The smoke ConfRAG instance is the same
nested case and was replayed, not removed or re-sampled. Strict span validation
remains unchanged. Iterative retrieval reached its three-round cap in seven
pilot cases. These are separate from normal model abstentions.

## Cost and integrity audit

Smoke cost: **$0.016803625**. Additional pilot cost: **$0.051148950**.
Total project cost to this checkpoint: **$0.067952575**; remaining under the
$50 cap: **$49.932047425**, including the protected $5 final Sol reserve.
No Sol or Astra calls were made.

Across smoke and pilot: **278 physical generations**, 278 non-generative token
preflights (**556 HTTP API calls**) and **177 local model-output cache hits**.
Logical model/token counts still charge reused work to each method. All physical
generations settled below their reserved bounds; no pending or unknown charges.
Do not interpret cached latency or order-dependent physical spend as a fair
uncached speed/cost superiority claim.

`uv run --locked python scripts/audit_phase12.py` verifies matched case IDs,
metric versions, model/effort, per-case ceilings, trace hashes and reconciliation
between physical trace costs and the persistent ledger. It also replays the
completed campaign with HTTP POST disabled: **zero new generation calls**.
The compact [audited results](../results/phase12_luna_pilot.json) retain every
summary and failure plus trace/dataset hashes. Full local artifacts are under
`artifacts/phase12/luna-medium/`; the durable ledger/cache is under
`artifacts/research/spending.sqlite3`. Do not reset that ledger between phases.

Run manifests truthfully record the previous commit and a dirty worktree. The
model, prompts, retrieval and scoring were fixed before smoke; subsequent edits
added reporting, audit checks and budget protections. The audit includes final
source hashes and is committed with the Phase 12 implementation.

## Decision

Do **not** scale to a full benchmark or spend the final Sol reserve now. The
pilot is informative about current limitations: low retrieval coverage,
frequent abstention and fragile exact-span extraction. It completes Phase 12's
matched execution requirement, not the research hypothesis. Next is **Phase 13
— Abstention metrics**, using saved outputs and deterministic tests at zero
additional API cost. Later architecture experiments must be separately specified
and costed; this pilot must not be silently reused as an untouched test set.
