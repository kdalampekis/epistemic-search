# ADR 0013 — Explicit ablation replacements and matched reports

Date: 2026-10-24. Status: accepted.

Phase 19 supports a reference and one disabled switch per variant. Multiple
simultaneous removals are rejected rather than given ambiguous interaction
semantics. All-true defaults preserve existing config serialization and prompts.
The ablation runner requires an explicitly VOI-enabled reference and finite shared
budgets. The same dataset, grader, retriever, model, effort and seed serve every
variant; actual resource consumption can differ and is reported.

| Disabled switch | Actual intervention and dependency consequences |
| --- | --- |
| `use_premise_graph` | Execute the existing iterative relevance baseline. Remove decomposition and its downstream evidence-state, formal and VOI control; use raw retrieved context. |
| `use_belief_state` | Execute the premise-only baseline. Keep decomposition; replace belief/formal/conflict/VOI control with its generative decision; use raw retrieved context. |
| `use_formal_sufficiency` | Keep decomposition, evidence ledger and beliefs; replace proof sufficiency and frontier/VOI target selection with one schema-validated generative control call per round. |
| `use_conflict_resolution` | Keep MIXED and conservative sufficiency; turn conflict actions into ordinary targeted searches, including disabling automatic conflict detection in the query template. |
| `use_cost_aware_controller` | Use importance instead of VOI ranking; preserve estimates, frontier, conflict priority and all hard budgets. |
| `allow_abstention` | Request a cited best answer when policy abstains or rounds expire. Null responses are retained as failures. Budget exhaustion, extraction errors and invalid citations still stop execution. |
| `compact_evidence` | Feed full retrieved document text to final generation instead of compact extracted spans; retain extraction, belief and control work. |

Removing a prerequisite removes dependent operations. Those first three rows
are replacement-system comparisons, not isolated causal estimates for one scalar
feature. Reports expose this scope. Removing conflict resolution does not erase
contradiction state; that would violate the evidence-state invariants. Forced
answers remain explicitly experimental and never assert established sufficiency.

Generative replacement output is validated for action/target/stance consistency
and known target IDs. All model/search calls use the existing budget guard and
providers. Nondefault answer/query prompt versions distinguish interventions.
The full ledger remains intact even when presentation changes. Exact-request
paid-output reuse is allowed, with logical usage and physical spending separate.
Decomposition artifacts are isolated per variant and case.

CSV and Markdown tables are generated from the same saved summaries; include
failed cases, partial-run indicators and unknown/incomplete cost counters.
Variant order and shared caps are recorded. A depleted project cap stops later
variants and leaves completed results reviewable. Reusing cached results couples
samples and changes measured latency; it is not an independent replicate.

An intervention may be inactive on an easy example. Tests deliberately activate
query, ranking, abstention and context changes. The one-case CLI fixture checks
all routes, not experimental efficacy. No full benchmark is scheduled.
