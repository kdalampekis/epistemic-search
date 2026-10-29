# RV2 dataset audit

Date: 2026-10-29. Cost: **$0** (no model call; downloads only). Every count below is computed
from the local files by `uv run --locked epistemic-search rv2-dataset-audit` and saved in
[dataset_audit.json](../results/rv2/dataset_audit.json). Reproducibility manifests (source,
license, retrieval time, commit or archive SHA-256, per-file hashes) are in
[data/manifests/](../../data/manifests/). Raw data lives in `data/external/` and is git-ignored.
Downloads: `uv run --locked python scripts/download_rv2_datasets.py`. Tests never touch the
network.

The audit's job is to find where a dataset does **not** support the intended experiment. Where
it does not, the experiment changes; labels are never invented. Three such changes were
forced and are listed first.

## What changed because of what the files contain

1. **StrategyQA cannot supply the oracle-structure test.** Its decompositions are questions,
   not assertions (6,671 of 6,720 steps end in `?`, 3,000 contain `#n` back-references), so
   none is convertible to the pipeline's claim graph without rewriting them, which would be
   invented structure. **RV2-B's causal substitution runs on EntailmentBank**; StrategyQA is
   reported as a convertibility audit only and gets no model run.
2. **SciFact does have a neutral class**, contrary to the plan's cautious assumption: a claim
   whose cited abstract contains no rationale carries the official label `NEI`. RV2-A reports
   three-way results and, separately, the SUPPORT/CONTRADICT-only two-way score.
3. **HotpotQA's canonical host no longer resolves** (`curtis.ml.cmu.edu`, checked 2026-10-29).
   The checksum-pinned Hugging Face mirror used in the pilot is used instead.

## Summary

| Dataset | Used for | Splits used | Gold evidence | Gold proof/decomposition | Verdict |
| --- | --- | --- | --- | --- | --- |
| VitaminC | RV2-A (stance) | dev, 100 items | evidence text per claim | – | Usable; primary |
| SciFact | RV2-A (stance) | dev, 100 pairs | abstract + rationale sentences | – | Usable; domain control |
| EntailmentBank | RV2-B, RV2-C | dev, 18 examples | leaf facts + distractors | full entailment trees | Usable; primary |
| StrategyQA | RV2-B audit only | train (structure only) | paragraph ids, free-text facts | sub-question lists | **Not convertible**; no model run |
| HotpotQA | RV2-D | dev distractor | supporting sentences | – | Usable (distractor setting) |
| 2WikiMultiHopQA | RV2-D | dev | supporting facts | evidence triples (not used) | Usable (distractor setting) |
| HoVer | – | – | – | – | Not downloaded (optional) |

## VitaminC

* **Canonical source:** <https://github.com/TalSchuster/VitaminC>. Schuster, Fisch, Barzilay,
  *Get Your Vitamin C! Robust Fact Verification with Contrastive Evidence*, NAACL 2021.
* **License:** the archive's own `LICENSE` says the annotations incorporate Wikipedia material
  under the Wikipedia Copyright Policy / CC BY-SA 3.0, and the synthetic annotations derive
  from FEVER. The code repository is MIT (GitHub API).
* **Download:** `vitaminc.zip` linked from the README (`talschuster.github.io/static/vitaminc.zip`,
  22 MB), extracted unchanged. Manifest records the archive SHA-256.
* **Files:** `vitaminc/{train,dev,test}.jsonl` with fields `unique_id, case_id,
  wiki_revision_id, label, claim, evidence, page, revision_type`.
* **Label vocabulary, read from the files (not assumed):** `SUPPORTS`, `REFUTES`,
  `NOT ENOUGH INFO`. Mapping: `SUPPORTS→SUPPORT`, `REFUTES→CONTRADICT`,
  `NOT ENOUGH INFO→NEUTRAL`. The loader raises on any other label; nothing is dropped.
* **Splits:** train 370,653 rows, dev 63,054, test 55,197. Dev: 42,290 real and 20,764
  synthetic (FEVER-derived) revisions.
* **Contrastive structure:** a case is mostly a 2×2 grid of two claims against two evidence
  versions. A contrastive pair is the same claim with two different evidence texts and
  different labels. Dev contains 22,362 CONTRADICT/SUPPORT pairs, 8,867 NEUTRAL/SUPPORT and
  only **148** CONTRADICT/NEUTRAL pairs.
* **RV2 sample:** 50 pairs (100 items) from dev, one pair per case, split 17/17/16 over the
  three pair types, giving 34 CONTRADICT / 33 NEUTRAL / 33 SUPPORT. Seed 20261029.
