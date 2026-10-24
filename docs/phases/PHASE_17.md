# Phase 17 — Controlled benchmark transformations

Status: **complete locally**; commit/push and hosted CI gate pending.
Phase 16 commit `0fc1b65` passed CI `40064451187` before work began.

## Implementation and design

Added a validated controlled-dataset adapter and deterministic YAML transformation
generator. All requested interventions are implemented: missing premise,
contradiction, irrelevant/redundant context, repeated evidence, order and freshness.
Outputs include the unchanged base, grouped variants, transformation metadata,
document provenance and replay hashes. Invalid plans fail before output creation;
existing outputs cannot be overwritten.

Evaluation and five-method comparison consume per-question controlled documents
and preserve the declared original answer grader. Order variants change prompt
presentation while retaining lexical top-k selection. Default retrieval and
historical config serialization remain unchanged. See
[ADR 0011](../decisions/0011-controlled-interventions.md) for label semantics and scope.

## Tests and acceptance

All intervention types and required metadata are covered. Tests verify stable
replay, nonmutation, grouped IDs, answerability provenance, synthetic attribution,
repetition lineage, explicit evidence dates, source collision rejection, no label
leakage into prompts, actual prompt order, original grader preservation and all
five methods using controlled documents. Invalid/duplicate datasets are rejected.

`uv run --locked ruff check .`, `ruff format --check .`, `mypy src tests`,
`pytest -q`, and `uv build` pass: **245 tests**, **52 typed files**.

```sh
uv run --locked epistemic-search transform configs/transform_fixture.yaml
uv run --locked epistemic-search evaluate configs/controlled_fixture.yaml
```

The smoke generates eight examples from one fictional base and seven variants.
All eight run without errors: eight searches and eight scripted abstentions,
zero API calls and $0. CI includes both commands. These are plumbing checks,
not accuracy results; the fixture intentionally always abstains.

## Limitations and next dependency

Semantic validity is author-declared and requires review before a real experiment.
Historical native labels are not recomputed. Unobserved top-k interventions do not
establish model robustness; order changes can be inert with a one-document context.
No benchmark scaling or empirical robustness claim follows. Additional research
API spend: **$0**; cumulative spend remains **$0.067952575**.

After push and successful CI: **Phase 18 — Optional formal backend**, restricted
to explicitly structured subsets and derivability from their extracted models.
