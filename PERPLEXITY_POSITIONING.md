# Perplexity Fellowship Positioning

## Delivered project narrative (Phase 25)

I built and evaluated an inspectable premise-aware retrieval prototype with
matched baselines, strict cost instrumentation and an offline reproduction
package. The small real-model pilot did not establish an advantage; I retained
its extraction failures, low coverage and missed conflict, and narrowed novelty
claims after checking close prior work. The result is a technical report and
trace dashboard showing what worked as software and what remains unvalidated
scientifically. My next research question is how to improve semantic extraction
and acquisition without tuning on the inspected evaluation cases.

Use the [technical report](docs/paper/REPORT.md) and generated artifacts as the
current evidence. The demo stories and desired metrics below are original goals,
not demonstrated real-model wins. No application or public submission has been sent.


## 1. Why this project fits

Perplexity Research publicly identifies **search, reasoning, agents, and systems** as core areas.

This project sits at their intersection:

```text
SEARCH
  ↓
What evidence should be acquired?

REASONING
  ↓
What follows from current evidence?

AGENTS
  ↓
Should the system search, answer, ask, resolve conflict, or abstain?

SYSTEMS
  ↓
How do we improve reliability without exploding tokens, latency, and search cost?
```

The pitch is not:

> I built a smaller Perplexity.

The pitch is:

> I investigated a reliability/control problem that becomes increasingly important as AI search becomes more agentic and multi-step.

## 2. Fellowship narrative

> I became interested in a failure mode of modern RAG systems: retrieving highly relevant information is not necessarily the same as retrieving all information required to justify an answer. I built a research prototype that represents the premises required for an answer, tracks supporting, contradictory, and missing evidence, and uses unresolved proof obligations to decide whether to search again, answer, or abstain. I am especially interested in whether this improves reliability while reducing unnecessary context and inference cost. Perplexity is compelling to me because these questions sit directly at the intersection of search, reasoning, agents, and systems, but at a scale I cannot reproduce independently.

## 3. Strong demo story

### Demo A — Missing premise

Show:

```text
Premise 1: SUPPORTED
Premise 2: SUPPORTED
Premise 3: UNKNOWN
Premise 4: SUPPORTED
```

Naive RAG:
- retrieves many relevant documents;
- answers anyway.

Our system:
- identifies Premise 3 as the blocker;
- issues a targeted search;
- resolves it or abstains;
- keeps final context compact.

### Demo B — Contradiction

Two credible sources disagree.

Our system:
- stores both stances;
- marks the claim `MIXED`;
- searches for higher-authority/fresher evidence;
- exposes unresolved conflict if it cannot resolve it;
- answers or abstains explicitly.

## 4. What makes the application credible

Prioritize:

1. clean public GitHub repo;
2. reproducible benchmarks;
3. trace visualizer;
4. quality-vs-token graph;
5. risk-coverage curve;
6. contradiction benchmark;
7. 4–6 page technical report;
8. honest limitations and negative results.

## 5. What not to say

Avoid:
- “I solved hallucinations.”
- “This is better than Perplexity.”
- “Formal logic proves web truth.”
- “No one has done premise-aware retrieval.”
- “I built a web-scale search engine.”

Prefer:

> “I am exploring whether explicit epistemic state and proof-obligation-guided search can improve the reliability-efficiency tradeoff of agentic retrieval.”

## 6. Token-efficiency angle

A common response to uncertainty is:

```text
uncertain
→ retrieve more
→ add more context
→ run LLM again
```

This may:
- increase token cost;
- add distractors;
- increase contradiction density;
- increase latency.

Our question:

> Can the system identify the specific missing fact that blocks the answer and acquire only the evidence likely to resolve it?

This turns the project into a systems question as well as a reasoning question.

## 7. Suggested application description

> **Epistemic Search** — A research prototype for premise-aware active retrieval. It decomposes questions into answer-critical proof obligations, maintains provenance-backed support/contradiction/unknown evidence states, identifies unresolved blockers, and chooses whether to answer, search for a specific missing premise, resolve a contradiction, or abstain. I am evaluating it against standard and iterative RAG on multi-hop, incomplete-evidence, and conflicting-source benchmarks, with particular focus on selective reliability and tokens/search calls per correct answer.

## 8. Interview questions to be ready for

- Why is retrieval relevance not evidence sufficiency?
- How do you evaluate premise decomposition?
- Why is token confidence not probability?
- How do you calibrate?
- How do you model source dependence?
- What if the premise graph is wrong?
- Why use a formal layer?
- How does this scale to open-web search?
- How would it interact with a production ranker?
- Would you learn the controller instead of hand-coding it?
- How do you prevent over-search?
- When is abstention too conservative?

## 9. Natural research extension

If the deterministic/heuristic controller works:

> Learn the retrieval policy from traces to maximize correct answers per unit search/token cost under an abstention-risk constraint.

Possible methods:
- contextual bandits;
- offline RL;
- policy optimization;
- learned value-of-information estimator.

That becomes a natural second-stage project.
