# Source and Claim Audit

This audit records the evidence used to create `main.tex`. It is not part of the submitted paper.

## Dataset-provenance correction — 11 October 2026

The file `datasets/workload_assignment/GFG_FINAL.csv` is **not** evidence of a distinct "GFG" project: its 49,000 raw rows all have `Project key = SRCTREEWIN` and `Project name = Sourcetree for Windows`; the reported classifier uses 1,078 assigned, dated rows. The 333-row Apache table has no issue keys or source manifest, so its row-level origin is unverified. The 499 China feature/effort pairs match Zenodo's China v1 dataset; the 81 Desharnais records match a public PROMISE-labelled copy, without establishing the local acquisition route. See the current [dataset provenance audit](../Dataset_Source_Provenance_Audit_2026-10-11.md) for source links, hashes, and rights caveats. The current dissertation deliverable is `IT22117014_Individual_Component_Dissertation_Submission_Candidate.docx` and its matching PDF; older filenames below are historical.

## Implementation update — 10 October 2026

The sections below preserve the evidence and results available when the paper was drafted; they are **not a current deployment claim**. The live auto-assignment endpoint now uses deterministic LPT and saves a separate balanced PostgreSQL schedule version. The legacy mixed-label JIRA classifier is not loaded for live student assignment. A GFG-only chronological rerun (`workload_proxy_v2_results.json`) scored 31.94% accuracy on the latest 216 issues, below a 77.31% majority-class baseline, and also remains offline. Academic draft generation, rescheduling and publication now check hall seats using four panelists plus team size plus configured audience seats. Six focused tests passed against an isolated PostgreSQL database (`test_scheduling_remediation.py`); no real-cohort or full cross-component outcome evaluation has been performed.

**Do not submit the existing `main.tex` or older dissertation DOCX without reconciling their descriptions of the live XGBoost/hybrid allocator, route behavior and hall-capacity rules with this update.** The corrected dissertation is `IT22117014_Individual_Component_Dissertation_Submission_Review.docx`, with a matching PDF and a separate `IT22117014_Submission_Checklist.md` for final author/institutional confirmations. The older paper's 81.27% number describes the historical mixed-label row split, not current student-suitability accuracy. The old `135.2%` effort figure is `exp(log MAE)-1`, not observed MAPE; the 116-row original-hour MAPE is approximately 152.6%.

## Current implementation inspected

- `main.py`: proposal extraction, effort distribution, task classification, dependency DAG scheduling, capacity-risk rule, Monte Carlo simulation, NSGA-II, workload assignment, final rebalancing, PostgreSQL schedule history, expertise similarity, and academic-event endpoints.
- `train_workload_model.py`: feature engineering, label construction, split, XGBoost training, and evaluation.
- `progress_tracking.py`: assignments, effort-weighted progress, document/GitHub evidence, supervisor review, and Viva snapshots.
- `academic_scheduler_service.py`: four-role panel selection and interval-conflict helpers.
- `postgres_db.py`: active PostgreSQL persistence schema.
- `test_data_pack/VALIDATION_REPORT.md`: controlled proposal, workbook, document, and Git fixtures.
- `evaluate_models.py`: effort, auxiliary delay, and optional T5 evaluation.
- `evaluate_workload_balancing.py`: paired random, LPT, model-only, and hybrid allocation trials on held-out task rows.

## Verified model identity corrections

- `models/workload_rf.joblib` is a legacy filename. The serialized estimator is `XGBClassifier`; its stored `algorithm` metadata still says Random Forest and is stale.
- `models/logistic_delay.joblib` is a legacy filename. Its saved operational artifact is not the source of the displayed schedule risk. Current Gantt risk is calculated from required working days divided by available working days.
- T5-small is optional/lazy and disabled by default. Evidence-based extraction is the operational path.
- PostgreSQL database `ipms_scheduling`, not the legacy SQLite file, is the active persistence layer.

## Data used by the reported experiments

