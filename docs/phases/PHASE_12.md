# Phase 12 — Baseline parity

Status: implementation ready; real-model execution blocked by missing local
provider credentials. Model/spend preferences were also requested. **Not complete.**
Phase 11 commit `d8baae2` passed hosted CI before implementation began.

## Implementation

Added closed-book and premise-only baselines, shared provider guards for
configured naive/iterative runs, and a five-method `compare` command. One config
controls the model, retriever, dataset subset, budgets and scorer. Manifests
record method order and actual usage; failures remain in comparison outputs.
Cold caches are isolated per method and example and decomposition is charged.

Closed-book has an explicit uncited output schema; it never searches or
fabricates citations. Premise-only uses the same decomposition/query components,
then a generative unresolved-premise judge without stance/belief/formal logic.
Provider calls use the common output allowance and cumulative guard protocol.
See ADR 0005 for the precise parity boundary and remaining budget limitations.

## Validation

- `compare configs/parity_fixture.yaml`: all five methods ran without errors.
  Recorded model calls: closed-book 1, naive 1, iterative 1, premise-only 2,
  full 4. Closed-book search calls 0; each other method 1. These counts describe
  the scripted fixture, not a quality or efficiency research finding.
- Native-data negative smoke: two seeded examples from each Phase 11 release,
  all five methods, scripted abstention/no evidence, no model-quality claims.
  Configs/scripts/results are under ignored `artifacts/phase12-native-smoke-configs`
  and `artifacts/{dataset}-parity-native-smoke` for inspection.
- Tests exercise equal configuration, cold per-case decomposition charges even
  for repeated questions, no duplicate usage, zero model ceilings for all five
  methods, closed-book no-search/no-label-leak, premise-targeted follow-ups,
  structured output validation, common remaining output allowance, failure
  retention, missing credential preflight, overwrite refusal and CLI integration.
- `uv sync --locked --extra benchmarks --python 3.12`: passed.
- `uv run --locked ruff check .` / `ruff format --check .`: passed.
- `uv run --locked mypy src tests`: passed, 41 files.
- `uv run --locked pytest`: 172 passed with the benchmark extra installed.
- `uv build`: wheel/source distribution passed. All 14 YAML configs validated.
- CI includes the five-method fixture run.

## Concrete real-data pilot configs

- `configs/hotpotqa_parity.yaml`
- `configs/2wikimultihopqa_parity.yaml`
- `configs/confrag_parity.yaml`

Each selects two cases by the existing seed policy and runs the five methods
with the same provider settings. The existing optional-provider snapshot
`gpt-4o-mini-2024-07-18` is carried forward as a configurable placeholder, not a
new model recommendation. Pricing is not guessed. Native dataset acquisition
has already completed. No test labels were used to choose prompts or cases.

`compare configs/hotpotqa_parity.yaml` was attempted and failed at credential
preflight with `Set OPENAI_API_KEY locally before running a real-model comparison`.
No provider call or real-run artifact directory was created. The environment
contains no OPENAI_API_KEY. A model/spend clarification is pending with the user.
Do not report fixture outputs as real experiments to bypass this dependency.

## Remaining acceptance work and next phase

Configure provider credentials locally, record any requested model/spend changes,
then run and audit the three concrete parity pilots, retaining failed cases and
actual usage. Resolve any discovered integration failures, update this report
and STATUS, and commit/push the completed phase with successful CI.

Current phase remains **Phase 12**. Phase 13 — Abstention metrics — must wait
until Phase 12's real-model execution dependency is satisfied.
