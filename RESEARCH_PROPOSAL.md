# Research Proposal

## Epistemic Search: Premise-Aware Active Retrieval with Belief States, Formal Sufficiency Checks, and Selective Answering

## 1. Motivation

Retrieval-Augmented Generation improves factual grounding by giving a language model external evidence. However, retrieval quality alone does not solve several important failure modes:

- the required evidence may not be present in the first retrieved set;
- the system may retrieve a large amount of relevant-but-insufficient context;
- multiple sources may contradict one another;
- the model may answer despite a missing premise;
- the system may not know when another retrieval is worth the cost;
- the model may confuse high linguistic confidence with justified belief;
- adding more context can add distractors, noise, latency, and token cost.

The central hypothesis of this project is:

> **A retrieval system should maintain an explicit epistemic state over the premises required to answer a question, and retrieval should be controlled by unresolved proof obligations rather than by relevance alone.**

## 2. Problem formulation

Given:

- question `q`;
- candidate conclusions `Y = {y1, ..., yn}`;
- retrieval environment `E`;
- finite search/token/latency budget `B`;

construct an agent that chooses actions:

```text
SEARCH(query)
OPEN(document)
ASK(user_question)
ANSWER(answer)
ABSTAIN(reason)
```

while maintaining:

```text
S_t = {
  proof_obligations,
  evidence_ledger,
  belief_state,
  contradictions,
  unresolved_gaps,
  remaining_budget
}
```

The policy should maximize answer utility while minimizing unsupported answers and acquisition cost.

A conceptual objective:

```text
Expected Utility =
  answer_quality
  - λ1 * unsupported_answer_risk
  - λ2 * retrieval_cost
  - λ3 * context_token_cost
  - λ4 * latency
```

This is initially an engineering objective, not a claim that the full problem has been solved optimally.

## 3. Research questions

### RQ1 — Premise-aware retrieval
Does explicit decomposition into answer-critical premises improve retrieval efficiency and answer accuracy compared with relevance-oriented iterative RAG?

### RQ2 — Sufficiency
Can a proof-obligation / sufficiency checker reduce unsupported answers by identifying exactly which required conditions remain unresolved?

### RQ3 — Abstention
Does explicit evidence-state tracking improve the risk-coverage tradeoff and abstention quality compared with model self-confidence alone?

### RQ4 — Contradiction
Does representing support and contradiction separately improve performance on conflicting web evidence?

### RQ5 — Cost-aware active search
Can a value-of-information-inspired search policy achieve equal or better answer quality with fewer search calls or fewer LLM input tokens?

### RQ6 — Formal reasoning
When the question admits a structured logical representation, does a symbolic sufficiency layer outperform purely generative “is the evidence enough?” judging?

### RQ7 — Robustness
How sensitive is the architecture to errors in premise extraction, evidence classification, and source quality?

## 4. Hypotheses

### H1
Premise-directed retrieval will resolve multi-hop questions with fewer irrelevant retrieved tokens than generic iterative retrieval at matched accuracy.

### H2
Explicit `UNKNOWN` and `CONTRADICTED` states will improve abstention precision and reduce unsupported answers.

### H3
A formal sufficiency checker will provide the largest gain on questions whose answer depends on conjunctions, exceptions, temporal conditions, or eligibility constraints.

### H4
Contradiction-aware evidence aggregation will outperform “concatenate everything and ask the LLM” on ConfRAG-style settings.

### H5
Value-of-information prioritization will improve the accuracy-versus-cost Pareto frontier.

### H6
The full system will fail when premise decomposition is materially wrong; therefore premise-quality metrics and decomposition ablations are necessary.

## 5. Proposed architecture

```text
Question
  ↓
Question / intent analyzer
  ↓
Candidate answer hypotheses
  ↓
Premise decomposer
  ↓
Proof-obligation graph
  ↓
Initial retrieval
  ↓
Atomic evidence extraction
  ↓
Evidence ledger
  ├── supports(claim)
  ├── contradicts(claim)
  ├── neutral(claim)
  └── provenance
  ↓
Belief-state estimator
  ↓
Formal / structured sufficiency checker
  ↓
Decision state
  ├── sufficient
  ├── missing premise
  ├── contradiction
  ├── ambiguity
  └── exhausted
  ↓
Controller
  ├── ANSWER
  ├── SEARCH_MORE(target_premise)
  ├── RESOLVE_CONFLICT(target_claim)
  ├── ASK
  └── ABSTAIN
```

## 6. Evidence model

Each atomic evidence item should include:

```yaml
evidence_id: e_123
source:
  uri: ...
  title: ...
  retrieved_at: ...
  source_type: web|corpus|benchmark

claim_id: c_3

stance:
  label: support|contradict|neutral
  score: 0.84

extraction:
  text_span: ...
  model: ...
  prompt_version: ...

provenance:
  search_query: ...
  rank: 2
  retrieval_score: ...

quality:
  freshness: ...
  authority: ...
  duplication_group: ...
```

