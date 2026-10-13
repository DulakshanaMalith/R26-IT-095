# IPMS — Full Integration Plan (Updated)
## All 4 Components · Role-Based Access · Step-by-Step

---

## 1. System Overview

The IPMS is built for **academic staff and supervisors only**. Students do NOT use this system directly.

### The 4 Components

| # | Component | Developer | Port | Technology |
|---|-----------|-----------|------|------------|
| 1 | **Adaptive Scheduling** (your component) | You | `8000` | FastAPI + SQLite |
| 2 | **Quality Assessment** (ResearchPilot) | Member 2 | `9000` | FastAPI + SQLite + ML |
| 3 | **Predictive Risk Monitoring** | Member 3 | `5000` | FastAPI |
| 4 | **Intelligent Team Formation** | Member 4 | `8003` | FastAPI + PostgreSQL |

---

## 2. User Roles

| Role | Who They Are |
|------|-------------|
| **Admin / Management Staff** | Department admin, HOD, project coordinators |
| **Supervisor** | Academic supervisors assigned to FYP groups |

---

## 3. Role-Based Access Map

| Feature | Staff | Supervisor |
|---------|:-----:|:----------:|
| **COMPONENT 1 — Scheduling** | | |
| Upload Proposal PDF | ❌ | ✅ |
| Auto-Schedule WBS from proposal (T5) | ❌ | ✅ |
| XGBoost effort estimation | ❌ | ✅ |
| NSGA-II Pareto schedule (3 options A/B/C) | ❌ | ✅ |
| Workload balancing (Random Forest) | ❌ | ✅ |
| Task assignment to IT numbers | ❌ | ✅ |
| View Gantt chart for their group | ❌ | ✅ |
| View risk warnings per task | ❌ | ✅ |
| **PP1 / PP2 / Viva Academic Scheduler** | | |
| Upload Supervisors Excel | ✅ | ❌ |
| Upload Halls / Rooms Excel | ✅ | ❌ |
| Auto-generate PP1, PP2, Viva schedule | ✅ | ❌ |
| Sentence-BERT supervisor matching | ✅ | ❌ |
| Export academic schedule to Excel | ✅ | ❌ |
| Edit scheduled events | ✅ | ❌ |
| **COMPONENT 2 — Quality Assessment** | | |
| View proposal readiness score | ❌ | ✅ |
| View missing sections list | ❌ | ✅ |
| View weakness / strength prediction | ❌ | ✅ |
| Edit AI review draft | ❌ | ✅ |
| Download final feedback PDF | ❌ | ✅ |
| **COMPONENT 3 — Risk Monitoring** | | |
| View Contribution Index (CI) per member | ❌ | ✅ |
| View GitHub commit activity | ❌ | ✅ |
| View Jira task completion / overdue | ❌ | ✅ |
| View risk level (LOW / MEDIUM / HIGH) | ❌ | ✅ |
| **COMPONENT 4 — Team Formation** | | |
| Upload cohort Excel workbook | ✅ | ❌ |
| Run NSGA-II team formation | ✅ | ❌ |
| Assign supervisors to groups | ✅ | ❌ |
| Save final allocation (ACTIVE) | ✅ | ❌ |
| Download editable allocation Excel | ✅ | ❌ |
| Manually revise team allocation | ✅ | ❌ |
| Validate and confirm revised allocation | ✅ | ❌ |
| Export team allocation PDF / Excel | ✅ | ❌ |

---

## 4. Data Flow — How the 4 Components Connect

