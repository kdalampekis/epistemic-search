# Automatically selected trace excerpts

hotpotqa — saved model pilot. NA means unavailable; errors and abstentions retained. No pooled dataset score.

One minimum seeded hash per observed outcome across methods. Illustrative, outcome-stratified, not representative. Full population is retained in inventory.json.

## abstention

```
{
  "group": "hotpotqa",
  "method": "naive_rag",
  "query_id": "5ae6050f55429929b0807a5e",
  "outcome": "abstention",
  "trace_file": "traces/000004.json",
  "trace_sha256": "bc4de574c3c718fe06809b5bd6973ee2602c2cc2ab350f9b5a856e2f7d1c6857",
  "selected": true
}
```

```
{
  "question": "This singer of A Rather Blustery Day also voiced what hedgehog?",
  "classification": {
    "run": "naive_rag",
    "query_id": "5ae6050f55429929b0807a5e",
    "trace_sha256": "bc4de574c3c718fe06809b5bd6973ee2602c2cc2ab350f9b5a856e2f7d1c6857",
    "outcome": "abstention",
    "primary": null,
    "secondary": [],
    "basis": "not_classified",
    "rationale": "No failure inferred: abstention, budget stop or ungraded output is not automatically an error.",
    "needs_review": false,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "5ae6050f55429929b0807a5e",
    "status": "completed",
    "answered": false,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.0,
    "trace_file": "traces/000004.json",
    "usage": {
      "prompt_tokens": 511,
      "completion_tokens": 322,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 303,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 2,
      "preflight_calls": 1,
      "retrieved_tokens": 237,
      "context_tokens": 243,
      "search_calls": 1,
      "model_calls": 1,
      "documents": 2,
      "latency_seconds": 4.64371808397118,
      "cost_usd": "0.0002121"
    },
    "usage_complete": true,
    "wall_seconds": 4.646537000022363
  },
  "output": {
    "answer": null,
    "citation_ids": []
  },
  "error": null,
  "events": []
}
```

## answer_mismatch

```
{
  "group": "hotpotqa",
  "method": "iterative_rag",
  "query_id": "5a7363ec5542991f29ee2dd7",
  "outcome": "answer_mismatch",
  "trace_file": "traces/000008.json",
  "trace_sha256": "3b32d0655b82606493b1b19b677c25b650a4b003a8d7cef975201bd2335ff2fe",
  "selected": true
}
```

```
{
  "question": "The USS Tortuga was named after the Dry Tortugas, a group of desert coral islets 60 miles west of which city with the motto \"One Human Family\"?",
  "classification": {
    "run": "iterative_rag",
    "query_id": "5a7363ec5542991f29ee2dd7",
    "trace_sha256": "3b32d0655b82606493b1b19b677c25b650a4b003a8d7cef975201bd2335ff2fe",
    "outcome": "answer_mismatch",
    "primary": "ANSWER_GENERATION_ERROR",
    "secondary": [],
    "basis": "output_symptom",
    "rationale": "Failed final output or reference mismatch; upstream root cause and benchmark ambiguity need review.",
    "needs_review": true,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "5a7363ec5542991f29ee2dd7",
    "status": "completed",
    "answered": true,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.8,
    "trace_file": "traces/000008.json",
    "usage": {
      "prompt_tokens": 416,
      "completion_tokens": 80,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 17,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 2,
      "preflight_calls": 1,
      "retrieved_tokens": 93,
      "context_tokens": 99,
      "search_calls": 1,
      "model_calls": 1,
      "documents": 2,
      "latency_seconds": 2.101503000012599,
      "cost_usd": "0.0000816"
    },
    "usage_complete": true,
    "wall_seconds": 2.104905417014379
  },
  "output": {
    "answer": "Key West, Florida.",
    "citation_ids": [
      "b_ac35a77a11186def06932b41",
      "b_0b9109fb0bea7782cfb2b4d1"
    ]
  },
  "error": null,
  "events": []
}
```

## budget_stop

```
{
  "group": "hotpotqa",
  "method": "iterative_rag",
  "query_id": "5ae63b2255429908198fa526",
  "outcome": "budget_stop",
  "trace_file": "traces/000000.json",
  "trace_sha256": "33824794eee06361d4915ecc17691b24947f8a5ba6cce5e74d8672c561ddb65e",
  "selected": true
}
```

