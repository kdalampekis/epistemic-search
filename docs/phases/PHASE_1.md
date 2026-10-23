# Phase 1 — Naive RAG baseline

## Implementation and decisions

One query is retrieved once, the configured top-k context is passed to a model,
and the structured answer is validated against the output schema and source IDs.
Gold labels and case metadata never enter the prompt. Missing evidence permits a
null answer; this is baseline prompt behavior, not a proof-sufficiency policy.

The local corpus ranks by lexical term overlap with stable source-ID tie breaking.
The scripted model is a deterministic smoke fixture, not a model-quality result.
Paths resolve relative to config. The CLI writes answers, original provenance,
requests/responses, usage, and errors to a new file, refusing to overwrite runs.

The optional OpenAI Responses adapter has an injectable httpx client, explicit
model identifier, timeout, no retries, and schema-constrained output. Credentials
come from the environment and never enter traces. Refusals/incomplete/invalid
outputs retain usage. Failed calls retain attempts and flag unknown usage.
The API contract follows [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
Remote seed support is explicitly false; no deterministic remote generation claim.

## Tests and acceptance criteria

- Fake-provider end-to-end: answer/citations, no gold leakage, byte-identical
  fixture output under fixed clocks.
- Optional real provider via config: `configs/naive_openai.yaml`; HTTP success,
  refusal, incomplete, malformed, and rate-limit cases tested with MockTransport.
  No paid live API call run.
- Complete cost trace: input/output/retrieved/context tokens, documents/calls,
  call latency, wall time, decimal cost. Unknown costs/usage remain explicit.
- Deterministic fixture retrieval/run: top-k ties, empty retrieval, null answers,
  malformed outputs, failed calls, and zero budgets covered.
- Required checks: locked install, ruff check/format, strict mypy, pytest (49
  tests), CLI fixture run, distribution build.

## Known limitations

- Local counts are labeled whitespace estimates, not model tokens. Remote
  input/output counts use provider reports; context counts remain estimated.
  Preflight estimates cannot guarantee hard token/latency ceilings; overruns are
  recorded and the run marked budget-exhausted, never hidden.
- Remote monetary ceilings fail closed pending preflight costing. Omitted prices
  mean unknown cost. Explicit rates, including cached inputs, are config estimates.
- Citation membership validates references, not entailment or truth.
- Fixture retrieval/scripts are integration fixtures, not competitive baselines.
  No benchmark quality or novelty claims are made.

## Next dependency

Phase 2 — Evaluation harness v1: shared dataset protocol, JSONL runner, EM/F1,
coverage, usage summaries, per-example traces, and JSON/CSV aggregation.
