"""
IPMS Adaptive Scheduling Backend API
Built with FastAPI, exposing our 3 trained Machine Learning models.
"""
import os
import sys
import torch
import joblib
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import sqlite3
import json
import re

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import io
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False
from pydantic import BaseModel, Field
from transformers import T5ForConditionalGeneration, T5Tokenizer

# Initialize SQLite database for Schedule Drift Analytics (Novelty 5)
def init_db():
    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS schedule_versions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  project_id TEXT, 
                  version INTEGER, 
                  schedule_json TEXT, 
                  created_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ════════════════════════════════════════════════════════════════════════════
# 1. GLOBAL ML MODELS
# ════════════════════════════════════════════════════════════════════════════
models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting IPMS Adaptive Scheduling Server...")
    print("Loading Machine Learning Models into memory (this may take a few seconds)...")
    
    # 1. Load Model 1 (T5 WBS Parser)
    print("  -> Loading Model 1 (T5 WBS Parser)...", end=" ", flush=True)
    models["tokenizer"] = T5Tokenizer.from_pretrained(r"models\t5_wbs_final")
    models["t5"] = T5ForConditionalGeneration.from_pretrained(r"models\t5_wbs_final")
    models["t5"].eval()
    print("✅")

    # 2. Load Model 2 (XGBoost Duration Estimator)
    print("  -> Loading Model 2 (XGBoost Duration Estimator)...", end=" ", flush=True)
    models["xgboost"] = joblib.load(r"models\xgboost_duration.joblib")
    print("✅")

    # 3. Load Model 3 (Logistic Regression Delay Predictor)
    print("  -> Loading Model 3 (Logistic Delay Predictor)...", end=" ", flush=True)
    bundle = joblib.load(r"models\logistic_delay.joblib")
    models["logreg"] = bundle["pipeline"]
    models["logreg_thresh"] = bundle["threshold"]
    print("✅")
    
    print("🔥 All models loaded successfully! Server is ready to accept connections.\n")
    yield
    print("🛑 Shutting down server and releasing ML models...")
    models.clear()


# ════════════════════════════════════════════════════════════════════════════
# 2. FASTAPI APP INITIALIZATION
# ════════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="IPMS Adaptive Scheduling API",
    description="Machine Learning Backend for Project Planning & Risk Prediction",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all frontend origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════════════════════
# 3. DATA MODELS (Pydantic)
# ════════════════════════════════════════════════════════════════════════════
class ProjectRequest(BaseModel):
    description: str = Field(..., description="Raw text of the project proposal")
    team_size: int = Field(default=4, ge=1, le=20, description="Number of developers in the group")
    duration_months: float = Field(default=6.0, ge=1.0, le=24.0, description="Expected duration in months")
    function_points: int = Field(default=120, ge=10, le=1000, description="Estimated complexity (Function Points)")
    start_date: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")

class TaskSchedule(BaseModel):
    task_id: int
    task_name: str
    effort_hours: int
    duration_days: int
    start_date: str
    end_date: str
    delay_risk_pct: float
    risk_status: str

class ScheduleResponse(BaseModel):
    project_summary: str
    team_size: int
    total_tasks: int
    total_effort_hours: int
    total_duration_days: int
    schedule: list[TaskSchedule]

class ExternalRiskSignal(BaseModel):
    group_id: str
    issue_type: str = Field(..., description="e.g., 'GITHUB_INACTIVITY', 'JIRA_OVERDUE'")
    days_inactive: int
    severity: str

class GithubCommit(BaseModel):
    message: str
    timestamp: str

class GithubWebhookPayload(BaseModel):
    ref: str
    commits: list[GithubCommit]
    repository: dict

# ════════════════════════════════════════════════════════════════════════════
# 4. ML PIPELINE HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════

# Standard WBS phases used as smart fallback for academic IT projects
_STANDARD_WBS = [
    "Requirements Gathering", "Literature Review & Research",
    "System Architecture Design", "Database Design",
    "Backend Development", "Frontend Development",
    "API Integration", "Testing & Quality Assurance",
    "User Acceptance Testing", "Deployment & Configuration",
    "Documentation", "Project Evaluation"
]