```
╔══════════════════════════════════════════════════════════════════════╗
║                         STAFF WORKFLOW                               ║
╚══════════════════════════════════════════════════════════════════════╝

[Staff] uploads cohort Excel workbook
         │
         ▼
[Component 4 — Team Formation :8003]
  Validates the workbook
  Runs Heuristic-Seeded NSGA-II V3 → forms groups
  Assigns supervisors to teams
  Staff selects one Pareto solution
  Saves ACTIVE allocation (revision_number=1, source=OPTIMIZER)
  to PostgreSQL
         │
         │  If staff wants to change teams later:
         │  Download editable.xlsx → edit → validate → confirm
         │  → old allocation ARCHIVED, new MANUAL_REVISION ACTIVE
         │
         │  REST API used by other components:
         │  GET /api/final-allocations/active/teams
         ▼
[Component 1 — Academic Scheduler :8000]
  Staff uploads Supervisors Excel + Halls Excel
  Sentence-BERT matches supervisors to project topics
  Assembles panel: 2 Prof/Dr + 1 Lecturer + 1 Instructor
  Checks hall availability, avoids overlaps
  Auto-schedules PP1, PP2, Viva events
  Exports academic schedule to Excel


╔══════════════════════════════════════════════════════════════════════╗
║                      SUPERVISOR WORKFLOW                             ║
╚══════════════════════════════════════════════════════════════════════╝

[Supervisor] logs in → enters their Supervisor ID (e.g. SUP-001)
         │
         ▼
[Supervisor] uploads proposal PDF
         │
         ▼
[Component 1 — Scheduling :8000]
  Extracts text from PDF (pdfplumber)
  Validates: is this a project proposal?
  T5 → extracts WBS tasks
  XGBoost → estimates effort hours per task
  Logistic Regression + SHAP → predicts delay risk
  NSGA-II → generates 3 Pareto schedule options (A/B/C)
  Random Forest → balances workload across IT numbers
  Shows Gantt chart for the group
         │
         ├──────────────────────────────────────────────────────┐
         │                                                      │
         ▼                                                      ▼
[Component 2 — Quality :9000]          [Component 3 — Risk :5000]
  Auto-called after PDF upload           Supervisor views team GitHub activity
  Returns: readiness score %             Returns: Contribution Index per member
  Returns: missing sections              Returns: inactive days, task completion
  Returns: weakness/strength tag         Returns: risk level LOW/MEDIUM/HIGH
  Supervisor edits AI review draft
  Downloads final feedback PDF
```

---

## 5. What Changed in the Updated Team Formation Document

The updated document has these **new things** compared to the old version:

### New Primary Endpoint for Staff

**OLD endpoint (supervisor-specific only):**
```http
GET /api/final-allocations/active/supervisors/{supervisor_id}/groups
```

**NEW primary endpoint (all teams at once — use this for Staff):**
```http
GET /api/final-allocations/active/teams
```

This returns ALL teams, ALL members, ALL supervisors in one call.
Staff uses this to load the full picture. Supervisors still use the supervisor-specific endpoint.

### New Response Fields

Every response now also includes:

| Field | Example | Meaning |
|-------|---------|---------|
| `revision_number` | `2` | Which revision this is (starts at 1) |
| `allocation_source` | `OPTIMIZER` or `MANUAL_REVISION` | Whether NSGA-II made it or staff edited it |
| `parent_allocation_id` | `TF-001` | Which allocation this was revised from |

### Staff Manual Revision Workflow (New)

Staff can now edit a saved allocation using a controlled process:

```
Save Final Allocation (NSGA-II result)
        │ revision_number=1, source=OPTIMIZER, status=ACTIVE
        ▼
Staff downloads editable Excel:
  GET /api/final-allocations/{id}/editable.xlsx
        │
        ▼
Staff edits ONLY these fields:
  TeamAssignments → TeamNumber, ProjectID
  SupervisorAssignments → SupervisorID
  (StudentID must NOT be changed)
        │
        ▼
Staff validates revised workbook:
  POST /api/final-allocations/revisions/validate
        │
        ▼
Staff confirms revised workbook:
  POST /api/final-allocations/revisions/confirm
        │
        ├── old allocation → ARCHIVED
        └── new revision → ACTIVE (revision_number=2, source=MANUAL_REVISION)
```

After this, all components calling `/active/teams` or `/active/supervisors/{id}/groups`
automatically get the NEW revised data. No changes needed in other components.

### Important: group_key Changes Across Revisions

```
BEFORE revision:  group_key = TF-20260825-120000-ABC123-T002
AFTER revision:   group_key = TF-20260826-143000-XYZ789-T002
```

Do NOT store or hardcode `group_key` as a permanent identifier.
Always re-fetch from `/active/...` endpoints to get the latest.

---

## 6. Integration Steps

---

### STEP 1 — Get All 4 Components on One Machine

Pull all branches from GitHub onto one machine:

```bash
git fetch --all

# Member 2's branch
git checkout Automated-Quality-Assessment-and-Adaptive-Mentorship

# Member 3's branch
git checkout Predictive-Risk-Monitoring-and-Contribution-Analytics

# Member 4's branch
git checkout Intelligent-Team-Formation-and-Topic-Feasibility-Analysis

# Back to your branch
git checkout Generative-Project-Planning-and-Adaptive-Scheduling
```

**Folder structure:**

