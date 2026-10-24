# Automatically selected trace excerpts

ablation-fixture — SCRIPTED FIXTURE (not model quality); named switch disabled. NA means unavailable; errors and abstentions retained. No pooled dataset score.

One minimum seeded hash per observed outcome across methods. Illustrative, outcome-stratified, not representative. Full population is retained in inventory.json.

## reference_match

```
{
  "group": "ablation-fixture",
  "method": "reference",
  "query_id": "europe-capital",
  "outcome": "reference_match",
  "trace_file": "traces/000000.json",
  "trace_sha256": "d36badb03dc5a2ee065a958f54b92c04625cc7cf73006b67199fe5e3a7a763cf",
  "selected": true
}
```

```
{
  "question": "What is France's capital, and is that country in Europe?",
  "classification": {
    "run": "reference",
    "query_id": "europe-capital",
    "trace_sha256": "d36badb03dc5a2ee065a958f54b92c04625cc7cf73006b67199fe5e3a7a763cf",
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
    "query_id": "europe-capital",
    "status": "completed",
    "answered": true,
    "labelled": true,
    "exact_match": 1.0,
    "token_f1": 1.0,
    "trace_file": "traces/000000.json",
    "usage": {
      "prompt_tokens": 264,
      "completion_tokens": 90,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 0,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 0,
      "preflight_calls": 0,
      "retrieved_tokens": 10,
      "context_tokens": 48,
      "search_calls": 1,
      "model_calls": 4,
      "documents": 1,
      "latency_seconds": 0.0,
      "cost_usd": "0"
    },
    "usage_complete": true,
    "wall_seconds": 0.006111417023930699
  },
  "output": {
    "answer": "Paris; yes.",
    "citation_ids": [
      "facts"
    ]
  },
  "error": null,
  "events": [
    {
      "id": "europe-capital:9",
      "query_id": "europe-capital",
      "type": "SUFFICIENCY",
      "timestamp": "2026-10-24T09:58:35.015113Z",
      "component": "control",
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
        "status": "SUPPORTED",
        "sufficient": true,
        "blockers": [],
        "minimal_frontier": [],
        "required_stances": {},
        "alternative_frontiers": [
          {}
        ],
        "structurally_satisfiable": true,
        "conflicts": [],
        "trace": [
          {
            "node_id": "n_182a12d686c0e3b1",
            "kind": "CLAIM",
            "status": "SUPPORTED",
            "children": []
          },
          {
            "node_id": "n_d93bba9f713e23e2",
            "kind": "CLAIM",
            "status": "SUPPORTED",
            "children": []
          },
          {
            "node_id": "n_0011c3b345e013ab",
            "kind": "AND",
            "status": "SUPPORTED",
            "children": [
              "n_182a12d686c0e3b1",
              "n_d93bba9f713e23e2"
            ]
          },
          {
            "node_id": "n_42b5a7dbf67c55f5",
            "kind": "CONCLUSION",
            "status": "SUPPORTED",
            "children": [
              "n_0011c3b345e013ab"
            ]
          }
        ],
        "scope": "derivability_from_extracted_model"
      }
    },
    {
      "id": "europe-capital:12",
      "query_id": "europe-capital",
      "type": "DECISION",
      "timestamp": "2026-10-24T09:58:35.015556Z",
      "component": "answering",
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
        "action": "ANSWER",
        "target_claim_id": null,
        "blocking_claims": [],
        "rationale": "Supported by the extracted evidence model",
        "confidence": null,
        "acquisition": null
      }
    }
  ]
}
```
