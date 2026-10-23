# AGENTS.md

## Project purpose

This repository is a research implementation of **Epistemic Search**, a premise-aware, evidence-state-aware retrieval system.

The primary objective is scientific validity and reproducibility, not feature velocity.

## Required reading order

Before implementing a phase, read:

1. `README.md`
2. `RESEARCH_PROPOSAL.md`
3. `ARCHITECTURE.md`
4. `EXPERIMENT_PLAN.md`
5. `LITERATURE_MAP.md`
6. `CODEX_BUILD_SPEC.md`
7. `docs/phases/STATUS.md`

## Non-negotiable invariants

1. Never conflate `UNKNOWN` with `FALSE`.
2. Never call a heuristic score a probability unless calibrated/evaluated as such.
3. Never claim a solver proves real-world truth; it proves derivability from the extracted model.
4. Preserve evidence provenance.
5. Keep model provider interfaces separate from domain logic.
6. Keep search provider interfaces separate from controller logic.
7. Every experiment must be reproducible from config.
8. Every method must have token/search/cost instrumentation.
9. Do not silently change evaluation logic between baselines.
10. Do not optimize on test sets.
11. Do not implement later phases early.
12. Prefer small deterministic components where possible.
13. Add an ADR for material architecture deviations.
14. Every LLM structured output must be schema-validated.
15. All external calls must be mockable in tests.

## Research integrity

When a result is negative:
- record it;
- do not hide it;
- add it to experiment notes.

When literature overlaps our idea:
- update `LITERATURE_MAP.md`;
- narrow novelty claims.

## Coding style

- Python 3.12+
- `uv` for environment/package management unless existing repo chooses otherwise
- Pydantic v2 for data models
- pytest
- ruff
- pyright or mypy
- Typer for CLI
- structured logging
- YAML configs
- deterministic seeds where possible

## Phase protocol

For each phase:

1. read its acceptance criteria;
2. implement only that phase;
3. add tests;
4. run lint/typecheck/tests;
5. update `docs/phases/STATUS.md`;
6. write `docs/phases/PHASE_<ID>.md` summarizing:
   - implementation;
   - design decisions;
   - tests;
   - known limitations;
   - next dependencies.
7. complete every acceptance criterion and required check before marking the phase complete;
8. commit and push the completed phase, then continue to the next phase without
   waiting for another instruction. Do not advance while the current phase is
   incomplete or its push has failed.

## No benchmark theater

Do not:
- cherry-pick examples;
- tune prompts on test labels;
- compare unequal budgets without disclosure;
- use different answer graders unfairly;
- omit failed cases.

## Finish message

At the end of each implementation turn, report:
- files changed;
- commands run;
- tests;
- acceptance criteria;
- unresolved risks;
- exact next recommended phase.