# Task-type FP multipliers by position in project lifecycle
_TASK_FP_WEIGHTS = [0.5, 0.6, 0.8, 0.9, 1.3, 1.3, 1.2, 1.1, 0.9, 0.8, 0.6, 0.5]

def _is_valid_task(name: str) -> bool:
    """Returns True only if this looks like a real project deliverable."""
    name = name.strip()
    if len(name) < 6 or len(name) > 65:
        return False
    # Reject names with version numbers or decimal numbers (e.g. L6 V2, 0.85, 3.1)
    if re.search(r'\b\d+\.\d+\b|\bv\d+\b|\bl\d+\b|\b\d{4}\b', name.lower()):
        return False
    # Reject all-caps acronyms as standalone names
    if re.fullmatch(r'[A-Z]{2,}(\s[A-Z]{2,})*', name):
        return False
    # Reject known noise tokens
    noise = ['figure', 'table', 'http', 'www', 'et al', 'ibid', 'chapter', 'section',
             'reference', 'appendix', 'equation', 'sbert', 'bert', 'lstm', 'gpt',
             'cosine', 'auc', 'roc', 'miniilm', 'f1 score', 'precision']
    if any(n in name.lower() for n in noise):
        return False
    return True

def extract_wbs_tasks(description: str) -> list[str]:
    tokenizer = models["tokenizer"]
    t5 = models["t5"]

    description = " ".join(description.split())
    words = description.split()

    # Skip first 200 words (cover page)
    if len(words) > 500:
        words = words[200:]

    # Grab up to 8 chunks of 250 words from the whole document, evenly spaced
    chunk_size = 250
    chunks = []
    if len(words) > chunk_size * 8:
        step = (len(words) - chunk_size) // 7
        for i in range(0, len(words) - chunk_size + 1, step):
            chunks.append(" ".join(words[i:i+chunk_size]))
    else:
        for i in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[i:i+chunk_size]))

    all_tasks = []

    for chunk in chunks:
        # Skip chunks that are obviously literature review or references
        chunk_lower = chunk.lower()
        if "literature review" in chunk_lower or "references" in chunk_lower[:50]:
            continue

        prompt = "extract project deliverables and implementation phases: " + chunk
        tokens = tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
        with torch.no_grad():
            out = t5.generate(tokens["input_ids"], max_length=64, num_beams=4, early_stopping=True)
        raw = tokenizer.decode(out[0], skip_special_tokens=True)

        for part in raw.split("|"):
            part = part.strip()
            for prefix in ("Task:", "Phase:", "Deliverable:", "Method:", "Summary:", "Section:"):
                if part.lower().startswith(prefix.lower()):
                    part = part[len(prefix):].strip()
            part = part.title()
            if _is_valid_task(part) and part not in all_tasks:
                all_tasks.append(part)

    # Step 3: If we got too few good tasks, append standard WBS to fill the gaps
    if len(all_tasks) < 4:
        print("  [T5] Found few tasks, supplementing with standard WBS...")
        all_tasks.extend(_STANDARD_WBS)

    # Deduplicate and limit to 10 tasks for a clean Gantt chart
    return list(dict.fromkeys(all_tasks))[:10]


