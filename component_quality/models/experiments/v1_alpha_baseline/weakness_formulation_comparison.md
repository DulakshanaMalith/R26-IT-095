# Weakness Formulation Comparison

| Input Granularity | Model | Samples | Authors | Accuracy | Macro F1 | Weighted F1 |
|---|---|---|---|---|---|---|
| span | LinearSVC | 2121 | 55 | 0.562 | 0.556 | 0.560 |
| span | LogReg | 2121 | 55 | 0.604 | 0.601 | 0.604 |
| paragraph | LinearSVC | 460 | 55 | 0.536 | 0.438 | 0.511 |
| paragraph | LogReg | 460 | 55 | 0.512 | 0.409 | 0.486 |
| chunk | LinearSVC | 1104 | 55 | 0.484 | 0.451 | 0.486 |
| chunk | LogReg | 1104 | 55 | 0.472 | 0.426 | 0.468 |