* **Limitations:** evidence is a single sentence, not a retrieved document; one third of dev
  is synthetic; the pair-type mix of the sample is by design, not the natural distribution.
  A pair shows that evidence changed, not that the change is "minimal" in a semantic sense.
* **Usable:** yes. This is the primary stance benchmark.

## SciFact

* **Canonical source:** <https://github.com/allenai/scifact>. Wadden et al., *Fact or Fiction:
  Verifying Scientific Claims*, EMNLP 2020.
* **License:** the repository license is `NOASSERTION` per the GitHub API and the README
  states none. **The dataset content license is not verified here.**
* **Download:** the release archive named by the official `script/download-data.sh`
  (`scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz`, last modified 2021-01-26,
  3 MB); `latest` is an alias, so the archive SHA-256 is the version identity.
* **Files:** `data/corpus.jsonl` (5,183 abstracts), `claims_{train,dev,test}.jsonl`,
  `cross_validation/`.
* **Splits:** train 809 claims, dev 300, **test 300 unlabeled** (no `evidence` field). The
  loader refuses `test`.
* **Labels:** per claim, `evidence` maps cited document ids to rationale sentences with a
  `SUPPORT` or `CONTRADICT` label; no document has mixed labels. A claim with empty `evidence`
  but a non-empty `cited_doc_ids` is `NEI` for each cited abstract (all 112 dev and 304 train
  NEI claims have cited documents). Unit of analysis: **(claim, cited abstract) pair**.
  Dev pairs: 138 SUPPORT, 71 CONTRADICT, 131 NEI. Mapping: `NEI→NEUTRAL`.
* **RV2 sample:** 100 dev pairs stratified 33/34/33. The text shown to the stance component is
  title plus the full abstract (not just rationale sentences), identically for all classes, so
  text length does not leak the label.
* **Limitations:** NEI means "this abstract has no rationale for this claim", not "no
  evidence exists anywhere"; the domain is biomedical; abstracts are long.
* **Usable:** yes, as a domain control for stance.

## EntailmentBank

* **Canonical source:** <https://github.com/allenai/entailment_bank>. Dalvi et al., *Explaining
  Answers with Entailment Trees*, EMNLP 2021. **Pinned commit
  `daac2fdb7ab52ec3ef8f2953f59288c1edd7c2f0`.**