```
{
  "question": "What is the date played of this college football game at Sun Life Stadium in Miami Gardens, Florida, where Clemson defeated the No. 4 Oklahoma Sooners, 37-17?",
  "classification": {
    "run": "iterative_rag",
    "query_id": "5ae63b2255429908198fa526",
    "trace_sha256": "33824794eee06361d4915ecc17691b24947f8a5ba6cce5e74d8672c561ddb65e",
    "outcome": "budget_stop",
    "primary": null,
    "secondary": [],
    "basis": "not_classified",
    "rationale": "No failure inferred: abstention, budget stop or ungraded output is not automatically an error.",
    "needs_review": false,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "5ae63b2255429908198fa526",
    "status": "budget_exhausted",
    "answered": false,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.0,
    "trace_file": "traces/000000.json",
    "usage": {
      "prompt_tokens": 2361,
      "completion_tokens": 291,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 165,
      "model_cache_hits": 3,
      "reused_cost_usd": "0.0003816",
      "api_calls": 0,
      "preflight_calls": 0,
      "retrieved_tokens": 852,
      "context_tokens": 1074,
      "search_calls": 3,
      "model_calls": 3,
      "documents": 6,
      "latency_seconds": 0.0,
      "cost_usd": "0"
    },
    "usage_complete": true,
    "wall_seconds": 0.006245375028811395
  },
  "output": null,
  "error": "Maximum retrieval rounds reached",
  "events": []
}
```

## execution_error

```
{
  "group": "hotpotqa",
  "method": "closed_book",
  "query_id": "5ae6050f55429929b0807a5e",
  "outcome": "execution_error",
  "trace_file": "traces/000004.json",
  "trace_sha256": "2c742c27fd2e18dcd794634f33200f2556291772993eeb38ba2ff2b83d4a176f",
  "selected": true
}
```

```
{
  "question": "This singer of A Rather Blustery Day also voiced what hedgehog?",
  "classification": {
    "run": "closed_book",
    "query_id": "5ae6050f55429929b0807a5e",
    "trace_sha256": "2c742c27fd2e18dcd794634f33200f2556291772993eeb38ba2ff2b83d4a176f",
    "outcome": "execution_error",
    "primary": "ANSWER_GENERATION_ERROR",
    "secondary": [],
    "basis": "observed_stage",
    "rationale": "Trace event 5ae6050f55429929b0807a5e:1 records failure in ANSWER_GENERATION_ERROR; semantic root cause is not established.",
    "needs_review": true,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "5ae6050f55429929b0807a5e",
    "status": "error",
    "answered": false,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.0,
    "trace_file": "traces/000004.json",
    "usage": {
      "prompt_tokens": 104,
      "completion_tokens": 4096,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 4096,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 2,
      "preflight_calls": 1,
      "retrieved_tokens": 0,
      "context_tokens": 0,
      "search_calls": 0,
      "model_calls": 1,
      "documents": 0,
      "latency_seconds": 44.341429084015545,
      "cost_usd": "0.0020584"
    },
    "usage_complete": true,
    "wall_seconds": 44.34324137499789
  },
  "output": null,
  "error": "Model attempt failed",
  "events": []
}
```

## reference_match

```
{
  "group": "hotpotqa",
  "method": "closed_book",
  "query_id": "5a80ad19554299485f5986a8",
  "outcome": "reference_match",
  "trace_file": "traces/000002.json",
  "trace_sha256": "73e1d3b47a2e17af01fed067e17c26111b25991fd3157e93ad3162ac41f3d25a",
  "selected": true
}
```

```
{
  "question": "In addition to his role in The Fattest Man in Britain, Bobby Ball is best known for his half of the doublt act Cannon and Ball with which other comedian?",
  "classification": {
    "run": "closed_book",
    "query_id": "5a80ad19554299485f5986a8",
    "trace_sha256": "73e1d3b47a2e17af01fed067e17c26111b25991fd3157e93ad3162ac41f3d25a",
    "outcome": "reference_match",
    "primary": null,
    "secondary": [],
    "basis": "not_classified",
    "rationale": "Matches the recorded reference; does not establish reasoning or real-world truth.",
    "needs_review": false,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "5a80ad19554299485f5986a8",
    "status": "completed",
    "answered": true,
    "labelled": true,
    "exact_match": 1.0,
    "token_f1": 1.0,
    "trace_file": "traces/000002.json",
    "usage": {
      "prompt_tokens": 123,
      "completion_tokens": 43,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 26,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 2,
      "preflight_calls": 1,
      "retrieved_tokens": 0,
      "context_tokens": 0,
      "search_calls": 0,
      "model_calls": 1,
      "documents": 0,
      "latency_seconds": 1.8781155420001596,
      "cost_usd": "0.0000338"
    },
    "usage_complete": true,
    "wall_seconds": 1.8811671659932472
  },
  "output": {
    "answer": "Tommy Cannon"
  },
  "error": null,
  "events": []
}
```
