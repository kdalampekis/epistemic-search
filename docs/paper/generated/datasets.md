Saved evaluation populations; fixture and real-model rows remain separate. Not full release sizes.

| group | kind | fixture_only | n | labelled | question_groups | known_answerability | model | effort | grader | split | retrieval_scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hotpotqa | comparison | False | 10 | 10 | 10 | 0 | gpt-6-luna | medium | hotpotqa-answer-v1 | dev | provided-context-per-question |
| 2wikimultihopqa | comparison | False | 10 | 10 | 10 | 0 | gpt-6-luna | medium | 2wiki-answer-aliases-v1.1 | dev | provided-context-per-question |
| confrag | comparison | False | 2 | 0 | 2 | 0 | gpt-6-luna | medium | confrag-ingestion-only-v1 | train | provided-context-per-question |
| ablation-fixture | ablation | True | 1 | 1 | 1 | 1 | fixture-script-v1 | NA | english-em-token-f1-v1 | dev | configured-corpus |
