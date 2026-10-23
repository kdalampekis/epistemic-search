# First Codex / Claude Code Prompt

Read:

- `AGENTS.md`
- `README.md`
- `RESEARCH_PROPOSAL.md`
- `ARCHITECTURE.md`
- `EXPERIMENT_PLAN.md`
- `LITERATURE_MAP.md`
- `CODEX_BUILD_SPEC.md`

We are starting from a new repository named `epistemic-search`.

Implement **Phase 0 — Research Repository Foundation only** from `CODEX_BUILD_SPEC.md`.

Do not start Phase 1.

Requirements:

- Python 3.12+
- uv
- Pydantic v2
- pytest
- ruff
- pyright or mypy
- Typer for the CLI
- provider-neutral `ModelProvider`
- provider-neutral `SearchProvider`
- all external calls mockable
- no API keys required for tests
- add core schemas for QueryCase, Claim, ProofNode, EvidenceItem, ClaimBelief, EpistemicState, BudgetState, Decision, and AgentEvent
- add token/search/cost accounting interfaces
- add structured logging
- add CI
- create `docs/phases/STATUS.md`
- add tests for serialization, validation, and provider mocks
- run install, lint, typecheck, and tests
- fix all failures before finishing

Research invariants:

1. `UNKNOWN` is not `FALSE`.
2. Do not call heuristic scores probabilities unless calibrated.
3. Formal derivability means derivability from the extracted model, not proof of real-world truth.
4. Preserve provenance.
5. Do not implement retrieval, decomposition, belief aggregation, or reasoning yet.
6. If a material unspecified architecture decision is required, create an ADR.

At the end provide:

1. files changed;
2. commands run;
3. test results;
4. Phase 0 acceptance criteria status;
5. unresolved risks;
6. the exact recommended prompt for Phase 1.
