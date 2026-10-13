# Adaptive Scheduling Component — Complete Documentation
### IPMS (Integrated Project Management System)
### Component Owner: Adaptive Scheduling (component_scheduling)
### Server: FastAPI — Port 8000

---

## 1. What is This Component?

The **Adaptive Scheduling Component** is one of four components inside the
Integrated Project Management System (IPMS) built for SLIIT final year
research projects.

**The problem it solves:**
When a group of students start a research project, they need to:
- Break the project into tasks (Work Breakdown Structure)
- Estimate how long each task will take
- Figure out who in the team should do which task
- Predict which tasks are likely to be delayed

Doing all of this manually is time-consuming and often inaccurate.
This component automates the entire process using **5 Machine Learning models**.

**What a user does:**
1. Uploads their project proposal PDF
2. Clicks "Generate Schedule"
3. Gets a full Gantt chart with tasks, durations, and risk levels
4. Clicks "Auto-Balance Workload"
5. Gets an AI-driven task assignment board showing who should do what

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI (Python) |
| Server Port | 8000 |
| Database | SQLite (schedule_drift.db) |
| PDF Extraction | pdfplumber + PyPDF2 |
| ML Framework | scikit-learn, XGBoost, PyTorch (Transformers) |
| Multi-Objective Optimization | pymoo (NSGA-II) |
| Graph Analysis | NetworkX |
| SHAP Explanations | shap |
| Frontend | HTML + CSS + Vanilla JavaScript |

---

## 3. The 5 Machine Learning Models

### Model 1 — T5 WBS Parser (Zero-Shot NLP)
- **Type:** Transformer Language Model (T5-small, 60M parameters)
- **Purpose:** Reads the uploaded proposal text and extracts project task names
- **How:** Uses text summarization on 300-word chunks of the proposal
- **Used in:** Strategy 5 of the WBS extraction pipeline (last resort)
- **Key fact:** Zero-shot means it was NOT retrained on project data —
  it uses general language understanding to identify task-like phrases
- **File:** Downloaded from HuggingFace (t5-small)

---

### Model 2 — XGBoost Duration Estimator
- **Type:** Gradient Boosted Decision Tree (Regression)
- **Purpose:** Predicts the total effort hours for the entire project
- **Input features:** function_points, log(function_points), source_encoding
- **Output:** Total effort in hours (e.g., 856 hours for a 6-month, 4-person project)
- **How hours are split:** Using a weight array based on task position
  - Core Algorithm tasks get weight 1.35 (highest complexity)
  - Literature Review gets weight 0.45 (lower complexity)
- **File:** models/xgboost_duration.joblib

---

### Model 3 — Logistic Regression Delay Predictor
- **Type:** Logistic Regression Pipeline with Standard Scaler
- **Purpose:** Predicts the probability that each task will be delayed
- **Training data:** NASA software defect dataset (code complexity metrics)
- **Proxy mapping:** Since this is a project management tool, effort hours
  are mapped to NASA complexity metrics:
  - High effort = High cyclomatic complexity V(G), ev(G)
  - Capacity ratio = Branch count, LOC estimates
- **Output:** Blended risk score = 50% JIRA probability + 50% capacity sigmoid
- **Risk threshold:** Tasks with blended_risk >= 50% are flagged as HIGH RISK
- **File:** models/logistic_delay.joblib

---

### Model 4 — DistilBERT Sentiment Analyser
- **Type:** Transformer-based text classifier (Novelty 9)
- **Purpose:** Analyses the sentiment of GitHub commit messages
- **Labels:** POSITIVE (+0.9 score) or NEGATIVE (-0.85 score)
- **Used for:** Detecting when a developer is struggling (negative commits
  like "fix crash", "broken again", "stuck on bug") and using that as an
  early warning signal to adjust the schedule
- **Current state:** Running as a keyword-based mock model for stability
- **Trigger:** GitHub webhook POST to /api/webhooks/github

---

### Model 5 — Random Forest Workload Balancer (Core Contribution)
- **Type:** Random Forest Classifier (Novelty 12)
- **Accuracy:** 81.3% on test data
- **Training data:** 1,411 JIRA sprint records
- **Purpose:** Decides which team member should be assigned each task
- **7 Input Features:**

| Feature | What it means |
|---|---|
| task_effort_estimate | How many hours the task takes |
| task_category | 1=backend/api/db task, 0=other |
| task_complexity | 3=hard over 80h, 2=medium over 40h, 1=easy |
| member_completion_rate | Percentage of past tasks this member finished |
| member_current_workload | How many tasks this member already has |
| member_avg_effort | Average hours per task for this member |
| is_collaborative | 0 for individual, 1 for team tasks |

- **Output:** P_on_time — probability (0.0 to 1.0) that this member will
  complete the task on time
- **Fairness constraint:** Overload Guard — if chosen member has 40% more
  work than the least busy member, override to least busy member
