# Phase 10 — Full Epistemic Search MVP

## Implementation and decisions

Integrated decomposition → initial retrieval → claim-specific evidence → beliefs
→ sufficiency → controller → targeted/conflict retrieval → answer or abstain.
The method is selected with `method: epistemic_search` and uses the existing
evaluation harness and unchanged scoring protocol. Results include the full
epistemic state, blocking claims, decisions, provenance and derivation traces.

All decomposition, extraction and answering calls share one accounting/budget
guard. Component-local traces do not double-charge provider usage. Canceled calls
retain attempts and mark usage incomplete. Cache hits retain origin metadata but
charge no new model call. Fixture scripts may be keyed by prompt version so a
cached decomposition cannot shift the remaining response sequence.

Final rendering remains schema/citation-validated and needs its own budget even
when the proof state is sufficient. If the renderer cannot run or abstains, the
system abstains rather than returning an unsupported answer. Unknown evidence
never becomes false, and unresolved mixed evidence remains in the ledger.

## Tests and acceptance

All four required fixture scenarios pass:

1. All required evidence initially available → ANSWER.
2. One missing premise → query specifically that premise → ANSWER.
3. Missing premise remains unresolved → ABSTAIN with blockers.
4. Conflicting premise → RESOLVE_CONFLICT and a logged independent-evidence query.

Additional tests enforce shared answering budgets, verify each provider call is
charged exactly once, check state/trace totals and cache accounting, and retain
usage on nested timeout cancellation. Full suite: 143 tests. Locked install,
lint/format, strict mypy, pytest, config-driven MVP evaluation/CLI and build pass.

## Known limitations

- Fixtures establish integration only; no real-model quality improvement claimed.
- Conflict resolution currently means acquiring more evidence. Conservative max
  aggregation will not erase earlier contradictory evidence just because another
  supportive document arrives; unresolved conflict leads to abstention.
- Local token estimates and remote overruns retain the previously documented
  caveats. Output reservations are conservative and may stop with unused allowance.
  The configured search backend is a free local fixture retriever; a priced search
  backend will need its own conservative preflight reservation.
- Cold and warm decomposition caches have different actual costs. Cache-hit/origin
  data are recorded; experiments must disclose and match cache policy (Phase 12).
- Semantic extraction and answer generation remain fallible. Formal sufficiency
  refers only to the extracted model, not real-world truth.

## Next dependency

**Phase 11 — Benchmark integrations**: reproducible HotpotQA, 2WikiMultiHopQA and
ConfRAG adapters/setup, with source/license/schema verification before any results.