```
D:\New folder (91)\
├── component_scheduling\         ← YOUR code (Port 8000)
│    ├── main.py
│    └── frontend\
│
├── component_quality\            ← Member 2 (Port 9000)
│    └── backend\src\api\main.py
│
├── component_risk\               ← Member 3 (Port 5000)
│    └── ipms-risk-app\main.py
│
└── component_team\               ← Member 4 (Port 8003)
     └── backend-fastapi\main.py
```

---

### STEP 2 — Fix CORS in All 4 Components

Ask each member to add this to their `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://127.0.0.1:9000",
        "http://127.0.0.1:5000",
        "http://127.0.0.1:8003",
        "http://localhost:8000",
        "http://localhost:9000",
        "http://localhost:5000",
        "http://localhost:8003",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### STEP 3 — Add Role-Based Access to Your Dashboard

**In `index.html`:**

```html
<!-- Role selector — shown on first visit -->
<div id="role-selector" class="role-modal">
    <h2>Welcome to IPMS</h2>
    <p>Select your role to continue:</p>
    <button onclick="setRole('staff')">🏢 Admin / Staff</button>
    <button onclick="setRole('supervisor')">👤 Supervisor</button>
</div>

<!-- Staff-only sections -->
<div class="staff-only" style="display:none">
    <section id="academic-scheduler-section">
        <!-- PP1 / PP2 / Viva scheduling -->
    </section>
    <section id="team-formation-section">
        <!-- Load all teams from Component 4 -->
    </section>
</div>

<!-- Supervisor-only sections -->
<div class="supervisor-only" style="display:none">
    <section id="pdf-upload-section">
        <!-- Upload PDF -->
    </section>
    <section id="schedule-section">
        <!-- WBS, XGBoost, NSGA-II, Workload -->
    </section>
    <section id="gantt-section">
        <!-- Gantt Chart -->
    </section>
    <section id="quality-section">
        <!-- Component 2 Quality results -->
    </section>
    <section id="risk-section">
        <!-- Component 3 Risk data -->
    </section>
</div>
```

**In `script.js`:**

```javascript
function setRole(role) {
    localStorage.setItem("ipms_role", role);
    applyRole(role);
    document.getElementById("role-selector").style.display = "none";
}

function applyRole(role) {
    const staffEls = document.querySelectorAll(".staff-only");
    const supEls   = document.querySelectorAll(".supervisor-only");

    if (role === "staff") {
        staffEls.forEach(el => el.style.display = "block");
        supEls.forEach(el => el.style.display = "none");
    } else {
        staffEls.forEach(el => el.style.display = "none");
        supEls.forEach(el => el.style.display = "block");
    }
}

window.onload = function() {
    const role = localStorage.getItem("ipms_role");
    if (role) applyRole(role);
    else document.getElementById("role-selector").style.display = "flex";
};
```

---

### STEP 4 — Connect Component 4 (Team Formation) → Component 1 (Scheduling)

Two endpoints — one for Staff, one for Supervisor.

**Add to `main.py`:**

```python
import requests as http_requests

TEAM_FORMATION_API = "http://127.0.0.1:8003"


# ── STAFF: Load ALL official groups ────────────────────────────────────────────
@app.get("/api/integration/all-teams")
async def get_all_teams():
    """
    Staff: Load all official teams from Team Formation.
    Calls GET /api/final-allocations/active/teams
    Returns teams[], each with: group_key, project, members, supervisor
    Automatically returns the latest revision (OPTIMIZER or MANUAL_REVISION)
    """
    try:
        r = http_requests.get(
            f"{TEAM_FORMATION_API}/api/final-allocations/active/teams",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "source": "team_formation",
                "allocation_id": data.get("allocation_id"),
                "revision_number": data.get("revision_number", 1),
                "allocation_source": data.get("allocation_source", "OPTIMIZER"),
                "teams": data.get("teams", [])
            }
        if r.status_code == 404:
            return {"source": "none",
                    "error": "No active allocation yet. Please complete team formation first."}
    except Exception as e:
        pass
    return {"source": "unavailable",
            "error": "Team Formation service is not running."}