- **File:** models/workload_rf.joblib

---

## 4. How the System Works — Step by Step

### Step 1: PDF Upload (POST /api/schedule/upload-pdf)

User uploads PDF
- Try pdfplumber (best quality, preserves layout)
- If fails, try PyPDF2 (standard extraction)
- If fails, try raw latin-1 byte decoding (last resort)
- If text less than 50 characters → Error: Unreadable PDF
- Return: clean extracted text

### Step 2: Schedule Generation (POST /api/schedule/generate)

**A. Auto-detect project duration**
- Scan Gantt section for "M1", "M2" ... "M10" markers
- If M10 found → duration = 10 months (overrides user input)

**B. Extract WBS tasks (5-strategy pipeline)**
- Strategy 1: Find "WORK BREAKDOWN STRUCTURE" table in PDF
- Strategy 2: Find task names in Gantt chart rows
- Strategy 3: Find "SO1:", "Specific Objective 1:" patterns (ALWAYS runs)
- Strategy 4: Find sentences starting with action verbs (develop, implement...)
- Strategy 5: T5 zero-shot summarization of proposal chunks
- Fallback: Use 10-task Research WBS Template if all strategies fail
- Filter each task through noise filter (removes: References, Budget, Appendix, Introduction)

**C. Extract team member IT numbers**
- Scan for "IT" + 8 digits pattern (e.g. IT22117014)
- If not found, use "Member 1", "Member 2" etc.

**D. Classify tasks**
- Collaborative: Literature Review, Integration Testing, Pilot Study, Report Writing, Viva
- Individual: All component-specific development tasks

**E. Estimate effort hours (XGBoost)**
- Predict total project effort
- Distribute using FP weights per task

**F. Predict delay risk (Logistic Regression)**
- Map effort to NASA complexity features
- Calculate blended risk score
- Tag: HIGH RISK (>=50%) or ON TRACK (<50%)

**G. Build Gantt schedule**
- Assign sequential start/end dates to each task
- Save to database as a new version

### Step 3: Workload Balancing (POST /api/progress/auto-assign)

**Phase 1 — Collaborative tasks:**
- Assign to "All Members"
- Split effort equally per member

**Phase 2 — Individual tasks:**
- Sort by effort DESCENDING (Longest Processing Time first)
- For each task:
  - For each member: Query DB for member history, Build 7-feature vector, Get P_on_time from Random Forest model
  - Pick member with highest P_on_time
  - Apply Overload Guard (40% threshold)
  - Assign task, update workload

**Phase 3 — Save to database (status = NOT_STARTED)**

---

## 5. All API Endpoints

| Method | Endpoint | What it does |
|---|---|---|
| POST | /api/schedule/upload-pdf | Extract text from uploaded PDF |
| POST | /api/schedule/generate | Generate full Gantt schedule |
| GET | /api/progress/individual | Get current task assignments |
| POST | /api/progress/auto-assign | AI workload balancing |
| POST | /api/progress/task-complete | Mark a task as done |
| DELETE | /api/progress/reset | Reset all assignments |
| POST | /api/progress/assign | Manually assign a task |
| POST | /api/webhooks/github | GitHub commit webhook |
| POST | /api/simulate | Monte Carlo what-if simulation |
| POST | /api/schedule/pareto | NSGA-II Pareto-optimal schedule |
| GET | /api/knowledge-graph | Cross-project dependency graph |
| GET | /api/notifications | Get system notifications |

---

## 6. Database Structure (SQLite — schedule_drift.db)

### Table: schedule_versions
Stores every version of the schedule

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Auto increment |
| project_id | TEXT | "demo_project_01" |
| version | INTEGER | 1, 2, 3 ... increments each generation |
| schedule_json | TEXT | Full schedule as JSON string |
| created_at | TEXT | Timestamp |

### Table: task_assignments
Stores who is assigned to which task

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Auto increment |
| project_id | TEXT | "demo_project_01" |
| task_id | INTEGER | Task number 1, 2, 3 ... |
| task_name | TEXT | "Core Algorithm & Model Development" |
| assigned_to | TEXT | "IT22114662" or "All Members" |
| effort_hours | REAL | 115.0 |
| status | TEXT | "NOT_STARTED" or "COMPLETED" |
| assigned_at | TEXT | Timestamp |

### Table: sentiment_log
Stores GitHub commit sentiment scores (Novelty 9)

### Table: notifications
System alerts for deadlines and risks

### Table: task_submissions
Document upload records per task

### Table: github_registrations
Registered GitHub repositories for auto-tracking

---

## 7. Novelty Features

### Novelty 7 — SHAP Explainability
Every delay prediction includes a human-readable explanation.
Example output: "Driven by: Resource Bottleneck (Risk: 67.3%)"
Uses the SHAP library to make the ML decision transparent to students.