| Data | Verified use | Size |
|---|---|---:|
| `datasets/workload_assignment/GFG_FINAL.csv` | Workload model after assigned/date cleaning | 1,078 rows |
| `datasets/model3_delay/apache_jira_delay.csv` | Workload model Apache subset | 333 rows |
| China + Desharnais/PROMISE data | Effort evaluation | 580 projects |
| Three generated proposal PDFs | Controlled extractor verification | 75 explicit tasks |
| Panel/hall workbooks | Parsing and constraint fixtures | 30 staff, 8 halls |
| Progress evidence pack | Integration fixtures | 5 documents, 13 commits |

The SciREX files and `world-cities.csv` are present locally but were not identified as inputs to the current reported training/evaluation pipeline, so the paper does not claim that they were used.

## Reproduced numerical results

- Workload classifier: 81.27% held-out accuracy; 0.815 weighted F1; five-fold accuracy 76.47% +/- 0.95 percentage points.
- Held-out confusion matrix (actual rows, predicted columns; delayed/unfixed then fixed): `[[103, 6], [47, 127]]`. Delayed/unfixed recall is 0.945 and fixed-proxy recall is 0.730.
- Historical-profile allocation baseline (100 trials, 20 tasks, four members): random CV 39.46% and 98% overload; LPT CV 3.72% and 0% overload; model-only CV 154.31% and 100% overload; hybrid CV 4.40% and 0% overload.
- Cold-start allocation baseline: random CV 42.35% and 99% overload; LPT CV 3.68% and 0% overload; model-only CV 167.40% and 100% overload; hybrid CV 4.28% and 0% overload.
- Effort regressor: log MAE 0.8554; log RMSE 1.0614; evaluation-script approximate relative error 135.2%.
- Auxiliary logistic delay experiment: F1 0.5329; accuracy 0.8102; five-fold F1 0.3838 +/- 0.0554. It remains recorded here for audit purposes but was removed from the main paper because it is not the displayed Gantt risk and does not evaluate the operational risk rule.
- Optional T5 zero-shot test: ROUGE-1 0.2621, ROUGE-2 0.0626, ROUGE-L 0.2447 on five examples.
- Controlled proposal extraction: 24/25, 24/25, and 25/25, totalling 73/75 (97.3%).
- Service-enabled test run reported earlier: 60/60 tests passed. A stopped PostgreSQL service can make later reruns fail and should not be presented as a code regression without diagnosis.

## Local research papers used

- `1603.02754v3.pdf`: Chen and Guestrin, XGBoost.
- `1910.10683v4.pdf`: Raffel et al., T5.
- `1106.1813v1.pdf`: Chawla et al., SMOTE. Consulted because the legacy auxiliary delay artifact contains SMOTE, but not cited in the manuscript because SMOTE is not used by the reported workload classifier and is not part of displayed schedule risk.
- `applsci-13-05014.pdf`: Taboada et al., AI-enabled project-management systematic review.
- `Automatically_Classifying_Functional_and_Non-functional_Requirements_Using_Supervised_Machine_Learning.pdf`: Kurtanovi\'c and Maalej, requirements classification.

## Local papers not used as evidence

- `withdraw.pdf`, `withdraw (1).pdf`, and `withdraw (2).pdf`: duplicate copies with a withdrawal-style filename; excluded to avoid relying on an uncertain source.
- `Underwater_Wide-Area_Layered_Light_Field_for_Underwater_Detection.pdf`: unrelated to project scheduling.
- `Guest_Editors_Introduction_to_the_Special_Section.pdf`: unrelated editorial material.
- Friend's team-formation paper: inspected only to understand expected IEEE organisation; no text, experiment, or numerical claim was copied into this component paper.

## Claims intentionally not made

- No superiority over LPT or manual scheduling. The controlled experiment shows hybrid fairness close to, but slightly worse than, LPT; manual scheduling was not evaluated.
- No claim that controlled JIRA resampling represents a real student cohort.
- No external validation on real Sri Lankan undergraduate cohorts.
- No claim that the dependency scheduler calculates CPM slack or a critical path.
- No claim that a Git commit proves completion.
- No claim that the risk colour is a calibrated ML probability.
- No claim that the optional T5 model is fine-tuned or operational by default.
- No claim that NSGA-II or Monte Carlo has been rigorously benchmarked in the current study.
