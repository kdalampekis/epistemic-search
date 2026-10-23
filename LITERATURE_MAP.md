# Literature Map and Novelty Guardrails

**Snapshot date:** 2026-10-23

This is a working novelty map, not an exhaustive literature review. Update it before submission.

## 1. Active / adaptive retrieval

### FLARE — Active Retrieval Augmented Generation
Jiang et al., 2023  
https://arxiv.org/abs/2305.06983

Key idea:
- decide when/what to retrieve during generation;
- trigger retrieval from low-confidence future content.

Relation:
- demonstrates why retrieve-once RAG can be insufficient;
- does not provide the full proof-obligation / belief-state architecture proposed here.

### Self-RAG
Asai et al., 2023  
https://arxiv.org/abs/2310.11511

Key idea:
- adaptive retrieval;
- self-reflection;
- learned reflection tokens.

Relation:
- important adaptive/self-evaluation baseline family.

### Adaptive-RAG
Jeong et al., 2024  
https://arxiv.org/abs/2403.14403

Key idea:
- choose no retrieval, single-step retrieval, or iterative retrieval based on question complexity.

Relation:
- efficiency-aware retrieval strategy;
- does not maintain premise-level epistemic state.

## 2. Explicit sufficiency and missing gaps

### S2G-RAG
Li et al., 2026  
https://arxiv.org/abs/2604.23783

Key idea:
- explicit sufficiency judge;
- structured missing-gap items;
- gap items drive next query;
- compact evidence context.

This is close prior work.

**Novelty guardrail:**  
Do not claim that explicitly detecting missing information and retrieving it is new.

### Socrates-RAG
Zhao et al., 2026  
https://arxiv.org/abs/2609.35773

Key idea:
- premise-directed active retrieval;
- competing answers;
- unresolved premise chosen to discriminate hypotheses;
- finite search budget;
- answer or abstain.

This is extremely close conceptually.

**Novelty guardrail:**  
Do not claim premise-directed active retrieval is novel.

Our target differentiation:
- explicit support/contradiction/unknown evidence state;
- probabilistic/calibrated belief;
- formal answer sufficiency;
- contradiction-specific control;
- cost/value-of-information acquisition;
- broad selective-risk and token-efficiency evaluation.

## 3. Uncertainty and abstention

### Semantic Entropy
Farquhar et al., Nature 2024  
https://www.nature.com/articles/s41586-024-07421-0

Key idea:
- uncertainty over semantic meaning rather than raw token sequences;
- effective detection of confabulations;
- useful for selective answering.

Relation:
- potential auxiliary uncertainty signal;
- not the same as evidence sufficiency.

### Do LLMs Know When to NOT Answer?
Madhusudhan et al., 2024  
https://arxiv.org/abs/2407.16221

Key idea:
- evaluates LLM abstention ability;
- answerable/unanswerable framing;
- shows strong models still struggle.

### Knowing When Not to Answer: Abstention-Aware Scientific Reasoning
Abdaljalil et al., 2026  
https://arxiv.org/abs/2602.14189

Key idea:
- decomposes scientific claims into minimal conditions;
- audits conditions against evidence;
- support/refute/abstain.

This is another close neighbor.

## 4. Symbolic / formal reasoning

### Logic-LM
Pan et al., 2023  
https://arxiv.org/abs/2305.12295

Key idea:
- LLM converts natural language to symbolic formulation;
- deterministic symbolic solver performs inference;
- solver errors can drive refinement.

Important lesson:
- formal inference can be exact relative to the symbolic model;
- semantic extraction can still be wrong.

### LINC
Add current canonical citation before submission.

Relation:
- another language-to-formal-inference line of work.

## 5. Information gain / retrieval efficiency

### InfoGain-RAG
Wang et al., EMNLP 2025  
https://aclanthology.org/2025.emnlp-main.365/

