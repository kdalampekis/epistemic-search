# Experimental Protocol

## 1. Goal

Evaluate whether explicit epistemic state and proof-obligation-guided retrieval improve:

1. answer quality;
2. abstention;
3. contradiction handling;
4. evidence efficiency;
5. token/search/latency efficiency.

The experiments must be designed as a publishable study, not as a product demo.

## 2. Systems

### B0 — Closed-book LLM
No retrieval.

### B1 — Naive top-k RAG
Single retrieval pass, fixed `k`.

### B2 — Iterative relevance RAG
Repeated search generated from current reasoning state, but no explicit premise graph.

### B3 — Sufficiency-judge RAG
Model judges whether evidence is sufficient and generates a gap query if not. This approximates the S2G-RAG family.

### B4 — Premise-directed RAG
Explicit unresolved premise selection, but no full belief state/formal sufficiency layer.

### M1 — Full Epistemic Search
Premise graph + evidence ledger + belief state + formal sufficiency + contradiction handling + cost-aware controller + abstention.

## 3. Datasets

### Tier 1 — required

#### HotpotQA
Multi-hop evidence chains.

#### 2WikiMultiHopQA
Compositional multi-hop questions.

#### ConfRAG
Real-world conflicting web references.

### Tier 2

#### DRUID
Unreliable, insufficient, and difficult retrieved contexts.

#### Abstain-QA or equivalent
Selective answering.

#### SciFact / PubMedQA
Condition-level evidence verification and abstention.

### Tier 3 — controlled transformations

Create reproducible variants:

1. Missing premise
2. Contradicted premise
3. Redundant relevant context
4. Repetition bias
5. Evidence-order bias
6. Freshness conflict

These allow causal analysis.

## 4. Equal-budget rule

All systems must be compared under matched limits:

```text
max_search_calls
max_documents
max_retrieved_tokens
max_llm_calls
max_total_llm_input_tokens
```

Report actual usage as well as ceilings.

## 5. Metrics

### Answer quality
- Exact Match
- token F1
- accuracy
- citation-supported answer accuracy

### Selective prediction
- answer coverage
- risk at coverage
- risk-coverage curve
- AURC
- abstention precision/recall/F1
- false-answer rate on unanswerable examples

### Evidence
- evidence recall
- evidence precision
- required-premise coverage
- decisive-evidence recall
- unresolved required premises at termination

### Contradiction
- contradiction precision/recall/F1
- correct conflict resolution
- unsafe answer rate under unresolved conflict
- both-sides coverage

### Calibration
- Brier score
- Expected Calibration Error
- reliability diagrams

### Efficiency
- search calls/question
- docs/chunks retrieved
- retrieved tokens
- LLM input/output tokens
- total tokens
- latency
- API cost
- accuracy per 1k input tokens
- correct answers/search call

## 6. Primary paper metrics

Primary:
1. answer accuracy;
2. selective risk/coverage;
3. retrieved/context token count;
4. contradiction F1.

Secondary:
- latency;
- cost;
- calibration;
- evidence recall.

## 7. Core experiments

### E1 — Premise guidance on multi-hop QA
Datasets:
- HotpotQA
- 2WikiMultiHopQA

Compare B1–B4 and M1.

Plot:
- accuracy vs search calls;
- accuracy vs retrieved tokens;
- premise coverage vs turns.

### E2 — Sufficiency and abstention
Use missing-premise variants.

Measure:
- answers despite missing evidence;
- correct missing-premise identification;
- targeted search;
- final abstention quality.

### E3 — Contradiction handling
Use ConfRAG.

Compare:
- raw concatenation;
- iterative relevance search;
- explicit evidence-state system.

Measure:
- detection;
- answer accuracy;
- unsafe answer rate;
- extra search cost.

### E4 — Token efficiency
At comparable quality levels, measure:
- retrieval tokens;
- context tokens;
- model calls;
- total tokens.

This is central to the fellowship story.

### E5 — Acquisition policy
Compare:
- random unresolved;
- highest importance;
- highest uncertainty;
- approximate value of information.

### E6 — Calibration
Compare:
- raw self-confidence;
- NLI score;
- calibrated NLI;
- evidence aggregation;
- optional semantic entropy.

### E7 — Formal checker vs generative sufficiency
Compare:
1. LLM sufficiency judge;
2. structured proof graph;
3. proof graph + belief thresholds.

## 8. Ablations

A1 no proof graph  
A2 no belief state  
A3 no contradiction state  
A4 no cost-aware controller  
A5 no abstention  
A6 no evidence compaction  
A7 no formal sufficiency  
A8 no premise-directed query

## 9. Premise decomposition evaluation

Evaluate separately:
- atomicity;
- completeness;
- necessity;
- dependency accuracy;
- gold evidence-hop recall where possible.

Perform manual annotation on a stratified subset.

## 10. Statistical analysis

Use:
- bootstrap confidence intervals;
- paired permutation/McNemar tests where appropriate;
- mean/median/p90 for cost distributions.

## 11. Robustness

Final comparison should include:
- at least one strong proprietary model;
- at least one strong open-weight model if feasible;
- at least two retrieval settings.

## 12. Human evaluation

After automated evaluation stabilizes, humans judge:
- answer justification;
- abstention appropriateness;
- citation support;
- whether identified blocker is genuinely necessary.

## 13. Required figures

1. Accuracy vs retrieved tokens
2. Accuracy vs search calls
3. Risk-coverage curve
4. Contradiction F1 vs conflict density
5. Reliability diagram
6. Premise coverage by retrieval turn
7. Action distribution
8. Failure taxonomy
9. Latency/cost breakdown
10. Ablation table

## 14. Experiment logging

```yaml
run_id: ...
git_commit: ...
config_hash: ...
dataset: ...
split: ...
model: ...
retriever: ...
seed: ...
method: ...

budget:
  max_search_calls: ...
  max_docs: ...
  max_tokens: ...

metrics: ...

artifacts:
  trace_file: ...
  answer_file: ...
  evidence_file: ...
```

## 15. Stop conditions

Do not write strong paper claims if:
- baselines are not reproducible;
- budget accounting is incomplete;
- evaluation differs between methods;
- test data were tuned against;
- examples are cherry-picked.

## 16. Minimum convincing fellowship result

Before applying with this project, aim for:
- 3 credible baselines;
- 2 QA datasets;
- ConfRAG contradiction results;
- 2+ ablations;
- token/cost accounting;
- risk-coverage analysis;
- 5–10 visual trace examples;
- 4–6 page technical report.

A small rigorous result is better than a huge unfinished architecture.
