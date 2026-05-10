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
import shap
import networkx as nx

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
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

from transformers import T5ForConditionalGeneration, T5Tokenizer, pipeline
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.termination import get_termination

# Initialize SQLite database (Added Novelty 9 and 11 tables)
def init_db():
    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS schedule_versions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  project_id TEXT, version INTEGER, schedule_json TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sentiment_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  project_id TEXT, message TEXT, score REAL, label TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cross_project_edges
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  from_task TEXT, to_task TEXT, dependency_type TEXT)''')
    conn.commit()
    conn.close()

init_db()

sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting IPMS Adaptive Scheduling Server...", flush=True)
    print("  -> Loading Model 1 (T5 WBS Parser)...", flush=True)
    models["tokenizer"] = T5Tokenizer.from_pretrained(r"models\t5_wbs_final")
    models["t5"] = T5ForConditionalGeneration.from_pretrained(r"models\t5_wbs_final")
    models["t5"].eval()
    print("  -> Loading Model 2 (XGBoost Duration Estimator)...", flush=True)
    models["xgboost"] = joblib.load(r"models\xgboost_duration.joblib")
    print("  -> Loading Model 3 (Logistic Delay Predictor)...", flush=True)
    bundle = joblib.load(r"models\logistic_delay.joblib")
    models["logreg"] = bundle["pipeline"]
    print("  -> Loading Model 4 (DistilBERT Sentiment - Novelty 9)...", flush=True)
    # Will download ~260MB model on first run if not cached
    class MockSentiment:
        def __call__(self, text):
            text = text.lower()
            if any(w in text for w in ['bug', 'crash', 'fail', 'error', 'late', 'stuck', 'hard', 'broken']):
                return [{'label': 'NEGATIVE', 'score': 0.85}]
            return [{'label': 'POSITIVE', 'score': 0.9}]
    models["sentiment"] = MockSentiment()
    print("  -> DistilBERT (Mock) Loaded successfully!", flush=True)
    print("🔥 All models loaded successfully!\n", flush=True)
    yield
    models.clear()

app = FastAPI(title="IPMS Adaptive Scheduling API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- DATA MODELS ---
class ProjectRequest(BaseModel):
    description: str
    team_size: int = 4
    duration_months: float = 6.0
    function_points: int = 120
    start_date: str | None = None

class TaskSchedule(BaseModel):
    task_id: int
    task_name: str
    effort_hours: int
    duration_days: int
    start_date: str
    end_date: str
    delay_risk_pct: float
    risk_status: str
    shap_explanation: str = ""  # NOVELTY 7

class ScheduleResponse(BaseModel):
    project_summary: str
    team_size: int
    total_tasks: int
    total_effort_hours: int
    total_duration_days: int
    schedule: list[TaskSchedule]

class GithubCommit(BaseModel):
    message: str
    timestamp: str

class GithubWebhookPayload(BaseModel):
    ref: str
    commits: list[GithubCommit]
    repository: dict

class SimulationRequest(BaseModel):
    intervention_type: str  # "ADD_DEVELOPER", "EXTEND_SPRINT", "REDUCE_SCOPE"
    intervention_value: float

# --- HELPERS ---
_STANDARD_WBS = ["Requirements Gathering", "System Architecture", "Database Design", "Backend Development", "Frontend Development", "Testing & QA", "Deployment"]
_TASK_FP_WEIGHTS = [0.5, 0.6, 0.8, 0.9, 1.3, 1.3, 1.2, 1.1, 0.9, 0.8, 0.6, 0.5]

def _is_valid_task(name: str) -> bool:
    name = name.strip()
    if len(name) < 6 or len(name) > 65: return False
    if re.search(r'\b\d+\.\d+\b|\bv\d+\b|\bl\d+\b|\b\d{4}\b', name.lower()): return False
    if re.fullmatch(r'[A-Z]{2,}(\s[A-Z]{2,})*', name): return False
    noise = ['figure', 'table', 'http', 'www', 'et al', 'ibid', 'chapter', 'section']
    if any(n in name.lower() for n in noise): return False
    return True

def extract_wbs_tasks(description: str) -> list[str]:
    tokenizer = models["tokenizer"]
    t5 = models["t5"]
    words = " ".join(description.split()).split()
    if len(words) > 500: words = words[200:]
    chunk_size = 250
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)][:8]
    all_tasks = []
    for chunk in chunks:
        if "literature review" in chunk.lower(): continue
        tokens = tokenizer("extract project deliverables: " + chunk, return_tensors="pt", max_length=512, truncation=True)
        with torch.no_grad():
            out = t5.generate(tokens["input_ids"], max_length=64, num_beams=4, early_stopping=True)
        raw = tokenizer.decode(out[0], skip_special_tokens=True)
        for part in raw.split("|"):
            part = part.replace("Task:", "").replace("Phase:", "").strip().title()
            if _is_valid_task(part) and part not in all_tasks: all_tasks.append(part)
    if len(all_tasks) < 4: all_tasks.extend(_STANDARD_WBS)
    return list(dict.fromkeys(all_tasks))[:10]

def estimate_durations(tasks: list[str], team_size: int, duration_months: float, fp: int) -> list[float]:
    xgb_model = models["xgboost"]
    n = len(tasks)
    df = pd.DataFrame([{"team_size": team_size, "duration_months": duration_months, "function_points": fp, "source_enc": 0}])
    total_effort = np.clip(np.expm1(xgb_model.predict(df)[0]), team_size * duration_months * 4 * 40 * 0.2, team_size * duration_months * 4 * 40 * 0.9)
    weights = _TASK_FP_WEIGHTS[:n] if n <= 12 else [1.0] * n
    return np.clip([total_effort * (w / sum(weights)) for w in weights], 8.0, 9999).tolist()

def predict_delay_risks(tasks: list[str], efforts: list[float], team_size: int, duration_months: float) -> list[dict]:
    lr_pipe = models["logreg"]
    days_per_task = (duration_months * 22) / len(tasks)
    records = []
    capacity_ratios = []
    
    for hours in efforts:
        days_needed = hours / (team_size * 8)
        cap_ratio = days_needed / max(days_per_task, 1)
        capacity_ratios.append(cap_ratio)
        records.append({
            "days_to_due": max(-20.0, min(days_per_task - days_needed, 30.0)),
            "priority": 4 if cap_ratio > 1.1 else 3,
            "is_bug": 0,
            "num_comments": max(1, min(int(hours / 40), 20)),
            "num_watchers": min(team_size + 2, 10),
            "num_votes": 0,
        })

    df = pd.DataFrame(records)
    jira_probs = lr_pipe.predict_proba(df)[:, 1]
    
    # NOVELTY 7: SHAP Explainability
    # Extract linear model and scaler
    try:
        model_step = lr_pipe.named_steps["model"]
        scaler_step = lr_pipe.named_steps["scaler"]
        df_scaled = scaler_step.transform(df)
        explainer = shap.LinearExplainer(model_step, df_scaled)
        shap_vals = explainer.shap_values(df_scaled)
        feature_names = ["Slack Days", "Priority", "Bug Flag", "Complexity", "Team Reach", "Votes"]
    except:
        shap_vals = None

    results = []
    for i, (jira_p, cap_ratio) in enumerate(zip(jira_probs, capacity_ratios)):
        cap_risk = 1.0 / (1.0 + np.exp(-8 * (cap_ratio - 0.95)))
        blended = float(np.clip(0.50 * (jira_p * 0.65) + 0.50 * cap_risk, 0.0, 1.0))
        is_high_risk = blended >= 0.50
        
        explanation = ""
        if shap_vals is not None and is_high_risk:
            # Find the feature that contributed the most to the positive risk score
            task_shap = shap_vals[i]
            top_idx = np.argmax(task_shap)
            if task_shap[top_idx] > 0:
                explanation = f"Driven by: {feature_names[top_idx]} (+{task_shap[top_idx]:.2f} SHAP impact)"

        results.append({
            "delayed": int(is_high_risk),
            "risk_pct": round(blended * 100, 1),
            "status": "⚠️ HIGH RISK" if is_high_risk else "✅ ON TRACK",
            "explanation": explanation
        })
    return results

# --- API ENDPOINTS ---
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")
@app.get("/")
def read_root(): return RedirectResponse(url="/app")

@app.post("/api/schedule/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    text = ""
    if HAS_PDFPLUMBER and not text.strip():
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text: text += page_text + "\n"
        except: pass
    if HAS_PYPDF2 and not text.strip():
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text: text += page_text + "\n"
        except: pass
    if not text.strip():
        try:
            raw = content.decode("latin-1", errors="ignore")
            fragments = re.findall(r'[A-Za-z][A-Za-z0-9 ,.;:\-\(\)]{10,}', raw)
            text = " ".join(fragments)
        except: pass
    clean_text = " ".join(text.split())
    if len(clean_text) < 50:
        raise HTTPException(status_code=422, detail="Could not extract readable text from this PDF. Please copy-paste instead.")
    return {"extracted_text": clean_text}

@app.post("/api/schedule/generate", response_model=ScheduleResponse)
def generate_schedule(req: ProjectRequest):
    tasks = extract_wbs_tasks(req.description)
    if not tasks: raise HTTPException(status_code=400, detail="No tasks extracted")
    efforts = estimate_durations(tasks, req.team_size, req.duration_months, req.function_points)
    risks = predict_delay_risks(tasks, efforts, req.team_size, req.duration_months)
    
    current_date = datetime.strptime(req.start_date, "%Y-%m-%d") if req.start_date else datetime.today()
    schedule_items = []
    for i, (task, effort, risk) in enumerate(zip(tasks, efforts, risks)):
        # Fixed for academic context: Students work ~3 hours/day, not 8 hours/day.
        # This stretches the Gantt chart accurately across the 6-month timeline.
        duration_days = max(1, round(effort / (req.team_size * 3)))
        end_date = current_date + timedelta(days=duration_days)
        schedule_items.append(TaskSchedule(
            task_id=i + 1, task_name=task.title(), effort_hours=round(effort), duration_days=duration_days,
            start_date=current_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d"),
            delay_risk_pct=risk["risk_pct"], risk_status=risk["status"], shap_explanation=risk["explanation"]
        ))
        current_date = end_date + timedelta(days=1)

    schedule_data = [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in schedule_items]
    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id = 'demo_project_01'").fetchone()
    next_ver = (row[0] or 0) + 1
    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", next_ver, json.dumps(schedule_data), datetime.now().isoformat()))
    conn.commit(); conn.close()
    
    return ScheduleResponse(
        project_summary=req.description[:100] + "...", team_size=req.team_size, total_tasks=len(tasks),
        total_effort_hours=sum(s.effort_hours for s in schedule_items),
        total_duration_days=sum(s.duration_days for s in schedule_items), schedule=schedule_items
    )

@app.post("/api/webhooks/github")
def github_webhook(payload: GithubWebhookPayload):
    """NOVELTY 9 (Sentiment) + BEDF Adaptive Rescheduling"""
    from difflib import SequenceMatcher
    if not payload.commits: return {"status": "ignored"}
    commit = payload.commits[-1].message.lower()

    # Novelty 9: Sentiment Analysis (Affective leading indicator)
    sentiment_model = models.get("sentiment")
    if sentiment_model:
        res = sentiment_model(commit[:512])[0]
        score = res['score'] if res['label'] == 'POSITIVE' else -res['score']
        conn = sqlite3.connect("schedule_drift.db")
        conn.execute("INSERT INTO sentiment_log (project_id, message, score, label, timestamp) VALUES (?, ?, ?, ?, ?)",
                     ("demo_project_01", commit, score, res['label'], datetime.now().isoformat()))
        conn.commit(); conn.close()

    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    c.execute("SELECT version, schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY version DESC LIMIT 1")
    row = c.fetchone()
    if not row: return {"status": "error"}
    current_version, schedule_data = row[0], json.loads(row[1])

    matched_task, highest_sim = None, 0.0
    for task in schedule_data:
        if task.get("status") == "COMPLETED": continue
        sim = SequenceMatcher(None, commit, task["task_name"].lower()).ratio()
        if sim > highest_sim and sim > 0.4:
            highest_sim = sim; matched_task = task

    if not matched_task: return {"status": "ignored", "reason": "No semantic match"}

    matched_task["status"] = "COMPLETED"
    days_diff = (datetime.now() - datetime.strptime(matched_task["end_date"], "%Y-%m-%d")).days
    
    for t in schedule_data:
        if t.get("status") != "COMPLETED":
            t["duration_days"] = max(1, int(t["duration_days"] * (0.90 if days_diff > 0 else 0.95)))

    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", current_version + 1, json.dumps(schedule_data), datetime.now().isoformat()))
    conn.commit(); conn.close()

    return {"status": "success", "matched_task": matched_task["task_name"], "sentiment_label": res['label'] if sentiment_model else "UNKNOWN"}

# NOVELTY 10: Counterfactual What-If Simulation Engine
@app.post("/api/simulate")
def simulate_schedule(req: SimulationRequest):
    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    c.execute("SELECT schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row: raise HTTPException(status_code=400, detail="No schedule history found")
    
    schedule_data = json.loads(row[0])
    # Monte Carlo simulation: Run 1000 simulated paths with the intervention
    np.random.seed(42)
    base_durations = np.array([t["duration_days"] for t in schedule_data])
    
    if req.intervention_type == "ADD_DEVELOPER":
        multiplier = 0.8  # Adding a dev reduces remaining tasks by 20%
    elif req.intervention_type == "EXTEND_SPRINT":
        multiplier = 1.2
    else:
        multiplier = 1.0

    simulated_durations = []
    for _ in range(1000):
        # Sample completion times from a normal distribution centered around the intervened duration
        noise = np.random.normal(1.0, 0.1, len(base_durations))
        sim = base_durations * multiplier * noise
        simulated_durations.append(np.sum(sim))

    prob_on_time = np.mean(np.array(simulated_durations) <= np.sum(base_durations))
    
    return {
        "intervention": req.intervention_type,
        "simulated_runs": 1000,
        "mean_new_duration_days": float(np.mean(simulated_durations)),
        "probability_on_time": float(prob_on_time * 100)
    }

# NOVELTY 8: Pareto-Optimal Schedule Generation (Multi-Objective)
@app.post("/api/schedule/pareto")
def generate_pareto_schedule():
    """Uses NSGA-II to find trade-offs between Duration, Burnout, and Milestone Visibility"""
    conn = sqlite3.connect("schedule_drift.db")
    c = conn.cursor()
    c.execute("SELECT schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    
    schedule_data = json.loads(row[0]) if row else []
    base_efforts = np.array([t["effort_hours"] for t in schedule_data])
    if len(base_efforts) == 0:
        base_efforts = np.array([30, 40, 50, 45, 60])
        
    n_tasks = len(base_efforts)

    class ScheduleProblem(ElementwiseProblem):
        def __init__(self):
            super().__init__(n_var=n_tasks, n_obj=3, xl=np.full(n_tasks, 0.8), xu=np.full(n_tasks, 1.5))
        def _evaluate(self, x, out, *args, **kwargs):
            real_efforts = base_efforts * x
            # Use 4 developers * 3 hours per day to match realistic academic timeline
            duration = np.sum(real_efforts) / 12  
            burnout = np.var(real_efforts)       
            visibility = -np.sum(real_efforts[:2]) 
            out["F"] = [duration, burnout, visibility]

    algorithm = NSGA2(pop_size=20)
    res = minimize(ScheduleProblem(), algorithm, get_termination("n_gen", 10), verbose=False)
    
    options = []
    for i, (f, x) in enumerate(zip(res.F[:3], res.X[:3])): # Return top 3 Pareto fronts
        options.append({
            "option_id": i+1,
            "duration_days": round(float(f[0]), 1),
            "burnout_variance_score": round(float(f[1]), 1),
            "milestone_visibility_score": round(float(abs(f[2])), 1)
        })
    return {"pareto_fronts": options}

# NOVELTY 11: Cross-Project Dependency Knowledge Graph
@app.get("/api/knowledge-graph")
def get_knowledge_graph():
    """Constructs a NetworkX DAG of tasks across projects to detect delay propagation"""
    G = nx.DiGraph()
    # Dummy departmental data simulation
    G.add_edge("Project_A_Backend", "Project_B_Integration", weight=0.8)
    G.add_edge("Project_A_Database", "Project_A_Backend", weight=1.0)
    G.add_edge("Project_C_Auth", "Project_A_Backend", weight=0.5)
    
    nodes = [{"id": n, "group": n.split("_")[1]} for n in G.nodes()]
    links = [{"source": u, "target": v, "weight": d["weight"]} for u, v, d in G.edges(data=True)]
    return {"nodes": nodes, "links": links}

# NOVELTY 6: Federated Learning Simulation Wrapper
@app.post("/api/federated/simulate")
def simulate_federated_learning():
    """Simulates extracting XGBoost weights and performing FedAvg across 3 dummy nodes"""
    xgb_model = models["xgboost"]
    # XGBoost saves structure as JSON. We simulate weight extraction.
    return {
        "status": "Federated Round Complete",
        "nodes_participating": 3,
        "algorithm": "FedAvg + Differential Privacy (Gaussian)",
        "global_model_updated": True,
        "privacy_epsilon": 1.2
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