Key idea:
- Document Information Gain estimates the value a retrieved document contributes;
- information-gain-based reranking/filtering improves generation.

Relation:
- directly relevant to value-of-information ideas.

Difference:
- our proposed policy chooses what unresolved proof obligation to acquire information about, not only which existing document to rank higher.

## 6. Conflicting evidence

### ConfRAG
Yuan et al., ACL 2026  
https://aclanthology.org/2026.acl-long.11/

Key facts:
- 1,814 real-world questions;
- average ~9.58 retrieved paragraphs per question;
- 57.2% contain explicit contradictions;
- strong models still show substantial gaps.

Use:
- primary contradiction benchmark.

Phase 11 verification (2026-10-23): the ACL Anthology entry confirms the
original dataset counts above. The authors' dataset card at
https://huggingface.co/datasets/OracleY/ConfRAG recommends
`ConfRAGsuggested.jsonl`; revision `529e760a78a58791d0387fe469e0732377a6d94d`
contains 1,098 records, verified by complete ingestion. These are distinct
release counts. ConfRAG evaluates clustering, answer coverage and reason
coverage; its opposing viewpoints must not be treated as interchangeable
gold answers for ordinary EM/F1. See `docs/experiments/benchmark_setup.md`.

### Rational Synthesizers or Heuristic Followers?
Naphade, Findings of ACL 2026  
https://aclanthology.org/2026.findings-acl.2003/

Key idea:
- models may follow repetition and ordering heuristics when aggregating evidence;
- explanations can be unfaithful.

Relation:
- supports explicit evidence accounting instead of naive context concatenation.

### DRUID
Hagström et al., ACL 2025  
https://aclanthology.org/2025.acl-long.968/

Key idea:
- real retrieved contexts can be unreliable, insufficient, or difficult to interpret.

Use:
- insufficiency/context-quality evaluation.

## 7. Adjacent 2026 epistemic-policy work

There is also rapidly emerging work framing RAG/action selection explicitly as an epistemic policy problem. This increases the importance of cautious novelty claims.

Before submission, search specifically for:
- epistemic policy RAG;
- belief-state RAG;
- certainty-aware RAG;
- proof-obligation retrieval;
- value-of-information retrieval.

## 8. Perplexity relevance

Perplexity Research publicly states that its research program focuses on:

- search;
- reasoning;
- agents;
- systems.

Research page:
https://research.perplexity.ai/

This project should be positioned as studying a control/reliability problem relevant to search systems, not as reproducing Perplexity's indexing infrastructure.

## 9. Most defensible working research gap

A cautious claim:

> Recent RAG systems increasingly support adaptive retrieval, gap detection, premise-directed search, uncertainty estimation, and abstention. It remains an open empirical question whether a unified explicit epistemic state—combining premise dependencies, support/contradiction evidence, calibrated uncertainty, structured answer sufficiency, and finite-budget value-of-information control—can improve the reliability-efficiency frontier of retrieval-augmented question answering.

This sentence must be revalidated immediately before paper submission.

## 10. Claims we must NOT make

Do not claim:

- “No one has done premise-aware retrieval.”
- “No RAG system detects missing information.”
- “This is the first RAG system to abstain.”
- “Formal reasoning guarantees factual truth.”
- “LLM confidence is probability.”
- “More retrieval always hurts.”
- “Perplexity does not reason about uncertainty.”

## 11. Literature-search checklist

Search:
- ACL Anthology
- arXiv cs.IR / cs.CL / cs.AI
- SIGIR
- ICLR
- NeurIPS
- ICML
- EMNLP
- NAACL
- AAAI

Queries:
- premise-directed retrieval
- premise-aware RAG
- structured sufficiency RAG
- belief-state RAG
- epistemic RAG
- contradiction-aware RAG
- selective RAG
- abstention RAG
- information gain RAG
- value of information LLM retrieval
- active information gathering LLM
- formal reasoning RAG
- evidence sufficiency retrieval
