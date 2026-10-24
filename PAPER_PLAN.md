# Paper Plan

Delivered snapshot: [Phase 25 technical report](docs/paper/REPORT.md). The plan
below is the original outline. The final title reflects the negative pilot; real
ablation, calibration, formal-backend and stronger-model claims remain untested.
This is a technical report, not a submitted superiority/novelty paper.

## Working title

**Epistemic Search: Premise-Aware Active Retrieval with Belief States, Formal Sufficiency Checks, and Selective Answering**

Alternative:

**Search What Is Missing: Proof-Obligation-Guided Retrieval for Reliable and Efficient RAG**

Do not finalize the title until the experiments reveal the strongest actual contribution.

## Abstract skeleton

Retrieval-augmented generation systems commonly optimize relevance but may still answer from incomplete or contradictory evidence. Recent work improves iterative retrieval by deciding when to search again or by identifying missing evidence gaps. We study whether retrieval can instead be controlled through an explicit epistemic state over the premises required to justify an answer. We introduce [METHOD], which decomposes questions into proof obligations, tracks supporting and contradicting evidence, estimates premise uncertainty, applies a structured sufficiency checker, and chooses among answering, targeted retrieval, conflict resolution, and abstention under a finite budget. Across [DATASETS], we compare against fixed and iterative RAG baselines under matched search and token budgets. [RESULTS]. Ablations show [FINDINGS]. Our results suggest [CAUTIOUS CONCLUSION].

## 1. Introduction

Narrative:

1. Search relevance is not identical to answer justification.
2. A system can retrieve many relevant passages while missing one decision-critical fact.
3. Conflicting sources make “more context” nontrivial and potentially harmful.
4. Existing adaptive RAG moves toward repeated retrieval, sufficiency judging, and premise-directed search.
5. We test whether an explicit proof/belief state improves reliability and efficiency.
6. Contributions.

## 2. Related work

- Retrieval-Augmented Generation
- Active/iterative retrieval
- Sufficiency and gap detection
- Selective prediction and abstention
- Uncertainty quantification
- Contradiction-aware RAG
- Neuro-symbolic/formal reasoning
- Information gain and active information acquisition

## 3. Method

### 3.1 Finite-budget QA formulation
### 3.2 Premise decomposition
### 3.3 Evidence ledger
### 3.4 Belief state
### 3.5 Structured/formal sufficiency
### 3.6 Epistemic controller
### 3.7 Cost-aware acquisition
### 3.8 Answer/abstention policy

## 4. Experimental setup

- datasets;
- baselines;
- models;
- retrievers;
- budgets;
- metrics;
- calibration;
- statistical testing.

## 5. Main table

| Method | Accuracy | Coverage | Selective Risk | Retrieved Tokens | Search Calls | Contradiction F1 |
|---|---:|---:|---:|---:|---:|---:|

## 6. Analysis

- where premise guidance helps;
- where it wastes computation;
- unresolved evidence;
- contradiction cases;
- calibration;
- token-cost Pareto frontier;
- failure taxonomy.

## 7. Ablations

- no formal reasoner;
- no belief state;
- no contradiction state;
- no cost-aware controller;
- no abstention;
- no evidence compaction;
- generic query instead of targeted premise query.

## 8. Limitations

Must explicitly discuss:

- premise extraction errors;
- evidence stance errors;
- source credibility/freshness;
- open-world incompleteness;
- dependence between sources;
- formalization brittleness;
- latency/cost;
- benchmark imperfections;
- coverage/reliability tradeoff.

## 9. Ethics

- do not present legal/medical demos as advice;
- preserve provenance;
- do not fabricate certainty;
- discuss source-authority bias;
- distinguish abstention from content refusal.

## 10. Reproducibility appendix

Include:
- prompts;
- configs;
- model versions;
- retriever/index versions;
- dataset hashes;
- metric definitions;
- cost accounting;
- statistical tests.

## 11. Submission strategy

Choose venue after results.

Potential communities:
- ACL / EMNLP / NAACL;
- SIGIR;
- ICLR/NeurIPS workshops;
- trustworthy/retrieval/agentic AI workshops.

The paper should follow the strongest empirical result rather than a predetermined venue.
