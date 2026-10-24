# Automatically selected trace excerpts

2wikimultihopqa — saved model pilot. NA means unavailable; errors and abstentions retained. No pooled dataset score.

One minimum seeded hash per observed outcome across methods. Illustrative, outcome-stratified, not representative. Full population is retained in inventory.json.

## abstention

```
{
  "group": "2wikimultihopqa",
  "method": "premise_only",
  "query_id": "a0b2a4ce0baf11ebab90acde48001122",
  "outcome": "abstention",
  "trace_file": "traces/000001.json",
  "trace_sha256": "1a5d9bb0bcc35c39a3d793e79cffc9a2b57cb858c42277d52268c842dd2fb600",
  "selected": true
}
```

```
{
  "question": "Who is the maternal grandfather of Rudolph Of France?",
  "classification": {
    "run": "premise_only",
    "query_id": "a0b2a4ce0baf11ebab90acde48001122",
    "trace_sha256": "1a5d9bb0bcc35c39a3d793e79cffc9a2b57cb858c42277d52268c842dd2fb600",
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
    "query_id": "a0b2a4ce0baf11ebab90acde48001122",
    "status": "completed",
    "answered": false,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.0,
    "trace_file": "traces/000001.json",
    "usage": {
      "prompt_tokens": 2367,
      "completion_tokens": 1340,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 1018,
      "model_cache_hits": 2,
      "reused_cost_usd": "0.000270",
      "api_calls": 4,
      "preflight_calls": 2,
      "retrieved_tokens": 543,
      "context_tokens": 561,
      "search_calls": 3,
      "model_calls": 4,
      "documents": 6,
      "latency_seconds": 13.589595124998596,
      "cost_usd": "0.0006367"
    },
    "usage_complete": true,
    "wall_seconds": 13.60187108302489
  },
  "output": {
    "answer": null,
    "citation_ids": []
  },
  "error": null,
  "events": [
    {
      "id": "a0b2a4ce0baf11ebab90acde48001122:6",
      "query_id": "a0b2a4ce0baf11ebab90acde48001122",
      "type": "DECISION",
      "timestamp": "2026-10-23T23:30:13.398239Z",
      "component": "judging",
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
        "action": "SEARCH_MORE",
        "target_claim_id": "c_572d7d9117a424cd",
        "answer": null,
        "citation_ids": []
      }
    },
    {
      "id": "a0b2a4ce0baf11ebab90acde48001122:7",
      "query_id": "a0b2a4ce0baf11ebab90acde48001122",
      "type": "QUERY_GENERATED",
      "timestamp": "2026-10-23T23:30:13.398320Z",
      "component": "judging",
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
        "query": "Who was the father of that person’s mother? Who is the maternal grandfather of Rudolph Of France?",
        "target_claim_id": "c_572d7d9117a424cd",
        "required_stance": "SUPPORTED",
        "original_question": "Who is the maternal grandfather of Rudolph Of France?",
        "entities": [],
        "temporal_scope": null,
        "evidence_ids": [],
        "conflict": false,
        "query_version": "targeted-query-v1"
      }
    },
    {
      "id": "a0b2a4ce0baf11ebab90acde48001122:11",
      "query_id": "a0b2a4ce0baf11ebab90acde48001122",
      "type": "DECISION",
      "timestamp": "2026-10-23T23:30:13.399842Z",
      "component": "judging",
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
        "action": "SEARCH_MORE",
        "target_claim_id": "c_572d7d9117a424cd",
        "answer": null,
        "citation_ids": []
      }
    },
    {
      "id": "a0b2a4ce0baf11ebab90acde48001122:12",
      "query_id": "a0b2a4ce0baf11ebab90acde48001122",
      "type": "QUERY_GENERATED",
      "timestamp": "2026-10-23T23:30:13.399897Z",
      "component": "judging",
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
        "query": "Who was the father of that person’s mother? Who is the maternal grandfather of Rudolph Of France?",
        "target_claim_id": "c_572d7d9117a424cd",
        "required_stance": "SUPPORTED",
        "original_question": "Who is the maternal grandfather of Rudolph Of France?",
        "entities": [],
        "temporal_scope": null,
        "evidence_ids": [],
        "conflict": false,
        "query_version": "targeted-query-v1"
      }
    },
    {
      "id": "a0b2a4ce0baf11ebab90acde48001122:16",
      "query_id": "a0b2a4ce0baf11ebab90acde48001122",
      "type": "DECISION",
      "timestamp": "2026-10-23T23:30:13.401229Z",
      "component": "judging",
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
        "action": "SEARCH_MORE",
        "target_claim_id": "c_572d7d9117a424cd",
        "answer": null,
        "citation_ids": []
      }
    }
  ]
}
```