# ── SUPERVISOR: Load groups for ONE supervisor ──────────────────────────────────
@app.get("/api/integration/supervisor-groups/{supervisor_id}")
async def get_supervisor_groups(supervisor_id: str):
    """
    Supervisor: Load their official groups from Team Formation.
    Calls GET /api/final-allocations/active/supervisors/{id}/groups
    """
    try:
        r = http_requests.get(
            f"{TEAM_FORMATION_API}/api/final-allocations/active"
            f"/supervisors/{supervisor_id}/groups",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "source": "team_formation",
                "revision_number": data.get("revision_number", 1),
                "allocation_source": data.get("allocation_source", "OPTIMIZER"),
                "supervisor": data.get("supervisor", {}),
                "groups": data.get("groups", [])
            }
        if r.status_code == 404:
            return {"source": "none",
                    "error": "No active allocation yet."}
    except Exception as e:
        pass
    return {"source": "unavailable",
            "error": "Team Formation service is not running."}
```

---

### STEP 5 — Connect Component 2 (Quality Assessment) → PDF Upload

**Add to `main.py`:**

```python
QUALITY_API = "http://127.0.0.1:9000"

def _check_quality_assessment(text: str) -> dict:
    """
    Supervisor: Auto-called after PDF upload.
    Sends proposal text to Quality Assessment component (port 9000).
    """
    try:
        r = http_requests.post(
            f"{QUALITY_API}/analyze",
            json={"text": text[:12000], "metadata": {}},  # 12000 char limit
            timeout=30
        )
        if r.status_code == 200:
            d = r.json()
            return {
                "available": True,
                "predicted_tag": d.get("predicted_tag", "Unknown"),
                "missing_sections": d.get("document_validation", {})
                                     .get("missing_sections", []),
                "readiness_score": d.get("semantic_grade", {})
                                    .get("percentage_score", 0),
                "readiness_label": d.get("semantic_grade", {})
                                    .get("readiness_label", ""),
                "retrieved_feedback": d.get("retrieved_feedback", [])[:2]
            }
    except Exception as e:
        print(f"  -> Quality API not available: {e}", flush=True)
    return {"available": False}
```

**In `upload_pdf` endpoint, change the return statement:**

```python
# Replace existing return with:

    # Auto-call Quality Assessment for supervisor
    print("  -> Calling Quality Assessment (port 9000)...", flush=True)
    quality = _check_quality_assessment(clean_text)

    return {
        "extracted_text"   : clean_text,
        "it_numbers"       : it_numbers,
        "validation_score" : validation["score"],
        "matched_sections" : validation["matched_groups"],
        "quality"          : quality,          # NEW
    }
```

---

### STEP 6 — Connect Component 3 (Risk Monitoring) → Progress Page

**Add to `main.py`:**

```python
RISK_API = "http://127.0.0.1:5000"

@app.get("/api/integration/risk/{group_id}")
async def get_group_risk(group_id: str):
    """
    Supervisor: Get risk data from Risk Monitoring component (port 5000).
    Shows CI score, GitHub activity, and risk level per group.
    """
    try:
        r = http_requests.get(
            f"{RISK_API}/api/risk/{group_id}",
            timeout=10
        )
        if r.status_code == 200:
            return {"available": True, "data": r.json()}
    except Exception as e:
        pass
    return {"available": False,
            "message": "Risk Monitoring service not available."}
```

---

### STEP 7 — Update START_ALL.bat for All 4 Components

```bat
@echo off
title IPMS — Full System (4 Components)
color 0A

echo  =========================================
echo   IPMS — Starting All 4 Components
echo  =========================================

echo  [1/4] Scheduling :8000 ...
start "IPMS-Scheduling" cmd /k "cd /d "d:\New folder (91)\component_scheduling" && python -m uvicorn main:app --host 0.0.0.0 --port 8000"
echo  Waiting 70s for ML models to load...
timeout /t 70 /nobreak >nul

echo  [2/4] Quality Assessment :9000 ...
start "IPMS-Quality" cmd /k "cd /d "d:\New folder (91)\component_quality\backend" && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 9000"
timeout /t 15 /nobreak >nul

echo  [3/4] Risk Monitoring :5000 ...
start "IPMS-Risk" cmd /k "cd /d "d:\New folder (91)\component_risk\ipms-risk-app" && python -m uvicorn main:app --host 0.0.0.0 --port 5000"
timeout /t 10 /nobreak >nul

echo  [4/4] Team Formation :8003 ...
start "IPMS-TeamFormation" cmd /k "cd /d "d:\New folder (91)\component_team\intelligent-team-formation-and-topic-feasiblity-analyzis\backend-fastapi" && python -m uvicorn main:app --host 0.0.0.0 --port 8003"
timeout /t 10 /nobreak >nul

