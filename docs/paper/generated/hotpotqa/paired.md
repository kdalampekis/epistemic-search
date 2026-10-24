hotpotqa — saved model pilot. Holm correction within this dataset/report only; marginal CIs.

| method | reference | metric | difference | CI_lower | CI_upper | p | p_Holm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| closed_book | naive_rag | coverage | 0.3 | 0 | 0.6 | 0.25 | 1 |
| closed_book | naive_rag | exact_match | 0 | -0.3 | 0.3 | 1 | 1 |
| closed_book | naive_rag | token_f1 | 0.0742594 | -0.20126 | 0.353896 | 0.59375 | 1 |
| iterative_rag | naive_rag | coverage | 0.1 | 0 | 0.3 | 1 | 1 |
| iterative_rag | naive_rag | exact_match | -0.2 | -0.5 | 0 | 0.5 | 1 |
| iterative_rag | naive_rag | token_f1 | -0.143721 | -0.338862 | 0.0182796 | 0.25 | 1 |
| premise_only | naive_rag | coverage | -0.3 | -0.6 | 0 | 0.25 | 1 |
| premise_only | naive_rag | exact_match | -0.2 | -0.5 | 0 | 0.5 | 1 |
| premise_only | naive_rag | token_f1 | -0.25516 | -0.482432 | -0.05 | 0.125 | 1 |
| epistemic_search | naive_rag | coverage | -0.4 | -0.7 | -0.1 | 0.125 | 1 |
| epistemic_search | naive_rag | exact_match | -0.2 | -0.5 | 0 | 0.5 | 1 |
| epistemic_search | naive_rag | token_f1 | -0.295766 | -0.583333 | -0.0324324 | 0.125 | 1 |
