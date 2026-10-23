# Phase 11 — Benchmark integrations

Status: complete. Phase 10 commit `b099c7c` passed hosted CI before work began.

## Implementation and decisions

Native adapters ingest HotpotQA distractor JSON, 2Wiki April 2021 JSON plus alias
JSONL, and ConfRAG suggested JSONL. Each example has its own complete provided
context pool. Labels, supporting facts, triples and ConfRAG annotations are
retained only for evaluation. Gold data cannot select retrieval documents or
enter model requests. Dataset row order and label values do not drive subsets.

Checksum-pinned setup downloads original files, verifies named ZIP members, and
converts the pinned Hotpot Hugging Face Parquet mirror to the native schema using
an optional pyarrow extra. A manifest records original and output hashes.
Actual setup through the CLI succeeded. No dataset files are committed to git.

Answer-only Hotpot/2Wiki metrics are explicitly versioned and shared across
methods. The generic metric remains unchanged. ConfRAG does not invent a single
correct answer: EM/F1 are null until its dedicated task evaluators in Phase 14.
See ADR 0004 and `docs/experiments/benchmark_setup.md` for source attribution,
release versions, failure handling and reproduction commands.

## Validation

- `uv sync --locked --python 3.12`: passed.
- `uv run --locked ruff check .` and `ruff format --check .`: passed.
- `uv run --locked mypy src tests`: passed, 38 files.
- `uv run --locked pytest`: 156 passed; optional Parquet test skipped without extra.
- `uv run --locked --extra benchmarks pytest tests/test_benchmarks.py`: 14 passed,
  including the previously skipped conversion test.
- `uv build`: wheel and source distribution passed.
- `prepare-datasets configs/datasets.lock.json artifacts/benchmarks`: succeeded,
  verifying all six raw/derived outputs.
- Complete native ingestion validated 7,405 Hotpot, 12,576 2Wiki and 1,098 ConfRAG
  rows, with 73,700 / 125,760 / 10,447 provided documents respectively.
- CLI evaluate on each of the three committed smoke configs: two seeded cases
  each, zero errors, no omitted cases, two search calls and two model calls each.
  Scripted abstention yields zero Hotpot/2Wiki answer scores, null ConfRAG scores,
  zero answer coverage and fully recorded fixture token counts. These are
  integration checks, not scientific model-quality results.

Tests cover label isolation, aliases/demonyms, categorical/empty F1, preserved
ConfRAG Unicode separators, annotation separation, seed/order-independent
sampling, malformed/duplicate/empty datasets, unknown test labels, stable source
IDs, checksum failure, extraction allowlists, overwrite refusal and Parquet
conversion. CI runs both the ordinary suite and the optional benchmark tests.

## Acceptance and limits

All three requested benchmarks have working native ingestion and config-driven,
reproducible setup. The actual recommended ConfRAG release has 1,098 records,
not the original paper's 1,814: this difference is documented in LITERATURE_MAP.
Hotpot's original host timed out; the pinned mirror is disclosed. Unicode
`splitlines()` initially produced false parse failures; newline record reading
fixed the reader without changing or dropping data.

The retrieval setting is per-question provided context, using lexical overlap;
it is not fullwiki retrieval or a competitive retrieval claim. Hotpot/2Wiki
scores cover answers only, not official supporting-fact/triple/joint tasks.
ConfRAG-specific task quality is deliberately not replaced by QA scoring.
The snapshot timestamp denotes ingestion, not source freshness. Upstream
annotations may still contain semantic errors. No live paid model calls ran.

## Next dependency

Phase 12 — Baseline parity: matched model, retriever, ceilings, dataset subset,
cache policy and evaluation for closed-book, naive, iterative, premise-only and
full methods. Do not start Phase 13 before this comparison is ready.
