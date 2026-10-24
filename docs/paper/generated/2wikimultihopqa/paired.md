2wikimultihopqa — saved model pilot. Holm correction within this dataset/report only; marginal CIs.

| method | reference | metric | difference | CI_lower | CI_upper | p | p_Holm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| closed_book | naive_rag | coverage | 1 | 1 | 1 | 0.00195312 | 0.0234375 |
| closed_book | naive_rag | exact_match | 0.5 | 0.2 | 0.8 | 0.0625 | 0.5 |
| closed_book | naive_rag | token_f1 | 0.774742 | 0.6018 | 0.926667 | 0.00195312 | 0.0234375 |
| iterative_rag | naive_rag | coverage | 0.7 | 0.4 | 1 | 0.015625 | 0.15625 |
| iterative_rag | naive_rag | exact_match | 0 | 0 | 0 | 1 | 1 |
| iterative_rag | naive_rag | token_f1 | 0.225861 | 0.103574 | 0.362424 | 0.015625 | 0.15625 |
| premise_only | naive_rag | coverage | 0 | 0 | 0 | 1 | 1 |
| premise_only | naive_rag | exact_match | 0 | 0 | 0 | 1 | 1 |
| premise_only | naive_rag | token_f1 | 0 | 0 | 0 | 1 | 1 |
| epistemic_search | naive_rag | coverage | 0.1 | 0 | 0.3 | 1 | 1 |
| epistemic_search | naive_rag | exact_match | 0 | 0 | 0 | 1 | 1 |
| epistemic_search | naive_rag | token_f1 | 0.06 | 0 | 0.18 | 1 | 1 |
