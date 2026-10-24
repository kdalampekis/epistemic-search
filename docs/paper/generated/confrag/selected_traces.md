# Automatically selected trace excerpts

confrag — saved model pilot. NA means unavailable; errors and abstentions retained. No pooled dataset score.

One minimum seeded hash per observed outcome across methods. Illustrative, outcome-stratified, not representative. Full population is retained in inventory.json.

## abstention

```
{
  "group": "confrag",
  "method": "naive_rag",
  "query_id": "1105",
  "outcome": "abstention",
  "trace_file": "traces/000000.json",
  "trace_sha256": "89a21ea035129876e3c536228f0d13942cd2b162c74e6279a0d2fcba9e1f11d2",
  "selected": true
}
```

```
{
  "question": "Why does the law never go after rappers who constantly talk about the illegal drugs they do in their songs?",
  "classification": {
    "run": "naive_rag",
    "query_id": "1105",
    "trace_sha256": "89a21ea035129876e3c536228f0d13942cd2b162c74e6279a0d2fcba9e1f11d2",
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
    "query_id": "1105",
    "status": "completed",
    "answered": false,
    "labelled": false,
    "exact_match": null,
    "token_f1": null,
    "trace_file": "traces/000000.json",
    "usage": {
      "prompt_tokens": 10304,
      "completion_tokens": 99,
      "cached_input_tokens": 0,
      "cache_write_tokens": 10301,
      "reasoning_tokens": 80,
      "model_cache_hits": 1,
      "reused_cost_usd": "0.001337425",
      "api_calls": 0,
      "preflight_calls": 0,
      "retrieved_tokens": 4726,
      "context_tokens": 4589,
      "search_calls": 1,
      "model_calls": 1,
      "documents": 2,
      "latency_seconds": 0.0,
      "cost_usd": "0"
    },
    "usage_complete": true,
    "wall_seconds": 0.00877008301904425
  },
  "output": {
    "answer": null,
    "citation_ids": []
  },
  "error": null,
  "events": []
}
```

## budget_stop

```
{
  "group": "confrag",
  "method": "iterative_rag",
  "query_id": "1105",
  "outcome": "budget_stop",
  "trace_file": "traces/000000.json",
  "trace_sha256": "d943874a67af57699ba3c4e34e2e03c27c7724ccc597efa822fae42f4ecc79e2",
  "selected": true
}
```

```
{
  "question": "Why does the law never go after rappers who constantly talk about the illegal drugs they do in their songs?",
  "classification": {
    "run": "iterative_rag",
    "query_id": "1105",
    "trace_sha256": "d943874a67af57699ba3c4e34e2e03c27c7724ccc597efa822fae42f4ecc79e2",
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
    "query_id": "1105",
    "status": "budget_exhausted",
    "answered": false,
    "labelled": false,
    "exact_match": null,
    "token_f1": null,
    "trace_file": "traces/000000.json",
    "usage": {
      "prompt_tokens": 40976,
      "completion_tokens": 278,
      "cached_input_tokens": 0,
      "cache_write_tokens": 40967,
      "reasoning_tokens": 115,
      "model_cache_hits": 3,
      "reused_cost_usd": "0.005260775",
      "api_calls": 0,
      "preflight_calls": 0,
      "retrieved_tokens": 14351,
      "context_tokens": 20739,
      "search_calls": 3,
      "model_calls": 3,
      "documents": 6,
      "latency_seconds": 0.0,
      "cost_usd": "0"
    },
    "usage_complete": true,
    "wall_seconds": 0.022053540975321084
  },
  "output": null,
  "error": "Maximum retrieval rounds reached",
  "events": []
}
```

## execution_error

```
{
  "group": "confrag",
  "method": "epistemic_search",
  "query_id": "1105",
  "outcome": "execution_error",
  "trace_file": "traces/000000.json",
  "trace_sha256": "1eef2dce98f997ad3c1ae5ff0bb1a8e1abcf5e985afd2ea7703d092f5a77fcc6",
  "selected": true
}
```

