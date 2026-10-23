# Benchmark setup and Phase 11 validation

## Reproduce acquisition

```sh
uv sync --locked --extra benchmarks --python 3.12
uv run --locked --extra benchmarks epistemic-search prepare-datasets configs/datasets.lock.json artifacts/benchmarks
uv run --locked epistemic-search evaluate configs/hotpotqa_smoke.yaml
uv run --locked epistemic-search evaluate configs/2wikimultihopqa_smoke.yaml
uv run --locked epistemic-search evaluate configs/confrag_smoke.yaml
```

Outputs must not already exist. Downloads total approximately 511 MB; only the
2Wiki dev and alias members are extracted (the archive also contains train/test).
Setup may use additional temporary disk space. All hashes are in the committed
lock and local `setup-manifest.json`. No model API key is needed for these smoke
runs. The smoke model always abstains, so QA EM/F1 must be zero, not evidence of
model performance. Each run selects two cases by seed 42 and records their IDs.
To evaluate all cases, omit `evaluation.limit`; do not select cases by outcomes.

## Verified releases

| Dataset | Release and scope | Validated rows | Provided documents |
| --- | --- | ---: | ---: |
| HotpotQA | Distractor validation, HF revision `1908d6afbbead072334abe2965f91bd2709910ab` | 7,405 | 73,700 |
| 2WikiMultiHopQA | Official April 7, 2021 `data_ids_april7.zip`, dev | 12,576 | 125,760 |
| ConfRAG | Suggested annotations, revision `529e760a78a58791d0387fe469e0732377a6d94d` | 1,098 | 10,447 |

The Hotpot server linked by the [official site](https://hotpotqa.github.io/)
timed out over HTTP and HTTPS in this environment. Setup therefore pins the
[hotpotqa Hugging Face mirror](https://huggingface.co/datasets/hotpotqa/hotpot_qa).
Parquet conversion preserves IDs, contexts, answers and supporting facts; it
changes serialization, so both original and converted hashes are recorded.

The [2Wiki repository](https://github.com/Alab-NII/2wikimultihop) links the April 7
release and documents the alias-aware scorer. The alias file ships in the same
archive. The repository LICENSE is Apache-2.0; do not infer a separate license
grant for third-party source text from that alone. Cite Ho et al., COLING 2020.
HotpotQA is CC BY-SA 4.0; cite Yang et al., EMNLP 2018. The ConfRAG dataset card
specifies CC BY 4.0; cite Yuan et al., ACL 2026. Preserve attribution and review
upstream terms before redistributing derived dataset artifacts.

The [ConfRAG card](https://huggingface.co/datasets/OracleY/ConfRAG) recommends the
suggested file. Its 1,098 records are not the original 1,814-question dataset
reported in the paper. Do not mix those counts or claim reproduction of paper
results using this release. It supplies no official dev/test partition; the HF
split is named train. Any later partition must be explicitly recorded.

ConfRAG contains Unicode line separators inside valid JSON strings. Read actual
newline-delimited records; Python `str.splitlines()` splits these strings and
creates spurious parse errors. No records were dropped or repaired.

See [ADR 0004](../decisions/0004-native-benchmark-protocols.md) for data isolation,
answer-only scoring, subset selection and the limits of this phase. ConfRAG's
clustering/answer-coverage/reason-coverage experiments belong to Phase 14.
