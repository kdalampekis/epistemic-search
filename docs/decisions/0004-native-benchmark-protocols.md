# ADR 0004 — Native benchmark inputs and explicit answer metrics

Accepted in Phase 11. Extends ADR 0002 without changing generic v1 scoring.

## Inputs and retrieval scope

HotpotQA distractor and 2Wiki use every provided paragraph, including distractors,
in a separate lexical retrieval pool per question. ConfRAG uses only website
`content` and source identity. Gold supporting facts, triples, answer IDs, aliases,
website answer/reason/trust annotations and clusters never enter retrieval or
model prompts. Evaluator labels are saved separately in `labels.jsonl`.

The application boundary supplies the document pool independently of QueryCase;
the evaluator still strips all labels and metadata before calling any method.
This is provided-context retrieval, not full-Wikipedia or live-web evaluation.
Original paragraph boundaries and ConfRAG document indices are retained through
stable source IDs. Snapshot timestamps record local ingestion, not publication
or freshness. The existing fixture retriever remains lexical overlap, not BM25.

All rows validate before selecting an optional subset. Selection sorts by
SHA256(`seed:case_id`), independent of answers, input order and performance.
Manifests record selected IDs, raw input and alias hashes, config, retrieval scope,
and scorer version. Full raw inputs are retained outside git for annotation audits.

## Scoring

- `english-em-token-f1-v1`: unchanged for generic JSONL.
- `hotpotqa-answer-v1`: official answer normalization and categorical yes/no/
  noanswer F1 rule; zero F1 for empty normalized strings.
- `2wiki-answer-aliases-v1.1`: same answer rules, maximum EM and F1 over canonical
  answer plus the release's aliases and demonyms. Alias file is mandatory.
- `confrag-ingestion-only-v1`: no fabricated single gold answer, EM/F1 null.
  Viewpoints are not equivalent answer aliases. Preserve contradiction/cluster/
  reason labels for Phase 14's dedicated tasks. Phase 11 runs measure plumbing,
  answer coverage and usage only, not ConfRAG task performance.

Official Hotpot/2Wiki answer scripts report percentages; internal scores remain
fractions in [0,1]. We do not claim official supporting-fact, evidence-triple or
joint metrics. All methods use the same selected dataset protocol. Abstentions,
errors and exhausted runs score zero on labelled QA and remain in denominators.

Sources inspected on 2026-10-23:
- https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py
- https://github.com/Alab-NII/2wikimultihop/blob/13800e5be57df1b4040b9b1588c6c811779e69e9/2wikimultihop_evaluate_v1.1.py
- https://huggingface.co/datasets/OracleY/ConfRAG/tree/529e760a78a58791d0387fe469e0732377a6d94d

## Acquisition

`configs/datasets.lock.json` pins download URLs and SHA256 bytes. Archive extraction
reads only named, checksum-verified members; no downloaded code executes. The
Hotpot mirror needs the optional, lockfile-pinned pyarrow dependency to convert
Parquet to native JSON. Original source hashes and converted output hashes are
recorded. Tests mock network access. Failed setup does not create a success
manifest; retry in a new directory. Raw datasets are not redistributed in git.