def estimate_durations(tasks: list[str], team_size: int, duration_months: float, fp: int) -> list[float]:
    """Estimates effort per task with variation based on task position in the lifecycle."""
    xgb_model = models["xgboost"]
    n = len(tasks)

    # Predict the TOTAL effort for the whole project using XGBoost
    df = pd.DataFrame([{
        "team_size": team_size,
        "duration_months": duration_months,
        "function_points": fp,
        "source_enc": 0
    }])
    log_pred = xgb_model.predict(df)[0]
    total_predicted_effort = np.expm1(log_pred)

    # Ensure the prediction is somewhat realistic based on total capacity
    total_capacity_hrs = team_size * duration_months * 4 * 40  # weeks × hrs/week
    total_effort = np.clip(total_predicted_effort, total_capacity_hrs * 0.2, total_capacity_hrs * 0.9)

    # Assign FP weights by position to create variation
    weights = _TASK_FP_WEIGHTS[:n] if n <= 12 else [1.0] * n
    total_weight = sum(weights)
    
    # Distribute total effort across tasks proportionally to weights
    efforts = [total_effort * (w / total_weight) for w in weights]

    return np.clip(efforts, 8.0, total_capacity_hrs * 0.4).tolist()


def predict_delay_risks(tasks: list[str], efforts: list[float], team_size: int, duration_months: float) -> list[dict]:
    """Blends JIRA logistic regression probability with capacity-based risk for realistic flags."""
    lr_pipe = models["logreg"]

    total_working_days = duration_months * 22  # ~22 working days per month
    days_per_task = total_working_days / len(tasks)

    records = []
    capacity_ratios = []

    for hours in efforts:
        # Working days needed for this task given the team
        days_needed = hours / (team_size * 8)
        # Positive = slack (on track), Negative = overloaded
        days_to_due = days_per_task - days_needed
        # Capacity ratio: > 1.0 means task needs more time than allocated
        cap_ratio = days_needed / max(days_per_task, 1)
        capacity_ratios.append(cap_ratio)

        num_comments = max(1, min(int(hours / 40), 20))
        num_watchers = min(team_size + 2, 10)
        priority = 4 if cap_ratio > 1.1 else 3

        records.append({
            "days_to_due": max(-20.0, min(days_to_due, 30.0)),
            "priority": priority,
            "is_bug": 0,
            "num_comments": num_comments,
            "num_watchers": num_watchers,
            "num_votes": 0,
        })

    df = pd.DataFrame(records)
    jira_probs = lr_pipe.predict_proba(df)[:, 1]

    results = []
    for i, (jira_p, cap_ratio) in enumerate(zip(jira_probs, capacity_ratios)):
        # Capacity-based risk: sigmoid of (cap_ratio - 0.95)
        # Shifts the curve so it only becomes risky when cap_ratio approaches 1.0
        cap_risk = 1.0 / (1.0 + np.exp(-8 * (cap_ratio - 0.95)))

        # JIRA model predictions can be pessimistic for academic projects; scale them
        jira_p_scaled = jira_p * 0.65 

        # Blend: 50% JIRA model + 50% capacity risk
        blended = 0.50 * jira_p_scaled + 0.50 * cap_risk
        blended = float(np.clip(blended, 0.0, 1.0))

        # Threshold of 0.50 for the blended score
        is_high_risk = blended >= 0.50
        risk_label = "⚠️ HIGH RISK" if is_high_risk else "✅ ON TRACK"

        results.append({
            "delayed": int(is_high_risk),
            "risk_pct": round(blended * 100, 1),
            "status": risk_label
        })
    return results


# ════════════════════════════════════════════════════════════════════════════
# 5. API ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════
# Serve the frontend UI files
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/")
def read_root():
    # Automatically redirect from http://localhost:8000 to http://localhost:8000/app
    return RedirectResponse(url="/app")