## answer_mismatch

```
{
  "group": "2wikimultihopqa",
  "method": "iterative_rag",
  "query_id": "28b6cbf808d511ebbd98ac1f6bf848b6",
  "outcome": "answer_mismatch",
  "trace_file": "traces/000007.json",
  "trace_sha256": "9171373f30066b9c7f11f98ce2f5e86bb644caf31c58b05ab2c0e0d99a8b6622",
  "selected": true
}
```

```
{
  "question": "Which film has the director who is older, Divorce In Montevideo or The Western Whirlwind?",
  "classification": {
    "run": "iterative_rag",
    "query_id": "28b6cbf808d511ebbd98ac1f6bf848b6",
    "trace_sha256": "9171373f30066b9c7f11f98ce2f5e86bb644caf31c58b05ab2c0e0d99a8b6622",
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
    "query_id": "28b6cbf808d511ebbd98ac1f6bf848b6",
    "status": "completed",
    "answered": true,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.20689655172413793,
    "trace_file": "traces/000007.json",
    "usage": {
      "prompt_tokens": 1614,
      "completion_tokens": 326,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 149,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 4,
      "preflight_calls": 2,
      "retrieved_tokens": 403,
      "context_tokens": 743,
      "search_calls": 2,
      "model_calls": 2,
      "documents": 4,
      "latency_seconds": 7.5029349160031416,
      "cost_usd": "0.0003244"
    },
    "usage_complete": true,
    "wall_seconds": 7.512796249997336
  },
  "output": {
    "answer": "Divorce in Montevideo. Its director, Manuel Romero, was born in 1891, while The Western Whirlwind’s director, Albert S. Rogell, was born in 1901, so Romero was older.",
    "citation_ids": [
      "b_91808caf412e29ebc366ef38",
      "b_e02fc3016b4c8560ab92aaa6",
      "b_be7a9ea8b03ca2a89246b4d9",
      "b_b400dd03c4e23f0d24f10d63"
    ]
  },
  "error": null,
  "events": []
}
```

## budget_stop

```
{
  "group": "2wikimultihopqa",
  "method": "iterative_rag",
  "query_id": "1118315c0bdd11eba7f7acde48001122",
  "outcome": "budget_stop",
  "trace_file": "traces/000000.json",
  "trace_sha256": "7ea4428f971323785d77396c982c5ddf7f71239b73c58c93f31b4b87f9ca1030",
  "selected": true
}
```

```
{
  "question": "What nationality is Blanche Of Valois's father?",
  "classification": {
    "run": "iterative_rag",
    "query_id": "1118315c0bdd11eba7f7acde48001122",
    "trace_sha256": "7ea4428f971323785d77396c982c5ddf7f71239b73c58c93f31b4b87f9ca1030",
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
    "query_id": "1118315c0bdd11eba7f7acde48001122",
    "status": "budget_exhausted",
    "answered": false,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.0,
    "trace_file": "traces/000000.json",
    "usage": {
      "prompt_tokens": 1483,
      "completion_tokens": 306,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 192,
      "model_cache_hits": 3,
      "reused_cost_usd": "0.0003013",
      "api_calls": 0,
      "preflight_calls": 0,
      "retrieved_tokens": 423,
      "context_tokens": 509,
      "search_calls": 3,
      "model_calls": 3,
      "documents": 6,
      "latency_seconds": 0.0,
      "cost_usd": "0"
    },
    "usage_complete": true,
    "wall_seconds": 0.005573333008214831
  },
  "output": null,
  "error": "Maximum retrieval rounds reached",
  "events": []
}
```

## execution_error