* **License:** the repository is Apache-2.0; the dataset content license is not verified here.
* **Download:** shallow `git clone`; only `data/public_dataset/` and `LICENSE` are kept.
* **Files:** `entailment_trees_emnlp2021_data_v2/dataset/task_{1,2,3}/{train,dev,test}.jsonl`
  (train 1,313, dev 187, test 340). Task 1 holds only the gold leaves; **task 2 holds the same
  leaves plus distractors in a 25-sentence pool**; task 3 requires corpus retrieval. RV2 uses
  task 2 (it contains task 1's leaves). Test is untouched.
* **Gold structure per record:** `question, answer, hypothesis`, the proof (`sentN & sentM ->
  intK: text; ... -> hypothesis`), the intermediate conclusions with text, the distractor ids
  with `distractors_relevance`, and depth/length. The adapter preserves all of it: leaf
  facts, intermediate conclusions, hypothesis, edge structure and distractors.
* **Convertibility (dev, 187):** all 187 proofs parse; all 187 convert to the pipeline's
  `ProofGraph` and the formal reasoner runs on all of them; **166 are trees and 21 share a
  node** (a leaf or intermediate conclusion used by two steps, a DAG); 0 are not convertible
  (`not_convertible = 0`). Leaf counts range from 2 to 15; depth from 1 to 7.
* **What the conversion loses:** the pipeline's graph has claims only at the leaves, so each
  intermediate conclusion becomes an AND node and **its text is dropped**. The adapter keeps
  the text; the graph cannot.
* **Distractors:** 144 of 187 dev examples have at least 20 distractors and every example
  has at least 10. The highest-relevance distractors are used for C3/C4, so they are the most
  confusable ones.
* **RV2 sample:** 18 dev examples, 6 each with 3, 4 and 5 leaves, chosen by seeded hash order
  (extendable as a prefix). Used for RV2-B and RV2-C.
* **Limitations:** (a) leaves are generic grade-school science facts that a language model
  already knows, so a model can answer without the missing leaf and "answered despite missing
  evidence" must not be confused with "answered wrongly"; (b) a high-relevance distractor can
  partly substitute for a removed leaf, so C3 abstention is "expected by the gold proof" rather
  than proven; C2 is the clean test; (c) answers are free text, so answer matching is a
  deterministic token-F1 proxy, not a semantic judge.
* **Usable:** yes; the primary dataset for RV2-C and RV2-B.

## StrategyQA

* **Canonical source:** code <https://github.com/eladsegal/strategyqa>, data
  <https://allenai.org/data/strategyqa>. Geva et al., *Did Aristotle Use a Laptop?*, TACL 2021.
* **License:** the code repository is MIT (GitHub API); the dataset license is not verified here.
* **Download:** `strategyqa_dataset.zip` from `storage.googleapis.com/ai2i/strategyqa/data/`
  (3.4 MB), extracted unchanged. Manifest records the archive SHA-256.
* **Which split carries what (measured):**

  | File | Examples | Fields |
  | --- | ---: | --- |
  | `strategyqa_train.json` | 2,290 | answer, decomposition, description, evidence, facts, qid, question, term |
  | `strategyqa_train_filtered.json` | 2,821 | answer, description, qid, question, term |
  | `strategyqa_test.json` | 490 | qid, question |

  Decompositions, facts and evidence exist **only in the 2,290 training examples**. Test has
  no answers. `strategyqa_train_paragraphs.json` holds 9,251 Wikipedia paragraphs.
* **Annotation type:** boolean answer (1,071 true); a decomposition of 1 to 5 sub-questions
  with `#n` back-references and a final comparison; free-text gold `facts`; per-step paragraph
  evidence from three annotators.
* **Convertibility (strict rule: every step is an assertion with no back-reference):**
  **fully convertible 0**, facts-only 2,290, none 0. The facts are declarative but have no
  annotated alignment to the steps, and a yes/no answer is not a conjunction of them (for a
  "no" answer the facts support the negation). So the facts can serve as evidence statements
  but not as an oracle proof.
* **Limitations / consequence:** realistic multi-step questions of this kind compute over
  retrieved values (for example "Is #2 greater than #1?"). The pipeline's boolean
  AND/OR/NOT graph over claims has no way to bind values. This is recorded as a scope
  limitation, not run: no model call is made on StrategyQA, so no internal split is needed.
* **Usable:** as a convertibility audit only.

## HotpotQA

* **Canonical source:** <https://github.com/hotpotqa/hotpot>. Yang et al., *HotpotQA*, EMNLP 2018.
* **License:** CC BY-SA 4.0 (dataset card); code Apache-2.0.
* **Download:** canonical host unreachable (see above). The pinned Hugging Face mirror
  (`hotpotqa/hotpot_qa`, revision `1908d6af…`, parquet SHA-256 `c20b638c…`) is converted to the
  official JSON schema by the pilot's `hotpot_from_parquet`.
* **Used:** dev distractor, 7,405 questions (5,918 bridge, 1,487 comparison), every question
  `level: hard`. **Distractor setting:** 10 paragraphs per question for 7,345 of them (the
  rest have 2 to 9). Exactly 2 gold titles per question. Gold = `supporting_facts`.
  The full-Wikipedia corpus is not downloaded and not needed: RV2-D diagnoses retrieval
  inside a fixed per-question pool, as in the pilot.
* **Limitations:** a 10-paragraph pool is far easier than open retrieval, and it is the only
  setting tested; the 22 pilot questions are excluded from RV2 samples.
* **Usable:** yes, for the retrieval diagnostic.

## 2WikiMultiHopQA

* **Canonical source:** <https://github.com/Alab-NII/2wikimultihop>. Ho et al., *Constructing a
  Multi-hop QA Dataset for Comprehensive Evaluation of Reasoning Steps*, COLING 2020.
* **License:** repository Apache-2.0; Wikipedia-derived content has its own terms.
* **Download:** the pilot's checksum-locked official `data_ids_april7.zip` release (SHA-256
  `95df2bf5…`); `dev.json` and `id_aliases.json` are kept.
* **Used:** dev, 12,576 questions (5,236 compositional, 3,040 comparison, 2,751
  bridge_comparison, 1,549 inference), 10 paragraphs each. Gold titles: 2 for 9,825 questions,
  4 for 2,751. Gold = `supporting_facts`.
* **Limitations:** the "corrected" release was not located separately; this is the April 7
  2021 release with ids. Same distractor-setting caveat as HotpotQA.
* **Usable:** yes, for the retrieval diagnostic.

## HoVer

Not downloaded and not used. It is optional in the plan, and its official download script also
fetches `wiki_wo_links.db` and retrieval caches. Recorded in `data/manifests/hover.yaml` with
`status: not_used`.

## Cross-cutting limits

* Contamination of the 22 pilot questions: RV2-D excludes them.
* No sample here is a held-out test set: official test splits are untouched or unlabeled.
* Small samples (50–100 items for stance, 18 for the controlled proof experiment) mean
  confidence intervals will be wide; the plan states in advance how that maps to
  `INCONCLUSIVE`.