@app.post("/api/schedule/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    text = ""

    # ── Attempt 1: pdfplumber (best for academic / modern PDFs) ──────────
    if HAS_PDFPLUMBER and not text.strip():
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            print(f"  [PDF] pdfplumber extracted {len(text)} chars")
        except Exception as e1:
            print(f"  [PDF] pdfplumber failed: {e1}")
            text = ""

    # ── Attempt 2: PyPDF2 fallback ────────────────────────────────────────
    if HAS_PYPDF2 and not text.strip():
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            print(f"  [PDF] PyPDF2 extracted {len(text)} chars")
        except Exception as e2:
            print(f"  [PDF] PyPDF2 failed: {e2}")
            text = ""

    # ── Attempt 3: Raw latin-1 decode as last resort ──────────────────────
    if not text.strip():
        try:
            raw = content.decode("latin-1", errors="ignore")
            # Pull printable ASCII fragments only
            fragments = re.findall(r'[A-Za-z][A-Za-z0-9 ,.;:\-\(\)]{10,}', raw)
            text = " ".join(fragments)
            print(f"  [PDF] Raw decode fallback: {len(text)} chars")
        except Exception as e3:
            print(f"  [PDF] All extraction methods failed: {e3}")

    clean_text = " ".join(text.split())

    if len(clean_text) < 50:
        raise HTTPException(
            status_code=422,
            detail="Could not extract readable text from this PDF. "
                   "If it is a scanned image PDF, please copy-paste the text manually."
        )

    # NOVELTY FIX: Removing the 15,000 character limit so the entire thesis 
    # document is sent to the extraction pipeline!
    return {"extracted_text": clean_text}

@app.post("/api/schedule/generate", response_model=ScheduleResponse)
def generate_schedule(req: ProjectRequest):
    """
    Main Endpoint: Generates a full predictive Gantt schedule from a project description.
    Executes Models 1, 2, and 3 sequentially.
    """
    # 1. Parse WBS Tasks
    tasks = extract_wbs_tasks(req.description)
    if not tasks:
        raise HTTPException(status_code=400, detail="Could not extract tasks from description.")

    # 2. Estimate Effort
    efforts = estimate_durations(tasks, req.team_size, req.duration_months, req.function_points)
    
    # 3. Predict Delays
    risks = predict_delay_risks(tasks, efforts, req.team_size, req.duration_months)
    
    # 4. Build Timeline
    try:
        current_date = datetime.strptime(req.start_date, "%Y-%m-%d") if req.start_date else datetime.today()
    except ValueError:
        current_date = datetime.today()
        
    schedule_items = []
    for i, (task, effort, risk) in enumerate(zip(tasks, efforts, risks)):
        duration_days = max(1, round(effort / (req.team_size * 8)))
        end_date = current_date + timedelta(days=duration_days)
        
        schedule_items.append(TaskSchedule(
            task_id=i + 1,
            task_name=task.title(),
            effort_hours=round(effort),
            duration_days=duration_days,
            start_date=current_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            delay_risk_pct=risk["risk_pct"],
            risk_status=risk["status"]
        ))
        # Next task starts the day after current task ends (simplified finish-to-start)
        current_date = end_date + timedelta(days=1)

    # NOVELTY 5: Persistent Storage for Schedule Drift Analytics
    # Save this generated version to the database so we can compare it to future changes
    schedule_data = [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in schedule_items]
    try:
        conn = sqlite3.connect("schedule_drift.db")
        c = conn.cursor()
        c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
                  ("demo_project_01", 1, json.dumps(schedule_data), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print("  [Novelty 5] Saved schedule version to SQLite for Drift Analytics.")
    except Exception as e:
        print(f"  [Novelty 5] DB Save Error: {e}")

    return ScheduleResponse(
        project_summary=req.description[:100] + "...",
        team_size=req.team_size,
        total_tasks=len(tasks),
        total_effort_hours=sum(s.effort_hours for s in schedule_items),
        total_duration_days=sum(s.duration_days for s in schedule_items),
        schedule=schedule_items
    )

@app.post("/api/schedule/external-risk-signal")
def receive_risk_signal(signal: ExternalRiskSignal):
    """
    NOVELTY #4: Closed-Loop Cross-Module Integration.
    Receives live signals from the Risk Monitoring module (e.g., GitHub inactivity).
    """
    print(f"\n🚨 EXTERNAL RISK SIGNAL RECEIVED FOR GROUP: {signal.group_id}")
    print(f"   Issue: {signal.issue_type} | Inactive: {signal.days_inactive} days | Severity: {signal.severity}")
    
    # In a full system, this would trigger the "Proactive Rescheduling Loop"
    # and update the database. For now, we acknowledge receipt.
    return {
        "status": "Signal received and processed",
        "action_taken": "LSTM Proactive Rescheduling Triggered (Simulated)",
        "group_id": signal.group_id
    }

@app.post("/api/webhooks/github")
def github_webhook(payload: GithubWebhookPayload):
    """
    PHASE 1 & 2: GitHub Webhook + Semantic Task Matching
    Automatically maps incoming commits to WBS tasks and updates the schedule.
    """
    from difflib import SequenceMatcher
    
    if not payload.commits:
        return {"status": "ignored", "reason": "No commits found"}

    latest_commit = payload.commits[-1]
    commit_message = latest_commit.message.lower()

    # 1. Load the latest active schedule from the database
    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    c.execute("SELECT version, schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY version DESC LIMIT 1")
    row = c.fetchone()
    
    if not row:
        conn.close()
        return {"status": "error", "reason": "No active schedule found for project."}
    
    current_version, schedule_json_str = row
    schedule_data = json.loads(schedule_json_str)

    # 2. Semantic Task Matching (Lightweight SBERT simulation using SequenceMatcher)
    matched_task = None
    highest_sim = 0.0
    
    for task in schedule_data:
        # Ignore already completed tasks
        if task.get("status") == "COMPLETED":
            continue
            
        # Calculate similarity between commit message and task name
        sim = SequenceMatcher(None, commit_message, task["task_name"].lower()).ratio()
        
        # Check for keyword overlap (simulating NLP token matching)
        commit_words = set(re.findall(r'\w+', commit_message))
        task_words = set(re.findall(r'\w+', task["task_name"].lower()))
        overlap = len(commit_words.intersection(task_words))
        
        if overlap > 0:
            sim += 0.3 * overlap  # Boost similarity if keywords match (e.g. 'database', 'frontend')
            
        if sim > highest_sim and sim > 0.4:  # Threshold for a match
            highest_sim = sim
            matched_task = task

    if not matched_task:
        conn.close()
        return {"status": "ignored", "reason": "Commit did not semantically match any pending task"}

    # 3. Task Completed! Execute Adaptive "Auto-Rescheduling" Loop
    print(f"\n✅ [AUTO-TRACK] Commit '{commit_message}' mapped to task -> {matched_task['task_name']} (Sim: {highest_sim:.2f})")
    matched_task["status"] = "COMPLETED"
    matched_task["actual_completion_date"] = datetime.now().isoformat()
    
    # Calculate Velocity: Did they finish early or late?
    planned_end = datetime.strptime(matched_task["end_date"], "%Y-%m-%d")
    days_diff = (datetime.now() - planned_end).days
    
    if days_diff > 0:
        print(f"  ⚠️ Task completed {days_diff} days LATE. Triggering Parkinson's Tightening Factor on remaining tasks...")
        # Reduce remaining durations by 10% (Tightening Factor Novelty)
        for t in schedule_data:
            if t.get("status") != "COMPLETED":
                t["duration_days"] = max(1, int(t["duration_days"] * 0.90))
    elif days_diff < 0:
        print(f"  ⚡ Task completed {-days_diff} days EARLY. Pulling schedule forward (BEDF)...")
        # Pull forward BEDF novelty
        for t in schedule_data:
            if t.get("status") != "COMPLETED":
                t["duration_days"] = max(1, int(t["duration_days"] * 0.95))

    # 4. Save to Database (Schedule Drift Analytics - Novelty 5)
    new_version = current_version + 1
    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", new_version, json.dumps(schedule_data), datetime.now().isoformat()))
    conn.commit()
    conn.close()

    print(f"  💾 Saved Drift Analytics Version {new_version} to Database.")
    
    return {
        "status": "success",
        "matched_task": matched_task["task_name"],
        "adaptive_action": "Tightened remaining deadlines" if days_diff > 0 else "Pulled schedule forward",
        "new_schedule_version": new_version
    }

if __name__ == "__main__":
    import uvicorn
    # Run the server locally on port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
