# Scheduling dataset source and provenance audit — 11 October 2026

This is an audit of the files actually read by the reported workload and effort experiments. It is not a claim that every file in `datasets/` was used, that a dataset was originally downloaded from the comparison URL, or that reuse/redistribution permission has been established.

| Local dataset | What the file itself establishes | Training use | Independently checked source / remaining gap |
|---|---|---|---|
| `datasets/workload_assignment/GFG_FINAL.csv` | 49,000 rows; every `Project key` is `SRCTREEWIN` and every `Project name` is `Sourcetree for Windows`. The name `GFG_FINAL.csv` is misleading. | `train_workload_model.py` keeps rows with an assignee and parseable `Created` date: 1,078 issues, five assignee IDs. The target is `Resolution == Fixed`. `train_workload_model_v2.py` uses this same file for its chronological proxy experiment. | The local `SRCTREEWIN-14001` issue key exists on [Atlassian's public issue tracker](https://jira.atlassian.com/browse/SRCTREEWIN-14001). This corroborates the project and issue identity, **not** the exact 49,000-row export, its query, download date, or licence. |
| `datasets/model3_delay/apache_jira_delay.csv` | 333 prepared rows labelled HIVE (95), HADOOP (91), SPARK (62), KAFKA (48) and FLINK (37). Columns are summary variables such as `days_open`, `priority` and `delayed`; there are no original issue keys or URLs. | The legacy classifier turns each project label into a pseudo-member (`apache_` + project) and sets class 1 to `1 - delayed`. It is not a roster of five people. | No original issue-level source, extraction script, collection date, version or licence was found in the local dataset folder. Call it a **local Apache-project issue-derived summary**, not a verified public raw Jira export. |
| `datasets/xgboost_combined_effort_dataset.csv` | 580 records: 499 tagged `China`, 81 tagged `Desharnais`; columns are `function_points`, `effort_hours`, `source`. | `retrain_real_only.py` trains/evaluates the effort regressor on this merged two-feature view. | All 499 China `(function_points, effort_hours)` pairs match, in the same order, `(AFP, Effort)` in [Zenodo's China v1 `china.arff`](https://zenodo.org/records/268446), DOI [10.5281/zenodo.268446](https://doi.org/10.5281/zenodo.268446). This is a content match, not proof of the original download route. The 81 Desharnais pairs match the local file below. |
| `datasets/model2_duration/desharnais.csv` | 81 rows; all 11 numeric core fields and their row order match a [public PROMISE-labelled Desharnais ARFF copy](https://github.com/yy2111/Software-Effort-Estimation/blob/master/Datasets/02.desharnais.arff). | Provides the 81 Desharnais rows in the merged effort file. | The comparison copy describes PROMISE provenance, but it is a third-party mirror. The precise original download URL/date/version and licence for the **local** copy remain undocumented. |

The `GFG_FINAL.csv` content was identified using `Project key`, `Project name` and `Issue key`, not its filename. The issue URL in the file is a *product* URL (`sourcetreeapp.com`), not a dataset download URL. The 1,411 classifier records (1,078 + 333) are issue-status proxies, not students; the two sources' class-1 meanings are different. Consequently, the historical classifier's reported accuracy cannot be described as student-assignment accuracy.

Other local files (`scirex/release_data/*.jsonl`, `world-cities.csv`, the auxiliary delay tables and the other effort tables) may support separate experiments or fixtures, but they are **not** inputs to the workload/effort results above. The panel/hall sheets, PDFs, document submissions and prepared Git commits are controlled integration fixtures, not external model-validation datasets.

## Reproducibility fingerprints

SHA-256 hashes refer to the current local files, not to an authenticated provider download:

```text
55cf60efb361a3a25e5cc0391d455d6cedefac69bc6f03e7296779c7591c2b9c  datasets/workload_assignment/GFG_FINAL.csv
f15d07ea1564446402de9506b9b2ce0efcec4c70ff8dcaffcb7680c8e1b7a8e3  datasets/model3_delay/apache_jira_delay.csv
1255315c1cd36a849b59a9d52cae04ec2eb7adb3ea9af03ed40da7d3ce273be4  datasets/xgboost_combined_effort_dataset.csv
341f6dbfd9745b5b4405d6a11253061960d6c36566b4b437b39294341243d358  datasets/model2_duration/desharnais.csv
```

The original acquisition records and redistribution terms, especially for the Sourcetree export and Apache summary, require author/source-provider confirmation before external release of the raw files. The [Zenodo record](https://zenodo.org/records/268446) identifies the China dataset and DOI, but its displayed licence field is blank; do not infer an open licence from public availability alone.
