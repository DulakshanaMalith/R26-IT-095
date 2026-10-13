# Common Report Component Handoff Pack

**Component Owner:** Lekamge R.L.M.D. (name supplied directly by the component owner on 10 October 2026; institutional registration spelling has not been independently checked).  
**Student ID:** IT22117014  
**Component:** Adaptive Scheduling and Generative Project Planning (component owner's wording, with spelling and capitalisation normalised from “adaptive sheduling and generative project planing” on 10 October 2026). Treat this as the owner-confirmed title; the exact university-registered wording remains to be checked against an approved record. Older poster/dissertation drafts use different title variants and should not silently replace this one.  
**Prepared From:** `IT22117014_Individual_Component_Dissertation_Submission_Candidate.docx` and its matching PDF; [dataset provenance audit](Dataset_Source_Provenance_Audit_2026-10-11.md); `main.py`; `train_workload_model.py`; `train_workload_model_v2.py`; `evaluate_workload_balancing.py`; `ieee_paper/workload_baseline_summary.json`; `ieee_paper/workload_proxy_v2_results.json`; `progress_tracking.py`; `academic_scheduler_service.py`; `postgres_db.py`; `student_submission_portal/app.py`; `test_data_pack/VALIDATION_REPORT.md`; `ieee_paper/SOURCE_AUDIT.md`; and the collection template `common_report_component_handoff_prompt.md`.  
**Evidence status:** Owner name/title updated from the component owner's 10 October 2026 message. A fresh isolated-PostgreSQL run passed **11/11** focused tests at approximately 20:48 +05:30, covering the earlier assignment/hall fixes plus History member restoration, mixed-format deadline scanning and a **synthetic local** PDF submission → supervisor approval → signed webhook evidence journey; see [fresh test record](Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md). A [read-only external audit](External_Evidence_Audit_2026-10-10.md) also matched a real public task-009 GitHub commit to an existing linked Scheduling database record and local `push` delivery row; GitHub's admin delivery receipt was not available. The earlier [screenshot set and redacted API trace](handoff_evidence/2026-10-10/README.md) shows 25-task initial/balanced versions, supervisor evidence view, academic events, and an HTTP 200 Team Formation → team-view response. Two additional screenshots show post-fix member restoration on a separate four-task test fixture. The current dissertation candidate has been regenerated with corrected dataset provenance and exported as a 46-page PDF, with four figures retained; see [author checklist](IT22117014_Submission_Candidate_Checklist.md) for institutional confirmations. Automatic Team Formation → scheduling group-ID import, direct Quality/Risk exchange, a **fresh complete** student/GitHub end-to-end journey, and a team-approved individual-contribution statement remain unverified. This is not production, complete system, or student-cohort validation.

### Resolution of older review comments

| Older comment | Current checked position | Evidence boundary |
|---|---|---|
| "Live hybrid assignment route has a known defect" | The live `/api/progress/auto-assign` route is unique, authenticated and uses **LPT**. The historical classifier-guided hybrid is an **offline comparison**, not a live model. | Code route inspection and focused PostgreSQL tests; not a student-outcome claim. |
| "Hall capacity is not enforced" | Draft generation, manual rescheduling and publication reject a hall below the configured required seats (team + four panellists + audience seats). | Focused database tests cover this policy; real institutional audience/equipment rules remain unverified. |
| "Fresh database-backed testing is needed" | The focused suite was rerun on 10 October 2026 at approximately 20:48 +05:30: **11 passed**, with two dependency deprecation warnings. | Isolated test database only; a synthetic local workflow is covered, but real external deliveries are still needed. |
| "Final cross-component payloads are verified" | A local HTTP 200 Team Formation active-allocation response and its rendered scheduling team-view page are now captured. **Automatic backend mapping and Quality/Risk exchange are still not established.** | [Local trace](handoff_evidence/2026-10-10/api_trace_summary.json) uses database clones with sample `P01`–`P03` teams, none matching scheduling group `R26-IT-095`. |

**Regression reproduction:** Create an empty PostgreSQL database named `ipms_scheduling_codex_test_20261010`, set `SCHEDULING_DATABASE_URL` to its connection URL, then run `python -m pytest component_scheduling/test_scheduling_remediation.py -q` from the workspace root. The tests write synthetic schedules, people and halls only to that exact test database and skip if a different database URL is configured.

**Fresh run record:** The current focused run returned exit code `0` and `11 passed, 2 warnings in 10.72s`; Python compilation and JavaScript syntax checks also passed. The original six tests cover authenticated LPT assignment and hall-seat safety. Five additional tests cover persisted member IDs in History, honest handling of unknown legacy IDs, flat/wrapped deadline notices, malformed legacy History rows, and a local synthetic PDF approval/signed-webhook journey. See [fresh test record](Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md), the historical `Scheduling_Remediation_Test_Evidence_2026-10-10.md`, and `test_scheduling_remediation.py`. The synthetic journey does not establish a real GitHub.com delivery or other component APIs.

## 1. Component Identity

The component converts a project proposal into a source-linked draft task plan and Gantt schedule, provides progress-evidence and review records, and supports academic-event timetable drafting. Its users are primarily supervisors for project planning/review and academic staff for event scheduling. A separate test-only document-submission portal is available locally; it is not institutional student authentication.

**Identity status:** the component owner supplied `Lekamge R.L.M.D.` and `Adaptive Scheduling and Generative Project Planning` for `IT22117014` on 10 October 2026. This resolves the missing owner-provided name/title, but an approved registration record or supervisor confirmation is still needed if the common report must reproduce the exact institutional wording. Use this owner-confirmed title consistently in new common-report text; do not silently substitute the different titles in older poster/dissertation drafts.

## 2. Subproblem Addressed

A proposal is not an executable work breakdown structure (WBS). Staff must identify actionable tasks, estimate effort, respect dependencies, distribute work, track what was actually submitted, and coordinate Proposal, PP1, PP2 and Viva events. Manual handling becomes difficult across many groups; a visual progress percentage can also confuse GitHub activity with approved work. This component investigates an evidence-linked, auditable workflow for those decisions. Its research gap is the connection of proposal provenance, dated plans, workload fairness, reviewable evidence and academic timetable records in one group-keyed prototype—not proof that automation improves real student outcomes.

**In scope:** proposal PDF parsing, provisional effort and dates, schedule versions, offline allocation comparison, task evidence and human review, academic panel/hall draft scheduling. **Out of scope:** quality grading, risk component decisions, team-formation optimisation, production identity/security certification, and a validated student-suitability predictor. See corrected dissertation §§1.2–1.5, 4 and 6.

## 3. Stakeholders and User Needs

| Stakeholder | Need | Component response and boundary |
|---|---|---|
| Project supervisor | Inspect proposal-derived tasks and student evidence | Gantt/history and document review; human approval remains necessary |
| Academic staff | Arrange evaluations across groups | Supervisor/hall upload, role- and availability-aware draft timetable |
| Student | Submit documents for eligible tasks | Separate portal with group/student ID and task-scoped upload; not a full student account system |
| Project coordinator | Compare group plans and event states | Group ID, schedule versions and event batches; cross-component data consistency needs verification |

The primary planning/review user is the supervisor; academic staff are the primary timetable users.

## 4. Inputs, Processing and Outputs

| Main input | Source and format | Purpose |
|---|---|---|
| Proposal, group ID, team size, expected months, start date, function points | Staff upload; PDF and form fields | Recover tasks and make a provisional plan |
| Member IDs and current schedule version | Staff action / PostgreSQL | Live LPT task ownership, load calculation and a new balanced schedule version |
| Supervisor and hall availability | Staff XLSX uploads | Candidate academic panels and rooms |
| Document and GitHub activity | Separate portal upload; signed webhook | Task-linked evidence, not automatic academic approval |

| Method/model | Current role | Important qualification |
|---|---|---|
| Rule-based WBS extraction and filtering | Source-linked proposal tasks | Scores mark source priority, not calibrated confidence |
| XGBoost effort regressor and task weights | Provisional project/task effort | Trained on non-student software-project records; large error |
| DAG/topological ordering and working-day calculation | Dated Gantt bars | Displayed initial owner is `Unassigned`; no CPM critical-path claim |
| XGBoost issue-status proxy classifiers | Historical offline experiments only | Mixed-label artifact and time-aware Sourcetree-only rerun are **not** validated student suitability |
| LPT, model-only and guarded hybrid policies | Live LPT; four-policy offline comparison | Hybrid is offline only; live route deliberately disables JIRA proxy scoring |
| TF–IDF similarity, optional MiniLM, role/time/capacity constraints | Candidate academic panel and event slots | Minimum seats = four panelists + team size + audience seats; real institutional policy still needs confirmation |

**Outputs:** proposal task records with source evidence; versioned, dated Gantt data; LPT assignment/load summaries; document submissions and review decisions; linked or flagged GitHub events; draft/published academic event batches; calendar/Excel exports. A generated date is a suggestion, a commit is activity, and an approved document is a human decision. See `main.py`, `progress_tracking.py`, and the current dissertation candidate §§3–4.

## 5. Contribution to the Complete IPMS

This component covers the planning-to-assessment part of the project lifecycle. It gives the integrated portal a proposal-grounded task identity, draft dates, saved versions, evidence and event schedule. Team Formation is a related upstream component at the *system* level, but the current scheduling backend's academic-group loader reads its own `current_project` records or caller-supplied groups; a live Team Formation API dependency is **not confirmed**. The common portal links to the scheduling, quality, risk and team applications; a direct Quality/Risk data exchange with this scheduling backend is **not confirmed**. Shared group and member identifiers must be kept consistent before the common report calls the integration seamless. Without this component, the shared portal would lack this proposal-to-Gantt and academic-event workflow. See `main.py:6082–6108`, root `index.html`, `frontend/team_portal.html`.

## 6. Technology Stack

| Layer | Confirmed technology and use |
|---|---|
| Frontend | HTML, CSS and JavaScript in `frontend/`; separate HTML/JS submission page |
| Backend | Python/FastAPI (`main.py`, `progress_tracking.py`, portal `app.py`) |
| Database | PostgreSQL, normally `ipms_scheduling` via `SCHEDULING_DATABASE_URL` |
| ML/algorithms | XGBoost, scikit-learn TF–IDF/cosine similarity; LPT, dependency ordering and offline guarded rebalancing; optional MiniLM/T5 and exploratory NSGA-II/Monte Carlo |
| File processing | PDF extraction and XLSX parsing; document signature/hash checks |
| Integration | HTTP API; GitHub HMAC-SHA256 webhook; separate portal-to-scheduler API with integration key |
| Runtime | Localhost-bound Uvicorn by default; test portal uses scheduler port 8000 and portal port 8010; no production deployment confirmed |

The `models/workload_rf.joblib` filename is legacy: its saved estimator is `XGBClassifier`, but it is not loaded for live assignment. The displayed Gantt risk is a capacity-rule indicator, not the legacy delay-risk model's calibrated probability. See `ieee_paper/workload_proxy_v2_results.json` and `ieee_paper/SOURCE_AUDIT.md`.

## 7. Architecture Summary

Staff use the scheduling UI and FastAPI backend to turn proposal text into task records and dated schedule versions in PostgreSQL. The authenticated auto-assignment route uses LPT and stores a separate balanced version. Progress routes store document versions, reviews and GitHub evidence against task keys; a standalone test-only student portal proxies eligible task queries and uploads. Academic routes use local group/topic records or caller-supplied groups plus uploaded staff/hall availability and capacity to create event batches.

| Module | Responsibility |
|---|---|
| `main.py` | Proposal, Gantt, workload-route code, academic routes and authentication |
| `train_workload_model.py` | Disabled-by-default legacy mixed-label experiment, retained for audit |
| `train_workload_model_v2.py` | Time-aware, Sourcetree-only offline proxy experiment; no live student-suitability claim (`GFG_FINAL.csv` is the legacy filename) |
| `evaluate_workload_balancing.py` | Paired offline allocation-policy experiment |
| `progress_tracking.py` | Assignments, document review, GitHub evidence and Viva snapshots |
| `academic_scheduler_service.py` | Panel-role and interval helpers |
| `postgres_db.py` | PostgreSQL connection and schema |
| `student_submission_portal/app.py` | Limited portal and authenticated proxy to scheduler API |

**Diagram to redraw:** `Supervisor/staff → scheduling UI → FastAPI → proposal/WBS/effort/DAG → PostgreSQL schedule → LPT balanced version` with separate branches `test-only student portal → submission API → supervisor review`, `GitHub → signed webhook → task activity`, and `staff workbooks + group/topic → academic-event drafts`. Mark JIRA-model/hybrid allocation **offline only**.

## 8. Integration with Other Components

| Direction | Data/mechanism | Confirmed status |
|---|---|---|
| Team Formation → scheduling view | `frontend/team_portal.html` calls Team API `GET http://127.0.0.1:8003/api/final-allocations/active/teams` | Local HTTP 200 and rendered team cards [captured](handoff_evidence/2026-10-10/README.md); no automatic import into schedule records shown |
| Scheduling ↔ Quality/Risk | Common portal opens separate applications | Navigation confirmed; direct schedule-data exchange and payloads **not confirmed** |
| Student portal → scheduling | `GET /api/integrations/projects/{project_id}/document-tasks`, `POST /api/integrations/document-submissions`, integration key | Implemented route and proxy code; fresh end-to-end run not retained |
| GitHub → scheduling | `POST /api/webhooks/github` with configured HMAC secret and task key | Route present; delivery success does not prove task completion |

| Method | Endpoint | Main purpose / request / result |
|---|---|---|
| POST | `/api/schedule/upload-pdf` | Proposal PDF → extracted task/proposal data |
| POST | `/api/schedule/generate` | Project parameters and tasks → dated/versioned schedule |
| GET | `/api/schedule/history` | Group schedule history |
| POST | `/api/progress/auto-assign` | Staff/supervisor-authenticated LPT ownership; saves balanced version; isolated regression tested |
| GET/POST | `/api/integrations/projects/{project_id}/document-tasks`, `/api/integrations/document-submissions` | Student task list and upload through separate portal |
| GET/POST | `/api/progress/submissions/{submission_id}/document`, `/api/progress/submissions/{submission_id}/review` | Supervisor reads/reviews a document |
| POST | `/api/webhooks/github` | Signed activity ingestion |
| POST | `/api/academic/auto-schedule` | Group/topic, week offsets and duration → draft event batch |
| GET | `/api/academic/events` | Event/group list for staff inspection |

An earlier dissertation audit incorrectly claimed the first duplicate route shadowed the later handler: the existing `_remove_duplicate_api_routes()` function already retained the latest route. The legacy handler is now unregistered explicitly; route inspection and a database-backed test confirm one active `/api/progress/auto-assign` route. Its live model branch is disabled until student-suitability data exist. Group/project ID (`R26-IT-095` form), student/member ID, task ID/task key (`[R26-IT-095-TASK-024]`), schedule version, submission ID, and academic batch/event IDs are confirmed scheduling identifiers. A common cross-component allocation ID is **not confirmed**.

### Cross-component contract and trace status

The Team Formation backend returns `success`, `allocation_id`, `allocation_status`, `revision_number`, `allocation_source`, `student_count`, `team_count`, and `teams[]`. Each team contains `group_key`, `team_number`, `project_id`, `project_title`, `members[]` (student IDs), and optional `supervisor` (`supervisor_id`, `supervisor_name`). The scheduling `team_portal.html` reads these fields for display. Code inspection and a local HTTP 200/browser capture now verify **Team Formation API → scheduling team-view rendering**. They do **not** establish that `project_id`/`group_key` automatically maps to scheduling's `R26-IT-095` group ID: the captured sample allocation uses `P01`–`P03` and `SIM-*` member IDs. Sources: Team Formation `app/services/final_allocation_service.py:get_active_team_data`, scheduling `frontend/team_portal.html:loadTeams`, and [capture trace](handoff_evidence/2026-10-10/api_trace_summary.json).

| Handoff to prove | Payload/identity evidence required | Status at this handoff |
|---|---|---|
| Team Formation API → scheduling team view | Timestamped, redacted `GET /api/final-allocations/active/teams` status and JSON; show `project_id`, `group_key`, `members[]`, supervisor presence, then rendered team cards | **Captured locally:** HTTP 200, three active sample teams and rendered cards; [trace](handoff_evidence/2026-10-10/api_trace_summary.json) and [screenshot](handoff_evidence/2026-10-10/09_team_formation_active_allocations.png) |
| Team Formation → scheduling proposal/academic records | Show exactly which Team `project_id` or `group_key` becomes scheduling `group_id`, and the request/response or database import that carries it | Automatic handoff not verified; manual group entry/local records remain possible |
| Scheduling ↔ Quality and Risk | Named producer/consumer endpoints, redacted request/response JSON and stable group/member ID mapping, if a direct exchange exists | No direct data exchange verified; portal navigation alone is insufficient |
| Test submission portal → scheduling | Redacted task-list and upload request/response, including group/member/task IDs, HTTP status and pending-review state | **Task-list GET captured:** portal returned HTTP 200 and seven eligible tasks for a typed member ID; [portal screenshot](handoff_evidence/2026-10-10/10_student_portal_task_selection.png) and [trace](handoff_evidence/2026-10-10/api_trace_summary.json). Existing submission/preview also visible; a fresh portal **upload** was not captured. |
| GitHub → scheduling progress | Delivery ID, HTTP status, task key and resulting activity record, with webhook secret/signature and personal data redacted | [Public commit and local DB cross-check](External_Evidence_Audit_2026-10-10.md) now confirms matching task-009 SHA and a pre-existing local `push` delivery row. GitHub's administrator delivery receipt and a fresh end-to-end run are still missing. |

For the screenshot run, Scheduling (`8000`) and Team Formation (`8003`) were started against **isolated clones** of their PostgreSQL databases, and the standalone test submission portal (`8010`) was pointed at the cloned Scheduling service. The [trace summary](handoff_evidence/2026-10-10/api_trace_summary.json) records request URLs, statuses and response digests without tokens, webhook secrets or document bytes. The temporary services were stopped after capture; the clones remain for reproducibility. No Quality/Risk service was run. For any final claim of automatic backend handoff, separately save a redacted request/response showing how the same group/member IDs move between components and the resulting database state; the sample team IDs in this run do not match `R26-IT-095`.

**Sequence:** obtain or enter group context → upload/inspect proposal → generate provisional versioned Gantt → assign shared/parallel/individual ownership with LPT and save a balanced version → accept task evidence and supervisor review → make Viva snapshot → draft and publish capacity-checked academic events. Missing proposal/group data are rejected or reported; the portal returns 503 when the scheduler is unavailable; webhook signatures/repository/task keys are checked; no undocumented cross-component fallback is asserted. See `student_submission_portal/app.py`, `progress_tracking.py`, `main.py`.

## 9. End-to-End Role

Team Formation can establish a group and supervisor in the wider IPMS, but the precise automatic handoff into the scheduling backend has not been verified. The scheduler accepts a proposal and creates a source-linked, dated plan for that group. Its initial visible task owners remain unassigned; authenticated LPT assignment can then create a distinct balanced version. The separate test portal lets a student submit a document for an eligible task, but typed IDs are not verified student identities. The supervisor can read and approve or reject it, while signed GitHub events remain activity evidence rather than automatic completion. Academic staff can use group/topic records and their uploaded availability to draft Proposal, PP1, PP2 and Viva events. Quality and Risk are separate applications in the common portal; their direct data exchanges with this component need evidence before being described as operational integration.

## 10. Research Method Summary

The study combines source inspection, controlled extraction fixtures, a historical issue-status classifier, an effort regression experiment, and paired offline allocation trials. It is a prototype evaluation, not a real-cohort or formal usability study.

| Dataset/fixture | Size and role | Important limit |
|---|---|---|
| Sourcetree Jira export + local Apache-project summary | 1,078 cleaned Sourcetree issues from 49,000 raw rows + 333 prepared Apache-labelled rows; stratified 80/20 row split, 283 hold-out | Sourcetree class 1 = `Fixed`; Apache class 1 = `not delayed`; five Sourcetree assignee IDs and five Apache project pseudo-members; self-outcome aggregate leakage. Apache rows have no original issue keys or source manifest. |
| Sourcetree-only time-aware proxy rerun | 1,078 assigned issues; latest 216 by creation date held out | Snapshot `Fixed` status is censored and not a student-suitability label; history features use earlier records only |
| China + Desharnais local merge | 499 + 81 project rows; 116 hold-out | Non-student effort data; all 499 China function-point/effort pairs match Zenodo v1; exact Desharnais acquisition route remains undocumented |
| Synthetic proposals | Three PDFs, 25 explicit WBS entries each | Designed recovery fixtures, not independent proposal corpus |
| Allocation simulations | 100 paired trials/scenario; 20 held-out tasks, four member profiles/trial | Resampled issue tasks, not 100 actual teams |
| Synthetic academic/evidence fixtures | 30 staff, eight halls; five documents, 13 commits | Parser/evidence fixtures, not human outcome data |

**Dataset source check (11 October 2026):** `GFG_FINAL.csv` is a misleading legacy filename: its 49,000 raw rows all identify Atlassian's Sourcetree-for-Windows project (`SRCTREEWIN`), and a contained issue key can be checked on [Atlassian Jira](https://jira.atlassian.com/browse/SRCTREEWIN-14001). All 499 China feature/effort pairs match [Zenodo China v1](https://zenodo.org/records/268446). The Apache summary lacks issue keys and extraction metadata; exact acquisition/rights for the local exports remain open. The [dated provenance audit](Dataset_Source_Provenance_Audit_2026-10-11.md) records hashes and the distinction between a content match and a verified original download.

**Metrics:** mixed-proxy accuracy/weighted F1/confusion matrix; effort log MAE/RMSE and separately recomputed original-hour MAPE; WBS-entry recovery; workload coefficient of variation (CV), max–min hour spread and overload-trial rate. **Comparators:** random, LPT, model-only, guarded hybrid. No supervisor-authored schedule comparator or statistically supported claim of hybrid superiority.

## 11. Strongest Research Results

| Result | Value | What it actually demonstrates | Data type |
|---|---:|---|---|
| Legacy mixed issue-status proxy hold-out accuracy / weighted F1 | 81.27% / 0.815 | Historical mixed-label, leakage-prone JIRA row split; **not** student suitability or current deployed performance | Historical issues |
| Time-aware Sourcetree-only proxy hold-out accuracy / weighted F1 | 31.94% / 0.2561 | Latest 216 issues; below the 77.31% majority-class baseline; model not deployed | Historical issues |
| Five-fold proxy accuracy | 76.47% ± 0.95 percentage points | Prepared-table CV; aggregates were not rebuilt within folds | Historical issues |
| Effort log MAE / RMSE | 0.8554 / 1.0614 | Error on `log1p(hours)`, not hours | Historical projects |
| Effort original-hour MAPE / median APE | About 152.6% / 61.8% | Audit recomputation on the same 116-row hold-out; high uncertainty | Historical projects |
| Explicit-WBS recovery | 73/75 (97.3%) | Known items recovered; false-positive precision unmeasured | Synthetic PDFs |
| Historical-profile workload CV | LPT 3.72%; hybrid 4.40% | Hybrid near, but slightly worse than, LPT for fairness | Controlled offline resampling |
| Historical-profile overload trials | LPT 0%; hybrid 0%; model-only 100% | Observed 1.40-ratio violations in 100 trials, not a universal guarantee | Controlled offline resampling |
| Cold-start workload CV | LPT 3.68%; hybrid 4.28% | Fairness with default profiles; no expertise benefit measured | Controlled offline resampling |

The old `135.2%` figure is `exp(log MAE)-1`, **not measured MAPE**. The legacy classifier mixed source labels and leaked member outcomes. The Sourcetree-only chronological rerun performed poorly, so neither classifier is loaded for live assignment. Allocation results come from the separate evaluator and do not establish real student benefits. The extraction number is fixture recovery rather than general PDF accuracy. See `ieee_paper/workload_proxy_v2_results.json`, `ieee_paper/workload_baseline_trials.csv`, and the current dissertation candidate's historical-results discussion.

## 12. Product and Technical Results

| Evidence | Supported conclusion | Not established |
|---|---|---|
| Saved proposal fixture report | Extractor returned 24/25, 24/25, 25/25 known tasks | Precision/generalisation on real proposals |
| 30-staff/eight-hall fixture report | Required workbook rows and date/time formats parsed | Real staff availability or institution-specific seating policy |
| Evidence pack validation | Five readable task-aligned documents and 13 task-keyed commits prepared | Supervisor acceptance or live DB ingestion |
| Source inspection | PostgreSQL schema/routes and review logic exist | Real external-service and user-identity validation; local synthetic flow is separately tested |
| Isolated PostgreSQL regression (11 tests) | Original six assignment/auth/hall checks plus History IDs, legacy deadline/history compatibility and a synthetic local PDF review/signed-webhook workflow | Real-cohort outcomes, a fresh GitHub admin delivery receipt or full cross-component integration |

An older audit mentions **60/60** backend tests, but its raw run log was not retained. The current focused run passed **11/11** tests against an isolated PostgreSQL database; do not present that as a production or real multi-component system pass. See `Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md`, `test_scheduling_remediation.py` and `test_data_pack/VALIDATION_REPORT.md`.

## 13. Stakeholder / User Validation

Formal supervisor, student, academic-staff usability or longitudinal outcome evaluation is **not confirmed from the available project evidence**. Prior manual demonstrations and screenshots are not a documented user study. No measured time savings, satisfaction score or institutional acceptance rate should be claimed.

## 14. Limitations and Threats

**Research:** mixed outcome labels and self-outcome/history leakage in the legacy proxy; row split with repeated identities; a newer chronological Sourcetree-only proxy still below its majority baseline; incomplete provenance for the prepared Apache summary; no student-cohort or manual-plan baseline; synthetic extraction fixtures without precision; high effort error. Trial-level paired allocation results are now saved, but their spread is descriptive over resampled issues, not independent-team uncertainty.

**Product:** assignment and hall-capacity fixes have focused tests, but initial plan and risk scores are advisory; the separate test portal and its backend submission endpoints have no verified student identity and are blocked in production mode; production identity, privacy and full-system validation remain open.

**Integration:** shared IDs and common portal links exist, but live backend exchange with Team Formation, Quality and Risk is not fully verified. The scheduler and portal depend on available PostgreSQL and backend services.

## 15. Commercialisation and Sustainability Input

**Value proposition:** reduce repetitive first-draft planning and make task evidence/review and academic schedules easier to inspect; no measured staff-time or cost savings yet. **Beneficiaries:** students, supervisors, academic staff and coordinators. **Adoption prerequisites:** broader route/capacity tests with real rules, institution-approved authentication, consent, security review, stable hosting, backups, retention/deletion policy and support ownership. **Resources:** PostgreSQL, backend/frontend hosting, model and document storage, staff availability maintenance and reviewer time. **Licensing/IP:** exact source-dataset licences, collection dates and institutional ownership are not confirmed; review them before distribution. **Responsible AI:** keep JIRA proxy scores away from grading, expose uncertainty, use human approval and secure personal documents/identities. **Sustainability:** document APIs, retain regression tests and allow administrators to update availability and rules. SDG 4 (quality education) is a plausible *intended* alignment, not a measured impact.

## 16. Individual and Shared Team Contribution

The scheduling-component artefacts support the following **component-level** contributions, but they do not establish which human wrote each line. Attribute them to IT22117014 personally only after the student/team confirms ownership:

- Proposal/WBS extraction, provisional effort and dependency-aware Gantt design.
- Workload model preparation and offline LPT/model/hybrid evaluation.
- Task progress, document-review and signed GitHub evidence workflow.
- Academic-event scheduling interface and panel/availability constraints.
- PostgreSQL versioning, API and frontend integration for this component.

Confirmed shared team architecture, UI, testing or deployment work by named members is **not confirmed from the available project evidence**. The common report should request a team-approved contribution table rather than inferring authorship from folders.

**Contribution statement awaiting team approval (not yet a factual attribution):** “*Adaptive Scheduling and Generative Project Planning* covers proposal-grounded WBS extraction, provisional effort and dependency-aware Gantt generation, live LPT workload assignment and schedule versioning, document/GitHub progress evidence, and capacity-aware academic-event scheduling. Lekamge R.L.M.D. (IT22117014)'s personal implementation, evaluation, writing and integration responsibilities are to be specified and approved by all team members and the supervisor before this paragraph is used as an individual-authorship claim.”

| Approval item | Required entry | Current status |
|---|---|---|
| IT22117014's own tasks and files | Student-written description, with any shared work separated | Not supplied/approved |
| Other members' shared contributions | Names/IDs and mutually agreed responsibilities | Not supplied/approved |
| Team confirmation | All member approvals and date, or signed contribution form | Not supplied |
| Supervisor confirmation if faculty requires it | Name, decision and date | Not supplied |

## 17. Suggested Paste-Ready Common-Report Content

### Chapter 2 — Subproblem summary

Research proposals describe intended work but do not provide a dated, auditable task plan. The scheduling component addresses task extraction, provisional effort and dependency planning, evidence review and academic-event coordination. It distinguishes model suggestions and GitHub activity from approved work. Its current live assignment uses LPT, saves a separate balanced Gantt version, and checks hall seating capacity. These code paths passed focused isolated-database tests; real-cohort outcomes remain unmeasured.

### Chapter 3 — Component summary

The component associated with Lekamge R.L.M.D. (IT22117014) is titled *Adaptive Scheduling and Generative Project Planning* (owner-confirmed title; exact registered wording pending verification). It takes proposal PDFs and project parameters, extracts source-linked WBS tasks, estimates provisional effort and generates a versioned Gantt. It also stores document-review and signed repository evidence and drafts Proposal, PP1, PP2 and Viva events from group/topic, staff and hall availability. Live assignment uses LPT; an offline evaluator compares random, LPT, score-only and guarded hybrid allocation. JIRA-trained scores are historical issue-status proxies, not validated student-suitability measures. Specific personal and shared implementation credit still requires the team-approved contribution statement in Section 16.

### Chapter 4 — Integration summary

The common portal links this scheduling application with separate team, quality and risk applications. Scheduling uses group and member identifiers, while its student submission portal calls the scheduling backend through an integration key. GitHub webhooks provide signed task-key activity, and staff review document versions before accepting work. The academic scheduler currently loads local group/topic records or groups supplied in the request. Direct, automatic backend exchange with Team Formation, Quality or Risk should be described only after a tested API trace is supplied.

### Chapter 5 — Implementation summary

Python/FastAPI services, PostgreSQL, HTML/JavaScript interfaces, XGBoost research artifacts and rule-based scheduling support the component. Proposal parsing preserves source evidence; a DAG calculation produces dates; separate progress routes manage uploads, review and signed GitHub events. The authenticated LPT route persists a new balanced schedule version. Academic routes rank eligible panel members and check role, time, booking and seating-capacity constraints. Focused PostgreSQL tests cover assignment versioning and hall-capacity rejection, but do not cover every system route.

### Chapter 6 — Results summary

The historical mixed-label Jira proxy reported 81.27% row-split accuracy, but its labels and member-history features make that number unsuitable for live student assignment. A Sourcetree-only time-aware rerun reached 31.94% chronological hold-out accuracy, below a 77.31% majority-class baseline, and was not deployed. In 100 simulated historical-profile allocation trials, LPT averaged 3.72% workload CV and the offline guarded hybrid 4.40%; neither overloaded under the tested threshold. A deterministic extractor recovered 73 of 75 explicit tasks in three synthetic proposal PDFs; precision on real proposals was not measured. The effort regressor's log MAE was 0.8554, and a separate audit computed approximately 152.6% original-hour MAPE. These do not demonstrate better real student outcomes.

### Chapter 7 — Commercialisation/sustainability contribution

The component could save staff effort in producing first-draft schedules and make review evidence easier to audit, but those benefits have not been measured. Institutional adoption requires accurate group data, staff/hall policies, secure identity and document handling, stable hosting, backups and maintained tests. Automated scores should remain advisory and human reviewers should control academic approval.

### Chapter 8 — Future direction

Expand assignment and hall-capacity testing to realistic multi-group policies and collect consented student-project data. Use consistent labels and prospective validation, compare with supervisor-authored plans, and measure extraction precision, staff time, schedule adherence and user experience.

## 18. Figures, Tables and Screenshot Evidence

| Visual | Best use | Source/status |
|---|---|---|
| Proposal-to-evidence workflow | Architecture, with live LPT assignment and offline hybrid distinguished | Available: current dissertation candidate Figure 1 |
| Four-policy CV chart | Bounded offline evaluation | Available: dissertation Figure 3 and saved summary JSON; **offline**, not live-model evidence |
| Mixed-proxy confusion matrix | Explain dataset/label limits | Available: dissertation Figure 4; **legacy** result |
| Initial Gantt | Same group after proposal generation; 25 `UNASSIGNED` tasks in cloned database version 7 | [Captured image](handoff_evidence/2026-10-10/01_initial_gantt_v7.png) and [trace](handoff_evidence/2026-10-10/api_trace_summary.json) |
| Balanced Gantt and workload | Same group after authenticated LPT assignment; version 8, four explicitly entered IT member IDs | [Gantt](handoff_evidence/2026-10-10/02_balanced_gantt_v8.png) and [load summary](handoff_evidence/2026-10-10/03_workload_balance_v8.png); 3.5% CV is a run output, not a cohort finding |
| Schedule history | Distinct initial and balanced version entries | [Captured history](handoff_evidence/2026-10-10/04_schedule_history_v7_v8.png); older exploratory versions also appear |
| Post-fix member restoration | New four-task test version retains its two IT IDs after reopening History | [History entry](handoff_evidence/2026-10-10/11_history_roster_version.png) and [restored IDs](handoff_evidence/2026-10-10/12_history_restored_member_ids.png); separate isolated test fixture, not the 25-task proposal run |
| Document and GitHub evidence | Pending review, protected document preview and one linked commit, without taking an approval action | [Queue](handoff_evidence/2026-10-10/05_supervisor_review_queue.png), [document modal](handoff_evidence/2026-10-10/06_document_review_modal.png), [GitHub modal](handoff_evidence/2026-10-10/07_github_evidence_modal.png); old sample filename numbering differs from its stored task key |
| Academic events | Existing published Proposal/PP1/PP2/Viva cards for `R26-IT-095`, with panels, halls and statuses | [Proposal/PP1](handoff_evidence/2026-10-10/08a_academic_proposal_pp1.png) and [PP2/Viva](handoff_evidence/2026-10-10/08b_academic_pp2_viva.png); the screenshots do not show required-seat calculations |
| Cross-component team view | Active Team Formation allocation rendered by scheduling team portal | [Captured page](handoff_evidence/2026-10-10/09_team_formation_active_allocations.png) and [HTTP trace](handoff_evidence/2026-10-10/api_trace_summary.json); sample teams do not map to scheduling group `R26-IT-095` |
| Standalone student portal | Test-only typed-ID task-list workflow, without claiming verified student identity | [Captured portal](handoff_evidence/2026-10-10/10_student_portal_task_selection.png) and HTTP 200 task-list [trace](handoff_evidence/2026-10-10/api_trace_summary.json); no new upload was performed |

The [screenshot README](handoff_evidence/2026-10-10/README.md) records capture date, isolated-database scope, group and schedule versions, image purpose and limitations. These screenshots illustrate UI states; they do not substitute for a complete payload trace or prove an academic outcome. The earlier 25-task v7 capture was made **before** the History fix and required explicit entry of four IDs. The later two-member test fixture demonstrates that newly saved versions now restore their IDs. Pre-fix unassigned versions without stored metadata cannot be reconstructed automatically and require manual confirmation.

## 19. References Relevant to the Common Report

| Ref. | Reference | Relevance |
|---|---|---|
| [1] | I. Taboada *et al*., “Artificial Intelligence Enabled Project Management: A Systematic Literature Review,” *Applied Sciences*, vol. 13, no. 8, art. 5014, 2023. doi: 10.3390/app13085014. | Project-management context |
| [2] | M. Jørgensen and M. Shepperd, “A Systematic Review of Software Development Cost Estimation Studies,” *IEEE Transactions on Software Engineering*, vol. 33, no. 1, pp. 33–53, 2007. doi: 10.1109/TSE.2007.256943. | Effort-estimation caution |
| [3] | T. Chen and C. Guestrin, “XGBoost: A Scalable Tree Boosting System,” *Proc. ACM SIGKDD*, pp. 785–794, 2016. doi: 10.1145/2939672.2939785. | Model method |
| [4] | R. L. Graham, “Bounds on Multiprocessing Timing Anomalies,” *SIAM Journal on Applied Mathematics*, vol. 17, no. 2, pp. 416–429, 1969. doi: 10.1137/0117039. | Load-balancing comparator context |
| [5] | E. Kalliamvakou *et al*., “The Promises and Perils of Mining GitHub,” *Proc. MSR*, pp. 92–101, 2014. doi: 10.1145/2597073.2597074. | Limits of commit evidence |

Confirm each reference against the final common-report bibliography before publication.

## 20. Evidence / Verification Checklist

| Claim | Status | Source / remaining check |
|---|---|---|
| Student ID | Present in component/dissertation records | Official university record still needed for full-name matching |
| Owner-provided name and component title | **Supplied by component owner on 10 Oct 2026** | `Lekamge R.L.M.D.`; *Adaptive Scheduling and Generative Project Planning* (spelling normalised) |
| Exact institution-registered name/title wording | **Not independently verified** | Compare the owner-provided wording with an approved registration or supervisor-confirmed record before a formal submission |
| XGBoost workload artifact identity | Confirmed by source/artifact audit | `train_workload_model.py`; corrected dissertation §4.9 |
| Sourcetree/Apache counts and mixed target | Confirmed for saved training setup; not student labels | `train_workload_model.py`; [dataset provenance audit](Dataset_Source_Provenance_Audit_2026-10-11.md); current dissertation candidate §§3, 5 |
| Effort and allocation metrics | Saved/recomputed offline only | Submission-review dissertation §§5–6; `workload_baseline_summary.json` and `workload_baseline_trials.csv` |
| 73/75 WBS recovery | Controlled fixture result | `test_data_pack/VALIDATION_REPORT.md` |
| Portal/API routes and PostgreSQL | Local cloned-DB UI and synthetic test-client document/review/webhook workflow demonstrated; real cross-component delivery pending | `main.py`, `progress_tracking.py`, `postgres_db.py`; [fresh test record](Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md) and [capture README](handoff_evidence/2026-10-10/README.md) |
| Live LPT ownership and versioning | **11/11 focused suite passed at approximately 20:48 +05:30, 10 Oct 2026** | `main.py`; `test_scheduling_remediation.py`; [fresh test record](Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md); isolated test DB, not production |
| Hall-capacity safety | Same focused run passed generation, reschedule and publish capacity checks | `main.py`; `test_scheduling_remediation.py`; institution-specific policy not validated |
| Live hybrid assignment defect | **Resolved by scope correction**: unique live LPT route; historical hybrid offline only | Route inspection and focused test; do not describe hybrid as the current live model |
| Team Formation payload trace and group-ID mapping | **Team API → team-view trace captured; automatic group-ID mapping not verified** | Local HTTP 200 and three sample team cards; `P01`–`P03`/`SIM-*` do not match `R26-IT-095`; [trace](handoff_evidence/2026-10-10/api_trace_summary.json) |
| Public GitHub commit vs stored task evidence | **Matched read-only** | [Task-009 commit/DB audit](External_Evidence_Audit_2026-10-10.md): same SHA, task key and time; local `push` row exists. No GitHub admin delivery receipt or fresh full workflow. |
| Quality/Risk direct exchange | **Not established** | Common portal links applications; require named endpoints and payloads before asserting data integration |
| Current UI screenshots | **13 captured from isolated clones/test database** | [Images and scope notes](handoff_evidence/2026-10-10/README.md); report-use approval/redaction still needed |
| History restores member IDs | **Fixed for newly generated versions and browser-verified** | New two-member test fixture restores both IDs; old unassigned rows without saved IDs remain unknown and require manual entry; [post-fix capture](handoff_evidence/2026-10-10/12_history_restored_member_ids.png) |
| Background deadline checker across old schedule formats | **Fixed and tested locally** | Flat/wrapped schedules, malformed rows, completed tasks and no duplicate unread notices covered by the 11-test run; earlier screenshot log was pre-fix |
| Team-approved individual contribution | **Not supplied** | Request all-member confirmation; do not infer authorship from file ownership |
| Earlier 60/60 tests | Audit mentions, raw run unavailable | Do not use as current pass claim |
| User/stakeholder validation | Not confirmed | Request reviewer feedback and study records |

## Missing / Unconfirmed Information

- University-record verification of the owner-provided name/title wording; supervisor and co-supervisor details if required. The component owner has already supplied the name and title above.
- Exact original download/export records, collection dates and reuse terms for the Sourcetree CSV and Apache summary; exact local Desharnais acquisition route. The China subset has been content-matched to Zenodo v1, but a content match is not a download receipt or licence grant.
- A real end-to-end run from the separate student portal through document review and GitHub.com delivery; a synthetic local test-client workflow now passes, but it does not prove a real external delivery.
- Automatic Team Formation→scheduling backend group-ID mapping (the team-view HTTP trace is captured but sample IDs do not match); named Quality/Risk producer/consumer endpoints and payloads if direct exchange is claimed.
- A fresh screenshot/API trace of the **separate portal UI** upload and a GitHub administrator delivery receipt. The public task-009 commit and corresponding local push/linked-commit records are now cross-checked, but they predate the synthetic local test and do not demonstrate one fresh complete journey.
- Report-use approval and any needed redaction for the captured screenshots; faculty-approved/real-user evidence remains uncollected.
- Recovery of IDs for pre-fix unassigned versions lacking metadata is impossible from those task rows alone; an owner must confirm those rosters manually. Newly generated versions retain IDs automatically.
- Team-approved personal/shared contribution statement and approval date.
- Formal supervisor/student/staff evaluation, manual-plan baseline and real-cohort outcome measures.
- Institution-approved privacy, IP, retention and deployment statements.

## Files the Group Should Request From Me

- Current submission-candidate dissertation DOCX and matching 46-page Word-exported PDF; complete the [author/institutional checklist](IT22117014_Submission_Candidate_Checklist.md) before submission.
- [Screenshot and API-trace evidence bundle](handoff_evidence/2026-10-10/README.md), included in the [complete handoff ZIP](handoff_evidence/Scheduling_Complete_Component_Handoff_2026-10-10.zip), for initial/balanced Gantt, review queue, GitHub evidence, academic events, Team Formation view, standalone student task list and post-fix History roster (see §18); proposal-upload success is logged in the earlier local run but its upload-screen state was not separately pictured.
- `main.py`, `progress_tracking.py`, `academic_scheduler_service.py`, model training/evaluation scripts and saved result JSON.
- `test_data_pack/VALIDATION_REPORT.md`, fixture manifest, historical six-test record and [fresh 11-test evidence](Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md), with fixture and database scope stated.
- Fresh focused route/database result, synthetic local document/webhook workflow and Team Formation → team-view trace are recorded above; separately request automatic group-ID import evidence, Quality/Risk payloads if claimed, and real external-delivery evidence.
- Approved registration wording (if different from the owner-provided name/title), supervisor details, and team-approved contribution statement.
