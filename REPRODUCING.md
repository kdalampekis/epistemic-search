# Reproducing Epistemic Search

There are two distinct reproducibility targets: executing the scripted system
checks and recomputing the reported pilot analysis from saved outputs. Neither
needs an API key. Remote model execution is not bitwise reproducible from a seed.

## 1. Locked offline fixture execution

Use a fresh source checkout (Python 3.12+, uv 0.9.28). Dependency installation
needs network or a populated uv cache; experiment execution uses fixture providers.
Do not copy `.env` into this checkout.

```sh
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras pytest
uv run --locked --all-extras python scripts/reproduce_offline.py fixtures
```

The script runs fixed/iterative comparisons, full and VOI examples, all seven
ablations, formal comparison, calibration, controlled interventions, failure
reports, dashboard and paper artifacts. It refuses existing fixture outputs and
removes `OPENAI_API_KEY` from child environments. Fixtures validate behavior,
not model quality. Fresh timestamps and local paths can change raw trace hashes;
fixture decisions/scores and scripted usage should remain the same.

## 2. Saved pilot reproduction package

Create the local archive from a checkout containing the original pilot and
ablation artifacts:

```sh
uv run --locked epistemic-search reproduction-bundle configs/paper_pilot.yaml artifacts/epistemic-search-reproduction.zip
uv run --locked epistemic-search verify-reproduction artifacts/epistemic-search-reproduction.zip
```

The archive includes allowlisted source/config/test/docs files, the lockfile,
complete scored runs, labels, traces, model/effort/seed metadata, grader versions,
dataset input hashes and a checksummed inventory. It excludes environment files,
credentials, model caches, spending databases and full benchmark downloads. The
manifest records the source commit and whether the working tree was dirty. Build
from a clean committed checkout for a release package. Archive member timestamps
are fixed; repeated exports from the same files produce identical bytes.

After verification, extract into a new directory and run:

```sh
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras python scripts/reproduce_offline.py saved
```

This regenerates `artifacts/reproduced-paper` and verifies all result/resource/
paired CSV tables plus statistical runs/comparisons/protocols against committed
outputs. It does not modify the original paper plan. Figure bytes may differ
across operating systems or fonts; numeric tables must agree exactly. Reanalysis
needs saved runs, not the original full benchmark corpora. A source-only clone
contains generated tables/figures and hashes, but **not** all raw pilot traces;
use the local archive for complete saved-output reproduction.

## 3. Dataset acquisition and attribution

The provider adapters and `prepare-datasets` CLI use checksum-pinned revisions in
`configs/datasets.lock.json`. See [benchmark setup](docs/experiments/benchmark_setup.md)
for download commands, licenses, source URLs and release counts. Full downloads
are intentionally omitted from the package. Retained trace contexts are benchmark
excerpts with original source provenance; preserve upstream attribution and terms
if sharing the archive. Archive creation is local and does not publish a dataset.

The pilot uses per-question provided contexts and seeded small subsets, not a web
index. ConfRAG is an ingestion/conflict diagnostic, not ordinary single-answer QA.
Its answer EM/F1 remains unavailable. No row is silently dropped.

## 4. Prompt and model provenance

Prompt construction/versioning lives in `baseline.py`, `iterative.py`,
`decomposition.py`, `evidence.py`, `engine.py`, `ablation_control.py`, `querying.py`
and `formal.py` under `src/epistemic_search`. Saved MODEL/DECOMPOSE events retain
actual structured requests/responses where recorded, and run manifests retain
resolved configs. Dataset selection, controller and statistical seeds are in YAML
and manifests. The current real pilot uses `gpt-6-luna` with medium reasoning;
no stronger-model robustness result or real calibration result is available.
Provider model identifiers are recorded aliases, not a guarantee of immutable
weights across future requests. Historical provider/pricing settings remain in
saved manifests; verify current access/prices before any fresh paid run.

## 5. Paid runs are a separate experiment

No reproduction command starts paid execution. The project cap remains **$50
total**, with **$5 within that cap** reserved for later Sol robustness. Astra is
excluded. The existing project ledger is `artifacts/research/spending.sqlite3`;
never reset it or substitute a fresh ledger to bypass cumulative spend. The
archive deliberately omits that mutable database and credentials. Fresh paid
execution requires the original reconciled ledger, matched model/effort settings,
an informative small pilot and a cost estimate before any experiment above $1.
See [budget policy](docs/experiments/research_budget.md).

Saved-output reproduction confirms arithmetic and provenance; it does not supply
independent model replications, semantic annotation, calibrated scores or evidence
of scientific superiority.

## 6. Regenerate the technical report

```sh
uv run --locked --extra paper python scripts/render_report.py
uv run --locked --extra paper python scripts/render_report.py --check
```

The prose template includes result tables and scalar values directly from checked
artifacts. The renderer verifies local links and records source/output hashes.
Open `docs/paper/REPORT.html` and print to PDF with CSS page size enabled to
recreate a print copy. The committed PDF was exported with installed Chromium;
`pdf-manifest.json` binds that PDF to the rendered HTML and browser version. PDF
timestamps can vary, so numeric/HTML checks are the portable reproduction target.