### Novelty 8 — NSGA-II Pareto-Optimal Scheduling
Uses a genetic algorithm (NSGA-II) to find 3 optimal schedule options.
Balances 3 objectives simultaneously:
1. Minimize total project duration
2. Minimize team burnout (effort variance)
3. Maximize early milestone visibility
User can choose which trade-off suits their project best.

### Novelty 9 — GitHub Commit Sentiment Analysis + BEDF Rescheduling
When a developer pushes a commit, the message is analysed for sentiment.
Negative sentiment (crashes, bugs, failures) triggers automatic schedule
compression using the BEDF (Backward Earliest Due Date First) algorithm.

### Novelty 10 — Monte Carlo What-If Simulation
Runs 1000 simulated project completions with random variation.
User can ask: "What if we add another developer?"
System answers: "Probability of finishing on time: 78%"

### Novelty 11 — Cross-Project Knowledge Graph
Uses NetworkX to build a directed graph of task dependencies across projects.
Detects delay propagation: if Project A's backend is late, Project B's
integration that depends on it is also flagged automatically.

### Novelty 12 — ML Workload Balancing (Random Forest)
Core contribution. Replaces simple round-robin assignment.
Uses Random Forest trained on 1,411 JIRA records.
Accuracy: 81.3%.
Fairness constraint prevents overloading high performers.

---

## 8. Standard 10-Task Research WBS Template
Used when PDF extraction fails to find enough tasks:

```
1.  Literature Review & Background Research
2.  Dataset Collection & Preprocessing
3.  System Architecture & Design
4.  Core Algorithm & Model Development
5.  Backend API Development
6.  Frontend Dashboard Development
7.  Model Training & Validation
8.  System Integration & Testing
9.  Pilot Study & User Evaluation
10. Report Writing & Viva Preparation
```

---

## 9. How to Run This Component

### Start the server
```
cd "d:\New folder (91)\component_scheduling"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### Access
- App UI:   http://127.0.0.1:8000/app
- API Docs: http://127.0.0.1:8000/docs

### Or use the main launcher
Double-click: d:\New folder (91)\START_ALL.bat

---

## 10. File Structure

```
component_scheduling/
├── main.py                  - All backend logic (1525 lines)
├── schedule_drift.db        - SQLite database (auto-created)
├── models/
│   ├── xgboost_duration.joblib
│   ├── logistic_delay.joblib
│   └── workload_rf.joblib
└── frontend/
    ├── index.html           - Main UI page
    ├── script.js            - All UI interactions and API calls
    └── styles.css           - Styling
```

---

## 11. Sample Output

After generating a schedule from an IPMS proposal PDF:

```
Task 1:  Literature Review & Background Research
         Effort: 69h  | Duration: 18 days | Risk: ON TRACK (32%)
         Assigned to: All Members

Task 2:  Dataset Collection & Preprocessing
         Effort: 87h  | Duration: 23 days | Risk: ON TRACK (41%)
         Assigned to: All Members

Task 3:  System Architecture & Design
         Effort: 124h | Duration: 32 days | Risk: HIGH RISK (58%)
         Assigned to: All Members

Task 4:  Core Algorithm & Model Development
         Effort: 115h | Duration: 30 days | Risk: HIGH RISK (71%)
         Assigned to: IT22114662 | RF Confidence: 84%

Task 5:  Backend API Development
         Effort: 106h | Duration: 28 days | Risk: HIGH RISK (63%)
         Assigned to: IT22117014 | RF Confidence: 79%

Task 6:  Frontend Dashboard Development
         Effort: 96h  | Duration: 25 days | Risk: ON TRACK (44%)
         Assigned to: IT22109576 | RF Confidence: 76%

Task 7:  Model Training & Validation
         Effort: 83h  | Duration: 22 days | Risk: HIGH RISK (52%)
         Assigned to: IT22101624 | RF Confidence: 81%

Task 8:  System Integration & Testing
         Effort: 78h  | Duration: 20 days | Risk: ON TRACK (48%)
         Assigned to: All Members

Task 9:  Pilot Study & User Evaluation
         Effort: 60h  | Duration: 16 days | Risk: ON TRACK (39%)
         Assigned to: All Members

Task 10: Report Writing & Viva Preparation
         Effort: 46h  | Duration: 12 days | Risk: ON TRACK (28%)
         Assigned to: All Members
```

Workload Summary after Auto-Balance:
```
IT22114662 : 115h individual  (Core Algorithm)
IT22117014 : 106h individual  (Backend API)
IT22109576 : 96h individual   (Frontend)
IT22101624 : 83h individual   (Model Training)
All Members: 278h shared      (Literature, Architecture, Integration, Pilot, Report)
```

---

Document prepared for: IPMS Adaptive Scheduling Component
Research Project — SLIIT Faculty of Computing