```
{
  "group": "2wikimultihopqa",
  "method": "epistemic_search",
  "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
  "outcome": "execution_error",
  "trace_file": "traces/000008.json",
  "trace_sha256": "1e28d378da6c151a7bcd654657886e4fb49029f02982e19d7f13ba2e9b1fc4eb",
  "selected": true
}
```

```
{
  "question": "Which film whose director was born first, Great West End Theatres or My Own True Love?",
  "classification": {
    "run": "epistemic_search",
    "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
    "trace_sha256": "1e28d378da6c151a7bcd654657886e4fb49029f02982e19d7f13ba2e9b1fc4eb",
    "outcome": "execution_error",
    "primary": "EVIDENCE_EXTRACTION_ERROR",
    "secondary": [],
    "basis": "observed_stage",
    "rationale": "Trace event 2bf61f58088a11ebbd6eac1f6bf848b6:7 records failure in EVIDENCE_EXTRACTION_ERROR; semantic root cause is not established.",
    "needs_review": true,
    "assessor": null,
    "protocol": null
  },
  "scores": {
    "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
    "status": "error",
    "answered": false,
    "labelled": true,
    "exact_match": 0.0,
    "token_f1": 0.0,
    "trace_file": "traces/000008.json",
    "usage": {
      "prompt_tokens": 1427,
      "completion_tokens": 2534,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 1844,
      "model_cache_hits": 1,
      "reused_cost_usd": "0.0010441",
      "api_calls": 4,
      "preflight_calls": 2,
      "retrieved_tokens": 520,
      "context_tokens": 520,
      "search_calls": 1,
      "model_calls": 3,
      "documents": 2,
      "latency_seconds": 9.331936292059254,
      "cost_usd": "0.0003656"
    },
    "usage_complete": true,
    "wall_seconds": 9.344914832967333
  },
  "output": {
    "answer": null,
    "citation_ids": []
  },
  "error": "Extracted span is absent from the exact source text",
  "events": [
    {
      "id": "2bf61f58088a11ebbd6eac1f6bf848b6:8",
      "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
      "type": "DECISION",
      "timestamp": "2026-10-23T23:35:54.035984Z",
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
          "c_2c3a38bd0ef7369d",
          "c_40c085f08b9f9e44",
          "c_511034a99b4d8ab5",
          "c_615042161d8ed02e",
          "c_79bc0a1515b5dabb",
          "c_d3ee5ae8fab18154",
          "c_d9b6bcc3d8e6b30b"
        ],
        "rationale": "Extracted span is absent from the exact source text",
        "confidence": null
      }
    }
  ]
}
```

## reference_match

```
{
  "group": "2wikimultihopqa",
  "method": "closed_book",
  "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
  "outcome": "reference_match",
  "trace_file": "traces/000008.json",
  "trace_sha256": "dc1a517ceb6c57e68dd4e2487f9815744ac1195ee5b656afe39ef15cfb539ac8",
  "selected": true
}
```

```
{
  "question": "Which film whose director was born first, Great West End Theatres or My Own True Love?",
  "classification": {
    "run": "closed_book",
    "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
    "trace_sha256": "dc1a517ceb6c57e68dd4e2487f9815744ac1195ee5b656afe39ef15cfb539ac8",
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
    "query_id": "2bf61f58088a11ebbd6eac1f6bf848b6",
    "status": "completed",
    "answered": true,
    "labelled": true,
    "exact_match": 1.0,
    "token_f1": 1.0,
    "trace_file": "traces/000008.json",
    "usage": {
      "prompt_tokens": 107,
      "completion_tokens": 229,
      "cached_input_tokens": 0,
      "cache_write_tokens": 0,
      "reasoning_tokens": 211,
      "model_cache_hits": 0,
      "reused_cost_usd": "0",
      "api_calls": 2,
      "preflight_calls": 1,
      "retrieved_tokens": 0,
      "context_tokens": 0,
      "search_calls": 0,
      "model_calls": 1,
      "documents": 0,
      "latency_seconds": 3.43069791700691,
      "cost_usd": "0.0001252"
    },
    "usage_complete": true,
    "wall_seconds": 3.433725000009872
  },
  "output": {
    "answer": "My Own True Love"
  },
  "error": null,
  "events": []
}
```