```
{
  "question": "Why does the law never go after rappers who constantly talk about the illegal drugs they do in their songs?",
  "classification": {
    "run": "epistemic_search",
    "query_id": "1105",
    "trace_sha256": "1eef2dce98f997ad3c1ae5ff0bb1a8e1abcf5e985afd2ea7703d092f5a77fcc6",
    "outcome": "execution_error",
    "primary": "EVIDENCE_EXTRACTION_ERROR",
    "secondary": [],
    "basis": "observed_stage",
    "rationale": "Trace event 1105:15 records failure in EVIDENCE_EXTRACTION_ERROR; semantic root cause is not established.",
    "needs_review": true,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "1105",
    "status": "error",
    "answered": false,
    "labelled": false,
    "exact_match": null,
    "token_f1": null,
    "trace_file": "traces/000000.json",
    "usage": {
      "prompt_tokens": 31981,
      "completion_tokens": 4866,
      "cached_input_tokens": 0,
      "cache_write_tokens": 31639,
      "reasoning_tokens": 3462,
      "model_cache_hits": 7,
      "reused_cost_usd": "0.006422075",
      "api_calls": 0,
      "preflight_calls": 0,
      "retrieved_tokens": 4726,
      "context_tokens": 14178,
      "search_calls": 1,
      "model_calls": 7,
      "documents": 2,
      "latency_seconds": 0.0,
      "cost_usd": "0"
    },
    "usage_complete": true,
    "wall_seconds": 0.019548584008589387
  },
  "output": {
    "answer": null,
    "citation_ids": []
  },
  "error": "Extracted span is absent from the exact source text",
  "events": [
    {
      "id": "1105:16",
      "query_id": "1105",
      "type": "DECISION",
      "timestamp": "2026-10-23T23:36:35.384960Z",
      "component": "evidence",
      "usage": {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "model_cache_hits": 0,
        "reused_cost_usd": "0",
        "api_calls": 0,
        "preflight_calls": 0,
        "retrieved_tokens": 0,
        "context_tokens": 0,
        "search_calls": 0,
        "model_calls": 0,
        "documents": 0,
        "latency_seconds": 0.0,
        "cost_usd": "0"
      },
      "payload": {
        "action": "ABSTAIN",
        "target_claim_id": null,
        "blocking_claims": [
          "c_32230d2b002d4681",
          "c_4d387556eaf5ea03",
          "c_771ce47d06e6f37e",
          "c_9c37709b96bd6fe0",
          "c_d843cadc22e31e57",
          "c_ea48d59d9e1db8f6"
        ],
        "rationale": "Extracted span is absent from the exact source text",
        "confidence": null
      }
    }
  ]
}
```

## ungraded_answer

```
{
  "group": "confrag",
  "method": "naive_rag",
  "query_id": "88",
  "outcome": "ungraded_answer",
  "trace_file": "traces/000001.json",
  "trace_sha256": "203844bebe38b177d5a4c809321b71dbda39c9bde7ceedd5c217e2f6467a8de0",
  "selected": true
}
```

```
{
  "question": "where is the hotel used in the movie the shining",
  "classification": {
    "run": "naive_rag",
    "query_id": "88",
    "trace_sha256": "203844bebe38b177d5a4c809321b71dbda39c9bde7ceedd5c217e2f6467a8de0",
    "outcome": "ungraded_answer",
    "primary": null,
    "secondary": [],
    "basis": "not_classified",
    "rationale": "No failure inferred: abstention, budget stop or ungraded output is not automatically an error.",
    "needs_review": false,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "88",
    "status": "completed",
    "answered": true,
    "labelled": false,
    "exact_match": null,
    "token_f1": null,
    "trace_file": "traces/000001.json",
    "usage": {
      "prompt_tokens": 14079,
      "completion_tokens": 108,
      "cached_input_tokens": 0,
      "cache_write_tokens": 14076,
      "reasoning_tokens": 41,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 2,
      "preflight_calls": 1,
      "retrieved_tokens": 3386,
      "context_tokens": 2985,
      "search_calls": 1,
      "model_calls": 1,
      "documents": 2,
      "latency_seconds": 2.3465957079897635,
      "cost_usd": "0.0018138"
    },
    "usage_complete": true,
    "wall_seconds": 2.3558773749973625
  },
  "output": {
    "answer": "The hotel’s exterior was filmed at Timberline Lodge on the south face of Mount Hood in Mount Hood National Forest, Oregon. [The Shining’s Overlook Hotel is fictional.]",
    "citation_ids": [
      "b_bc093b601c67328acca9577f"
    ]
  },
  "error": null,
  "events": []
}
```