echo  Opening dashboard...
start "" "http://127.0.0.1:8000/app"

echo  =========================================
echo   ALL 4 SERVICES RUNNING!
echo   Scheduling  :  http://127.0.0.1:8000/app
echo   Quality     :  http://127.0.0.1:9000/docs
echo   Risk        :  http://127.0.0.1:5000
echo   Teams       :  http://127.0.0.1:8003/docs
echo  =========================================
pause
```

---

## 7. What to Ask Each Member

### Member 2 — Quality Assessment (Port 9000)

- [ ] Exact command to start their server
- [ ] Confirm `/analyze` accepts `{ "text": "...", "metadata": {} }`
- [ ] Add CORS for port `8000` (Step 2 above)
- [ ] Push latest code to GitHub

### Member 3 — Risk Monitoring (Port 5000)

- [ ] Exact command to start their server
- [ ] Share the exact API endpoint URL for fetching risk by group
- [ ] Share the exact JSON fields in their response
- [ ] Add CORS for port `8000` (Step 2 above)
- [ ] Push latest code to GitHub

### Member 4 — Team Formation (Port 8003)

- [ ] How to set up PostgreSQL on a new machine (what DB name, user, password)
- [ ] Confirm both these endpoints work:
  - `GET /api/final-allocations/active/teams`
  - `GET /api/final-allocations/active/supervisors/{id}/groups`
- [ ] Add CORS for port `8000` (Step 2 above)
- [ ] Push latest code to GitHub

---

## 8. Who Does What

| Task | Who |
|------|-----|
| Role selector (Staff/Supervisor) in dashboard | **You** |
| Staff section: PP1/PP2/Viva, Team Formation load | **You** |
| Supervisor section: PDF, WBS, Gantt, Quality, Risk | **You** |
| `/api/integration/all-teams` endpoint | **You** |
| `/api/integration/supervisor-groups/{id}` endpoint | **You** |
| Modify `upload_pdf` to call Quality API | **You** |
| `/api/integration/risk/{id}` endpoint | **You** |
| Update `START_ALL.bat` for all 4 | **You** |
| Add CORS for port 8000 | **Members 2, 3, 4** |
| Push latest code to GitHub | **All members** |

---

## 9. Team Formation API Quick Reference (Updated)

| Use Case | Endpoint |
|----------|---------|
| Staff — load ALL teams | `GET /api/final-allocations/active/teams` |
| Supervisor — load their groups | `GET /api/final-allocations/active/supervisors/{id}/groups` |
| Staff — download editable Excel | `GET /api/final-allocations/{id}/editable.xlsx` |
| Staff — validate revised workbook | `POST /api/final-allocations/revisions/validate` |
| Staff — confirm revised workbook | `POST /api/final-allocations/revisions/confirm` |
| Export Excel report | `GET /api/final-allocations/{id}/export.xlsx` |
| Export PDF report | `GET /api/final-allocations/{id}/export.pdf` |

### Important Rules for Team Formation

> ✅ **DO** use `GET /active/teams` for staff — always gets the latest revision automatically

> ✅ **DO** use `GET /active/supervisors/{id}/groups` for supervisors

> ❌ **DO NOT** hardcode any `group_key` — it changes every time staff creates a new revision

> ❌ **DO NOT** connect directly to Team Formation's PostgreSQL database

> ✅ **DO** handle HTTP 404 gracefully: show "No official allocation available yet"

> ✅ **DO** handle network failures gracefully: show "Team Formation service not available"

---

## 10. Recommended Integration Order

```
Day 1:
  ✅ Step 1 — Pull all 4 branches to one machine
  ✅ Step 2 — Fix CORS in all components (ask other members)
  ✅ Step 7 — Update START_ALL.bat and test all 4 start together

Day 2:
  ✅ Step 3 — Add role selector to dashboard (Staff / Supervisor)
  ✅ Step 4 — Connect Team Formation → Scheduling
              (both staff /active/teams + supervisor /active/supervisors/{id}/groups)

Day 3:
  ✅ Step 5 — Connect Quality Assessment → PDF Upload (Supervisor workflow)
  ✅ Step 6 — Connect Risk Monitor → Progress Page (Supervisor workflow)

Day 4:
  ✅ Full end-to-end test of both workflows
  ✅ Demo preparation
```

---

*Last updated: 2026-08-26 | Based on updated Team Formation integration document with revision workflow support*