Do not collapse all evidence into one similarity score.

## 7. Belief state

For each claim:

```yaml
claim_id: c_3
status: MIXED
support_mass: 0.63
contradiction_mass: 0.51
uncertainty: 0.44
evidence_ids: [...]
```

The exact probabilistic model is an experimental variable.

Phase 1 may use interpretable normalized evidence scores.

Later experiments may compare:

- logistic evidence aggregation;
- calibrated NLI probabilities;
- Bayesian-style updates under explicit independence assumptions;
- Dempster-Shafer-style evidence mass;
- learned evidence aggregation.

Do not present heuristic scores as calibrated probabilities.

## 8. Formal reasoning layer

The system should support a structured representation such as:

```text
Conclusion := C1 AND C2 AND C3 AND NOT C4
```

or:

```text
eligible(X) ∧ jurisdiction(X, CA) ∧ effective(Law, t)
∧ ¬exception(X)
→ allowed(X, Action)
```

The first implementation should favor a small, inspectable proof graph over a general-purpose theorem prover.

Potential backends:

1. deterministic AND/OR/NOT graph propagation;
2. Datalog-like rules;
3. Z3/SMT for structured benchmark subsets.

Formal reasoning must be downstream of semantic extraction.

## 9. Active retrieval controller

The controller receives unresolved claims.

Baseline policy:

```text
choose highest-importance unresolved premise
→ generate targeted query
→ retrieve
```

Cost-aware policy:

```text
utility(action) =
expected_information_gain(action)
× decision_criticality(target_claim)
÷ expected_cost(action)
```

Cost can include:

- search calls;
- retrieved tokens;
- LLM input tokens;
- latency;
- monetary API cost.

We should test whether approximate value-of-information improves the tradeoff; we do not assume it will.

## 10. Abstention policy

The system should abstain when:

- critical premises remain unresolved after budget exhaustion;
- contradictions remain decision-critical and unresolved;
- evidence is insufficient to distinguish competing answers;
- confidence/calibration falls below a configured operating threshold.

Abstention should include an explanation:

```yaml
decision: ABSTAIN
reason: unresolved_required_premise
blocking_claims:
  - c_3
evidence_summary: ...
```

## 11. Novelty position

The project must acknowledge close prior work.

Especially relevant:
- FLARE / active retrieval;
- Self-RAG / adaptive retrieval and self-reflection;
- Adaptive-RAG / complexity-adaptive strategy;
- S2G-RAG / explicit sufficiency and structured gaps;
- Socrates-RAG / premise-directed inquiry;
- Semantic Entropy / semantic uncertainty;
- Logic-LM / LINC / language-to-symbolic reasoning;
- InfoGain-RAG / document information gain;
- ConfRAG / contradiction-aware evaluation;
- abstention-aware QA.

Therefore the defensible novelty target is the **joint architecture and controlled evaluation** of:

```text
premise graph
+
explicit evidence states
+
belief state
+
formal sufficiency
+
contradiction handling
+
cost-aware acquisition
+
selective answer / abstain
```

## 12. Expected scientific contributions

A publishable paper should aim for at least two substantive contributions:

### Contribution A — Method
A finite-budget epistemic controller that chooses retrieval based on unresolved proof obligations and explicitly supports abstention.

### Contribution B — Evaluation
A benchmark protocol measuring:
- answer correctness;
- evidence sufficiency;
- contradiction handling;
- abstention;
- retrieval cost;
- context tokens;
- calibration.

### Optional Contribution C — Controlled dataset transformations
Construct controlled variants of existing QA benchmarks where:
- one required premise is deliberately missing;
- one premise is contradicted;
- distractor evidence is added;
- source freshness differs.

This enables causal analysis of system behavior.

## 13. What would falsify the thesis

The research should be considered unsuccessful if:

- premise decomposition costs more than it saves and does not improve reliability;
- a simple LLM sufficiency judge matches the full formal architecture;
- targeted search does not outperform generic iterative search under equal budgets;
- belief-state modeling does not improve abstention/calibration;
- formalization errors dominate any downstream benefit.

Negative results should be documented rather than hidden.

## 14. Strong fellowship demonstration

A strong demo should show one query where:

```text
Naive RAG:
retrieves many relevant documents
→ misses one required premise
→ answers incorrectly

Epistemic Search:
identifies missing premise
→ retrieves specifically for it
→ resolves or abstains
→ uses fewer or comparable context tokens
```

and one query where:

```text
Sources conflict
→ system exposes the contradiction
→ searches authoritative/fresh evidence
→ updates belief state
→ answers or abstains explicitly
```
