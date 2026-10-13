import os
import shap

import sys

import joblib

import warnings

import numpy as np

import pandas as pd

from datetime import datetime, timedelta

from contextlib import asynccontextmanager

import postgres_db
from postgres_db import connect as get_db_connection

import json

import re

import shap

import networkx as nx

from apscheduler.schedulers.background import BackgroundScheduler



from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request, Depends, Query

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from fastapi.responses import RedirectResponse

from pydantic import BaseModel, Field

import io

from auth import AuthenticatedUser, authenticate, issue_token, require_roles, current_user
from progress_tracking import router as progress_tracking_router
from academic_scheduler_service import (
    academic_role_key as _academic_role_key,
    academic_role_label as _academic_role_label,
    minutes as _minutes,
    clock as _clock,
    interval_free as _interval_free,
    select_academic_panel,
)



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



from pymoo.algorithms.moo.nsga2 import NSGA2

from pymoo.core.problem import ElementwiseProblem

from pymoo.optimize import minimize

from pymoo.termination import get_termination



# Initialize SQLite database (Added Novelty 9 and 11 tables)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = postgres_db.database_url()
MODEL_DIR = os.path.join(BASE_DIR, "models")


def _model_path(filename: str) -> str:
    """Return an absolute model path so imports do not depend on the CWD."""
    return os.path.join(MODEL_DIR, filename)

def init_db():

    conn = get_db_connection()

    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS schedule_versions

                 (id BIGSERIAL PRIMARY KEY,

                  project_id TEXT, version INTEGER, schedule_json TEXT, created_at TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS sentiment_log

                 (id BIGSERIAL PRIMARY KEY,

                  project_id TEXT, message TEXT, score REAL, label TEXT, timestamp TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS cross_project_edges

                 (id BIGSERIAL PRIMARY KEY,

                  from_task TEXT, to_task TEXT, dependency_type TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS task_submissions

                 (id BIGSERIAL PRIMARY KEY,

                  project_id TEXT, task_id INTEGER, filename TEXT,

                  submitted_at TEXT, status TEXT DEFAULT "SUBMITTED")''')

    c.execute('''CREATE TABLE IF NOT EXISTS notifications

                 (id BIGSERIAL PRIMARY KEY,

                  project_id TEXT, task_id INTEGER, task_name TEXT,

                  type TEXT, message TEXT, created_at TEXT, is_read INTEGER DEFAULT 0)''')

    c.execute('''CREATE TABLE IF NOT EXISTS github_registrations

                 (id BIGSERIAL PRIMARY KEY,

                  project_id TEXT, repo_url TEXT, registered_at TEXT)''')

    # NOVELTY 12: Individual WBS Progress Tracking

    c.execute('''CREATE TABLE IF NOT EXISTS task_assignments

                 (id BIGSERIAL PRIMARY KEY,

                  project_id TEXT,

                  task_id INTEGER,

                  task_name TEXT,

                  assigned_to TEXT,

                  effort_hours REAL,

                  status TEXT DEFAULT "NOT_STARTED",

                  assigned_at TEXT,

                  UNIQUE(project_id, task_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS task_assignment_history
                 (id BIGSERIAL PRIMARY KEY,
                  project_id TEXT,
                  task_id INTEGER,
                  from_member TEXT,
                  to_member TEXT,
                  method TEXT,
                  reason TEXT,
                  created_at TEXT,
                  approved_by TEXT)''')

    # ── Academic Event Scheduler Tables ──────────────────────────────────────

    c.execute('''CREATE TABLE IF NOT EXISTS current_project
                 (id BIGSERIAL PRIMARY KEY,
                  group_id TEXT,
                  research_topic TEXT,
                  supervisor_name TEXT,
                  description_snippet TEXT,
                  updated_at TEXT)''')


    c.execute('''CREATE TABLE IF NOT EXISTS supervisors

                 (id BIGSERIAL PRIMARY KEY,

                  name TEXT, email TEXT,

                  expertise TEXT,

                  available_dates TEXT,

                  available_times TEXT,

                  role TEXT DEFAULT 'Professor',

                  uploaded_at TEXT)''')

    # Add role column if upgrading from old DB
    try:
        c.execute("ALTER TABLE supervisors ADD COLUMN role TEXT DEFAULT 'Professor'")
    except Exception:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS halls

                 (id BIGSERIAL PRIMARY KEY,

                  hall_name TEXT, capacity INTEGER, floor_building TEXT,

                  available_dates TEXT,

                  available_times TEXT,

                  uploaded_at TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS academic_events

                 (id BIGSERIAL PRIMARY KEY,

                  event_type TEXT,

                  group_id TEXT,

                  group_topic TEXT,

                  supervisor_id INTEGER,

                  supervisor_name TEXT,

                  match_score REAL,

                  hall_id INTEGER,

                  hall_name TEXT,

                  scheduled_date TEXT,

                  scheduled_time TEXT,

                  duration_minutes INTEGER DEFAULT 60,

                  status TEXT DEFAULT "Scheduled",

                  notes TEXT,

                  created_at TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS event_panel_members

                 (id BIGSERIAL PRIMARY KEY,

                  event_id INTEGER,

                  member_name TEXT,

                  member_role TEXT,

                  member_email TEXT)''')

    conn.commit()

    conn.close()



def init_db():
    """Initialize the PostgreSQL-only scheduling schema."""
    postgres_db.initialize_schema()


init_db()



sys.stdout.reconfigure(encoding="utf-8")

warnings.filterwarnings("ignore")

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

os.environ["TOKENIZERS_PARALLELISM"] = "false"



# USED MODEL - XGBOOST DURATION REGRESSOR
# Predicts task effort hours; generate_schedule converts those hours into
# working-day durations and dependency-aware dates.
models = {"xgboost": joblib.load(_model_path("xgboost_duration.joblib"))}

# ============================================================================
# USED MODELS AND ALGORITHEMS - SEARCH INDEX
# Search these exact keywords in this file:
#   USED MODEL - XGBOOST DURATION REGRESSOR
#   USED MODEL - RANDOM FOREST DELAY RISK PROXY
#   USED MODEL - T5 TRANSFORMER OPTIONAL
#   USED MODEL - XGBOOST COMPLETION CLASSIFIER
#   USED MODEL - SENTIMENT MOCK
#   USED ALGORITHEMS - EVIDENCE-BASED PDF EXTRACTION
#   USED ALGORITHEMS - DEPENDENCY-AWARE DAG SCHEDULING
#   USED ALGORITHEMS - CRITICAL PATH ANALYSIS NOTE
#   USED ALGORITHEMS - LPT GREEDY ASSIGNMENT
#   USED ALGORITHEMS - COEFFICIENT OF VARIATION
#   USED ALGORITHEMS - FINAL WHOLE-TASK REBALANCING
#   USED ALGORITHEMS - MONTE CARLO SIMULATION -> simulate_schedule()
#   USED ALGORITHEMS - NSGA-II MULTI-OBJECTIVE OPTIMIZATION -> generate_pareto_schedule()
#   USED ALGORITHEMS - EXPERTISE SIMILARITY MATCHING -> _compute_similarity()
#   USED ALGORITHEMS - CONSTRAINT-BASED ACADEMIC SCHEDULING -> auto_schedule()
# ============================================================================


def _load_core_model(key: str, filename: str, bundle_key: str | None = None):
    """Lazily load a local model for tests and non-server callers."""
    if key not in models:
        loaded = joblib.load(_model_path(filename))
        models[key] = loaded[bundle_key] if bundle_key else loaded
    return models[key]


# USED MODEL - T5 TRANSFORMER OPTIONAL
# Used only as an explicitly enabled WBS fallback; normal operation uses the
# proposal-evidence extractor so startup does not depend on this large model.
def _load_optional_t5():
    """Load the local T5 fallback only when explicitly enabled and first needed."""
    enabled = os.getenv("ENABLE_T5_WBS", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        models["t5_status"] = "disabled"
        return None
    if models.get("t5") is not None and models.get("tokenizer") is not None:
        return models["t5"], models["tokenizer"]
    if models.get("t5_load_attempted"):
        return None

    models["t5_load_attempted"] = True
    local_model = os.path.join(MODEL_DIR, "t5_wbs_final")
    try:
        from transformers import T5ForConditionalGeneration, T5Tokenizer

        print("  -> Lazily loading optional local T5 WBS fallback...", flush=True)
        tokenizer = T5Tokenizer.from_pretrained(local_model, local_files_only=True)
        t5_model = T5ForConditionalGeneration.from_pretrained(
            local_model,
            local_files_only=True,
            low_cpu_mem_usage=True,
        )
        t5_model.eval()
        models["tokenizer"] = tokenizer
        models["t5"] = t5_model
        models["t5_status"] = "loaded"
        return t5_model, tokenizer
    except (OSError, MemoryError, RuntimeError) as exc:
        models.pop("tokenizer", None)
        models.pop("t5", None)
        models["t5_status"] = f"unavailable: {exc}"
        print(f"  -> Optional T5 unavailable; continuing with evidence-based extraction ({exc})", flush=True)
        return None



@asynccontextmanager

async def lifespan(app: FastAPI):

    print("🚀 Starting IPMS Adaptive Scheduling Server...", flush=True)

    print("  -> Model 1 (T5 WBS fallback): optional/lazy; disabled by default", flush=True)

    print("  -> Loading Model 2 (XGBoost Duration Estimator)...", flush=True)

    models["xgboost"] = joblib.load(_model_path("xgboost_duration.joblib"))

    print("  -> Loading Model 3 (NASA Defect-Proxy Random Forest; research proxy only)...", flush=True)

    # USED MODEL - RANDOM FOREST DELAY RISK PROXY
    # NOTE: ``logistic_delay.joblib`` is a legacy filename. Inspection of the
    # saved pipeline shows StandardScaler + SMOTE + RandomForestClassifier.
    # Do not describe the current artifact as Logistic Regression in the viva.
    bundle = joblib.load(_model_path("logistic_delay.joblib"))

    models["risk_proxy"] = bundle["pipeline"]
    models["logreg"] = models["risk_proxy"]  # backward-compatible internal key

    print("  -> Loading Model 4 (DistilBERT Sentiment - Novelty 9)...", flush=True)

    # Will download ~260MB model on first run if not cached

    # USED MODEL - SENTIMENT MOCK
    # This is a deterministic demonstration stub, not a trained DistilBERT
    # model. State this clearly if the panel asks about sentiment analysis.
    class MockSentiment:

        def __call__(self, text):

            text = text.lower()

            if any(w in text for w in ['bug', 'crash', 'fail', 'error', 'late', 'stuck', 'hard', 'broken']):

                return [{'label': 'NEGATIVE', 'score': 0.85}]

            return [{'label': 'POSITIVE', 'score': 0.9}]

    models["sentiment"] = MockSentiment()

    print("  -> DistilBERT (Mock) Loaded successfully!", flush=True)

    # USED MODEL - HISTORICAL JIRA PROXY, OFFLINE RESEARCH ONLY
    # The legacy mixed-label artifact and the time-aware GFG v2 experiment do
    # not validate which student is best for a project task. Loading either in
    # the live allocator would present a proxy probability as suitability.
    # Until consented student-task labels are available, use deterministic LPT.
    models["workload_rf"] = None
    models["workload_features"] = []
    models["workload_model_name"] = "LPT (no validated student model)"
    print("  -> Workload assignment: LPT; JIRA classifiers remain offline research proxies.", flush=True)

    print("\U0001f525 Required models loaded; scheduling server is ready!\n", flush=True)

    if not scheduler.running:
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)
    models.clear()



app = FastAPI(title="IPMS Adaptive Scheduling API", lifespan=lifespan)

_production_mode = os.getenv("IPMS_ENV", "").strip().lower() == "production"
_cors_origins = [origin.strip() for origin in os.getenv("IPMS_CORS_ORIGINS", "").split(",") if origin.strip()]
if _production_mode and (not _cors_origins or any(origin in {"*", "null"} for origin in _cors_origins)):
    raise RuntimeError("Set IPMS_CORS_ORIGINS to explicit trusted frontend origins in production.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _production_mode else ["*"],
    allow_credentials=False,  # Bearer tokens and integration keys; no browser cookies.
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the verified evidence API before the legacy prototype routes below.
# Starlette resolves routes in declaration order, so these hardened handlers are
# authoritative while older URLs remain source-compatible during migration.
app.include_router(progress_tracking_router)



# --- DATA MODELS ---

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = authenticate(req.username, req.password, req.role)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username, password, or role.")
    return {
        "access_token": issue_token(user),
        "token_type": "bearer",
        "user": {"username": user.username, "display": user.display, "role": user.role},
    }


@app.get("/api/auth/me")
def auth_me(user: AuthenticatedUser = Depends(current_user)):
    return {"username": user.username, "display": user.display, "role": user.role}


@app.get("/api/health")
def health_check():
    conn = None
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        return {
            "status": "healthy", "database": "postgresql",
            "t5_wbs": models.get("t5_status", "disabled/lazy"),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PostgreSQL unavailable: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()

class ProjectRequest(BaseModel):

    description: str

    project_id: str = "demo_project_01"

    team_size: int = 4

    duration_months: float = 6.0

    function_points: int = 120

    start_date: str | None = None



class TaskSchedule(BaseModel):
    task_id: int
    task_key: str = ""
    task_name: str
    source_section: str = "Unknown"
    extraction_method: str = "UNKNOWN"
    source_evidence: str = ""
    confidence: float = 0.0
    validation_reason: str = ""
    effort_hours: float
    duration_days: int
    start_date: str
    end_date: str
    assigned_to: str = ""
    # Generation creates the dependency/capacity timeline only. A real owner is
    # attached later by /api/progress/auto-assign.
    assignment_stage: str = "UNASSIGNED"
    component_owner: str = ""
    is_collaborative: bool = False
    is_parallel: bool = False
    dependencies: list[int] = Field(default_factory=list)
    classification: str = "OTHER"
    complexity: str = "MEDIUM"
    delay_risk_pct: float
    risk_status: str
    shap_explanation: str = ""
    requires_document: bool = False
    task_type: str = "CODE"
    progress_pct: int = 0
    submission_status: str = "Pending"
    status: str = "NOT_STARTED"

class ScheduleResponse(BaseModel):

    project_summary: str

    team_size: int

    total_tasks: int

    total_effort_hours: float

    total_duration_days: int

    schedule: list[TaskSchedule]

    team_members: list[str] = Field(default_factory=list)
    dependency_edges: list[dict] = Field(default_factory=list)
    parallel_groups: list[list[int]] = Field(default_factory=list)
    deadline_feasible: bool = True
    deadline_warning: str | None = None
    debug: dict = Field(default_factory=dict)



class GithubCommit(BaseModel):

    message: str

    timestamp: str



class GithubWebhookPayload(BaseModel):

    ref: str

    commits: list[GithubCommit]

    repository: dict



class SimulationRequest(BaseModel):

    intervention_type: str

    intervention_value: float



class GithubRegisterRequest(BaseModel):

    project_id: str = "demo_project_01"

    repo_url: str



class TaskCompleteRequest(BaseModel):

    project_id: str = "demo_project_01"

    task_id: int



class TaskAssignRequest(BaseModel):

    project_id: str = "demo_project_01"

    task_id: int

    task_name: str

    assigned_to: str

    effort_hours: float



# --- HELPERS ---

# ── FIX 1: Research-aware WBS template (replaces generic SDLC fallback) ──────

# Ordered to match a real 10-month FYP/research project lifecycle at SLIIT.

# Used only when all 5 extraction strategies yield < 4 tasks.

_RESEARCH_WBS_TEMPLATE = [

    "Literature Review & Background Research",

    "Dataset Collection & Preprocessing",

    "System Architecture & Design",

    "Core Algorithm & Model Development",

    "Backend API Development",

    "Frontend Dashboard Development",

    "Model Training & Validation",

    "System Integration & Testing",

    "Pilot Study & User Evaluation",

    "Report Writing & Viva Preparation",

]

# Keep legacy name so nothing else breaks

_STANDARD_WBS = _RESEARCH_WBS_TEMPLATE

_TASK_FP_WEIGHTS = [0.45, 0.55, 0.75, 0.95, 1.35, 1.25, 1.15, 1.05, 0.90, 0.85, 0.65, 0.50]

_DEFAULT_MEMBER_NAMES = ["Member 1", "Member 2", "Member 3", "Member 4", "Member 5", "Member 6"]



def extract_team_names(description: str, team_size: int) -> list[str]:

    """

    Extracts real SLIIT student names from a project proposal PDF.

    SLIIT IT numbers format: IT + exactly 8 digits (e.g. IT22117014).

    Names follow the IT number in various formats:

      - 'IT22117014 Dulakshana Malith'        (first + last name)

      - 'IT22117014 Lekamge R.L.M.D.'         (surname + initials)

      - 'IT22117014 R.L.M. Dulakshana Lekamge' (initials + full name)

    Strategy: scan every line containing IT+8digits, extract all 3+ letter

    capitalized words, take first 1-2 as the display name.

    Falls back to acknowledgement section names, then generic 'Member N'.

    """

    names = []



    STOP_WORDS = {

        # Academic institution / degree words

        'department', 'information', 'technology', 'institute', 'university',

        'bachelor', 'science', 'honours', 'engineering', 'computing', 'faculty',

        'project', 'report', 'proposal', 'supervisor', 'supervised', 'prof',

        'lecturer', 'senior', 'associate', 'professor', 'doctor', 'sri', 'lanka',

        'page', 'figure', 'table', 'appendix', 'section', 'chapter',

        'the', 'and', 'for', 'with', 'from', 'this', 'that', 'will', 'has',

        'have', 'are', 'was', 'students', 'student', 'hons', 'degree', 'bsc',

        'msc', 'phd', 'its', 'our', 'their', 'who', 'each',

        # Project / AI / system words that could appear on IT-number lines

        'intelligent', 'management', 'system', 'undergraduate', 'research',

        'analysis', 'based', 'using', 'formation', 'feasibility', 'topic',

        'group', 'team', 'academic', 'automated', 'prediction', 'assessment',

        'monitoring', 'scheduling', 'quality', 'planning', 'tracking',

        'dashboard', 'platform', 'framework', 'model', 'algorithm', 'network',

        'learning', 'artificial', 'deep', 'natural', 'language', 'processing',

        'data', 'software', 'application', 'development', 'design',

        'implementation', 'evaluation', 'performance', 'module', 'component',

        'pipeline', 'integration', 'testing', 'deployment', 'optimization',

    }



    def is_name_word(w: str) -> bool:

        """

        True only for words that look like a real person's name:

          - Length >= 4  (blocks 'BSc', 'Hon', 'The')

          - Starts with a capital letter

          - Has at least 3 lowercase letters (blocks 'SLIIT', 'STUDENTS', 'AI')

          - Not in the stop-word list

        """

        if len(w) < 4:

            return False

        if not w[0].isupper():

            return False

        if sum(1 for c in w if c.islower()) < 3:   # needs real lowercase content

            return False

        if w.lower() in STOP_WORDS:

            return False

        return True



    def name_from_it_line(line: str) -> str | None:

        """Extract a person's display name from a line containing an IT number."""

        cleaned = re.sub(r'\bIT\d{8}\b', '', line)

        cleaned = re.sub(r'[^A-Za-z\s]', ' ', cleaned)

        words = [w for w in cleaned.split() if is_name_word(w)]

        if not words:

            return None

        display = ' '.join(words[:2])

        return display if len(display) >= 4 else None



    # ── Strategy 1: Scan every line that contains IT + 8 digits ──────────────

    for line in description.splitlines():

        if re.search(r'\bIT\d{8}\b', line):

            name = name_from_it_line(line)

            if name and name not in names:

                names.append(name)

        if len(names) >= team_size:

            break



    # ── Strategy 2: Inline IT mentions (PDF may lose newlines) ───────────────

    if len(names) < team_size:

        chunks = re.findall(

            r'\bIT\d{8}\b(.{2,80}?)(?=\bIT\d{8}\b|[;\n]|\Z)',

            description

        )

        for chunk in chunks:

            cleaned = re.sub(r'[^A-Za-z\s]', ' ', chunk)

            words = [w for w in cleaned.split() if is_name_word(w)]

            if not words:

                continue

            name = ' '.join(words[:2])

            if len(name) >= 4 and name not in names:

                names.append(name)

            if len(names) >= team_size:

                break



    # ── Strategy 3: Acknowledgement section — ALWAYS run ─────────────────────

    # Finds "Lekamge R.L.M.D.", "Kulathunga S.A.I.K.", "Rashmika R.M.D." etc.

    # Run unconditionally so we always capture the 3 named members even if

    # Strategy 1/2 already found some (possibly wrong) names.

    ack_idx = re.search(r'ACKNOWLEDGEMENT|ACKNOWLEDGMENT', description, re.IGNORECASE)

    if ack_idx:

        ack_text = description[ack_idx.start():ack_idx.start() + 1000]

        # Pattern: Surname followed by initials "X.X.X." format

        surname_matches = re.findall(

            r'\b([A-Z][a-z]{2,})\s+[A-Z][A-Z.]{2,}',

            ack_text

        )

        for surname in surname_matches:

            if is_name_word(surname) and surname not in names:

                names.append(surname)



    # ── Strategy 4: "member" keyword lines (Group Members / Team Members) ─────

    if len(names) < team_size:

        for line in description.splitlines():

            if re.search(r'(?:group|team)\s+member', line, re.IGNORECASE):

                words = [w for w in re.sub(r'[^A-Za-z\s]', ' ', line).split()

                         if is_name_word(w)]

                for w in words:

                    if w not in names:

                        names.append(w)



    # ── Deduplicate and pad to team_size ─────────────────────────────────────

    seen = []

    for n in names:

        n = n.strip()

        if n and n not in seen:

            seen.append(n)



    for i in range(len(seen) + 1, team_size + 1):

        seen.append(f"Member {i}")

    return seen[:team_size]





def extract_it_numbers(description: str, team_size: int) -> list[str]:

    """

    Extracts SLIIT IT registration numbers from the proposal document.

    Pattern: IT + exactly 8 digits  (e.g. IT22117014, IT21100001)

    This is the most reliable member identifier — no name ambiguity.

    Deduplicates while preserving first-occurrence order.

    Pads with 'Member N' if fewer than team_size numbers found.

    """

    # Find all IT + 8-digit numbers in the text

    all_numbers = re.findall(r'\bIT\d{8}\b', description)



    # Deduplicate, preserving order of first appearance

    seen_nums = []

    for num in all_numbers:

        if num not in seen_nums:

            seen_nums.append(num)



    # Pad with generic placeholders if not enough IT numbers found

    for i in range(len(seen_nums) + 1, team_size + 1):

        seen_nums.append(f"Member {i}")



    return seen_nums[:team_size]





def _is_valid_task(name: str) -> bool:

    """

    Returns True only if `name` looks like a genuine WBS task.

    Filters out:

      - TOC / document section headings (Commercialization, Budget, References…)

      - Figure / table captions

      - Short / overly long strings

      - ALL-CAPS abbreviation strings

      - Lines with version numbers or years

    """

    name = name.strip()

    if len(name) < 6 or len(name) > 160: return False

    if re.search(r'\b\d+\.\d+\b|\bv\d+\b|\bl\d+\b|\b\d{4}\b', name.lower()): return False

    if re.fullmatch(r'[A-Z]{2,}(\s[A-Z]{2,})*', name): return False



    # ── Extended noise list: document sections that are NOT WBS tasks ─────────

    noise = [

        # Generic document sections

        'figure', 'table', 'http', 'www', 'et al', 'ibid', 'chapter', 'section',

        # Proposal document sections

        'commercialization', 'commercialisation',

        'budget', 'justification',

        'references', 'bibliography', 'appendix', 'appendices',

        'introduction', 'background', 'context', 'acknowledgement', 'acknowledgment',

        'list of abbreviation', 'list of figure', 'list of table',

        'table of content', 'contents',

        'intellectual property',

        'pricing strategy', 'revenue model', 'competitive advantage',

        'stakeholder',

        'non-functional', 'scalability', 'security consideration',

        'data flow', 'ethical consideration',

        'performance metric',

        'high-level', 'system architecture overview', 'system workflow',

        'component interaction', 'research gap', 'research approach',

        'specific objective', 'main objective',

    ]

    name_lower = name.lower()

    if any(n in name_lower for n in noise): return False



    # ── Block pure section-number prefixed headings (e.g. "6 Commercialization") ─

    if re.match(r'^\d+[\.\s]+[A-Z]', name) and len(name.split()) <= 4:

        return False



    return True





# ── FIX 3: Auto-detect project duration from Gantt section ────────────────────

def extract_duration_from_gantt(description: str) -> float | None:

    """

    Scans the Gantt chart section of a proposal for month column headers

    (M1, M2 ... M10, M12, etc.) and returns the maximum month found.

    Example: if 'M10' is found → returns 10.0 (months).

    Returns None if no month markers are found.

    """

    # Find the Gantt chart section

    gantt_idx = re.search(r'GANTT\s+CHART|Gantt\s+Chart', description, re.IGNORECASE)

    if not gantt_idx:

        return None

    gantt_chunk = description[gantt_idx.start(): gantt_idx.start() + 3000]

    # Find all M<number> patterns (M1, M2, ... M10, M12)

    months_found = re.findall(r'\bM(\d{1,2})\b', gantt_chunk)

    if not months_found:

        # Broaden search: also check for 'Month 1' ... 'Month 12'

        months_found = re.findall(r'\bMonth\s+(\d{1,2})\b', gantt_chunk, re.IGNORECASE)

    if months_found:

        max_month = max(int(m) for m in months_found)

        if 3 <= max_month <= 24:   # sanity check: 3 to 24 months

            return float(max_month)

    return None





# -- FIX 4: Parallel component task generator for multi-member FYP projects ----
def generate_parallel_component_tasks(description: str, team_members: list[str],
                                      extracted_tasks: list[str]) -> list[dict]:
    """
    Task categories for a multi-component IPMS project (4 members, 4 components).

    SHARED   -> owner='all'  (done TOGETHER: Lit Review, Integration, Viva...)
    PARALLEL -> owner='all'  (each member does their OWN version in parallel:
                              model training, algorithm dev, implementation...)
    ROLE     -> one member   (unique deliverable assigned round-robin)

    PARALLEL tasks appear as 'All Members' because all 4 members independently
    build and train models for THEIR OWN component. It is NOT 1-person work.
    """

    SHARED_KEYWORDS = [
        'kickoff', 'initiation',
        'literature review', 'background research',
        'integration testing', 'system integration',
        'pilot study', 'user evaluation', 'user study',
        'report writing', 'viva', 'submission', 'documentation',
        'dataset collection', 'data collection', 'data preprocessing',
        'preprocessing', 'system architecture', 'architecture',
        'requirement', 'planning',
    ]

    # Every member independently does these for THEIR OWN component.
    # They appear as "All Members" (parallel independent work, not 1 person).
    PARALLEL_KEYWORDS = [
        'algorithm', 'model training', 'model validation', 'model development',
        'core algorithm', 'core development', 'core implementation',
        'machine learning', 'deep learning', 'neural', 'classification',
        'prediction', 'detection', 'feature extraction',
        'training and validation', 'training & validation',
        'develop model', 'implement model',
        'backend', 'frontend', 'api development', 'dashboard development',
        'interface development', 'component development', 'module development',
        'implementation', 'development',
    ]

    ALWAYS_SHARED = [
        "Literature Review & Background Research",
        "System Architecture & Design",
        "Dataset Collection & Preprocessing",
        "System Integration & Testing",
        "Pilot Study & User Evaluation",
        "Report Writing & Viva Preparation",
    ]

    result    = []
    seen      = set()
    n_members = len(team_members) if team_members else 1

    def is_shared(task_name: str) -> bool:
        tl = task_name.lower()
        return any(kw in tl for kw in SHARED_KEYWORDS)

    def is_parallel(task_name: str) -> bool:
        tl = task_name.lower()
        return any(kw in tl for kw in PARALLEL_KEYWORDS)

    # Step 1: classify extracted tasks
    role_tasks = []
    for t in extracted_tasks:
        if is_shared(t):
            if t not in seen:
                result.append({"task_name": t, "task_type": "shared", "owner": "all"})
                seen.add(t)
        elif is_parallel(t):
            # Parallel: all members do this independently for their own component
            if t not in seen:
                result.append({"task_name": t, "task_type": "shared", "owner": "all"})
                seen.add(t)
        else:
            role_tasks.append(t)

    # Step 2: ensure core shared milestones always present
    for t in ALWAYS_SHARED:
        if t not in seen:
            result.append({"task_name": t, "task_type": "shared", "owner": "all"})
            seen.add(t)

    # Step 3: ROLE tasks -> unique deliverable, round-robin one per member
    role_idx = 0
    for t in role_tasks:
        if t not in seen:
            owner = team_members[role_idx % n_members] if team_members else "all"
            result.append({"task_name": t, "task_type": "individual", "owner": owner})
            seen.add(t)
            role_idx += 1

    return result


EXCLUDED_TASK_SECTIONS = {
    "title_page", "declaration", "acknowledgement", "abbreviations",
    "acronyms", "glossary", "table_of_contents", "list_of_figures",
    "list_of_tables", "references", "bibliography",
}

SOURCE_CONFIDENCE = {
    "WBS_TABLE": 0.95,
    "GANTT": 0.90,
    "SPECIFIC_OBJECTIVE": 0.85,
    "METHODOLOGY_ACTION": 0.75,
    "NLP_FALLBACK": 0.55,
}


def should_accept_task(task: dict) -> tuple[bool, str]:
    name = task.get("name", "").strip()
    if not name:
        return False, "empty candidate"
    name_lower = name.lower()
    method = task.get("extraction_method", "NLP_FALLBACK")
    source_key = re.sub(r"[^a-z]+", "_", task.get("source_section", "").lower()).strip("_")
    if source_key in EXCLUDED_TASK_SECTIONS:
        return False, "excluded source section"
    
    # 1. Block metadata
    if "bsc" in name_lower and "degree" in name_lower: return False, "degree metadata"
    if "information technology" in name_lower and len(name.split()) <= 5: return False, "institution metadata"
    if "supervisor:" in name_lower or "supervisor name" in name_lower or "student id" in name_lower: return False, "student/supervisor metadata"
    if name_lower.startswith("group ") and len(name.split()) <= 3: return False, "group metadata"
    if "declaration" in name_lower and len(name.split()) < 4: return False, "declaration text"
    if "references" in name_lower or "appendix" in name_lower: return False, "section heading"
    # PDF tables of contents commonly produce lines such as
    # ``Gantt Chart ........ 21``.  They are headings with page numbers, not
    # executable work, and must not enter the generated schedule.
    heading_without_page = re.sub(r'[.\s]+\d+\s*$', '', name_lower).strip(' .')
    canonical_heading = re.sub(r'\s*\([^)]*\)\s*$', '', heading_without_page).strip()
    if re.search(r'\.{3,}\s*\d*\s*$', name) or canonical_heading in {
        "gantt chart", "work breakdown structure", "wbs", "methodology",
        "specific objectives", "proposed solution",
    }:
        return False, "summary heading"
    
    # 2. Block abbreviation definitions
    if "abbreviation" in name_lower and "full form" in name_lower: return False, "abbreviation header"
    
    parts = name.split()
    if len(parts) >= 2:
        acronym = parts[0].upper()
        if 2 <= len(acronym) <= 6 and acronym.isalpha():
            letters = list(acronym)
            first_letters = [w[0].upper() for w in parts[1:] if w and w[0].isalpha()]
            
            matches = 0
            for l in letters:
                if l in first_letters:
                    matches += 1
                    first_letters.remove(l)
            
            if matches >= max(2, len(letters) - 1) or (acronym == "SHAP" and "Shapley" in name) or (acronym == "API" and "Application" in name):
                return False, "abbreviation definition"

    # 3. Require actionable verbs for weak sources
    action_verbs = ['develop', 'implement', 'design', 'evaluate', 'test', 'validate', 'build', 'create', 'analyze', 'analyse', 'collect', 'prepare', 'train', 'integrate', 'deploy', 'document', 'review', 'configure', 'compare', 'measure', 'assess', 'construct', 'automate', 'generate']
    
    if method in {"METHODOLOGY_ACTION", "NLP_FALLBACK"}:
        has_verb = any(
            re.search(rf'\b{re.escape(v)}(?:e[ds]?|ed|ing|s)?\b', name_lower)
            for v in action_verbs
        )
        if not has_verb:
            return False, "missing actionable evidence"

    # 4. Reject standalone technology-only terms (no action verb, single concept)
    # Important: Only reject when the ENTIRE name is just a technology term
    TECH_ONLY_TERMS = [
        'transformers', 'xgboost', 'sbert', 'bert', 'gpt', 'llm',
        'machine learning', 'deep learning', 'neural network', 'neural networks',
        'random forest', 'decision tree', 'logistic regression',
        'rest api', 'graphql', 'docker', 'kubernetes',
        'tensorflow', 'pytorch', 'keras', 'scikit-learn',
    ]
    # Only reject if name_lower IS exactly the tech term (possibly title-cased)
    if name_lower in TECH_ONLY_TERMS:
        return False, "technology-only term (no action verb)"
    # Also reject if the name has <=2 words and matches a tech term exactly
    if len(parts) <= 2 and any(name_lower == t for t in TECH_ONLY_TERMS):
        return False, "technology-only term (standalone)"

    # 5. Reject vague component/heading candidates from weak sources
    # WBS_TABLE and GANTT rows are allowed even without verb (explicit provenance)
    if method in {"GANTT", "NLP_FALLBACK", "METHODOLOGY_ACTION", "SPECIFIC_OBJECTIVE"}:
        VAGUE_HEADING_PATTERNS = [
            r'^[a-z]+ component$',       # "analysis component", "ai component"
            r'^[a-z]+ module$',          # "data module", "core module"
            r'^[a-z]+ layer$',           # "service layer"
            r'^[a-z]+ framework$',       # "ml framework"
            r'^[a-z]+ system$',          # "ai system" (when standalone, 2 words)
        ]
        is_vague = any(re.fullmatch(p, name_lower) for p in VAGUE_HEADING_PATTERNS)
        if is_vague and len(parts) <= 2:
            return False, "vague heading/component name (no action evidence)"
            
    return True, "valid"

def _get_keyword_tokens(name: str) -> set:
    """Extract meaningful keyword tokens from a task name for containment checking."""
    stopwords = {'the', 'a', 'an', 'and', 'or', 'of', 'for', 'to', 'in', 'on', 'at', 'by', 'with', 'its', 'their'}
    action_prefixes = {'implement', 'develop', 'design', 'create', 'build', 'integrate', 'evaluate', 'test', 'analyze', 'construct', 'automate', 'assess', 'train'}
    tokens = set(name.lower().split())
    tokens -= stopwords
    tokens -= action_prefixes
    return tokens

def normalize_tasks(raw_tasks: list[dict]) -> list[dict]:
    normalized = []
    seen = set()
    for task in raw_tasks:
        name = task["name"].strip()
        name = re.sub(r'^[\d\.]+\s+', '', name)
        name = name.title()
        
        # Deduplicate conservatively: convert to lowercase and remove common prefix verbs for comparison
        cmp_name = name.lower()
        cmp_name = re.sub(r'^(implement|develop|design|create|build|integrate|evaluate|test|analyze)\s+', '', cmp_name).strip()
        
        if cmp_name not in seen and len(cmp_name) > 3:
            seen.add(cmp_name)
            task["name"] = name
            task.setdefault("source_section", "Unknown")
            task.setdefault("source_evidence", name)
            task.setdefault("confidence", SOURCE_CONFIDENCE.get(task.get("extraction_method"), 0.5))
            task.setdefault("validation_reason", "valid executable task")
            normalized.append(task)

    # ── Semantic containment pass ──────────────────────────────────────────
    # After exact dedup, check if any task's keywords are a subset of another's.
    # Keep only the longer/more specific task. Never merge tasks with different
    # work objects (verified by checking that at least 1 unique keyword exists).
    merged_indices = set()
    for i in range(len(normalized)):
        for j in range(len(normalized)):
            if i == j or i in merged_indices or j in merged_indices:
                continue
            tokens_i = _get_keyword_tokens(normalized[i]["name"])
            tokens_j = _get_keyword_tokens(normalized[j]["name"])
            # Only merge if i's tokens are a proper subset of j's (j is more specific)
            # and they share at least 2 meaningful keywords (same topic area)
            if len(tokens_i) >= 2 and tokens_i < tokens_j and len(tokens_j - tokens_i) >= 1:
                # i is contained in j — mark i for removal, keep j
                print(f"MERGE: '{normalized[i]['name']}' contained in '{normalized[j]['name']}' → keeping longer task")
                kept = normalized[j]
                removed = normalized[i]
                kept.setdefault("merged_sources", []).append({
                    "name": removed["name"],
                    "source_section": removed.get("source_section", "Unknown"),
                    "source_evidence": removed.get("source_evidence", ""),
                })
                kept["confidence"] = max(kept.get("confidence", 0.0), removed.get("confidence", 0.0))
                merged_indices.add(i)

    final = [t for idx, t in enumerate(normalized) if idx not in merged_indices]
    if merged_indices:
        print(f"  → Semantic containment removed {len(merged_indices)} duplicate(s), {len(final)} tasks remain")
    for idx, task in enumerate(final, 1):
        task["stable_id"] = f"TASK-{idx:03d}"
    return final

def extract_wbs_tasks(description: str) -> list[dict]:
    all_tasks = []
    MIN_COVERAGE_TASKS = 8
    MIN_WEAK_COVERAGE_TASKS = 4
    debug_counts = {"WBS_TABLE": 0, "GANTT": 0, "SPECIFIC_OBJECTIVE": 0, "METHODOLOGY_ACTION": 0, "NLP_FALLBACK": 0}

    def count_valid():
        return sum(1 for t in all_tasks if should_accept_task(t)[0])

    # 1. Try WBS Table
    wbs_idx = re.search(
        r'WORK\s+BREAKDOWN\s+STRUCTURE|Table\s*\d*\s*:\s*Work\s+Breakdown|\bWBS\b\s*[:\)]?',
        description,
        re.IGNORECASE,
    )
    wbs_match_text = ""
    if wbs_idx:
        section_start = wbs_idx.start()
        section_tail = description[wbs_idx.end():]
        next_heading = re.search(
            r'(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:GANTT\s+CHART|REFERENCES|BIBLIOGRAPHY|APPENDIX|ABBREVIATIONS?)\s*$',
            section_tail,
        )
        section_end = wbs_idx.end() + (next_heading.start() if next_heading else min(len(section_tail), 6000))
        wbs_match_text = description[section_start:section_end]

    if wbs_match_text:
        # PDF table extraction normally preserves rows better than columns.
        # Parse one numbered row at a time; never let a regex span into the next row.
        for raw_line in wbs_match_text.splitlines():
            row = re.sub(r'\s+', ' ', raw_line).strip()
            match = re.match(r'^\s*\d{1,3}(?:\.\d+)*[\.)]?\s+(.+?)\s*$', row)
            if not match:
                continue
            evidence = match.group(1).strip()
            # Remove common schedule columns while preserving the full task name.
            candidate = re.split(
                r'\s{2,}|\s+M\d+\b|\s+Month\s+\d+\b|\s+\d+(?:\.\d+)?\s*(?:days?|weeks?|months?|hours?|h)\b',
                evidence,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            candidate = re.sub(r'\s*\(SO\d+\)', '', candidate.strip().rstrip(',:;.')).strip().title()
            if _is_valid_task(candidate) and not any(x["name"].lower() == candidate.lower() for x in all_tasks):
                all_tasks.append({
                    "name": candidate,
                    "source_section": "WBS Table",
                    "source_evidence": evidence[:300],
                    "extraction_method": "WBS_TABLE",
                    "confidence": SOURCE_CONFIDENCE["WBS_TABLE"],
                })
                debug_counts["WBS_TABLE"] += 1

    # 2. Try Gantt
    if count_valid() < MIN_COVERAGE_TASKS:
        gantt_idx = re.search(r'GANTT\s+CHART', description, re.IGNORECASE)
        if gantt_idx:
            for line in description[gantt_idx.start():gantt_idx.start() + 2000].split('\n'):
                clean = re.sub(r'[\u2022\u2713\*\-]', '', line)
                clean = re.sub(r'\s*M\d+\s*', ' ', clean).strip()
                if re.match(r'^[A-Z][A-Za-z\s&\-\/]{5,160}$', clean):
                    t = clean.strip().title()
                    if _is_valid_task(t) and not any(x["name"] == t for x in all_tasks):
                        all_tasks.append({"name": t, "source_section": "Gantt Chart", "extraction_method": "GANTT"})
                        debug_counts["GANTT"] += 1

    # 3. Try Specific Objectives
    if count_valid() < MIN_COVERAGE_TASKS:
        so_patterns = [r'(?:SO\s*\d+|Specific\s+Objective\s+\d+)\s*[:\-]?\s*([A-Z][^\n.!?]{10,80})', r'Objective\s+\d+\s*[:\-]\s*To\s+([A-Z][^\n.!?]{10,75})', r'\d+\.\s+(?:To\s+)?([A-Z][a-z]+(?:ment|tion|ing|sis|ure|ure)\b[^\n.!?]{5,70})']
        for pattern in so_patterns:
            for t in re.findall(pattern, description, re.IGNORECASE):
                t = re.sub(r'^To\s+', '', t.strip().rstrip('.,;:'), flags=re.IGNORECASE).strip().title()
                if _is_valid_task(t) and not any(x["name"] == t for x in all_tasks):
                    all_tasks.append({"name": t, "source_section": "Specific Objectives", "extraction_method": "SPECIFIC_OBJECTIVE"})
                    debug_counts["SPECIFIC_OBJECTIVE"] += 1

    # 4. Try action verbs anywhere in objectives/methodology/solution prose.
    if count_valid() < MIN_WEAK_COVERAGE_TASKS:
        action_verbs = [
            'develop', 'implement', 'design', 'create', 'build', 'integrate',
            'setup', 'configure', 'deploy', 'evaluate', 'test', 'train',
            'validate', 'analyze', 'analyse', 'collect', 'prepare', 'generate',
            'establish', 'construct', 'produce', 'define', 'perform', 'conduct',
            'predict', 'document', 'review', 'compare', 'measure',
        ]
        verb_pattern = re.compile(
            r'\b(' + '|'.join(map(re.escape, action_verbs)) + r')(?:s|ed|ing)?\b',
            re.IGNORECASE,
        )
        relevant_heading = re.compile(
            r'(?im)^\s*(?:\d+(?:\.\d+)*\s*)?'
            r'(specific objectives?|methodology|proposed solution|system design|implementation|testing|evaluation)\s*:?\s*$'
        )
        excluded_heading = re.compile(
            r'(?im)^\s*(?:\d+(?:\.\d+)*\s*)?'
            r'(abbreviations?|acronyms?|glossary|references|bibliography|appendix|acknowledgements?)\s*:?\s*$'
        )
        starts = list(relevant_heading.finditer(description))
        method_chunks = []
        for heading in starts:
            next_relevant = relevant_heading.search(description, heading.end())
            next_excluded = excluded_heading.search(description, heading.end())
            endpoints = [m.start() for m in (next_relevant, next_excluded) if m]
            end = min(endpoints) if endpoints else min(len(description), heading.end() + 6000)
            method_chunks.append((heading.group(1).title(), description[heading.end():end]))
        if not method_chunks:
            method_chunks = [("Methodology", description)]

        for section_name, chunk in method_chunks:
            for sentence in re.split(r'[.!?]\s+|\n+', chunk):
                sentence = re.sub(r'\s+', ' ', sentence).strip(' -\t')
                match = verb_pattern.search(sentence)
                if not match or not (3 <= len(sentence.split()) <= 35):
                    continue
                if any(noise in sentence.lower() for noise in ['figure ', 'table ', 'chapter ', 'et al', 'according to']):
                    continue
                # Keep the executable clause, even when prose precedes the verb.
                candidate = sentence[match.start():]
                candidate = re.split(r'\b(?:whereas|although|because)\b', candidate, maxsplit=1, flags=re.IGNORECASE)[0]
                candidate = candidate.strip(' ,;:').title()
                if _is_valid_task(candidate) and not any(x["name"].lower() == candidate.lower() for x in all_tasks):
                    all_tasks.append({
                        "name": candidate,
                        "source_section": section_name,
                        "source_evidence": sentence[:300],
                        "extraction_method": "METHODOLOGY_ACTION",
                        "confidence": SOURCE_CONFIDENCE["METHODOLOGY_ACTION"],
                    })
                    debug_counts["METHODOLOGY_ACTION"] += 1

    # 5. NLP Fallback
    if count_valid() < MIN_WEAK_COVERAGE_TASKS:
        try:
            optional_t5 = _load_optional_t5()
            if optional_t5 is None:
                raise RuntimeError("Optional T5 fallback is disabled or unavailable")
            t5, tokenizer = optional_t5
            # Exclude front matter/glossary/references and prefer evidence-rich sections.
            included_lines = []
            excluded = False
            priority = False
            for line in description.splitlines():
                heading_key = re.sub(r'[^a-z]+', '_', re.sub(r'^\s*\d+(?:\.\d+)*\s*', '', line).lower()).strip('_')
                if heading_key in EXCLUDED_TASK_SECTIONS:
                    excluded = True
                    priority = False
                    continue
                if heading_key in {
                    'work_breakdown_structure', 'wbs', 'gantt_chart', 'specific_objectives',
                    'methodology', 'proposed_solution', 'system_design', 'implementation',
                    'testing', 'evaluation',
                }:
                    excluded = False
                    priority = True
                if not excluded and priority:
                    included_lines.append(line)
            nlp_text = "\n".join(included_lines)
            if not nlp_text.strip():
                raise ValueError("No evidence-rich section available for NLP fallback")
            words = " ".join(nlp_text.split()).split()
            for chunk in [" ".join(words[i:i+300]) for i in range(0, len(words), 300)][:5]:
                import torch
                tokens = tokenizer("summarize: " + chunk, return_tensors="pt", max_length=512, truncation=True)
                with torch.no_grad():
                    # MODEL CALCULATION - T5 WBS TEXT GENERATION
                    out = t5.generate(tokens["input_ids"], max_length=32, num_beams=4, early_stopping=True)
                raw = tokenizer.decode(out[0], skip_special_tokens=True)
                for part in re.split(r'[,;]|\band\b', raw):
                    part = part.strip()
                    if len(part) > 10 and len(part.split()) < 12:
                        t = part.title()
                        if _is_valid_task(t) and not any(x["name"] == t for x in all_tasks):
                            all_tasks.append({"name": t, "source_section": "NLP Summarization", "extraction_method": "NLP_FALLBACK"})
                            debug_counts["NLP_FALLBACK"] += 1
        except Exception as e:
            print(f"NLP Fallback failed: {e}")
            pass

    # VALIDATION PHASE
    valid_tasks = []
    rejected_counts = {
        "abbreviation definition": 0,
        "degree metadata": 0,
        "institution metadata": 0,
        "student/supervisor metadata": 0,
        "group metadata": 0,
        "declaration text": 0,
        "section heading": 0,
        "abbreviation header": 0,
        "missing actionable evidence": 0
    }
    
    for t in all_tasks:
        accepted, reason = should_accept_task(t)
        if accepted:
            valid_tasks.append(t)
        else:
            rejected_counts[reason] = rejected_counts.get(reason, 0) + 1
            print(f"REJECTED: {t['name']}\\nReason: {reason}")
            
    final_tasks = normalize_tasks(valid_tasks)
    extract_wbs_tasks.last_debug = {
        "strategy_counts": dict(debug_counts),
        "raw_candidates": len(all_tasks),
        "rejected": dict(rejected_counts),
        "after_actionability": len(valid_tasks),
        "final_executable_tasks": len(final_tasks),
    }
    
    print(f"\\n--- TASK VALIDATION REPORT ---")
    print(f"Raw Candidates: {len(all_tasks)}")
    print(f"Rejected Abbreviations: {rejected_counts.get('abbreviation definition', 0) + rejected_counts.get('abbreviation header', 0)}")
    print(f"Rejected Metadata/Front Matter: {sum(v for k,v in rejected_counts.items() if 'metadata' in k or 'declaration' in k)}")
    print(f"Rejected Weak Action: {rejected_counts.get('missing actionable evidence', 0)}")
    print(f"After Validation: {len(valid_tasks)}")
    print(f"After Deduplication: {len(final_tasks)}")
    print(f"Final Tasks: {len(final_tasks)}")
    for t in final_tasks:
        print(f"  - {t['name']}")
    print(f"------------------------------\\n")
    
    return final_tasks

# ── Task-type weights and complexity multipliers (configurable) ─────────────
TASK_TYPE_WEIGHTS = {
    "LITERATURE_REVIEW": 0.8,
    "REQUIREMENTS":      0.8,
    "DESIGN":            1.0,
    "DATA_COLLECTION":   1.0,
    "DEVELOPMENT":       1.5,
    "ML_MODEL":          1.6,
    "OPTIMIZATION":      1.7,
    "INTEGRATION":       1.3,
    "TESTING":           1.0,
    "EVALUATION":        1.0,
    "DOCUMENTATION":     0.8,
    "DEPLOYMENT":        0.7,
    "OTHER":             1.0,
}

COMPLEXITY_MULTIPLIER = {
    "LOW":    0.8,
    "MEDIUM": 1.0,
    "HIGH":   1.3,
}

# High-complexity keyword signals
HIGH_COMPLEXITY_KEYWORDS = [
    'nsga', 'sbert', 'knowledge graph', 'adaptive', 'optimization',
    'semantic grading', 'xgboost', 'prediction model', 'recommendation engine',
    'feedback loop', 'multi-objective', 'transformer', 'profiling engine',
]

def classify_task(task_name: str) -> dict:
    """
    Classify a task into a type and complexity level.
    Returns {"task_type": str, "complexity": str, "type_weight": float, "complexity_mult": float}
    """
    tl = task_name.lower()

    # Determine task type based on keyword matching (ordered by specificity)
    if any(k in tl for k in ['literature', 'background research', 'survey', 'related work']):
        task_type = "LITERATURE_REVIEW"
    elif any(k in tl for k in ['requirement', 'elicitation', 'specification']):
        task_type = "REQUIREMENTS"
    elif any(k in tl for k in ['design', 'architecture', 'schema', 'blueprint']):
        task_type = "DESIGN"
    elif any(k in tl for k in ['data collection', 'dataset', 'preprocessing', 'data preparation']):
        task_type = "DATA_COLLECTION"
    elif any(k in tl for k in ['nsga', 'optimization', 'genetic algorithm', 'multi-objective', 'pareto']):
        task_type = "OPTIMIZATION"
    elif any(k in tl for k in ['train', 'model', 'classifier', 'predictor', 'neural', 'sbert', 'xgboost', 'bert', 'nlp', 'ml ']):
        task_type = "ML_MODEL"
    elif any(k in tl for k in ['integrat', 'api', 'dashboard', 'interface', 'connect']):
        task_type = "INTEGRATION"
    elif any(k in tl for k in ['test', 'qa ', 'quality assurance', 'validation', 'verify']):
        task_type = "TESTING"
    elif any(k in tl for k in ['evaluat', 'assess', 'measure', 'performance', 'benchmark', 'confirm']):
        task_type = "EVALUATION"
    elif any(k in tl for k in ['document', 'report', 'writing', 'viva', 'submission', 'manual']):
        task_type = "DOCUMENTATION"
    elif any(k in tl for k in ['deploy', 'release', 'launch', 'production']):
        task_type = "DEPLOYMENT"
    elif any(k in tl for k in ['develop', 'implement', 'build', 'construct', 'create', 'engine', 'scheduler', 'generator', 'knowledge graph']):
        task_type = "DEVELOPMENT"
    else:
        task_type = "OTHER"

    # Determine complexity
    if any(k in tl for k in HIGH_COMPLEXITY_KEYWORDS):
        complexity = "HIGH"
    elif task_type in {"ML_MODEL", "OPTIMIZATION", "INTEGRATION"}:
        complexity = "MEDIUM"
    elif task_type in {"LITERATURE_REVIEW", "REQUIREMENTS", "DOCUMENTATION", "DEPLOYMENT"}:
        complexity = "LOW"
    else:
        complexity = "MEDIUM"

    type_weight = TASK_TYPE_WEIGHTS.get(task_type, 1.0)
    complexity_mult = COMPLEXITY_MULTIPLIER.get(complexity, 1.0)
    return {
        "task_type": task_type,
        "complexity": complexity,
        "type_weight": type_weight,
        "complexity_mult": complexity_mult,
        "effective_weight": round(type_weight * complexity_mult, 4),
    }


def estimate_durations(tasks: list[str], team_size: int, duration_months: float, fp: int) -> list[float]:
    """
    Returns per-task effort hours using XGBoost total-effort + weighted distribution.
    Weights are derived from task type × complexity (not a fixed position-based list).
    Conservation: sum(returned efforts) ≈ XGBoost total effort (within rounding).
    """
    if not tasks:
        return []
    xgb_model = _load_core_model("xgboost", "xgboost_duration.joblib")
    n = len(tasks)

    df = pd.DataFrame([{"function_points": fp, "log_fp": np.log1p(fp), "source_enc": 0}])
    # MODEL CALCULATION - XGBOOST TOTAL EFFORT PREDICTION
    # The regressor predicts log-effort; expm1 converts it back to hours.
    total_effort = float(np.clip(
        np.expm1(xgb_model.predict(df)[0]),
        team_size * duration_months * 4 * 40 * 0.2,
        team_size * duration_months * 4 * 40 * 0.9
    ))

    # Classify each task and compute effective weights
    classifications = [classify_task(t) for t in tasks]
    eff_weights = [c["effective_weight"] for c in classifications]
    weight_sum = sum(eff_weights) or 1.0

    # Distribute total effort proportionally, with minimum floor of 4h
    raw_efforts = [total_effort * (w / weight_sum) for w in eff_weights]
    efforts = [max(4.0, round(e, 1)) for e in raw_efforts]

    # Rounding correction: adjust last task so sum stays close to total_effort
    diff = total_effort - sum(efforts)
    if efforts:
        efforts[-1] = max(4.0, round(efforts[-1] + diff, 1))

    # Debug output
    print(f"  → Total XGBoost effort: {total_effort:.1f}h  |  Task weights sum: {weight_sum:.2f}")
    for i, (t, c, e) in enumerate(zip(tasks, classifications, efforts)):
        print(f"     T{i+1:02d}: {t[:50]:<50} [{c['task_type']}/{c['complexity']}] w={c['effective_weight']} → {e}h")

    return efforts



# MODEL CALCULATION - DELAY RISK CAPACITY RULE
# Current schedule risk uses required-days / available-days utilization. The
# separately loaded research proxy is not used for this operational result.
def predict_delay_risks(tasks: list[str], efforts: list[float], team_size: int, duration_months: float) -> list[dict]:
    days_per_task = (duration_months * 22) / len(tasks)
    out = []
    
    for hours in efforts:
        days_needed = hours / (team_size * 8)
        cap_ratio = days_needed / max(days_per_task, 1)
        
        utilization = cap_ratio
        
        if utilization >= 0.90:
            status = "HIGH"
        elif utilization >= 0.70:
            status = "MEDIUM"
        else:
            status = "LOW"
            
        out.append({
            "status": status,
            "risk_pct": round(min(utilization * 100, 100)),
            "explanation": f"Utilization={utilization:.2f} (Required: {days_needed:.1f}d / Available: {max(days_per_task,1):.1f}d)"
        })
    return out

def _shap_label(feature: str, shap_val: float) -> str:
    """Map a NASA feature name to a human-readable project management label."""
    mapping = {
        "v(g)"       : "Cyclomatic Complexity",
        "ev(g)"      : "Essential Complexity",
        "iv(g)"      : "Design Complexity",
        "branchcount": "Branch Count",
        "loc"        : "Lines of Code / Task Size",
        "locode"     : "Executable Code Lines",
        "loblank"    : "Code Blank Lines",
        "locomment"  : "Comment Density",
        "n"          : "Program Length",
        "v"          : "Program Volume",
        "l"          : "Program Level",
        "d"          : "Program Difficulty",
        "i"          : "Intelligence Content",
        "e"          : "Effort Metric",
        "t"          : "Time Estimator",
        "b"          : "Error Estimator",
        "total_op"   : "Total Operators",
        "total_opnd" : "Total Operands",
        "uniq_op"    : "Unique Operators",
        "uniq_opnd"  : "Unique Operands",
    }
    label = mapping.get(feature.lower(), feature)
    direction = "raises" if shap_val > 0 else "lowers"
    return f"{label} {direction} risk"





# --- API ENDPOINTS ---

app.mount("/app", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="frontend")

@app.get("/")

@app.get("/home")
def read_home(): 
    from fastapi.responses import FileResponse
    import os
    # Serve the main IPMS unified dashboard from the parent directory
    parent_index = os.path.join(os.path.dirname(__file__), '..', 'index.html')
    if os.path.exists(parent_index):
        return FileResponse(parent_index)
    else:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/app")

@app.get("/favicon.ico")
def read_favicon(): 
    return {}

def read_root(): return RedirectResponse(url="/app")





def _validate_proposal(text: str) -> dict:

    """

    Scores uploaded PDF text to determine if it is a project proposal.

    Checks 5 keyword groups that appear in genuine academic proposals.

    Returns: {is_valid, score, matched_groups, detected_as}

    """

    text_lower = text.lower()



    PROPOSAL_GROUPS = {

        "Project Structure"  : ["introduction", "abstract", "objective", "scope",

                                "background", "problem statement", "motivation",

                                "aim", "purpose", "overview"],

        "Research Content"   : ["research", "methodology", "literature",

                                "analysis", "dataset", "model", "algorithm",

                                "evaluation", "experiment", "study"],

        "Technical Content"  : ["system", "develop", "implement", "design",

                                "architecture", "module", "component", "database",

                                "machine learning", "deep learning", "nlp", "api",

                                "neural", "classification", "framework"],

        "Project Planning"   : ["schedule", "timeline", "gantt", "wbs",

                                "work breakdown", "milestone", "deliverable",

                                "sprint", "phase", "plan", "activity"],

        "Academic Markers"   : ["university", "supervisor", "student", "degree",

                                "department", "faculty", "sliit", "undergraduate",

                                "final year", "dissertation", "proposal",

                                "academic", "project report", "it22", "it21"],

    }



    # IMPORTANT: Only words that CANNOT appear in a real academic proposal.

    # Removed: tax, payment, total, patient, clause, task — these legitimately

    # appear in proposal budget / ethics / planning sections.

    NON_PROPOSAL_SIGNALS = {

        "Invoice / Receipt"  : ["invoice number", "purchase order", "bill to",

                                "ship to", "amount due", "remittance",

                                "vat registration", "payment terms", "receipt no",

                                "subtotal", "gst number"],

        "News / Article"     : ["published by", "journalist", "reporter",

                                "breaking news", "editorial board",

                                "newspaper", "press release"],

        "Legal Document"     : ["hereby agrees", "terms and conditions",

                                "indemnify", "plaintiff", "defendant",

                                "attorney", "legal counsel", "affidavit"],

        "Book / Novel"       : ["once upon a time", "prologue", "epilogue",

                                "he whispered", "she whispered", "the narrator"],

        "CV / Resume"        : ["curriculum vitae", "date of birth",

                                "marital status", "hobbies",

                                "references available on request"],

        "Medical Report"     : ["patient name", "date of admission",

                                "blood pressure", "physician signature",

                                "hospital registration", "prescription"],

    }



    matched_groups = []

    for group_name, keywords in PROPOSAL_GROUPS.items():

        matched = [kw for kw in keywords if kw in text_lower]

        if len(matched) >= 2:

            matched_groups.append(group_name)



    score = len(matched_groups)  # 0-5



    # If score is 3+ the document is clearly a proposal — skip non-proposal

    # check entirely to avoid false positives from budget/commercialisation

    # sections that mention financial terms.

    detected_as = "Project Proposal"

    if score < 3:

        for doc_type, keywords in NON_PROPOSAL_SIGNALS.items():

            hits = sum(1 for kw in keywords if kw in text_lower)

            # Require 4+ hits (not 2) to avoid false positives

            if hits >= 4:

                detected_as = doc_type

                break



    # Valid if score >= 3 (always), or score == 2 with no strong non-proposal signal

    is_valid = (score >= 3) or (score == 2 and detected_as == "Project Proposal")

    return {"is_valid": is_valid, "score": score,

            "matched_groups": matched_groups, "detected_as": detected_as}





def extract_group_id(description: str) -> str:
    """Return a normalized proposal group ID such as ``R26-IT-095``."""
    if not description:
        return ""

    # PDF text extraction can introduce spaces, line breaks, or Unicode dash
    # characters between parts of an otherwise valid group identifier.
    match = re.search(
        r"(?<![A-Z0-9])R\s*(\d{2})\s*[^A-Z0-9]{0,4}I\s*T\s*[^A-Z0-9]{0,4}(\d{3})(?!\d)",
        description,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return f"R{match.group(1)}-IT-{match.group(2)}".upper()


# USED ALGORITHEMS - EVIDENCE-BASED PDF EXTRACTION
# Reads proposal text with pdfplumber, falls back to PyPDF2/raw fragments,
# validates proposal evidence, and extracts a normalized group ID.
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

    # Fix: Preserve newlines for WBS/Gantt extraction, but clean horizontal spaces
    clean_text = re.sub(r'[ \t]+', ' ', text)
    clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text).strip()

    if len(clean_text) < 50:

        raise HTTPException(

            status_code=422,

            detail="Could not extract readable text from this PDF. Please copy-paste the proposal text instead."

        )



    # ── Validate: is this actually a project proposal? ─────────────────────────

    validation = _validate_proposal(clean_text)

    if not validation["is_valid"]:

        detected = validation["detected_as"]

        score    = validation["score"]

        matched  = validation["matched_groups"]

        found_str = ", ".join(matched) if matched else "none"



        if detected not in ("Project Proposal", "Unknown Document"):

            detail = (

                f"This does not appear to be a project proposal.\n"

                f"Detected document type: {detected}\n\n"

                f"This system only accepts academic project proposals containing "

                f"sections like Objectives, Methodology, WBS, Gantt Chart, and "

                f"technical system descriptions. Please upload your project proposal PDF."

            )

        else:

            detail = (

                f"This does not look like an academic project proposal.\n"

                f"Proposal relevance score: {score}/5 (minimum 2 required)\n"

                f"Matching sections found: {found_str}\n\n"

                f"A valid proposal should contain: Introduction/Abstract, "

                f"Research Objectives, Methodology/System Architecture, "

                f"WBS/Gantt Chart, and technical terms (system, implement, model, API). "

                f"Please upload your project proposal PDF."

            )

        raise HTTPException(status_code=422, detail=detail)



    # ── Extract group ID and IT numbers ─────────────────────────────────────────

    group_id = extract_group_id(clean_text)

    it_numbers = list(dict.fromkeys(re.findall(r'\bIT\d{8}\b', clean_text)))



    return {

        "extracted_text"   : clean_text,

        "group_id"         : group_id,

        "it_numbers"       : it_numbers,

        "validation_score" : validation["score"],

        "matched_sections" : validation["matched_groups"],

    }



def detect_dependencies(tasks: list[str]) -> dict:
    """
    Infer conservative, phase-based dependencies between tasks.
    Tasks within the same phase can run in parallel (no dep between them).
    Only sequential phase transitions are enforced:
      LITERATURE/REQUIREMENTS → DESIGN → DEVELOPMENT/ML_MODEL/OPTIMIZATION
        → INTEGRATION → TESTING → EVALUATION → DOCUMENTATION
    """
    import math
    deps = {i: [] for i in range(len(tasks))}

    # Phase order: lower number = must come first
    PHASE_ORDER = {
        "LITERATURE_REVIEW": 0,
        "REQUIREMENTS":      0,
        "DESIGN":            1,
        "DATA_COLLECTION":   1,
        "ML_MODEL":          2,
        "OPTIMIZATION":      2,
        "DEVELOPMENT":       2,
        "INTEGRATION":       3,
        "TESTING":           4,
        "EVALUATION":        5,
        "DOCUMENTATION":     6,
        "DEPLOYMENT":        6,
        "OTHER":             2,
    }

    # Classify each task into a phase
    task_phases = []
    for t in tasks:
        c = classify_task(t)
        task_phases.append(PHASE_ORDER.get(c["task_type"], 2))

    # For each task, it depends on ALL tasks in the immediately preceding phase
    # (not on tasks in the same phase — those run in parallel)
    for i in range(len(tasks)):
        my_phase = task_phases[i]
        if my_phase == 0:
            continue  # First phase has no deps
        # Find the phase just before mine
        prev_phase = my_phase - 1
        # Walk backwards to find the nearest preceding phase that has tasks
        while prev_phase >= 0:
            predecessors = [j for j, ph in enumerate(task_phases) if ph == prev_phase and j != i]
            if predecessors:
                for pred in predecessors:
                    if pred not in deps[i]:
                        deps[i].append(pred)
                break
            prev_phase -= 1
        
    # Validation: Cycle Edge Removal
    def remove_cycles(graph):
        visited = set()
        stack = set()
        def dfs(node):
            visited.add(node)
            stack.add(node)
            edges_to_remove = []
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    edges_to_remove.extend(dfs(neighbor))
                elif neighbor in stack:
                    edges_to_remove.append((node, neighbor))
            stack.remove(node)
            return edges_to_remove

        for v in list(graph.keys()):
            if v not in visited:
                removed = dfs(v)
                for u, w in removed:
                    if w in graph[u]:
                        graph[u].remove(w)
                        print(f"Cycle detected: removed edge {u} -> {w}")
        return graph

    deps = remove_cycles(deps)
    return deps


# USED ALGORITHEMS - DEPENDENCY-AWARE DAG SCHEDULING
# Validates dependencies as a directed acyclic graph and returns a stable
# topological order so predecessor tasks finish before dependent tasks start.
# USED ALGORITHEMS - CRITICAL PATH ANALYSIS NOTE
# The current component does NOT calculate CPM slack or a separate critical
# path. It implements dependency-aware topological and capacity scheduling.
def validate_dependency_dag(dependencies: dict[int, list[int]], task_count: int) -> list[int]:
    """Validate dependency IDs and return a deterministic topological order."""
    graph = nx.DiGraph()
    graph.add_nodes_from(range(task_count))
    for task_index, predecessors in dependencies.items():
        if task_index not in graph:
            raise ValueError(f"Unknown dependent task index: {task_index}")
        for predecessor in predecessors:
            if predecessor not in graph:
                raise ValueError(f"Unknown predecessor task index: {predecessor}")
            graph.add_edge(predecessor, task_index)
    if not nx.is_directed_acyclic_graph(graph):
        cycle = nx.find_cycle(graph)
        raise ValueError(f"Cyclic task dependencies detected: {cycle}")
    return list(nx.lexicographical_topological_sort(graph, key=lambda idx: idx))


# USED ALGORITHEMS - LPT GREEDY ASSIGNMENT
# Longest Processing Time sorts tasks by descending effort and repeatedly gives
# the next task to the currently least-loaded member.
def cold_start_lpt_assign(efforts: list[float], members: list[str]) -> tuple[dict[int, str], dict[str, float]]:
    """Assign every task by descending effort to the least-loaded member."""
    if not members:
        raise ValueError("At least one team member is required")
    member_loads = {member: 0.0 for member in members}
    assignments = {}
    for task_index in sorted(range(len(efforts)), key=lambda idx: (-efforts[idx], idx)):
        # MODEL CALCULATION - LPT LEAST-LOADED MEMBER SELECTION
        member = min(members, key=lambda name: (member_loads[name], name))
        assignments[task_index] = member
        member_loads[member] += float(efforts[task_index])
    return assignments, member_loads

@app.post("/api/schedule/generate", response_model=ScheduleResponse)
def generate_schedule(req: ProjectRequest):

    # ── FIX 3: Auto-detect project duration from Gantt section ───────────────

    # Scans the proposal text for Gantt month columns (M1...M10) and overrides

    # the user-supplied duration if a more accurate value is found.

    detected_months = extract_duration_from_gantt(req.description)

    if detected_months and detected_months > req.duration_months:

        print(f"  -> FIX 3: Auto-detected duration = {detected_months} months "

              f"(overrides user input of {req.duration_months} months)", flush=True)

        effective_months = detected_months

    else:

        effective_months = req.duration_months



    # ── FIX 5: Use detected duration in effort calculation ───────────────────

    
    raw_task_dicts = extract_wbs_tasks(req.description)
    if not raw_task_dicts: raise HTTPException(status_code=400, detail="No tasks extracted")
    print(f"DEBUG 1 (raw_task_dicts): {len(raw_task_dicts)} tasks", flush=True)
    task_dicts = raw_task_dicts # already normalized
    tasks = [t["name"] for t in task_dicts]
    print(f"DEBUG 2 (tasks list): {len(tasks)} tasks", flush=True)

    # 🛠️ FIX 4: Extract team members then generate parallel component structure 🛠️
    team_members = extract_it_numbers(req.description, req.team_size)
    is_multi_component = (
        req.team_size >= 3
        and any(kw in req.description.lower() for kw in
                ['component', 'module', 'sub-system', 'ipms', 'integrated',
                 'specific objective', 'so1', 'so2', 'so3', 'so4'])
    )

    # FIX: Use detected duration in effort calculation
    efforts = estimate_durations(tasks, req.team_size, effective_months, req.function_points)
    print(f"DEBUG 3 (efforts): {len(efforts)} items", flush=True)
    
    # Effort is project work, so component detection must never divide or clone it.
    predicted_total_effort = round(sum(efforts), 1)

    if is_multi_component and len(tasks) >= 3:
        parallel_map = generate_parallel_component_tasks(
            req.description, team_members, tasks
        )
        task_owner_map = {p["task_name"].lower(): p["owner"] for p in parallel_map}
        print(f"  -> FIX 4: Multi-component project detected — parallel track mode", flush=True)
        print(f"DEBUG 5 (parallel_map): {len(parallel_map)} tasks generated", flush=True)
    else:
        task_owner_map = {}

    current_date = datetime.strptime(req.start_date, "%Y-%m-%d") if req.start_date else datetime.today()
    while current_date.weekday() >= 5:
        current_date += timedelta(days=1)
    
    deadline = current_date + timedelta(days=max(1, int(effective_months * 30.4375)))
    deps = detect_dependencies(tasks)
    print(f"DEBUG 6 (deps keys): {len(deps.keys())} items", flush=True)
    # Cold-start assignment: LPT over effort hours, with no skill/role dependency.
    assigned_member, member_loads = cold_start_lpt_assign(efforts, team_members)
    try:
        topological_order = validate_dependency_dag(deps, len(tasks))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def next_working_day(value: datetime) -> datetime:
        result = value
        while result.weekday() >= 5:
            result += timedelta(days=1)
        return result

    def add_working_days(start: datetime, working_days: int) -> datetime:
        result = next_working_day(start)
        remaining = max(1, working_days) - 1
        while remaining:
            result += timedelta(days=1)
            if result.weekday() < 5:
                remaining -= 1
        return result

    PRODUCTIVE_HOURS_PER_DAY = 4.0
    task_end_dates = {}
    resource_free_date = {member: current_date for member in team_members}
    scheduled_by_index = {}
    schedule_items = []

    for i in topological_order:
        task, effort = tasks[i], efforts[i]
        classification = classify_task(task)
        owner = assigned_member[i]
        duration_days = max(1, int(np.ceil(effort / PRODUCTIVE_HOURS_PER_DAY)))
        
        task_name_title = task.title()
        is_collaborative = _is_collaborative_task(task_name_title)
        is_parallel = not is_collaborative and _is_parallel_task(task_name_title)
        # ``owner`` is an internal cold-start capacity lane used to calculate
        # feasible dates. Do not expose it as a final assignment: workload
        # balancing is the authoritative assignment step.
        display_owner = "Unassigned"
        doc_keywords = ["requirement", "architecture", "design", "documentation", "report", "manual", "testing", "qa", "review", "proposal", "literature", "pilot", "evaluation", "viva", "submission"]
        requires_doc = any(word in task_name_title.lower() for word in doc_keywords)
        
        # Earliest Start Date Logic: max(project_start, dependencies_ready, resource_ready)
        dep_ready_date = current_date
        for pred_id in deps.get(i, []):
            if pred_id in task_end_dates:
                # MODEL CALCULATION - DEPENDENCY EARLIEST START DATE
                predecessor_ready = next_working_day(task_end_dates[pred_id] + timedelta(days=1))
                dep_ready_date = max(dep_ready_date, predecessor_ready)
                
        res_ready_date = resource_free_date.get(owner, current_date)
        start_date = next_working_day(max(current_date, dep_ready_date, res_ready_date))
        end_date = add_working_days(start_date, duration_days)
        
        # Update trackers
        task_end_dates[i] = end_date
        resource_free_date[owner] = next_working_day(end_date + timedelta(days=1))

        available_days = max(1, sum(
            1 for offset in range((deadline - start_date).days + 1)
            if (start_date + timedelta(days=offset)).weekday() < 5
        ))
        utilization = duration_days / available_days
        risk_pct = round(min(100.0, utilization * 100.0), 1)
        risk_status = "HIGH" if utilization >= 0.9 else ("MEDIUM" if utilization >= 0.7 else "LOW")
        
        schedule_items.append(TaskSchedule(
            task_id=i + 1, task_key=f"{req.project_id}-TASK-{i + 1:03d}", task_name=task_name_title, 
            source_section=task_dicts[i].get("source_section", "Unknown"),
            extraction_method=task_dicts[i].get("extraction_method", "UNKNOWN"),
            source_evidence=task_dicts[i].get("source_evidence", task),
            confidence=task_dicts[i].get("confidence", 0.5),
            validation_reason=task_dicts[i].get("validation_reason", "valid executable task"),
            effort_hours=round(effort, 1),
            duration_days=duration_days,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            assigned_to=display_owner,
            assignment_stage="UNASSIGNED",
            component_owner="",
            is_collaborative=is_collaborative,
            is_parallel=is_parallel,
            dependencies=[pred + 1 for pred in deps.get(i, [])],
            classification=classification["task_type"],
            complexity=classification["complexity"],
            delay_risk_pct=risk_pct, risk_status=risk_status,
            shap_explanation=(f"Capacity/deadline heuristic: {duration_days} working days "
                              f"required of {available_days} available ({utilization:.2f} utilization)."),
            requires_document=requires_doc,
            task_type="DOCUMENT" if requires_doc else "CODE",
            progress_pct=0,
            submission_status="Pending",
            status="NOT_STARTED"
        ))
        scheduled_by_index[i] = schedule_items[-1]

    # Preserve stable task-ID order in the API while dates follow topological execution.
    schedule_items = [scheduled_by_index[i] for i in range(len(tasks))]

    schedule_data = [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in schedule_items]

    conn = get_db_connection()

    c = conn.cursor()

    row = c.execute(

        "SELECT MAX(version) FROM schedule_versions WHERE project_id = ?",
        (req.project_id,),

    ).fetchone()

    next_ver = (row[0] or 0) + 1

    c.execute(

        "INSERT INTO schedule_versions (project_id, version, schedule_json, created_at, team_members_json) VALUES (?, ?, ?, ?, ?)",

        (req.project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat(), json.dumps(team_members))

    )

    # Persist the initial cold-start LPT assignment for progress/rebalancing.
    c.execute("DELETE FROM task_assignments WHERE project_id = ?", (req.project_id,))
    assigned_at = datetime.now().isoformat()
    for item in schedule_items:
        c.execute(
            """INSERT INTO task_assignments
               (project_id, task_id, task_name, assigned_to, effort_hours, status, assigned_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                req.project_id, item.task_id, item.task_name, item.assigned_to,
                item.effort_hours, item.status, assigned_at,
            ),
        )

    conn.commit(); conn.close()

    # ── Save project info for Academic Scheduler auto-fill ────────────────────
    try:
        import re as _re
        # Extract group/project ID (R26-IT-095 pattern)
        grp_match = _re.search(r'R\d{2}-IT-\d{3}', req.description)
        group_id_found = grp_match.group(0) if grp_match else req.project_id

        # Extract supervisor name
        sup_match = _re.search(
            r'(?:supervisor|lecturer)[^\n:]*?:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            req.description, _re.IGNORECASE
        )
        sup_name = sup_match.group(1).strip() if sup_match else ""

        # ── Smarter research topic extraction ─────────────────────────────
        # Try to find "Research Topic:", "Title:", "Project Title:" labels first
        topic_label_match = _re.search(
            r'(?:research\s+topic|project\s+title|title)\s*[:\-]\s*(.+)',
            req.description, _re.IGNORECASE
        )
        if topic_label_match:
            research_topic = topic_label_match.group(1).strip()[:150]
        else:
            # Fall back: skip very short lines and generic header lines,
            # pick the first substantive sentence that looks like a topic
            skip_words = ['university', 'faculty', 'department', 'submitted', 'presented',
                          'bachelor', 'master', 'degree', 'academic year', 'copyright',
                          'all rights', 'group', 'member', 'student id', 'supervisor']
            topic_lines = []
            for ln in req.description.splitlines():
                ln = ln.strip()
                if 15 < len(ln) < 150:
                    ln_lower = ln.lower()
                    if not any(sw in ln_lower for sw in skip_words):
                        topic_lines.append(ln)
            research_topic = topic_lines[0] if topic_lines else req.description[:120]

        _conn = get_db_connection()
        # Preserve other groups for staff mass academic scheduling while
        # replacing the latest metadata for this specific group.
        _conn.execute("DELETE FROM current_project WHERE group_id=?", (group_id_found,))
        _conn.execute(
            "INSERT INTO current_project (group_id, research_topic, supervisor_name, description_snippet, updated_at) VALUES (?,?,?,?,?)",
            (group_id_found, research_topic, sup_name, req.description[:300], datetime.now().isoformat())
        )
        _conn.commit(); _conn.close()
    except Exception:
        pass  # Never block the main response


    final_finish = max((datetime.strptime(s.end_date, "%Y-%m-%d") for s in schedule_items), default=current_date)
    project_span_days = (final_finish - current_date).days + 1
    deadline_feasible = final_finish <= deadline
    deadline_warning = None if deadline_feasible else (
        f"Capacity/dependency schedule finishes {final_finish.date()}, after the "
        f"{deadline.date()} project deadline. Tasks were not silently compressed."
    )
    dependency_edges = [
        {"from_task_id": predecessor + 1, "to_task_id": task_index + 1}
        for task_index, predecessors in deps.items()
        for predecessor in predecessors
    ]
    starts = {}
    for item in schedule_items:
        starts.setdefault(item.start_date, []).append(item.task_id)
    parallel_groups = [ids for ids in starts.values() if len(ids) > 1]
    extraction_debug = getattr(extract_wbs_tasks, "last_debug", {})
    debug = {
        **extraction_debug,
        "predicted_total_effort": predicted_total_effort,
        "distributed_total_effort": round(sum(s.effort_hours for s in schedule_items), 1),
        "dependency_edge_count": len(dependency_edges),
        "cycles_detected": 0,
        "parallel_groups": parallel_groups,
        "deadline_feasible": deadline_feasible,
        "productive_hours_per_member_day": PRODUCTIVE_HOURS_PER_DAY,
        "cold_start_workload_hours": {k: round(v, 1) for k, v in member_loads.items()},
    }

    return ScheduleResponse(

        project_summary=req.description[:100] + "...",

        team_size=req.team_size,

        total_tasks=len(tasks),

        total_effort_hours=round(sum(s.effort_hours for s in schedule_items), 1),

        total_duration_days=project_span_days,

        schedule=schedule_items,

        team_members=team_members,
        dependency_edges=dependency_edges,
        parallel_groups=parallel_groups,
        deadline_feasible=deadline_feasible,
        deadline_warning=deadline_warning,
        debug=debug,

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

        conn = get_db_connection()

        conn.execute("INSERT INTO sentiment_log (project_id, message, score, label, timestamp) VALUES (?, ?, ?, ?, ?)",

                     ("demo_project_01", commit, score, res['label'], datetime.now().isoformat()))

        conn.commit(); conn.close()



    conn = get_db_connection()

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

    # PROGRESS INCREMENT LOGIC
    if matched_task.get("task_type") == "CODE":
        current_prog = matched_task.get("progress_pct", 0)
        new_prog = min(100, current_prog + 25)  # E.g., each matched commit adds 25% progress
        matched_task["progress_pct"] = new_prog
        if new_prog < 100:
            # Just save the progress, do not trigger BEDF recalculation yet
            c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
                      ("demo_project_01", current_version + 1, json.dumps(schedule_data), datetime.now().isoformat()))
            conn.commit(); conn.close()
            return {"status": "progress_updated", "task": matched_task["task_name"], "progress": new_prog}
    
    # If progress reached 100% or it's a direct completion
    matched_task["progress_pct"] = 100
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

    conn = get_db_connection()

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

        # MODEL CALCULATION - MONTE CARLO DURATION SAMPLE
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

    conn = get_db_connection()

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

            # MODEL CALCULATION - NSGA-II OBJECTIVE VALUES
            # Duration, workload variance (burnout), and early milestone
            # visibility are optimized together as competing objectives.
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



# --- GITHUB REPO REGISTRATION ---

@app.post("/api/github/register")

def register_github_repo(req: GithubRegisterRequest):

    conn = get_db_connection()

    conn.execute("DELETE FROM github_registrations WHERE project_id = ?", (req.project_id,))

    conn.execute("INSERT INTO github_registrations (project_id, repo_url, registered_at) VALUES (?, ?, ?)",

                 (req.project_id, req.repo_url, datetime.now().isoformat()))

    conn.commit(); conn.close()

    return {"status": "registered", "repo_url": req.repo_url,

            "webhook_url": "http://your-server:8000/api/webhooks/github",

            "instructions": "Go to your GitHub repo > Settings > Webhooks > Add webhook. Set Payload URL to the webhook_url above, Content-Type to application/json, and select 'Just the push event'."}



@app.get("/api/github/status")

def get_github_status(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    row = conn.execute("SELECT repo_url, registered_at FROM github_registrations WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()

    conn.close()

    if not row: return {"connected": False, "repo_url": None}

    return {"connected": True, "repo_url": row[0], "registered_at": row[1]}



# --- MILESTONE DROPBOX (per-task document submission) ---

@app.post("/api/milestone/submit")

async def submit_milestone(task_id: int = Form(...), project_id: str = Form(default="demo_project_01"), file: UploadFile = File(...)):

    content = await file.read()

    if not content:

        raise HTTPException(status_code=400, detail="File is empty.")

    

    save_dir = os.path.join("submissions", project_id, str(task_id))

    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, file.filename)

    with open(save_path, "wb") as f:

        f.write(content)

    

    conn = get_db_connection()

    c = conn.cursor()

    c.execute("INSERT INTO task_submissions (project_id, task_id, filename, submitted_at, status) VALUES (?, ?, ?, ?, ?)",

              (project_id, task_id, file.filename, datetime.now().isoformat(), "SUBMITTED"))

    

    # Mark task as COMPLETED in latest schedule

    row = c.execute("SELECT id, schedule_json FROM schedule_versions WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()

    if row:

        schedule_data = json.loads(row[1])

        for t in schedule_data:

            if t["task_id"] == task_id:

                t["status"] = "COMPLETED"

                t["completion_type"] = "DROPBOX"

                t["completed_at"] = datetime.now().isoformat()

                break

        ver_row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id = ?", (project_id,)).fetchone()

        next_ver = (ver_row[0] or 0) + 1

        c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",

                  (project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat()))

    

    # Clear any existing warning notifications for this task

    c.execute("DELETE FROM notifications WHERE project_id = ? AND task_id = ?", (project_id, task_id))

    conn.commit(); conn.close()

    return {"status": "success", "message": f"Document submitted for task {task_id}", "filename": file.filename}



@app.get("/api/milestone/submissions")

def get_submissions(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    rows = conn.execute("SELECT task_id, filename, submitted_at, status FROM task_submissions WHERE project_id = ? ORDER BY submitted_at DESC", (project_id,)).fetchall()

    conn.close()

    return {"submissions": [{"task_id": r[0], "filename": r[1], "submitted_at": r[2], "status": r[3]} for r in rows]}



# --- TASK COMPLETION (manual toggle) ---

@app.post("/api/task/complete")

def mark_task_complete(req: TaskCompleteRequest):

    conn = get_db_connection()

    c = conn.cursor()

    row = c.execute("SELECT id, schedule_json FROM schedule_versions WHERE project_id = ? ORDER BY id DESC LIMIT 1", (req.project_id,)).fetchone()

    if not row:

        conn.close()

        raise HTTPException(status_code=400, detail="No schedule found")

    schedule_data = json.loads(row[1])

    matched = False

    for t in schedule_data:

        if t["task_id"] == req.task_id:

            t["status"] = "COMPLETED"

            t["completion_type"] = "MANUAL"

            t["completed_at"] = datetime.now().isoformat()

            matched = True

            break

    if not matched:

        conn.close()

        raise HTTPException(status_code=404, detail="Task not found")

    ver_row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id = ?", (req.project_id,)).fetchone()

    next_ver = (ver_row[0] or 0) + 1

    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",

              (req.project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat()))

    c.execute("DELETE FROM notifications WHERE project_id = ? AND task_id = ?", (req.project_id, req.task_id))

    conn.commit(); conn.close()

    return {"status": "completed", "task_id": req.task_id}



# --- NOTIFICATIONS ---

@app.get("/api/notifications")

def get_notifications(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    rows = conn.execute("SELECT id, task_id, task_name, type, message, created_at FROM notifications WHERE project_id = ? AND is_read = 0 ORDER BY created_at DESC", (project_id,)).fetchall()

    conn.close()

    return {"notifications": [{"id": r[0], "task_id": r[1], "task_name": r[2], "type": r[3], "message": r[4], "created_at": r[5]} for r in rows]}



@app.post("/api/notifications/read")

def mark_all_read(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    conn.execute("UPDATE notifications SET is_read = 1 WHERE project_id = ?", (project_id,))

    conn.commit(); conn.close()

    return {"status": "ok"}



# ============================================================

# NOVELTY 12: Individual WBS Progress Tracker

# Board Feedback: "Show Individual work breakdown through

# the project WBS and determine individual & project progress"

# ============================================================



@app.post("/api/progress/assign")

def assign_task_to_member(req: TaskAssignRequest):

    """Assign a WBS task to a specific team member."""

    conn = get_db_connection()

    conn.execute(

        """INSERT INTO task_assignments (project_id, task_id, task_name, assigned_to, effort_hours, status, assigned_at)

           VALUES (?, ?, ?, ?, ?, 'NOT_STARTED', ?)

           ON CONFLICT(project_id, task_id) DO UPDATE SET

             assigned_to=excluded.assigned_to,

             task_name=excluded.task_name,

             effort_hours=excluded.effort_hours,

             assigned_at=excluded.assigned_at""",

        (req.project_id, req.task_id, req.task_name, req.assigned_to, req.effort_hours, datetime.now().isoformat())

    )

    conn.commit(); conn.close()

    return {"status": "assigned", "task_id": req.task_id, "assigned_to": req.assigned_to}



@app.post("/api/progress/task-complete")

def complete_assigned_task(req: TaskCompleteRequest):

    """Mark an assigned task as completed (updates both assignment and schedule tables)."""

    conn = get_db_connection()

    c = conn.cursor()

    # Update the assignment status

    c.execute(

        "UPDATE task_assignments SET status='COMPLETED' WHERE project_id=? AND task_id=?",

        (req.project_id, req.task_id)

    )

    # Also sync with the main schedule_versions table

    row = c.execute(

        "SELECT id, schedule_json FROM schedule_versions WHERE project_id=? ORDER BY id DESC LIMIT 1",

        (req.project_id,)

    ).fetchone()

    if row:

        schedule_data = json.loads(row[1])

        for t in schedule_data:

            if t["task_id"] == req.task_id:

                t["status"] = "COMPLETED"

                t["completion_type"] = "INDIVIDUAL_PROGRESS"

                t["completed_at"] = datetime.now().isoformat()

                break

        ver_row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id=?", (req.project_id,)).fetchone()

        next_ver = (ver_row[0] or 0) + 1

        c.execute(

            "INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?,?,?,?)",

            (req.project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat())

        )

    conn.commit(); conn.close()

    return {"status": "completed", "task_id": req.task_id}



@app.get("/api/progress/individual")

def get_individual_progress(project_id: str = "demo_project_01"):

    """

    NOVELTY 12 Core Logic:

    Returns per-member progress weighted by XGBoost-predicted effort hours.

    This goes beyond simple task counting — a 100-hour task completion counts

    more than a 10-hour task, giving a true measure of workload delivery.

    """

    conn = get_db_connection()

    rows = conn.execute(

        "SELECT assigned_to, task_id, task_name, effort_hours, status FROM task_assignments WHERE project_id=?",

        (project_id,)

    ).fetchall()

    conn.close()



    if not rows:

        return {"members": [], "project_progress_pct": 0.0}



    # Group tasks by member

    members = {}

    for assigned_to, task_id, task_name, effort_hours, status in rows:

        if assigned_to not in members:

            members[assigned_to] = {"tasks": [], "total_effort": 0.0, "completed_effort": 0.0}

        members[assigned_to]["tasks"].append({

            "task_id": task_id,

            "task_name": task_name,

            "effort_hours": effort_hours,

            "status": status

        })

        members[assigned_to]["total_effort"] += effort_hours

        if status == "COMPLETED":

            members[assigned_to]["completed_effort"] += effort_hours



    result_members = []

    for name, data in members.items():

        total     = data["total_effort"]

        completed = data["completed_effort"]

        progress_pct = round((completed / total) * 100, 1) if total > 0 else 0.0



        # ── Bottleneck logic (fixed) ───────────────────────────────────────

        # A member is ONLY a bottleneck when:

        #   1. They have personally completed at least 1 task (project is underway)

        #   2. AND their effort-weighted progress is still below 50%

        #

        # This prevents the false "Bottleneck detected" warning that appears

        # for everyone right after auto-assign when no tasks are marked done yet.

        # (0% < 50% was always True at the start, flagging everyone incorrectly)

        completed_tasks_count = sum(1 for t in data["tasks"] if t["status"] == "COMPLETED")

        is_bottleneck = (completed_tasks_count > 0) and (progress_pct < 50.0)



        result_members.append({

            "member":                  name,

            "total_tasks":             len(data["tasks"]),

            "completed_tasks":         completed_tasks_count,

            "total_effort_hours":      round(total, 1),

            "completed_effort_hours":  round(completed, 1),

            "progress_pct":            progress_pct,

            "is_bottleneck":           is_bottleneck,

            "tasks":                   data["tasks"]

        })



    # Overall project progress weighted by effort (XGBoost output reuse)

    all_total     = sum(m["total_effort_hours"]     for m in result_members)

    all_completed = sum(m["completed_effort_hours"] for m in result_members)

    project_progress_pct = round((all_completed / all_total) * 100, 1) if all_total > 0 else 0.0





    return {

        "members": sorted(result_members, key=lambda x: x["progress_pct"], reverse=True),

        "project_progress_pct": project_progress_pct,

        "total_effort_hours": round(all_total, 1),

        "completed_effort_hours": round(all_completed, 1)

    }



@app.delete("/api/progress/reset")

def reset_assignments(project_id: str = "demo_project_01"):

    """Clear all task assignments for a project (used when a new schedule is generated)."""

    conn = get_db_connection()

    conn.execute("DELETE FROM task_assignments WHERE project_id=?", (project_id,))

    conn.commit(); conn.close()
    return {"status": "reset"}


@app.post("/api/progress/submit-document")
async def submit_document(task_id: int = Form(...), file: UploadFile = File(...)):
    """Handles file uploads for DOCUMENT tasks, checks deadlines, and auto-marks 100% progress."""
    conn = get_db_connection()
    c = conn.cursor()

    row = c.execute("SELECT version, schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY version DESC LIMIT 1").fetchone()
    if not row:
        conn.close()
        return {"status": "error", "message": "No schedule found"}
    
    current_version, schedule_data = row[0], json.loads(row[1])

    matched_task = None
    for task in schedule_data:
        if task["task_id"] == task_id:
            matched_task = task
            break

    if not matched_task:
        conn.close()
        return {"status": "error", "message": "Task not found"}

    if matched_task.get("task_type") != "DOCUMENT":
        conn.close()
        return {"status": "error", "message": "This is not a document submission task."}

    # Mark submission record
    c.execute("INSERT INTO task_submissions (project_id, task_id, filename, submitted_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", task_id, file.filename, datetime.now().isoformat()))

    # Calculate status (On Time vs Late)
    now = datetime.now()
    deadline = datetime.strptime(matched_task["end_date"], "%Y-%m-%d")
    days_diff = (now - deadline).days
    submission_status = "On Time" if days_diff <= 0 else "Late"

    # Update Task Progress
    matched_task["progress_pct"] = 100
    matched_task["submission_status"] = submission_status
    matched_task["status"] = "COMPLETED"

    # BEDF Adaptive Tightening (because 100% completed)
    for t in schedule_data:
        if t.get("status") != "COMPLETED":
            t["duration_days"] = max(1, int(t["duration_days"] * (0.90 if days_diff > 0 else 0.95)))

    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", current_version + 1, json.dumps(schedule_data), datetime.now().isoformat()))
    conn.commit(); conn.close()
    
    return {"status": "success", "task_name": matched_task["task_name"], "submission_status": submission_status}


@app.get("/api/progress/full")
def get_full_progress():
    """Unified API for the progress dashboard tracking both DOCUMENT and CODE tasks."""
    conn = get_db_connection()
    c = conn.cursor()
    row = c.execute("SELECT schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY version DESC LIMIT 1").fetchone()
    conn.close()
    if not row: return {"status": "error", "message": "No schedule found"}
    
    schedule_data = json.loads(row[0])
    doc_tasks, code_tasks = [], []

    for task in schedule_data:
        task_info = {
            "task_id": task["task_id"], "task_name": task["task_name"],
            "end_date": task["end_date"], "status": task.get("status", "NOT_STARTED"),
            "progress_pct": task.get("progress_pct", 0),
            "submission_status": task.get("submission_status", "Pending"),
            "risk_status": task.get("risk_status", "Low Risk")
        }
        if task.get("task_type") == "DOCUMENT":
            doc_tasks.append(task_info)
        else:
            code_tasks.append(task_info)

    return {"status": "success", "doc_tasks": doc_tasks, "code_tasks": code_tasks}




class AutoAssignRequest(BaseModel):

    project_id: str = "demo_project_01"

    team_members: list[str]

    tasks: list[dict]  # list of {task_id, task_name, effort_hours}

    proposal_text: str = ""



# Keywords that indicate a task involves ALL team members working together


# ─────────────────────────────────────────────────────────────────────────────
# Component Detection: Extracts member→component mapping from proposal text
# ─────────────────────────────────────────────────────────────────────────────
def extract_components_from_proposal(text: str, members: list) -> dict:
    """
    Scans proposal text to find which component each member owns.
    Returns: {member_id: component_name}

    Detection priority:
    1. "IT22XXXXXX ... Component Name" patterns
    2. Specific Objectives (SO1, SO2...) mapped to members by order
    3. Component sections: "Component N: Name"
    4. Fallback: "Component A", "Component B", ...
    """
    result = {}
    LABELS = ["Component A", "Component B", "Component C",
              "Component D", "Component E", "Component F"]

    # Strategy 1: IT number near a component/module/system name
    for member in members:
        patterns = [
            rf'{re.escape(member)}\s*[-\u2013:–]\s*([A-Za-z][A-Za-z\s&/]+?)(?=\n|,|\.|;|$)',
            rf'([A-Za-z][A-Za-z\s&/]+?)\s*[-\u2013:–]\s*{re.escape(member)}',
            rf'{re.escape(member)}[^\n]{{0,60}}(?:develop|responsible for|component|module|system)\s*[:\-]?\s*([A-Za-z][A-Za-z\s&/]{{4,50}})',
            rf'(?:component|module|system)\s*[:\-]?\s*([A-Za-z][A-Za-z\s&/]{{4,50}})[^\n]{{0,60}}{re.escape(member)}',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                name = m.group(1).strip().strip('.,;:')
                # Filter noise
                noise = ['the', 'and', 'for', 'this', 'that', 'with', 'will',
                         'each', 'their', 'group', 'team', 'project', 'member']
                if 4 < len(name) < 60 and name.lower() not in noise:
                    result[member] = name
                    break

    # Strategy 2: Specific Objectives SO1..SO4 mapped by member order
    so_matches = re.findall(
        r'SO\s*\d+\s*[:\-–]\s*([A-Za-z][A-Za-z\s&,/]{4,80}?)(?=SO\s*\d+|\n\n|\Z)',
        text, re.IGNORECASE
    )
    for i, member in enumerate(members):
        if member not in result and i < len(so_matches):
            name = so_matches[i].strip()[:55]
            if name:
                result[member] = name

    # Strategy 3: Numbered component sections
    comp_matches = re.findall(
        r'(?:Component|Module)\s*\d+\s*[:\-–]\s*([A-Za-z][A-Za-z\s&/]{4,60}?)(?=\n|,)',
        text, re.IGNORECASE
    )
    for i, member in enumerate(members):
        if member not in result and i < len(comp_matches):
            result[member] = comp_matches[i].strip()[:55]

    # Strategy 4: Fallback — generic labels
    for i, member in enumerate(members):
        if member not in result:
            result[member] = LABELS[i] if i < len(LABELS) else f"Component {i+1}"

    return result

_COLLABORATIVE_KEYWORDS = [
    # TRULY SHARED: the whole team works TOGETHER on these milestones.
    # Do NOT add development/implementation/algorithm here — those are
    # component-specific tasks that each member does for their own component.

    # Team meetings & final deliverables
    'kickoff', 'initiation', 'viva', 'submission',
    'report writing', 'report preparation',
    'documentation',

    # Research phase (done once together)
    'literature review', 'background research', 'survey',

    # Planning & architecture (whole team designs the system together)
    'system architecture', 'architecture & design', 'architecture and design',
    'requirements analysis', 'planning',

    # Data collection (all members contribute data for the whole system)
    'dataset collection', 'data collection', 'data gathering',
    'data preparation', 'data preprocessing', 'preprocessing',

    # Integration & evaluation (testing the COMBINED system together)
    'system integration', 'integration testing',
    'pilot study', 'user evaluation', 'user study',
    'quality assurance',
]

def _is_collaborative_task(task_name: str) -> bool:

    """Returns True if the task should involve ALL team members working together."""

    name_lower = task_name.lower()

    return any(kw in name_lower for kw in _COLLABORATIVE_KEYWORDS)




_PARALLEL_KEYWORDS = [
    # PARALLEL/COMPONENT tasks: every member must do their OWN version
    # for their component. These are cloned into N copies (one per member),
    # each with effort / N hours.

    # Core technical development (every member implements for their component)
    'algorithm', 'model development', 'model training', 'model validation',
    'training & validation', 'training and validation',
    'backend api', 'backend development', 'api development',
    'frontend dashboard', 'frontend development', 'dashboard development',
    'machine learning', 'deep learning', 'neural network',
    'classification', 'prediction model', 'recommendation',
    'core algorithm', 'core development',
    'component development', 'module development',
    'feature development', 'feature extraction',
    'data model', 'data pipeline',
]

def _is_parallel_task(task_name: str) -> bool:
    """
    Returns True if this is a parallel/component task —
    meaning EVERY member must do their own version of it for their component.
    These tasks get cloned into N copies (one per member).
    """
    name_lower = task_name.lower()
    # Must not be a shared/collaborative task first
    if _is_collaborative_task(task_name):
        return False
    return any(kw in name_lower for kw in _PARALLEL_KEYWORDS)


_PARALLEL_KEYWORDS = [
    # PARALLEL/COMPONENT tasks: every member must do their OWN version
    # for their component. These are cloned into N copies (one per member),
    # each with effort / N hours.

    # Core technical development (every member implements for their component)
    'algorithm', 'model development', 'model training', 'model validation',
    'training & validation', 'training and validation',
    'backend api', 'backend development', 'api development',
    'frontend dashboard', 'frontend development', 'dashboard development',
    'machine learning', 'deep learning', 'neural network',
    'classification', 'prediction model', 'recommendation',
    'core algorithm', 'core development',
    'component development', 'module development',
    'feature development', 'feature extraction',
    'data model', 'data pipeline',
]

def _is_parallel_task(task_name: str) -> bool:
    """
    Returns True if this is a parallel/component task —
    meaning EVERY member must do their own version of it for their component.
    These tasks get cloned into N copies (one per member).
    """
    name_lower = task_name.lower()
    # Must not be a shared/collaborative task first
    if _is_collaborative_task(task_name):
        return False
    return any(kw in name_lower for kw in _PARALLEL_KEYWORDS)


WORKLOAD_OVERLOAD_RATIO = float(os.getenv("WORKLOAD_OVERLOAD_RATIO", "1.40"))


# ============================================================================
# USED ALGORITHEMS - COEFFICIENT OF VARIATION
# WORKLOAD BALANCING METRICS
# Measures fairness using coefficient of variation (CV) and independently
# checks whether the maximum load exceeds the configured max/min ratio.
# ============================================================================
def calculate_workload_balance(
    member_workload: dict[str, float],
    overload_ratio: float = WORKLOAD_OVERLOAD_RATIO,
) -> dict:
    """Calculate CV and the separate max/min overload safety verdict."""
    hours = [float(value) for value in member_workload.values()]
    if not hours:
        return {
            "mean_hours": 0.0,
            "std_hours": 0.0,
            "cv_percent": 0.0,
            "balance_score_pct": 100.0,
            "max_deviation_hours": 0.0,
            "max_to_min_ratio": 1.0,
            "overload_detected": False,
            "cv_balance_label": "EXCELLENT",
            "balance_label": "EXCELLENT",
        }

    mean_hours = float(np.mean(hours))
    std_hours = float(np.std(hours))
    # MODEL CALCULATION - WORKLOAD COEFFICIENT OF VARIATION
    cv_percent = round((std_hours / mean_hours * 100.0) if mean_hours > 0 else 0.0, 1)
    max_hours = max(hours)
    min_hours = min(hours)
    max_to_min_ratio = (max_hours / min_hours) if min_hours > 0 else (1.0 if max_hours == 0 else None)
    overload_detected = max_hours > (min_hours * overload_ratio) + 1e-9
    cv_label = (
        "EXCELLENT" if cv_percent < 10 else
        "GOOD" if cv_percent < 20 else
        "FAIR" if cv_percent < 30 else
        "POOR"
    )

    return {
        "mean_hours": mean_hours,
        "std_hours": std_hours,
        "cv_percent": cv_percent,
        "balance_score_pct": max(0.0, round(100.0 - cv_percent, 1)),
        "max_deviation_hours": round(max_hours - mean_hours, 1),
        "max_to_min_ratio": max_to_min_ratio,
        "overload_detected": overload_detected,
        "cv_balance_label": cv_label,
        "balance_label": "OVERLOADED" if overload_detected else cv_label,
    }


# ============================================================================
# USED ALGORITHEMS - FINAL WHOLE-TASK REBALANCING
# FINAL WHOLE-TASK REBALANCING
# Only individual tasks may move. Shared and parallel tasks stay unchanged.
# A move is accepted only when it improves overload, spread, or variance.
# ============================================================================
def rebalance_final_assignments(
    assignments: list[dict],
    member_workload: dict[str, float],
    member_components: dict[str, str] | None = None,
    overload_ratio: float = WORKLOAD_OVERLOAD_RATIO,
) -> list[dict]:
    """Move whole individual tasks until no improving transfer remains.

    Shared and parallel tasks are immutable. The result can remain overloaded
    when whole-task sizes make the configured ratio impossible; the caller then
    reports that condition instead of claiming that the allocation is safe.
    """
    members = list(member_workload)
    if len(members) < 2:
        return []

    movable_indexes = [
        index for index, assignment in enumerate(assignments)
        if not assignment.get("is_collaborative")
        and not assignment.get("is_parallel")
        and assignment.get("assigned_to") in member_workload
        and float(assignment.get("effort_hours", 0.0)) > 0
    ]
    if not movable_indexes:
        return []

    # MODEL CALCULATION - FINAL REBALANCING OBJECTIVE
    # Minimize overload excess first, then spread, then variance.
    def objective(loads: dict[str, float]) -> tuple[float, float, float]:
        values = list(loads.values())
        maximum, minimum = max(values), min(values)
        overload_excess = max(0.0, maximum - minimum * overload_ratio)
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return (round(overload_excess, 9), round(maximum - minimum, 9), round(variance, 9))

    moves = []
    max_iterations = max(1, len(movable_indexes) * len(members) * 4)
    for _ in range(max_iterations):
        current_objective = objective(member_workload)
        best = None
        for index in movable_indexes:
            assignment = assignments[index]
            source = assignment["assigned_to"]
            effort = float(assignment["effort_hours"])
            for target in members:
                if target == source:
                    continue
                trial = dict(member_workload)
                trial[source] -= effort
                trial[target] += effort
                trial_objective = objective(trial)
                if trial_objective >= current_objective:
                    continue
                candidate_key = (trial_objective, index, target)
                if best is None or candidate_key < best[0]:
                    best = (candidate_key, index, source, target, effort, trial)

        if best is None:
            break

        _, index, source, target, effort, new_loads = best
        before = calculate_workload_balance(member_workload, overload_ratio)
        member_workload.update(new_loads)
        after = calculate_workload_balance(member_workload, overload_ratio)
        assignment = assignments[index]
        assignment["assigned_to"] = target
        assignment["component_name"] = (member_components or {}).get(
            target, assignment.get("component_name", "Component")
        )
        assignment["final_guard_triggered"] = True
        assignment["assign_method"] = f"{assignment.get('assign_method', 'Assignment')} + Final Overload Guard"
        assignment["assign_reason"] = (
            f"{assignment.get('assign_reason', '')} Final validation moved this task "
            f"from {source} to {target} to reduce the team workload spread."
        ).strip()
        moves.append({
            "task_id": assignment.get("task_id"),
            "task_name": assignment.get("task_name"),
            "from_member": source,
            "to_member": target,
            "effort_hours": round(effort, 1),
            "ratio_before": None if before["max_to_min_ratio"] is None else round(before["max_to_min_ratio"], 3),
            "ratio_after": None if after["max_to_min_ratio"] is None else round(after["max_to_min_ratio"], 3),
        })
    return moves

# Kept only as a historical implementation reference. It must not register a
# route: its response references undefined names. The earlier startup de-duper
# already kept the later route, but explicit unregistration removes ambiguity.
def _legacy_auto_assign_tasks(req: AutoAssignRequest):

    """

    NOVELTY 12 Enhancement: Intelligent Workload-Balanced Auto-Assignment.



    Two modes of assignment:

    1. COLLABORATIVE tasks (kickoff, integration, testing, data gathering etc.)

       → Assigned to ALL team members. Effort is split equally.

       These are tasks where all 4 members must work together.



    2. INDIVIDUAL tasks (component-specific development work)

       → Assigned to the member with the LEAST current workload

       using the Longest Processing Time (LPT) greedy algorithm.



    This reflects real project dynamics where some phases require

    the whole team while others are owned by individual members.

    """

    if not req.team_members or not req.tasks:

        raise HTTPException(status_code=400, detail="No members or tasks provided.")



    member_workload = {name: 0.0 for name in req.team_members}

    assignments = []



    # ── Solo researcher mode: if only 1 member, skip collaborative logic ────
    is_solo = len(req.team_members) == 1

    # ── Detect components for each member from proposal text ─────────────────
    proposal_text = getattr(req, 'proposal_text', '') or ''
    member_components = extract_components_from_proposal(proposal_text, req.team_members)

    # ── Classify into 3 buckets ──────────────────────────────────────────────
    # SHARED   → All Members work together (1 entry, "All Members")
    # PARALLEL → Every member does their own copy (N entries, one per member)
    # ROLE     → Unique deliverable, assigned to ONE member via RF+LPT

    if is_solo:
        shared_tasks   = []
        parallel_tasks = []
        role_tasks     = list(req.tasks)
    else:
        shared_tasks   = [t for t in req.tasks if _is_collaborative_task(t["task_name"])]
        parallel_tasks = [t for t in req.tasks if not _is_collaborative_task(t["task_name"])
                                                and _is_parallel_task(t["task_name"])]
        role_tasks     = [t for t in req.tasks if not _is_collaborative_task(t["task_name"])
                                                and not _is_parallel_task(t["task_name"])]

    # Keep backward compat names for the RF/LPT loop
    collab_tasks = shared_tasks
    individual_tasks = role_tasks
    sorted_individual = sorted(role_tasks, key=lambda t: t["effort_hours"], reverse=True)



    # ── Check if Random Forest model is available ─────────────────────────────

    rf_model    = models.get("workload_rf")

    rf_features = models.get("workload_features", [])

    use_ml      = rf_model is not None

    assign_method = "XGBoost issue-status proxy (experimental)" if use_ml else "LPT Greedy (default)"



    # ── Helper: compute per-member history from DB ────────────────────────────

    def _get_member_stats(member_name: str) -> dict:

        """Pull historical completion rate and workload for this member from DB."""

        try:

            conn = get_db_connection()

            rows = conn.execute(

                "SELECT effort_hours, status FROM task_assignments WHERE assigned_to=? AND project_id=?",

                (member_name, req.project_id)

            ).fetchall()

            conn.close()

            if not rows:

                return {"completion_rate": 0.75, "current_workload": 0.0, "avg_effort": 40.0}

            total      = len(rows)

            completed  = sum(1 for r in rows if r[1] == "COMPLETED")

            workload   = sum(r[0] for r in rows if r[1] not in ("COMPLETED",))

            avg_effort = sum(r[0] for r in rows) / total

            return {

                "completion_rate"  : completed / total,

                "current_workload" : workload,

                "avg_effort"       : avg_effort

            }

        except Exception:

            return {"completion_rate": 0.75, "current_workload": 0.0, "avg_effort": 40.0}



    # ── Assign PARALLEL tasks: clone N copies, one per member ───────────────
    n_members = len(req.team_members)
    for task in parallel_tasks:
        per_member_effort = round(task["effort_hours"] / n_members, 1)
        for idx, member in enumerate(req.team_members):
            # Virtual task ID: base_id*1000 + member_index+1 for uniqueness
            virtual_id = task["task_id"] * 1000 + idx + 1
            comp_name = member_components.get(member, f"Component {chr(65+idx)}")
            assignments.append({
                "task_id"         : virtual_id,
                "task_name"       : f"[{comp_name}] {task['task_name']}",
                "assigned_to"     : member,
                "effort_hours"    : per_member_effort,
                "is_collaborative": False,
                "is_parallel"     : True,
                "confidence_pct"  : 100,
                "assign_method"   : "Parallel Component Split",
                "assign_reason"   : f"All {n_members} members do this task for their own component. Effort split equally: {task['effort_hours']}h / {n_members} = {per_member_effort}h each.",
                "component_name"  : comp_name,
            })
            member_workload[member] += per_member_effort

    # ── Assign SHARED tasks to ALL members ────────────────────────────────────

    for task in collab_tasks:

        per_member_effort = task["effort_hours"] / len(req.team_members)

        assignments.append({

            "task_id"         : task["task_id"],

            "task_name"       : task["task_name"],

            "assigned_to"     : "All Members",

            "effort_hours"    : task["effort_hours"],

            "is_collaborative": True,

            "is_parallel"     : False,

            "confidence_pct"  : 100,

            "assign_method"   : "Collaborative",

            "component_name"  : "Shared"

        })

        for m in req.team_members:

            member_workload[m] += per_member_effort



    # ── Assign individual tasks using Random Forest ML ────────────────────────

    # Model 5 feature schema (7 features, NO leaky deadline_days_remaining):

    #   [task_effort_estimate, task_category, task_complexity,

    #    member_completion_rate, member_current_workload,

    #    member_avg_effort, is_collaborative]

    import numpy as np

    member_task_count = {name: 0 for name in req.team_members}
    
    for task in sorted_individual:
        task_name  = task["task_name"]
        effort     = float(task["effort_hours"])

        # Cold-Start LPT Algorithm: Lowest Workload -> Fewest Assigned Tasks -> Stable ID
        sorted_members = sorted(
            req.team_members,
            key=lambda m: (member_workload[m], member_task_count[m], m)
        )
        best_member = sorted_members[0]
        
        workload_before = member_workload[best_member]
        assign_reason = f"COLD_START_LPT: Assigned to {best_member}. Workload before: {workload_before:.1f}h. Tie-break method: strict effort-first."
        
        member_workload[best_member] += effort
        member_task_count[best_member] += 1
        comp_name = member_components.get(best_member, "Component A") if not is_solo else ""
        
        assignments.append({
            "task_id"         : task["task_id"],
            "task_name"       : f"[{comp_name}] {task_name}" if comp_name else task_name,
            "assigned_to"     : best_member,
            "effort_hours"    : effort,
            "is_collaborative": False,
            "is_parallel"     : False,
            "confidence_pct"  : 100.0,
            "assign_method"   : "COLD_START_LPT",
            "assign_reason"   : assign_reason,
            "component_name"  : comp_name
        })

    return {"status": "success", "matched_task": matched_task["task_name"], "sentiment_label": res['label'] if sentiment_model else "UNKNOWN"}



# NOVELTY 10: Counterfactual What-If Simulation Engine

@app.post("/api/simulate")

def simulate_schedule(req: SimulationRequest):

    conn = get_db_connection()

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

    conn = get_db_connection()

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



# --- GITHUB REPO REGISTRATION ---

@app.post("/api/github/register")

def register_github_repo(req: GithubRegisterRequest):

    conn = get_db_connection()

    conn.execute("DELETE FROM github_registrations WHERE project_id = ?", (req.project_id,))

    conn.execute("INSERT INTO github_registrations (project_id, repo_url, registered_at) VALUES (?, ?, ?)",

                 (req.project_id, req.repo_url, datetime.now().isoformat()))

    conn.commit(); conn.close()

    return {"status": "registered", "repo_url": req.repo_url,

            "webhook_url": "http://your-server:8000/api/webhooks/github",

            "instructions": "Go to your GitHub repo > Settings > Webhooks > Add webhook. Set Payload URL to the webhook_url above, Content-Type to application/json, and select 'Just the push event'."}



@app.get("/api/github/status")

def get_github_status(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    row = conn.execute("SELECT repo_url, registered_at FROM github_registrations WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()

    conn.close()

    if not row: return {"connected": False, "repo_url": None}

    return {"connected": True, "repo_url": row[0], "registered_at": row[1]}



# --- MILESTONE DROPBOX (per-task document submission) ---

@app.post("/api/milestone/submit")

async def submit_milestone(task_id: int = Form(...), project_id: str = Form(default="demo_project_01"), file: UploadFile = File(...)):

    content = await file.read()

    if not content:

        raise HTTPException(status_code=400, detail="File is empty.")

    

    save_dir = os.path.join("submissions", project_id, str(task_id))

    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, file.filename)

    with open(save_path, "wb") as f:

        f.write(content)

    

    conn = get_db_connection()

    c = conn.cursor()

    c.execute("INSERT INTO task_submissions (project_id, task_id, filename, submitted_at, status) VALUES (?, ?, ?, ?, ?)",

              (project_id, task_id, file.filename, datetime.now().isoformat(), "SUBMITTED"))

    

    # Mark task as COMPLETED in latest schedule

    row = c.execute("SELECT id, schedule_json FROM schedule_versions WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,)).fetchone()

    if row:

        schedule_data = json.loads(row[1])

        for t in schedule_data:

            if t["task_id"] == task_id:

                t["status"] = "COMPLETED"

                t["completion_type"] = "DROPBOX"

                t["completed_at"] = datetime.now().isoformat()

                break

        ver_row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id = ?", (project_id,)).fetchone()

        next_ver = (ver_row[0] or 0) + 1

        c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",

                  (project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat()))

    

    # Clear any existing warning notifications for this task

    c.execute("DELETE FROM notifications WHERE project_id = ? AND task_id = ?", (project_id, task_id))

    conn.commit(); conn.close()

    return {"status": "success", "message": f"Document submitted for task {task_id}", "filename": file.filename}



@app.get("/api/milestone/submissions")

def get_submissions(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    rows = conn.execute("SELECT task_id, filename, submitted_at, status FROM task_submissions WHERE project_id = ? ORDER BY submitted_at DESC", (project_id,)).fetchall()

    conn.close()

    return {"submissions": [{"task_id": r[0], "filename": r[1], "submitted_at": r[2], "status": r[3]} for r in rows]}



# --- TASK COMPLETION (manual toggle) ---

@app.post("/api/task/complete")

def mark_task_complete(req: TaskCompleteRequest):

    conn = get_db_connection()

    c = conn.cursor()

    row = c.execute("SELECT id, schedule_json FROM schedule_versions WHERE project_id = ? ORDER BY id DESC LIMIT 1", (req.project_id,)).fetchone()

    if not row:

        conn.close()

        raise HTTPException(status_code=400, detail="No schedule found")

    schedule_data = json.loads(row[1])

    matched = False

    for t in schedule_data:

        if t["task_id"] == req.task_id:

            t["status"] = "COMPLETED"

            t["completion_type"] = "MANUAL"

            t["completed_at"] = datetime.now().isoformat()

            matched = True

            break

    if not matched:

        conn.close()

        raise HTTPException(status_code=404, detail="Task not found")

    ver_row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id = ?", (req.project_id,)).fetchone()

    next_ver = (ver_row[0] or 0) + 1

    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",

              (req.project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat()))

    c.execute("DELETE FROM notifications WHERE project_id = ? AND task_id = ?", (req.project_id, req.task_id))

    conn.commit(); conn.close()

    return {"status": "completed", "task_id": req.task_id}



# --- NOTIFICATIONS ---

@app.get("/api/notifications")

def get_notifications(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    rows = conn.execute("SELECT id, task_id, task_name, type, message, created_at FROM notifications WHERE project_id = ? AND is_read = 0 ORDER BY created_at DESC", (project_id,)).fetchall()

    conn.close()

    return {"notifications": [{"id": r[0], "task_id": r[1], "task_name": r[2], "type": r[3], "message": r[4], "created_at": r[5]} for r in rows]}



@app.post("/api/notifications/read")

def mark_all_read(project_id: str = "demo_project_01"):

    conn = get_db_connection()

    conn.execute("UPDATE notifications SET is_read = 1 WHERE project_id = ?", (project_id,))

    conn.commit(); conn.close()

    return {"status": "ok"}



# ============================================================

# NOVELTY 12: Individual WBS Progress Tracker

# Board Feedback: "Show Individual work breakdown through

# the project WBS and determine individual & project progress"

# ============================================================



@app.post("/api/progress/assign")

def assign_task_to_member(req: TaskAssignRequest):

    """Assign a WBS task to a specific team member."""

    conn = get_db_connection()

    conn.execute(

        """INSERT INTO task_assignments (project_id, task_id, task_name, assigned_to, effort_hours, status, assigned_at)

           VALUES (?, ?, ?, ?, ?, 'NOT_STARTED', ?)

           ON CONFLICT(project_id, task_id) DO UPDATE SET

             assigned_to=excluded.assigned_to,

             task_name=excluded.task_name,

             effort_hours=excluded.effort_hours,

             assigned_at=excluded.assigned_at""",

        (req.project_id, req.task_id, req.task_name, req.assigned_to, req.effort_hours, datetime.now().isoformat())

    )

    conn.commit(); conn.close()

    return {"status": "assigned", "task_id": req.task_id, "assigned_to": req.assigned_to}



@app.post("/api/progress/task-complete")

def complete_assigned_task(req: TaskCompleteRequest):

    """Mark an assigned task as completed (updates both assignment and schedule tables)."""

    conn = get_db_connection()

    c = conn.cursor()

    # Update the assignment status

    c.execute(

        "UPDATE task_assignments SET status='COMPLETED' WHERE project_id=? AND task_id=?",

        (req.project_id, req.task_id)

    )

    # Also sync with the main schedule_versions table

    row = c.execute(

        "SELECT id, schedule_json FROM schedule_versions WHERE project_id=? ORDER BY id DESC LIMIT 1",

        (req.project_id,)

    ).fetchone()

    if row:

        schedule_data = json.loads(row[1])

        for t in schedule_data:

            if t["task_id"] == req.task_id:

                t["status"] = "COMPLETED"

                t["completion_type"] = "INDIVIDUAL_PROGRESS"

                t["completed_at"] = datetime.now().isoformat()

                break

        ver_row = c.execute("SELECT MAX(version) FROM schedule_versions WHERE project_id=?", (req.project_id,)).fetchone()

        next_ver = (ver_row[0] or 0) + 1

        c.execute(

            "INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?,?,?,?)",

            (req.project_id, next_ver, json.dumps(schedule_data), datetime.now().isoformat())

        )

    conn.commit(); conn.close()

    return {"status": "completed", "task_id": req.task_id}



@app.get("/api/progress/individual")

def get_individual_progress(project_id: str = "demo_project_01"):

    """

    NOVELTY 12 Core Logic:

    Returns per-member progress weighted by XGBoost-predicted effort hours.

    This goes beyond simple task counting — a 100-hour task completion counts

    more than a 10-hour task, giving a true measure of workload delivery.

    """

    conn = get_db_connection()

    rows = conn.execute(

        "SELECT assigned_to, task_id, task_name, effort_hours, status FROM task_assignments WHERE project_id=?",

        (project_id,)

    ).fetchall()

    conn.close()



    if not rows:

        return {"members": [], "project_progress_pct": 0.0}



    # Group tasks by member

    members = {}

    for assigned_to, task_id, task_name, effort_hours, status in rows:

        if assigned_to not in members:

            members[assigned_to] = {"tasks": [], "total_effort": 0.0, "completed_effort": 0.0}

        members[assigned_to]["tasks"].append({

            "task_id": task_id,

            "task_name": task_name,

            "effort_hours": effort_hours,

            "status": status

        })

        members[assigned_to]["total_effort"] += effort_hours

        if status == "COMPLETED":

            members[assigned_to]["completed_effort"] += effort_hours



    result_members = []

    for name, data in members.items():

        total     = data["total_effort"]

        completed = data["completed_effort"]

        progress_pct = round((completed / total) * 100, 1) if total > 0 else 0.0



        # ── Bottleneck logic (fixed) ───────────────────────────────────────

        # A member is ONLY a bottleneck when:

        #   1. They have personally completed at least 1 task (project is underway)

        #   2. AND their effort-weighted progress is still below 50%

        #

        # This prevents the false "Bottleneck detected" warning that appears

        # for everyone right after auto-assign when no tasks are marked done yet.

        # (0% < 50% was always True at the start, flagging everyone incorrectly)

        completed_tasks_count = sum(1 for t in data["tasks"] if t["status"] == "COMPLETED")

        is_bottleneck = (completed_tasks_count > 0) and (progress_pct < 50.0)



        result_members.append({

            "member":                  name,

            "total_tasks":             len(data["tasks"]),

            "completed_tasks":         completed_tasks_count,

            "total_effort_hours":      round(total, 1),

            "completed_effort_hours":  round(completed, 1),

            "progress_pct":            progress_pct,

            "is_bottleneck":           is_bottleneck,

            "tasks":                   data["tasks"]

        })



    # Overall project progress weighted by effort (XGBoost output reuse)

    all_total     = sum(m["total_effort_hours"]     for m in result_members)

    all_completed = sum(m["completed_effort_hours"] for m in result_members)

    project_progress_pct = round((all_completed / all_total) * 100, 1) if all_total > 0 else 0.0





    return {

        "members": sorted(result_members, key=lambda x: x["progress_pct"], reverse=True),

        "project_progress_pct": project_progress_pct,

        "total_effort_hours": round(all_total, 1),

        "completed_effort_hours": round(all_completed, 1)

    }



@app.delete("/api/progress/reset")

def reset_assignments(project_id: str = "demo_project_01"):

    """Clear all task assignments for a project (used when a new schedule is generated)."""

    conn = get_db_connection()

    conn.execute("DELETE FROM task_assignments WHERE project_id=?", (project_id,))

    conn.commit(); conn.close()
    return {"status": "reset"}


@app.post("/api/progress/submit-document")
async def submit_document(task_id: int = Form(...), file: UploadFile = File(...)):
    """Handles file uploads for DOCUMENT tasks, checks deadlines, and auto-marks 100% progress."""
    conn = get_db_connection()
    c = conn.cursor()

    row = c.execute("SELECT version, schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY version DESC LIMIT 1").fetchone()
    if not row:
        conn.close()
        return {"status": "error", "message": "No schedule found"}
    
    current_version, schedule_data = row[0], json.loads(row[1])

    matched_task = None
    for task in schedule_data:
        if task["task_id"] == task_id:
            matched_task = task
            break

    if not matched_task:
        conn.close()
        return {"status": "error", "message": "Task not found"}

    if matched_task.get("task_type") != "DOCUMENT":
        conn.close()
        return {"status": "error", "message": "This is not a document submission task."}

    # Mark submission record
    c.execute("INSERT INTO task_submissions (project_id, task_id, filename, submitted_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", task_id, file.filename, datetime.now().isoformat()))

    # Calculate status (On Time vs Late)
    now = datetime.now()
    deadline = datetime.strptime(matched_task["end_date"], "%Y-%m-%d")
    days_diff = (now - deadline).days
    submission_status = "On Time" if days_diff <= 0 else "Late"

    # Update Task Progress
    matched_task["progress_pct"] = 100
    matched_task["submission_status"] = submission_status
    matched_task["status"] = "COMPLETED"

    # BEDF Adaptive Tightening (because 100% completed)
    for t in schedule_data:
        if t.get("status") != "COMPLETED":
            t["duration_days"] = max(1, int(t["duration_days"] * (0.90 if days_diff > 0 else 0.95)))

    c.execute("INSERT INTO schedule_versions (project_id, version, schedule_json, created_at) VALUES (?, ?, ?, ?)",
              ("demo_project_01", current_version + 1, json.dumps(schedule_data), datetime.now().isoformat()))
    conn.commit(); conn.close()
    
    return {"status": "success", "task_name": matched_task["task_name"], "submission_status": submission_status}


@app.get("/api/progress/full")
def get_full_progress():
    """Unified API for the progress dashboard tracking both DOCUMENT and CODE tasks."""
    conn = get_db_connection()
    c = conn.cursor()
    row = c.execute("SELECT schedule_json FROM schedule_versions WHERE project_id = 'demo_project_01' ORDER BY version DESC LIMIT 1").fetchone()
    conn.close()
    if not row: return {"status": "error", "message": "No schedule found"}
    
    schedule_data = json.loads(row[0])
    doc_tasks, code_tasks = [], []

    for task in schedule_data:
        task_info = {
            "task_id": task["task_id"], "task_name": task["task_name"],
            "end_date": task["end_date"], "status": task.get("status", "NOT_STARTED"),
            "progress_pct": task.get("progress_pct", 0),
            "submission_status": task.get("submission_status", "Pending"),
            "risk_status": task.get("risk_status", "Low Risk")
        }
        if task.get("task_type") == "DOCUMENT":
            doc_tasks.append(task_info)
        else:
            code_tasks.append(task_info)

    return {"status": "success", "doc_tasks": doc_tasks, "code_tasks": code_tasks}




class AutoAssignRequest(BaseModel):

    project_id: str = "demo_project_01"

    team_members: list[str]

    tasks: list[dict]  # list of {task_id, task_name, effort_hours}

    proposal_text: str = ""



# Keywords that indicate a task involves ALL team members working together


# ─────────────────────────────────────────────────────────────────────────────
# Component Detection: Extracts member→component mapping from proposal text
# ─────────────────────────────────────────────────────────────────────────────
def extract_components_from_proposal(text: str, members: list) -> dict:
    """
    Scans proposal text to find which component each member owns.
    Returns: {member_id: component_name}

    Detection priority:
    1. "IT22XXXXXX ... Component Name" patterns
    2. Specific Objectives (SO1, SO2...) mapped to members by order
    3. Component sections: "Component N: Name"
    4. Fallback: "Component A", "Component B", ...
    """
    result = {}
    LABELS = ["Component A", "Component B", "Component C",
              "Component D", "Component E", "Component F"]

    # Strategy 1: IT number near a component/module/system name
    for member in members:
        patterns = [
            rf'{re.escape(member)}\s*[-\u2013:–]\s*([A-Za-z][A-Za-z\s&/]+?)(?=\n|,|\.|;|$)',
            rf'([A-Za-z][A-Za-z\s&/]+?)\s*[-\u2013:–]\s*{re.escape(member)}',
            rf'{re.escape(member)}[^\n]{{0,60}}(?:develop|responsible for|component|module|system)\s*[:\-]?\s*([A-Za-z][A-Za-z\s&/]{{4,50}})',
            rf'(?:component|module|system)\s*[:\-]?\s*([A-Za-z][A-Za-z\s&/]{{4,50}})[^\n]{{0,60}}{re.escape(member)}',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                name = m.group(1).strip().strip('.,;:')
                # Filter noise
                noise = ['the', 'and', 'for', 'this', 'that', 'with', 'will',
                         'each', 'their', 'group', 'team', 'project', 'member']
                if 4 < len(name) < 60 and name.lower() not in noise:
                    result[member] = name
                    break

    # Strategy 2: Specific Objectives SO1..SO4 mapped by member order
    so_matches = re.findall(
        r'SO\s*\d+\s*[:\-–]\s*([A-Za-z][A-Za-z\s&,/]{4,80}?)(?=SO\s*\d+|\n\n|\Z)',
        text, re.IGNORECASE
    )
    for i, member in enumerate(members):
        if member not in result and i < len(so_matches):
            name = so_matches[i].strip()[:55]
            if name:
                result[member] = name

    # Strategy 3: Numbered component sections
    comp_matches = re.findall(
        r'(?:Component|Module)\s*\d+\s*[:\-–]\s*([A-Za-z][A-Za-z\s&/]{4,60}?)(?=\n|,)',
        text, re.IGNORECASE
    )
    for i, member in enumerate(members):
        if member not in result and i < len(comp_matches):
            result[member] = comp_matches[i].strip()[:55]

    # Strategy 4: Fallback — generic labels
    for i, member in enumerate(members):
        if member not in result:
            result[member] = LABELS[i] if i < len(LABELS) else f"Component {i+1}"

    return result

_COLLABORATIVE_KEYWORDS = [
    # TRULY SHARED: the whole team works TOGETHER on these milestones.
    # Do NOT add development/implementation/algorithm here — those are
    # component-specific tasks that each member does for their own component.

    # Team meetings & final deliverables
    'kickoff', 'initiation', 'viva', 'submission',
    'report writing', 'report preparation',
    'documentation',

    # Research phase (done once together)
    'literature review', 'background research', 'survey',

    # Planning & architecture (whole team designs the system together)
    'system architecture', 'architecture & design', 'architecture and design',
    'requirements analysis', 'planning',

    # Data collection (all members contribute data for the whole system)
    'dataset collection', 'data collection', 'data gathering',
    'data preparation', 'data preprocessing', 'preprocessing',

    # Integration & evaluation (testing the COMBINED system together)
    'system integration', 'integration testing',
    'pilot study', 'user evaluation', 'user study',
    'quality assurance',
]

def _is_collaborative_task(task_name: str) -> bool:

    """Returns True if the task should involve ALL team members working together."""

    name_lower = task_name.lower()

    return any(kw in name_lower for kw in _COLLABORATIVE_KEYWORDS)




_PARALLEL_KEYWORDS = [
    # PARALLEL/COMPONENT tasks: every member must do their OWN version
    # for their component. These are cloned into N copies (one per member),
    # each with effort / N hours.

    # Core technical development (every member implements for their component)
    'algorithm', 'model development', 'model training', 'model validation',
    'training & validation', 'training and validation',
    'backend api', 'backend development', 'api development',
    'frontend dashboard', 'frontend development', 'dashboard development',
    'machine learning', 'deep learning', 'neural network',
    'classification', 'prediction model', 'recommendation',
    'core algorithm', 'core development',
    'component development', 'module development',
    'feature development', 'feature extraction',
    'data model', 'data pipeline',
]

def _is_parallel_task(task_name: str) -> bool:
    """
    Returns True if this is a parallel/component task —
    meaning EVERY member must do their own version of it for their component.
    These tasks get cloned into N copies (one per member).
    """
    name_lower = task_name.lower()
    # Must not be a shared/collaborative task first
    if _is_collaborative_task(task_name):
        return False
    return any(kw in name_lower for kw in _PARALLEL_KEYWORDS)


_PARALLEL_KEYWORDS = [
    # PARALLEL/COMPONENT tasks: every member must do their OWN version
    # for their component. These are cloned into N copies (one per member),
    # each with effort / N hours.

    # Core technical development (every member implements for their component)
    'algorithm', 'model development', 'model training', 'model validation',
    'training & validation', 'training and validation',
    'backend api', 'backend development', 'api development',
    'frontend dashboard', 'frontend development', 'dashboard development',
    'machine learning', 'deep learning', 'neural network',
    'classification', 'prediction model', 'recommendation',
    'core algorithm', 'core development',
    'component development', 'module development',
    'feature development', 'feature extraction',
    'data model', 'data pipeline',
]

def _is_parallel_task(task_name: str) -> bool:
    """
    Returns True if this is a parallel/component task —
    meaning EVERY member must do their own version of it for their component.
    These tasks get cloned into N copies (one per member).
    """
    name_lower = task_name.lower()
    # Must not be a shared/collaborative task first
    if _is_collaborative_task(task_name):
        return False
    return any(kw in name_lower for kw in _PARALLEL_KEYWORDS)


def _normalize_schedule_ownership(schedule: list[dict]) -> list[dict]:
    """Normalize Gantt ownership, including legacy history without task flags."""
    normalized = []
    for original in schedule:
        task = dict(original)
        task_name = str(task.get("task_name") or "")
        is_collaborative = bool(task.get("is_collaborative")) or _is_collaborative_task(task_name)
        is_parallel = (
            not is_collaborative
            and (bool(task.get("is_parallel")) or _is_parallel_task(task_name))
        )
        assignment_stage = str(task.get("assignment_stage") or "").upper()
        if assignment_stage == "UNASSIGNED":
            # Preserve the flat, pre-balance Gantt state. Classification flags
            # remain available for the later workload-balancing decision.
            task["assigned_to"] = "Unassigned"
            task["component_owner"] = ""
        elif is_collaborative or is_parallel:
            task["assigned_to"] = "All Members"
            task["component_owner"] = "all"
        else:
            owner = str(task.get("component_owner") or task.get("assigned_to") or "").strip()
            task["component_owner"] = "all" if owner.lower() in {"all", "all members"} else owner
        task["is_collaborative"] = is_collaborative
        task["is_parallel"] = is_parallel
        normalized.append(task)
    return normalized


def _apply_workload_assignments_to_schedule(
    schedule: list[dict], assignments: list[dict]
) -> list[dict]:
    """Merge workload decisions into the persisted Gantt task snapshot."""
    original_ids = {int(task.get("task_id", 0)) for task in schedule}
    direct_assignments = {
        int(item["task_id"]): item
        for item in assignments
        if int(item.get("task_id", 0)) in original_ids
    }
    parallel_task_ids = {
        int(item["task_id"]) // 1000
        for item in assignments
        if item.get("is_parallel") and int(item.get("task_id", 0)) >= 1000
    }

    merged = []
    for original in schedule:
        task = dict(original)
        task_id = int(task.get("task_id", 0))
        assignment = direct_assignments.get(task_id)
        if assignment:
            task["assigned_to"] = assignment["assigned_to"]
            task["assignment_stage"] = "BALANCED"
            task["component_owner"] = (
                "all" if assignment.get("is_collaborative") else assignment["assigned_to"]
            )
            task["is_collaborative"] = bool(assignment.get("is_collaborative"))
            task["is_parallel"] = bool(assignment.get("is_parallel"))
            task["assign_method"] = assignment.get("assign_method", "")
            task["assign_reason"] = assignment.get("assign_reason", "")
        elif task_id in parallel_task_ids:
            # Keep one Gantt row for the source task while clearly showing that
            # each member performs their component-specific copy in parallel.
            task["assigned_to"] = "All Members"
            task["assignment_stage"] = "BALANCED"
            task["component_owner"] = "all"
            task["is_collaborative"] = False
            task["is_parallel"] = True
            task["assign_method"] = "Parallel Component Split"
        merged.append(task)
    return _normalize_schedule_ownership(merged)


# ============================================================================
# ACTIVE WORKLOAD-BALANCING API
# Frontend route: POST /api/progress/auto-assign
# Flow: classify tasks -> score members -> apply overload guard -> rebalance
# the complete allocation -> save assignments -> synchronize Gantt history.
# WORKLOAD BALANCE STEP 1 separates shared, parallel, and individual tasks.
# WORKLOAD BALANCE STEP 2 uses LPT in live service; the historical JIRA proxy
# branch is intentionally disabled until student-suitability data validate it.
# ============================================================================
def _validate_auto_assign_request(req: AutoAssignRequest) -> None:
    """Reject ambiguous task/member IDs before creating virtual assignments."""
    req.project_id = str(req.project_id or "").strip()
    members = [str(member).strip() for member in req.team_members]
    if not req.project_id or not 1 <= len(members) <= 100 or any(not member for member in members):
        raise HTTPException(status_code=422, detail="A project ID and 1–100 named members are required.")
    if len({member.casefold() for member in members}) != len(members):
        raise HTTPException(status_code=422, detail="Team member IDs must be unique.")
    normalized_tasks = []
    task_ids = set()
    for task in req.tasks:
        try:
            task_id = int(task["task_id"])
            task_name = str(task["task_name"]).strip()
            effort = float(task["effort_hours"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Every task needs an ID, name and numeric effort.") from exc
        if task_id <= 0 or task_id > 2_147_483_647 or task_id in task_ids or not task_name or not np.isfinite(effort) or effort <= 0:
            raise HTTPException(status_code=422, detail="Task IDs must be unique positive 32-bit integers; names and effort must be valid.")
        task_ids.add(task_id)
        normalized_tasks.append({**task, "task_id": task_id, "task_name": task_name, "effort_hours": effort})
    if not normalized_tasks:
        raise HTTPException(status_code=422, detail="At least one task is required.")
    virtual_ids = set()
    if len(members) > 1:
        for task in normalized_tasks:
            task_id, task_name = task["task_id"], task["task_name"]
            if _is_collaborative_task(task_name):
                copies = (task_id * 10000 + idx + 1 for idx in range(len(members)))
            elif _is_parallel_task(task_name):
                copies = (task_id * 1000 + idx + 1 for idx in range(len(members)))
            else:
                continue
            for copy_id in copies:
                if copy_id > 2_147_483_647 or copy_id in task_ids or copy_id in virtual_ids:
                    raise HTTPException(status_code=422, detail="Virtual task IDs collide or overflow; regenerate the task IDs.")
                virtual_ids.add(copy_id)
    req.team_members = members
    req.tasks = normalized_tasks


@app.post("/api/progress/auto-assign")

def auto_assign_tasks(
    req: AutoAssignRequest,
    _user: AuthenticatedUser = Depends(require_roles("supervisor", "staff")),
):

    _validate_auto_assign_request(req)

    """

    NOVELTY 12 Enhancement: Intelligent Workload-Balanced Auto-Assignment.



    Two modes of assignment:

    1. COLLABORATIVE tasks (kickoff, integration, testing, data gathering etc.)

       → Assigned to ALL team members. Effort is split equally.

       These are tasks where all 4 members must work together.



    2. INDIVIDUAL tasks (component-specific development work)

       → Assigned to the member with the LEAST current workload

       using the Longest Processing Time (LPT) greedy algorithm.



    This reflects real project dynamics where some phases require

    the whole team while others are owned by individual members.

    """

    if not req.team_members or not req.tasks:

        raise HTTPException(status_code=400, detail="No members or tasks provided.")



    member_workload = {name: 0.0 for name in req.team_members}

    assignments = []



    # ── Solo researcher mode: if only 1 member, skip collaborative logic ────
    is_solo = len(req.team_members) == 1

    # ── Detect components for each member from proposal text ─────────────────
    proposal_text = getattr(req, 'proposal_text', '') or ''
    member_components = extract_components_from_proposal(proposal_text, req.team_members)

    # ── Classify into 3 buckets ──────────────────────────────────────────────
    # SHARED   → All Members work together (1 entry, "All Members")
    # PARALLEL → Every member does their own copy (N entries, one per member)
    # ROLE     → Unique deliverable, assigned to ONE member via RF+LPT

    if is_solo:
        shared_tasks   = []
        parallel_tasks = []
        role_tasks     = list(req.tasks)
    else:
        shared_tasks   = [t for t in req.tasks if _is_collaborative_task(t["task_name"])]
        parallel_tasks = [t for t in req.tasks if not _is_collaborative_task(t["task_name"])
                                                and _is_parallel_task(t["task_name"])]
        role_tasks     = [t for t in req.tasks if not _is_collaborative_task(t["task_name"])
                                                and not _is_parallel_task(t["task_name"])]

    # Keep backward compat names for the RF/LPT loop
    collab_tasks = shared_tasks
    individual_tasks = role_tasks
    sorted_individual = sorted(role_tasks, key=lambda t: t["effort_hours"], reverse=True)



    # ── Check if Random Forest model is available ─────────────────────────────

    rf_model    = models.get("workload_rf")

    rf_features = models.get("workload_features", [])

    use_ml      = rf_model is not None

    assign_method = "XGBoost issue-status proxy (experimental)" if use_ml else "LPT Greedy (default)"



    # ── Helper: compute per-member history from DB ────────────────────────────

    def _get_member_stats(member_name: str) -> dict:

        """Pull historical completion rate and workload for this member from DB."""

        try:

            conn = get_db_connection()

            rows = conn.execute(

                "SELECT effort_hours, status FROM task_assignments WHERE assigned_to=? AND project_id=?",

                (member_name, req.project_id)

            ).fetchall()

            conn.close()

            if not rows:

                return {"completion_rate": 0.75, "current_workload": 0.0, "avg_effort": 40.0}

            total      = len(rows)

            completed  = sum(1 for r in rows if r[1] == "COMPLETED")

            workload   = sum(r[0] for r in rows if r[1] not in ("COMPLETED",))

            avg_effort = sum(r[0] for r in rows) / total

            return {

                "completion_rate"  : completed / total,

                "current_workload" : workload,

                "avg_effort"       : avg_effort

            }

        except Exception:

            return {"completion_rate": 0.75, "current_workload": 0.0, "avg_effort": 40.0}



    # ── Assign PARALLEL tasks: clone N copies, one per member ───────────────
    n_members = len(req.team_members)
    for task in parallel_tasks:
        per_member_effort = round(task["effort_hours"] / n_members, 1)
        for idx, member in enumerate(req.team_members):
            # Virtual task ID: base_id*1000 + member_index+1 for uniqueness
            virtual_id = task["task_id"] * 1000 + idx + 1
            comp_name = member_components.get(member, f"Component {chr(65+idx)}")
            assignments.append({
                "task_id"         : virtual_id,
                "task_name"       : f"[{comp_name}] {task['task_name']}",
                "assigned_to"     : member,
                "effort_hours"    : per_member_effort,
                "is_collaborative": False,
                "is_parallel"     : True,
                "confidence_pct"  : 100,
                "assign_method"   : "Parallel Component Split",
                "assign_reason"   : f"All {n_members} members do this task for their own component. Effort split equally: {task['effort_hours']}h / {n_members} = {per_member_effort}h each.",
                "component_name"  : comp_name,
            })
            member_workload[member] += per_member_effort

    # ── Assign SHARED tasks to ALL members ────────────────────────────────────

    for task in collab_tasks:

        per_member_effort = task["effort_hours"] / len(req.team_members)

        assignments.append({

            "task_id"         : task["task_id"],

            "task_name"       : task["task_name"],

            "assigned_to"     : "All Members",

            "effort_hours"    : task["effort_hours"],

            "is_collaborative": True,

            "is_parallel"     : False,

            "confidence_pct"  : 100,

            "assign_method"   : "Collaborative",

            "component_name"  : "Shared"

        })

        for m in req.team_members:

            member_workload[m] += per_member_effort



    # ── Assign individual tasks using Random Forest ML ────────────────────────

    # Model 5 feature schema (7 features, NO leaky deadline_days_remaining):

    #   [task_effort_estimate, task_category, task_complexity,

    #    member_completion_rate, member_current_workload,

    #    member_avg_effort, is_collaborative]

    import numpy as np

    for task in sorted_individual:

        task_name  = task["task_name"].lower()

        effort     = float(task["effort_hours"])



        # task_category: 1 = backend/bug/api/db (complex), 0 = feature/doc/design

        task_cat   = 1 if any(k in task_name for k in

                        ["backend", "api", "bug", "fix", "database",

                         "security", "server", "integration"]) else 0



        # task_complexity: effort-based ordinal (matches training schema)

        task_cmplx = 3 if effort > 80 else (2 if effort > 40 else 1)



        best_member     = None

        best_confidence = -1.0

        member_scores   = {}   # store all scores for the reason field

        overload_override = False



        if use_ml:

            # ── ML Path: score every member, pick highest on-time probability ──

            for member in req.team_members:

                stats = _get_member_stats(member)



                # member_current_workload: convert accumulated hours → task count

                # (training data used task count, not hours)

                avg_eff      = max(stats["avg_effort"], 1.0)

                hours_so_far = member_workload[member] + stats["current_workload"]

                task_count   = round(hours_so_far / avg_eff, 1)



                # Named DataFrame — matches FEATURES in train_workload_model.py exactly

                # WORKLOAD BALANCE STEP 3 - BUILD MODEL INPUT FOR EACH MEMBER
                # These column names exactly match train_workload_model.py.
                feat_df = pd.DataFrame([{

                    "task_effort_estimate"    : effort,

                    "task_category"           : float(task_cat),

                    "task_complexity"         : float(task_cmplx),

                    "member_completion_rate"  : stats["completion_rate"],

                    "member_current_workload" : task_count,

                    "member_avg_effort"       : stats["avg_effort"],

                    "is_collaborative"        : 0.0

                }])

                # Positive-class probability = predicted task-completion
                # suitability for this member.
                # MODEL CALCULATION - XGBOOST MEMBER SUITABILITY PROBABILITY
                prob = float(rf_model.predict_proba(feat_df)[0][1])  # completion proxy

                member_scores[member] = round(prob * 100, 1)

                if prob > best_confidence:

                    best_confidence = prob

                    best_member     = member



            # ── Overload guard: if RF winner already has 40% more load than

            # the least-loaded member, override to the least-loaded member.

            # This ensures all team members receive tasks.

            # WORKLOAD BALANCE STEP 4 - PER-TASK OVERLOAD GUARD
            # Override the ML winner when it already carries over 140% of the
            # least-loaded member's assigned effort.
            least_loaded = min(member_workload, key=member_workload.get)

            if best_member and member_workload[best_member] > member_workload[least_loaded] * 1.40:

                overload_override = True

                rf_chosen   = best_member

                best_member = least_loaded

                best_confidence = 0.60   # conservative confidence



            confidence_pct = round(best_confidence * 100, 1)



            # ── Build human-readable reason string ────────────────────────────

            scores_sorted = sorted(member_scores.items(), key=lambda x: x[1], reverse=True)

            scores_str = " | ".join([f"{m}: {s}%" for m, s in scores_sorted])

            if overload_override:

                assign_reason = (f"XGBoost selected {rf_chosen} (top completion score: {member_scores.get(rf_chosen,0)}%) "

                                 f"but Overload Guard triggered "

                                 f"(W={round(member_workload[rf_chosen],1)}h > W_min×1.40={round(member_workload[least_loaded]*1.40,1)}h). "

                                 f"Override → {best_member} (least loaded: {round(member_workload[best_member],1)}h). "

                                 f"All scores: [{scores_str}]")

            else:

                assign_reason = (f"XGBoost classifier selected {best_member} with highest completion score={confidence_pct}%. "

                                 f"All member scores: [{scores_str}]. "

                                 f"Overload Guard: OK (no override needed).")

        else:

            # ── LPT Fallback: assign to least loaded member ────────────────────

            best_member    = min(member_workload, key=member_workload.get)

            confidence_pct = None  # no calibrated student-suitability confidence

            assign_reason  = f"LPT assignment; no validated student-suitability model. Assigned to least-loaded member: {best_member} ({round(member_workload[best_member],1)}h)"



        member_workload[best_member] += effort

        comp_name = member_components.get(best_member, "Component A") if not is_solo else ""

        assignments.append({

            "task_id"         : task["task_id"],

            "task_name"       : task["task_name"],

            "assigned_to"     : best_member,

            "effort_hours"    : effort,

            "is_collaborative": False,

            "is_parallel"     : False,

            "confidence_pct"  : confidence_pct,

            "assign_method"   : assign_method,

            "assign_reason"   : assign_reason,

            "component_name"  : comp_name

        })

    # WORKLOAD BALANCE STEP 5 - VALIDATE AND REBALANCE COMPLETE ALLOCATION
    # A per-task check cannot guarantee the completed allocation. Run a final
    # whole-task optimization and then calculate the authoritative verdict.
    pre_rebalance_balance = calculate_workload_balance(member_workload)
    final_rebalance_moves = rebalance_final_assignments(
        assignments, member_workload, member_components
    )
    final_balance = calculate_workload_balance(member_workload)



    # ── Persist to database ───────────────────────────────────────────────────

    # WORKLOAD BALANCE STEP 6 - SAVE FINAL TASK OWNERS TO POSTGRESQL
    conn = get_db_connection()
    balanced_schedule = []
    schedule_version = None
    try:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (req.project_id,))
        # Lock the latest version so concurrent assignment requests cannot
        # allocate the same next version or silently overwrite the draft.
        latest_schedule_row = conn.execute(
            """SELECT id, version, schedule_json FROM schedule_versions
               WHERE project_id=? ORDER BY version DESC, id DESC LIMIT 1 FOR UPDATE""",
            (req.project_id,),
        ).fetchone()
        if not latest_schedule_row:
            raise HTTPException(status_code=409, detail="Generate a project schedule before assigning tasks.")
        try:
            stored_payload = json.loads(latest_schedule_row[2])
        except (TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=409, detail="The saved schedule is invalid.") from exc
        stored_schedule = stored_payload.get("schedule") if isinstance(stored_payload, dict) else stored_payload
        if not isinstance(stored_schedule, list):
            raise HTTPException(status_code=409, detail="The saved schedule has no task list.")
        if any(str(item.get("assignment_stage", "")).upper() == "BALANCED" for item in stored_schedule):
            raise HTTPException(
                status_code=409,
                detail="This schedule is already balanced. Generate a new draft or use the reviewed reassignment workflow.",
            )
        saved_tasks = {int(item["task_id"]): item for item in stored_schedule}
        submitted_tasks = {int(item["task_id"]): item for item in req.tasks}
        if len(submitted_tasks) != len(req.tasks) or saved_tasks.keys() != submitted_tasks.keys():
            raise HTTPException(status_code=409, detail="Tasks have changed. Reload the latest schedule before balancing.")
        for task_id, submitted in submitted_tasks.items():
            saved = saved_tasks[task_id]
            if (str(submitted["task_name"]).strip() != str(saved.get("task_name", "")).strip()
                    or abs(float(submitted["effort_hours"]) - float(saved.get("effort_hours", 0))) > 0.11):
                raise HTTPException(status_code=409, detail="Tasks have changed. Reload the latest schedule before balancing.")

        balanced_schedule = _apply_workload_assignments_to_schedule(stored_schedule, assignments)
        if isinstance(stored_payload, dict):
            stored_payload = dict(stored_payload)
            stored_payload["schedule"] = balanced_schedule
        else:
            stored_payload = balanced_schedule
        schedule_version = int(latest_schedule_row[1]) + 1
        assigned_at = datetime.now().isoformat()
        for assignment in assignments:
            conn.execute(
                """INSERT INTO task_assignments
                   (project_id, task_id, task_name, assigned_to, effort_hours, status, assigned_at)
                   VALUES (?, ?, ?, ?, ?, 'NOT_STARTED', ?)
                   ON CONFLICT(project_id, task_id) DO UPDATE SET
                     assigned_to=excluded.assigned_to,
                     task_name=excluded.task_name,
                     effort_hours=excluded.effort_hours,
                     assigned_at=excluded.assigned_at""",
                (req.project_id, assignment["task_id"], assignment["task_name"],
                 assignment["assigned_to"], assignment["effort_hours"], assigned_at),
            )
        for task in shared_tasks:
            per_effort = task["effort_hours"] / len(req.team_members)
            for idx, member in enumerate(req.team_members):
                conn.execute(
                    """INSERT INTO task_assignments
                       (project_id, task_id, task_name, assigned_to, effort_hours, status, assigned_at)
                       VALUES (?, ?, ?, ?, ?, 'NOT_STARTED', ?)
                       ON CONFLICT(project_id, task_id) DO UPDATE SET
                         assigned_to=excluded.assigned_to,
                         task_name=excluded.task_name,
                         effort_hours=excluded.effort_hours,
                         assigned_at=excluded.assigned_at""",
                    (req.project_id, task["task_id"] * 10000 + idx + 1,
                     task["task_name"], member, per_effort, assigned_at),
                )
        # Preserve the unassigned version and add an immutable balanced version.
        conn.execute(
            """INSERT INTO schedule_versions (project_id, version, schedule_json, created_at, team_members_json)
               VALUES (?, ?, ?, ?, ?)""",
            (req.project_id, schedule_version, json.dumps(stored_payload), assigned_at,
             json.dumps(req.team_members)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # ── Workload summary ──────────────────────────────────────────────────────

    workload_summary = [

        {

            "member": name,

            "total_effort_hours": round(hours, 1),

            "individual_tasks": sum(1 for a in assignments if a["assigned_to"] == name),

            "collaborative_tasks": len(collab_tasks)

        }

        for name, hours in sorted(member_workload.items(), key=lambda x: x[1], reverse=True)

    ]



    # ── Balance Score: Coefficient of Variation (CV%) ────────────────────────

    # CV = (std_dev / mean) × 100

    # CV = 0%  → perfect equality (everyone has identical hours)

    # CV < 15% → well balanced   (good distribution)

    # CV > 30% → poor balance    (someone is overloaded)

    mean_hours = final_balance["mean_hours"]
    cv_percent = final_balance["cv_percent"]
    balance_score_pct = final_balance["balance_score_pct"]
    max_deviation_hours = final_balance["max_deviation_hours"]
    balance_label = final_balance["balance_label"]



    # ── Build component summary for grouped UI ───────────────────────────────
    component_summary = []
    # Individual per-component tasks
    for member in req.team_members:
        comp_name = member_components.get(member, "Component")
        member_tasks = [a for a in assignments
                        if a["assigned_to"] == member and not a["is_collaborative"]]
        comp_effort = sum(a["effort_hours"] for a in member_tasks)
        component_summary.append({
            "member"        : member,
            "component_name": comp_name,
            "tasks"         : member_tasks,
            "total_effort"  : round(comp_effort, 1),
            "completed"     : 0,
            "progress_pct"  : 0,
        })
    # Shared tasks section
    shared_assignments = [a for a in assignments if a["is_collaborative"]]
    shared_effort = sum(a["effort_hours"] for a in shared_assignments)
    component_summary.append({
        "member"        : "All Members",
        "component_name": "Shared Tasks",
        "tasks"         : shared_assignments,
        "total_effort"  : round(shared_effort, 1),
        "completed"     : 0,
        "progress_pct"  : 0,
    })

    return {

        "status"              : "auto-assigned",

        "assign_method"       : assign_method,

        "assignments"         : assignments,

        "schedule"            : balanced_schedule,
        "schedule_version"    : schedule_version,

        "workload_summary"    : workload_summary,

        "collaborative_count" : len(shared_tasks),  # original input task list

        "parallel_count"      : len(parallel_tasks),

        "individual_count"    : len(role_tasks),

        "balance_score_pct"   : balance_score_pct,

        "cv_percent"          : cv_percent,

        "mean_effort_hours"   : round(mean_hours, 1),

        "max_deviation_hours" : max_deviation_hours,

        "balance_label"       : balance_label,

        "cv_balance_label"    : final_balance["cv_balance_label"],

        "max_to_min_ratio"    : (None if final_balance["max_to_min_ratio"] is None
                                  else round(final_balance["max_to_min_ratio"], 3)),

        "overload_threshold_ratio": WORKLOAD_OVERLOAD_RATIO,

        "overload_detected"   : final_balance["overload_detected"],

        "pre_rebalance_overload_detected": pre_rebalance_balance["overload_detected"],

        "final_rebalance_moves": final_rebalance_moves,

        "fairness_method"     : ("Experimental issue-status proxy + load guard + whole-task rebalancing"
                                 if use_ml else "LPT + final whole-task overload validation"),

        "component_summary"   : component_summary,

        "member_components"   : member_components,

        "is_solo"             : is_solo

    }



# --- BACKGROUND DEADLINE CHECKER ---

def check_deadlines():
    conn = None
    try:
        conn = get_db_connection()
        c = conn.cursor()
        projects = c.execute(
            """SELECT DISTINCT ON (project_id) project_id, schedule_json
               FROM schedule_versions ORDER BY project_id, id DESC"""
        ).fetchall()
        today = datetime.today().date()

        for project_id, schedule_json in projects:
            try:
                stored = json.loads(schedule_json)
                tasks = stored.get("schedule") if isinstance(stored, dict) else stored
                if not isinstance(tasks, list):
                    raise ValueError("schedule is not a task list")
            except (TypeError, ValueError) as exc:
                print(f"Deadline checker skipped invalid schedule for {project_id}: {exc}", flush=True)
                continue

            for task in tasks:
                if not isinstance(task, dict):
                    continue
                if str(task.get("status", "")).upper() == "COMPLETED":
                    continue
                try:
                    task_id = int(task["task_id"])
                    task_name = str(task["task_name"]).strip()
                    end_date = datetime.fromisoformat(str(task["end_date"])).date()
                    if not task_name:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue

                days_left = (end_date - today).days
                if days_left > 3:
                    continue
                existing = c.execute(
                    "SELECT id FROM notifications WHERE project_id=? AND task_id=? AND is_read=0",
                    (project_id, task_id),
                ).fetchone()
                if existing:
                    continue
                notification_type = "OVERDUE" if days_left < 0 else "WARNING"
                message = (
                    f"OVERDUE: '{task_name}' was due {abs(days_left)} day(s) ago. Reschedule immediately."
                    if days_left < 0 else
                    f"WARNING: '{task_name}' is due in {days_left} day(s). No submission detected."
                )
                c.execute(
                    """INSERT INTO notifications
                       (project_id, task_id, task_name, type, message, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (project_id, task_id, task_name, notification_type,
                     message, datetime.now().isoformat()),
                )
        conn.commit()
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        print(f"Deadline checker error: {exc}", flush=True)
    finally:
        if conn is not None:
            conn.close()



scheduler = BackgroundScheduler()

scheduler.add_job(
    check_deadlines, 'interval', hours=6, id='deadline_checker',
    next_run_time=datetime.now() + timedelta(seconds=5),
)


# ═══════════════════════════════════════════════════════════════════════════════
#  ACADEMIC EVENT AUTO-SCHEDULER  (Novelty — Intelligent Scheduling)
# ═══════════════════════════════════════════════════════════════════════════════

import io
import openpyxl
from datetime import datetime, timedelta, date
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
# (UploadFile, File, Form, Request already imported at top)

# ── Lazy-load sentence-transformer (downloads ~80MB on first use) ────────────
_sentence_model = None

def _get_sentence_model():
    global _sentence_model
    if _sentence_model is None:
        if os.getenv("ENABLE_SENTENCE_TRANSFORMER", "0").strip().lower() not in {"1", "true", "yes"}:
            _sentence_model = "tfidf"
            return _sentence_model
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("  -> Sentence Transformer (MiniLM) loaded for supervisor matching.", flush=True)
        except Exception as e:
            print(f"  -> Sentence Transformer unavailable ({e}), using TF-IDF fallback.", flush=True)
            _sentence_model = "tfidf"
    return _sentence_model


# USED ALGORITHEMS - EXPERTISE SIMILARITY MATCHING
# Compares the research topic with supervisor expertise using MiniLM embeddings
# when enabled, or TF-IDF cosine similarity as the local fallback.
def _compute_similarity(text_a: str, text_b: str, model) -> float:
    """Return cosine similarity [0,1] between two texts."""
    text_a, text_b = (text_a or "").strip(), (text_b or "").strip()
    if not text_a or not text_b:
        return 0.0
    try:
        if model == "tfidf":
            vec = TfidfVectorizer().fit_transform([text_a, text_b])
            # MODEL CALCULATION - TF-IDF EXPERTISE COSINE SIMILARITY
            return float(cosine_similarity(vec[0], vec[1])[0][0])
        emb = model.encode([text_a, text_b])
        # MODEL CALCULATION - MINILM EXPERTISE COSINE SIMILARITY
        return float(cosine_similarity([emb[0]], [emb[1]])[0][0])
    except (ValueError, TypeError):
        return 0.0


def _parse_dates(dates_str: str):
    """Parse comma-separated date strings into a set of date objects."""
    out = set()
    if isinstance(dates_str, (datetime, date)):
        return {dates_str.date() if isinstance(dates_str, datetime) else dates_str}
    for d in re.split(r"[,;\n]+", str(dates_str or "")):
        d = d.strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                out.add(datetime.strptime(d, fmt).date())
                break
            except ValueError:
                pass
    return out


def _parse_time_range(time_str: str):
    """Return (start_time_str, end_time_str) from '09:00-12:00'."""
    value = str(time_str or "").strip()
    if not value:
        return "09:00", "17:00"
    match = re.fullmatch(
        r"\s*(\d{1,2}:\d{2})(?::\d{2})?\s*-\s*(\d{1,2}:\d{2})(?::\d{2})?\s*",
        value,
    )
    if not match:
        raise ValueError(f"Invalid time range: {value}")
    start, end = match.groups()
    # Validate the actual clock values now rather than silently accepting them.
    datetime.strptime(start, "%H:%M")
    datetime.strptime(end, "%H:%M")
    return start.zfill(5), end.zfill(5)


def _times_overlap(start1, end1, start2, end2) -> bool:
    """Check if two HH:MM time ranges overlap."""
    def t(s): return datetime.strptime(s, "%H:%M")
    return t(start1) < t(end2) and t(start2) < t(end1)


# ── Upload Supervisors Excel ──────────────────────────────────────────────────
@app.post("/api/academic/upload-supervisors")
async def upload_supervisors(
    file: UploadFile = File(...),
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    conn = None
    try:
        content = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE supervisors SET active=FALSE")

        inserted = 0
        for row in rows:
            if not row or not row[0]:
                continue
            name        = str(row[0] or "").strip()
            email       = str(row[1] or "").strip()
            expertise   = str(row[2] or "").strip()
            avail_dates = str(row[3] or "").strip()
            avail_times = str(row[4] or "09:00-17:00").strip()
            # Column 6: Role — Professor / Doctor / Lecturer / Instructor
            role        = str(row[5] or "Professor").strip() if len(row) > 5 else "Professor"
            existing = c.execute(
                """SELECT id FROM supervisors
                   WHERE (email<>'' AND LOWER(email)=LOWER(?)) OR LOWER(name)=LOWER(?)
                   ORDER BY id LIMIT 1""",
                (email, name),
            ).fetchone()
            if existing:
                supervisor_id = int(existing[0])
                c.execute(
                    """UPDATE supervisors SET name=?, email=?, expertise=?, available_dates=?,
                              available_times=?, role=?, uploaded_at=?, active=TRUE WHERE id=?""",
                    (name, email, expertise, avail_dates, avail_times, role,
                     datetime.now().isoformat(), supervisor_id),
                )
            else:
                c.execute(
                    """INSERT INTO supervisors
                       (name,email,expertise,available_dates,available_times,role,uploaded_at)
                       VALUES (?,?,?,?,?,?,?) RETURNING id""",
                    (name, email, expertise, avail_dates, avail_times, role, datetime.now().isoformat()),
                )
                supervisor_id = int(c.fetchone()[0])
            c.execute("DELETE FROM staff_availability WHERE supervisor_id=?", (supervisor_id,))
            start_time, end_time = _parse_time_range(avail_times)
            if _minutes(end_time) <= _minutes(start_time):
                raise ValueError(f"Invalid availability time for {name}: {avail_times}")
            for available_date in sorted(_parse_dates(avail_dates)):
                c.execute(
                    """INSERT INTO staff_availability
                       (supervisor_id, available_date, start_time, end_time)
                       VALUES (?,?,?,?) ON CONFLICT DO NOTHING""",
                    (supervisor_id, available_date, start_time, end_time),
                )
            inserted += 1

        conn.commit()
        conn.close()
        return {"status": "ok", "supervisors_loaded": inserted}
    except Exception as exc:
        if conn is not None:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=422, detail=f"Supervisor workbook is invalid: {exc}") from exc


# ── Upload Halls Excel ────────────────────────────────────────────────────────
@app.post("/api/academic/upload-halls")
async def upload_halls(
    file: UploadFile = File(...),
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    conn = None
    try:
        content = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE halls SET active=FALSE")

        inserted = 0
        for row in rows:
            if not row or not row[0]:
                continue
            hall_name  = str(row[0] or "").strip()
            capacity   = int(row[1]) if row[1] is not None else 0
            if capacity <= 0:
                raise ValueError(f"Hall capacity must be positive for {hall_name}.")
            floor_bld  = str(row[2] or "").strip()
            avail_dates= str(row[3] or "").strip()
            avail_times= str(row[4] or "09:00-17:00").strip()
            existing = c.execute(
                "SELECT id FROM halls WHERE LOWER(hall_name)=LOWER(?) ORDER BY id LIMIT 1",
                (hall_name,),
            ).fetchone()
            if existing:
                hall_id = int(existing[0])
                c.execute(
                    """UPDATE halls SET capacity=?, floor_building=?, available_dates=?,
                              available_times=?, uploaded_at=?, active=TRUE WHERE id=?""",
                    (capacity, floor_bld, avail_dates, avail_times,
                     datetime.now().isoformat(), hall_id),
                )
            else:
                c.execute(
                    """INSERT INTO halls
                       (hall_name,capacity,floor_building,available_dates,available_times,uploaded_at)
                       VALUES (?,?,?,?,?,?) RETURNING id""",
                    (hall_name, capacity, floor_bld, avail_dates, avail_times, datetime.now().isoformat()),
                )
                hall_id = int(c.fetchone()[0])
            c.execute("DELETE FROM hall_availability WHERE hall_id=?", (hall_id,))
            start_time, end_time = _parse_time_range(avail_times)
            if _minutes(end_time) <= _minutes(start_time):
                raise ValueError(f"Invalid availability time for {hall_name}: {avail_times}")
            for available_date in sorted(_parse_dates(avail_dates)):
                c.execute(
                    """INSERT INTO hall_availability
                       (hall_id, available_date, start_time, end_time)
                       VALUES (?,?,?,?) ON CONFLICT DO NOTHING""",
                    (hall_id, available_date, start_time, end_time),
                )
            inserted += 1

        conn.commit()
        conn.close()
        return {"status": "ok", "halls_loaded": inserted}
    except Exception as exc:
        if conn is not None:
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=422, detail=f"Hall workbook is invalid: {exc}") from exc


# ── Get current project info (for Academic Scheduler auto-fill) ───────────────
@app.get("/api/academic/current-project")
def get_current_project(
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT group_id, research_topic, supervisor_name, updated_at FROM current_project ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"found": False, "group_id": "", "research_topic": "", "supervisor_name": ""}
    return {
        "found": True,
        "group_id": row[0] or "",
        "research_topic": row[1] or "",
        "supervisor_name": row[2] or "",
        "updated_at": row[3] or ""
    }


# ── Get uploaded supervisors and halls (for preview) ─────────────────────────
@app.get("/api/academic/supervisors")
def get_supervisors(
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, name, email, expertise, available_dates, available_times, role FROM supervisors WHERE active=TRUE"
    ).fetchall()
    conn.close()
    return [{"id":r[0],"name":r[1],"email":r[2],"expertise":r[3],
             "available_dates":r[4],"available_times":r[5],"role":r[6] or "Professor"} for r in rows]

@app.get("/api/academic/halls")
def get_halls(
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    conn = get_db_connection()
    rows = conn.execute("SELECT id,hall_name,capacity,floor_building,available_dates,available_times FROM halls WHERE active=TRUE").fetchall()
    conn.close()
    return [{"id":r[0],"hall_name":r[1],"capacity":r[2],"floor":r[3],"available_dates":r[4],"available_times":r[5]} for r in rows]


ACADEMIC_EVENT_TYPES = ("Proposal Presentation", "PP1", "PP2", "Viva")


def _availability_window(conn, resource_type: str, resource_id: int, candidate_date,
                         legacy_dates: str, legacy_time: str) -> tuple[str, str] | None:
    """Prefer normalized PostgreSQL availability, falling back for legacy imports."""
    if resource_type == "staff":
        table, id_column = "staff_availability", "supervisor_id"
    elif resource_type == "hall":
        table, id_column = "hall_availability", "hall_id"
    else:
        raise ValueError("Unknown academic resource type")
    rows = conn.execute(
        f"SELECT available_date, start_time, end_time FROM {table} "
        f"WHERE {id_column}=? AND is_available=TRUE ORDER BY available_date, start_time",
        (resource_id,),
    ).fetchall()
    if rows:
        for available_date, start_time, end_time in rows:
            if available_date == candidate_date:
                return str(start_time)[:5], str(end_time)[:5]
        return None
    allowed_dates = _parse_dates(legacy_dates or "")
    if allowed_dates and candidate_date not in allowed_dates:
        return None
    return _parse_time_range(legacy_time or "09:00-17:00")


def _load_academic_groups(conn, supplied_groups) -> list[dict]:
    groups = supplied_groups or []
    if not groups:
        rows = conn.execute(
            """SELECT group_id, research_topic, updated_at FROM current_project
               WHERE group_id IS NOT NULL AND group_id <> ''
               ORDER BY updated_at DESC, id DESC"""
        ).fetchall()
        seen = set()
        for group_id, topic, _ in rows:
            if group_id in seen:
                continue
            seen.add(group_id)
            groups.append({"group_id": group_id, "topic": topic})

    normalized = []
    seen = set()
    for group in groups:
        group_id = str(group.get("group_id", "")).strip()
        if not group_id or group_id in seen:
            continue
        seen.add(group_id)
        normalized.append({
            "group_id": group_id,
            "topic": str(group.get("topic") or group.get("research_topic") or "software engineering").strip(),
            "team_size": group.get("team_size"),
        })
    return normalized


def _academic_required_seats(team_size: int, audience_seats: int = 0) -> int:
    """Reserve seats for the four-person panel, the team and any audience."""
    if not 1 <= team_size <= 100 or not 0 <= audience_seats <= 1000:
        raise ValueError("Team size must be 1–100 and audience seats 0–1000.")
    return 4 + team_size + audience_seats


def _hall_has_capacity(capacity, required_seats: int) -> bool:
    try:
        return int(capacity) >= required_seats
    except (TypeError, ValueError):
        return False


def _academic_event_required_seats(conn, batch_id: int | None, group_id: str) -> int:
    """Read the capacity policy saved with a draft; support older batches."""
    row = conn.execute(
        "SELECT configuration_json FROM academic_schedule_batches WHERE id=?", (batch_id,)
    ).fetchone() if batch_id is not None else None
    try:
        config = json.loads(row[0]) if row and row[0] else {}
        team_size = int(config.get("group_team_sizes", {}).get(group_id, config.get("default_team_size", 4)))
        audience = int(config.get("audience_seats", 0))
        return _academic_required_seats(team_size, audience)
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=409, detail="The event batch has an invalid seating policy.") from exc


def _active_academic_batch_id(conn) -> int | None:
    """Return the published schedule, or the newest draft when none is published."""
    row = conn.execute(
        """SELECT id FROM academic_schedule_batches
           ORDER BY CASE status WHEN 'PUBLISHED' THEN 0 WHEN 'DRAFT' THEN 1 ELSE 2 END,
                    version DESC LIMIT 1"""
    ).fetchone()
    return int(row[0]) if row else None


def _academic_event_snapshot(conn, event_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, batch_id, event_type, group_id, supervisor_name, hall_id,
                  hall_name, scheduled_date, scheduled_time, status, notes
           FROM academic_events WHERE id=?""",
        (event_id,),
    ).fetchone()
    if not row:
        return None
    keys = ["id", "batch_id", "event_type", "group_id", "supervisor_name", "hall_id",
            "hall_name", "scheduled_date", "scheduled_time", "status", "notes"]
    return dict(zip(keys, row))


def _audit_academic_event(conn, event_id: int, batch_id: int | None, action: str,
                          actor: str, before: dict | None, after: dict | None,
                          reason: str = "") -> None:
    conn.execute(
        """INSERT INTO academic_event_audit
           (event_id, batch_id, action, actor, before_json, after_json, reason)
           VALUES (?,?,?,?,?,?,?)""",
        (event_id, batch_id, action, actor,
         json.dumps(before, default=str) if before else None,
         json.dumps(after, default=str) if after else None, reason),
    )


# ── Auto-Schedule All Groups (Proposal, PP1, PP2, Viva; 4-member panel) ──────
# USED ALGORITHEMS - CONSTRAINT-BASED ACADEMIC SCHEDULING
# Assigns four-role panels and halls while enforcing staff/hall availability,
# preventing booking overlaps, balancing panel load, and matching expertise.
@app.post("/api/academic/auto-schedule")
async def auto_schedule(
    request: Request,
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    body = await request.json()
    start_date_str = str(body.get("start_date", "")).strip()
    duration_min = int(body.get("duration_minutes", 60))
    weeks = [
        int(body.get("proposal_week", 2)),
        int(body.get("pp1_week", 8)),
        int(body.get("pp2_week", 14)),
        int(body.get("viva_week", 20)),
    ]
    try:
        base_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="A valid project start date is required.")
    if duration_min < 30 or duration_min > 240:
        raise HTTPException(status_code=422, detail="Event duration must be between 30 and 240 minutes.")
    if any(week < 1 or week > 52 for week in weeks) or weeks != sorted(set(weeks)):
        raise HTTPException(
            status_code=422,
            detail="Proposal, PP1, PP2 and Viva weeks must be unique, increasing values from 1 to 52.",
        )
    try:
        default_team_size = int(body.get("default_team_size", 4))
        audience_seats = int(body.get("audience_seats", 0))
        _academic_required_seats(default_team_size, audience_seats)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Team size must be 1–100 and audience seats 0–1000.") from exc

    conn = get_db_connection()
    try:
        groups = _load_academic_groups(conn, body.get("groups"))
        if not groups:
            raise HTTPException(
                status_code=422,
                detail="No project groups are available. Generate a project schedule first or supply groups.",
            )
        try:
            group_team_sizes = {
                group["group_id"]: int(
                    default_team_size if group["team_size"] is None else group["team_size"]
                )
                for group in groups
            }
            for size in group_team_sizes.values():
                _academic_required_seats(size, audience_seats)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Each group's team size must be 1–100.") from exc

        supervisors = conn.execute(
            """SELECT id, name, expertise, available_dates, available_times, role, email
               FROM supervisors WHERE active=TRUE ORDER BY id"""
        ).fetchall()
        halls = conn.execute(
            """SELECT id, hall_name, available_dates, available_times, capacity
               FROM halls WHERE active=TRUE ORDER BY id"""
        ).fetchall()
        if not supervisors:
            raise HTTPException(status_code=422, detail="No supervisors uploaded.")
        if not halls:
            raise HTTPException(status_code=422, detail="No halls uploaded.")

        role_counts = {
            role: sum(1 for supervisor in supervisors if _academic_role_key(supervisor[5]) == role)
            for role in ("prof_dr", "lecturer", "instructor")
        }
        missing_roles = []
        if role_counts["prof_dr"] < 2:
            missing_roles.append("2 Professors/Doctors")
        if role_counts["lecturer"] < 1:
            missing_roles.append("1 Lecturer")
        if role_counts["instructor"] < 1:
            missing_roles.append("1 Instructor")
        if missing_roles:
            raise HTTPException(
                status_code=422,
                detail="A complete four-member panel requires " + ", ".join(missing_roles) + ".",
            )

        model = _get_sentence_model()
        cursor = conn.cursor()
        # Serialize version allocation so simultaneous generation requests cannot
        # receive the same PostgreSQL version number.
        cursor.execute("SELECT pg_advisory_xact_lock(72469321)")
        version_row = cursor.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM academic_schedule_batches"
        ).fetchone()
        batch_version = int(version_row[0])
        cursor.execute(
            """INSERT INTO academic_schedule_batches
               (version, status, start_date, configuration_json, created_by)
               VALUES (?, 'DRAFT', ?, ?, ?) RETURNING id""",
            (batch_version, base_date, json.dumps({
                "proposal_week": weeks[0], "pp1_week": weeks[1],
                "pp2_week": weeks[2], "viva_week": weeks[3],
                "duration_minutes": duration_min,
                "default_team_size": default_team_size,
                "group_team_sizes": group_team_sizes,
                "audience_seats": audience_seats,
                "panel_seats": 4,
            }), _user.username),
        )
        batch_id = int(cursor.fetchone()[0])
        hall_bookings: dict[tuple[int, str], list[tuple[int, int]]] = {}
        person_bookings: dict[tuple[str, str], list[tuple[int, int]]] = {}
        panel_loads: dict[int, int] = {int(supervisor[0]): 0 for supervisor in supervisors}
        hall_loads: dict[int, int] = {int(hall[0]): 0 for hall in halls}
        output = []

        for group in groups:
            required_seats = _academic_required_seats(
                group_team_sizes[group["group_id"]], audience_seats
            )
            # MODEL CALCULATION - PANEL EXPERTISE SCORE WITH LOAD PENALTY
            scored = sorted(
                [(_compute_similarity(group["topic"], supervisor[2], model), supervisor) for supervisor in supervisors],
                key=lambda item: (
                    -(item[0] - 0.04 * panel_loads[int(item[1][0])]),
                    panel_loads[int(item[1][0])], item[1][1].lower(),
                ),
            )
            panel_scored = select_academic_panel(scored)
            panel_staff = [item[1] for item in panel_scored]
            best_score, primary = max(panel_scored, key=lambda item: item[0])
            for person in panel_staff:
                panel_loads[int(person[0])] += len(ACADEMIC_EVENT_TYPES)

            for event_type, week in zip(ACADEMIC_EVENT_TYPES, weeks):
                target_date = base_date + timedelta(weeks=week - 1)
                chosen = None
                for offset in range(21):
                    candidate = target_date + timedelta(days=offset)
                    candidate_str = candidate.isoformat()
                    person_windows = [
                        _availability_window(conn, "staff", person[0], candidate, person[3], person[4])
                        for person in panel_staff
                    ]
                    if any(window is None for window in person_windows):
                        continue
                    for hall in sorted(halls, key=lambda item: (hall_loads[int(item[0])], item[1].lower())):
                        # Missing or undersized capacity cannot be accepted as a
                        # feasible academic event room.
                        if not _hall_has_capacity(hall[4], required_seats):
                            continue
                        hall_window = _availability_window(
                            conn, "hall", hall[0], candidate, hall[2], hall[3]
                        )
                        if hall_window is None:
                            continue
                        # MODEL CALCULATION - COMMON STAFF/HALL AVAILABILITY WINDOW
                        start_minute = max(_minutes(window[0]) for window in [*person_windows, hall_window])
                        end_minute = min(_minutes(window[1]) for window in [*person_windows, hall_window])
                        slot = start_minute
                        while slot + duration_min <= end_minute:
                            slot_end = slot + duration_min
                            hall_key = (hall[0], candidate_str)
                            people_free = all(
                                _interval_free(
                                    person_bookings.get((person[1].strip().lower(), candidate_str), []),
                                    slot,
                                    slot_end,
                                )
                                for person in panel_staff
                            )
                            if _interval_free(hall_bookings.get(hall_key, []), slot, slot_end) and people_free:
                                chosen = (candidate_str, slot, slot_end, hall)
                                break
                            slot += 30
                        if chosen:
                            break
                    if chosen:
                        break

                if chosen:
                    scheduled_date, start_minute, end_minute, hall = chosen
                    scheduled_time = f"{_clock(start_minute)} - {_clock(end_minute)}"
                    hall_id, hall_name = hall[0], hall[1]
                    status = "Scheduled"
                    notes = f"Conflict-checked; hall capacity covers {required_seats} seats."
                    hall_bookings.setdefault((hall_id, scheduled_date), []).append((start_minute, end_minute))
                    hall_loads[int(hall_id)] += 1
                    for person in panel_staff:
                        person_bookings.setdefault((person[1].strip().lower(), scheduled_date), []).append(
                            (start_minute, end_minute)
                        )
                else:
                    scheduled_date, scheduled_time = target_date.isoformat(), ""
                    hall_id, hall_name = None, "TBD"
                    status = "Unscheduled"
                    notes = (
                        f"No hall with at least {required_seats} seats and a common, conflict-free "
                        "panel/hall slot was found within 21 days."
                    )

                cursor.execute(
                    """INSERT INTO academic_events
                       (event_type, group_id, group_topic, supervisor_id, supervisor_name,
                        match_score, hall_id, hall_name, scheduled_date, scheduled_time,
                        duration_minutes, status, notes, created_at, batch_id, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())""",
                    (
                        event_type, group["group_id"], group["topic"], primary[0], primary[1],
                        round(best_score, 4), hall_id, hall_name, scheduled_date, scheduled_time,
                        duration_min, status, notes, datetime.now().isoformat(), batch_id,
                    ),
                )
                event_id = cursor.lastrowid
                panel = []
                for person in panel_staff:
                    role_label = _academic_role_label(person[5])
                    cursor.execute(
                        """INSERT INTO event_panel_members
                           (event_id, member_name, member_role, member_email) VALUES (?,?,?,?)""",
                        (event_id, person[1], role_label, person[6]),
                    )
                    panel.append({"name": person[1], "role": role_label, "email": person[6] or ""})
                output.append({
                    "id": event_id,
                    "group_id": group["group_id"],
                    "event_type": event_type,
                    "supervisor": primary[1],
                    "match_score_pct": round(best_score * 100, 1),
                    "hall": hall_name,
                    "date": scheduled_date,
                    "time": scheduled_time,
                    "status": status,
                    "notes": notes,
                    "required_seats": required_seats,
                    "panel": panel,
                })

        scheduled_count = sum(1 for event in output if event["status"] == "Scheduled")
        conn.execute(
            """INSERT INTO academic_event_audit
               (batch_id, action, actor, after_json, reason) VALUES (?,?,?,?,?)""",
            (batch_id, "GENERATE", _user.username, json.dumps({
                "version": batch_version, "events_created": len(output),
                "scheduled_count": scheduled_count,
                "unscheduled_count": len(output) - scheduled_count,
            }), "Generated a new conflict-checked draft schedule."),
        )
        conn.commit()
        return {
            "status": "ok",
            "batch_id": batch_id,
            "batch_version": batch_version,
            "batch_status": "DRAFT",
            "groups_scheduled": len(groups),
            "events_created": len(output),
            "scheduled_count": scheduled_count,
            "unscheduled_count": len(output) - scheduled_count,
            "schedule": output,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Get All Academic Events (with panel members) ──────────────────────────────
@app.get("/api/academic/events")
def get_academic_events(
    batch_id: int | None = Query(default=None, ge=1),
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    conn = get_db_connection()
    selected_batch_id = batch_id if batch_id is not None else _active_academic_batch_id(conn)
    where_sql = "WHERE batch_id=?" if selected_batch_id is not None else "WHERE batch_id IS NULL"
    rows = conn.execute(
        f"""SELECT id, event_type, group_id, group_topic, supervisor_name, match_score,
                   hall_name, scheduled_date, scheduled_time, duration_minutes, status, notes,
                   batch_id
            FROM academic_events {where_sql} ORDER BY scheduled_date, scheduled_time""",
        (selected_batch_id,) if selected_batch_id is not None else (),
    ).fetchall()
    keys = ["id","event_type","group_id","group_topic","supervisor_name","match_score",
            "hall_name","scheduled_date","scheduled_time","duration_minutes","status","notes","batch_id"]
    result = []
    for r in rows:
        ev = dict(zip(keys, r))
        # Fetch panel members for this event
        panel = conn.execute(
            "SELECT member_name, member_role FROM event_panel_members WHERE event_id=? ORDER BY id",
            (ev["id"],)
        ).fetchall()
        ev["panel"] = [{"name": p[0], "role": p[1]} for p in panel]
        result.append(ev)
    conn.close()
    return result


@app.get("/api/academic/batches")
def get_academic_batches(
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT b.id, b.version, b.status, b.start_date, b.created_by, b.created_at,
                      b.published_by, b.published_at, COUNT(e.id),
                      COUNT(e.id) FILTER (WHERE e.status='Unscheduled')
               FROM academic_schedule_batches b
               LEFT JOIN academic_events e ON e.batch_id=b.id
               GROUP BY b.id ORDER BY b.version DESC"""
        ).fetchall()
        keys = ["id", "version", "status", "start_date", "created_by", "created_at",
                "published_by", "published_at", "event_count", "unscheduled_count"]
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


def _publish_academic_batch(batch_id: int, user: AuthenticatedUser, action: str):
    conn = get_db_connection()
    try:
        conn.execute("SELECT pg_advisory_xact_lock(72469322)")
        target = conn.execute(
            "SELECT id, version, status FROM academic_schedule_batches WHERE id=? FOR UPDATE",
            (batch_id,),
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Schedule version not found.")
        counts = conn.execute(
            """SELECT COUNT(*), COUNT(*) FILTER (WHERE status<>'Scheduled')
               FROM academic_events WHERE batch_id=?""",
            (batch_id,),
        ).fetchone()
        if counts[0] == 0:
            raise HTTPException(status_code=409, detail="An empty schedule version cannot be published.")
        incomplete = counts[1]
        if incomplete:
            raise HTTPException(
                status_code=409,
                detail=f"Version {target[1]} has {incomplete} unscheduled event(s). Resolve them before publishing.",
            )
        capacity_rows = conn.execute(
            """SELECT e.group_id, e.hall_name, h.capacity
               FROM academic_events e
               LEFT JOIN halls h ON h.id=e.hall_id
               WHERE e.batch_id=? AND e.status='Scheduled'""",
            (batch_id,),
        ).fetchall()
        for group_id, hall_name, capacity in capacity_rows:
            required_seats = _academic_event_required_seats(conn, batch_id, group_id)
            if not _hall_has_capacity(capacity, required_seats):
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot publish: hall {hall_name or 'TBD'} lacks {required_seats} seats for {group_id}.",
                )
        conn.execute(
            "UPDATE academic_schedule_batches SET status='ARCHIVED' WHERE status='PUBLISHED' AND id<>?",
            (batch_id,),
        )
        conn.execute(
            """UPDATE academic_schedule_batches SET status='PUBLISHED', published_by=?,
                      published_at=NOW() WHERE id=?""",
            (user.username, batch_id),
        )
        conn.execute(
            """INSERT INTO academic_event_audit
               (batch_id, action, actor, reason) VALUES (?,?,?,?)""",
            (batch_id, action, user.username, f"Published academic schedule version {target[1]}"),
        )
        conn.commit()
        return {"status": "ok", "batch_id": batch_id, "version": target[1], "batch_status": "PUBLISHED"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.post("/api/academic/batches/{batch_id}/publish")
def publish_academic_batch(
    batch_id: int,
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    return _publish_academic_batch(batch_id, _user, "PUBLISH")


@app.post("/api/academic/batches/{batch_id}/rollback")
def rollback_academic_batch(
    batch_id: int,
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    return _publish_academic_batch(batch_id, _user, "ROLLBACK")


@app.delete("/api/academic/batches/{batch_id}")
def delete_academic_draft(
    batch_id: int,
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT status FROM academic_schedule_batches WHERE id=? FOR UPDATE", (batch_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Schedule version not found.")
        if row[0] != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft schedule versions can be deleted.")
        conn.execute("DELETE FROM academic_schedule_batches WHERE id=?", (batch_id,))
        conn.commit()
        return {"status": "ok", "deleted_batch_id": batch_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.get("/api/academic/audit")
def get_academic_audit(
    batch_id: int | None = Query(default=None, ge=1),
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    conn = get_db_connection()
    try:
        selected_batch_id = batch_id if batch_id is not None else _active_academic_batch_id(conn)
        if selected_batch_id is None:
            return []
        rows = conn.execute(
            """SELECT id, event_id, action, actor, before_json, after_json, reason, created_at
               FROM academic_event_audit WHERE batch_id=? ORDER BY created_at DESC, id DESC
               LIMIT 250""",
            (selected_batch_id,),
        ).fetchall()
        return [{
            "id": row[0], "event_id": row[1], "action": row[2], "actor": row[3],
            "before": json.loads(row[4]) if row[4] else None,
            "after": json.loads(row[5]) if row[5] else None,
            "reason": row[6] or "", "created_at": row[7],
        } for row in rows]
    finally:
        conn.close()


@app.post("/api/academic/events/{event_id}/reschedule")
async def reschedule_academic_event(
    event_id: int,
    request: Request,
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    """Conflict-check and update one Proposal/PP/Viva event."""
    body = await request.json()
    new_date = str(body.get("new_date", "")).strip()
    new_time = str(body.get("new_time", "")).strip()
    new_hall = str(body.get("new_hall", "")).strip()
    try:
        candidate_date = datetime.strptime(new_date, "%Y-%m-%d").date()
        time_start, time_end = _parse_time_range(new_time)
        start_minute, end_minute = _minutes(time_start), _minutes(time_end)
        if end_minute <= start_minute:
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="Use a valid date and time range such as 09:00 - 10:00.",
        )
    if not new_hall:
        raise HTTPException(status_code=422, detail="Select a hall.")

    conn = get_db_connection()
    try:
        event = conn.execute(
            """SELECT e.id, e.supervisor_name, e.duration_minutes, e.batch_id,
                      COALESCE(b.status, 'DRAFT'), e.group_id
               FROM academic_events e
               LEFT JOIN academic_schedule_batches b ON b.id=e.batch_id
               WHERE e.id=? FOR UPDATE OF e""",
            (event_id,),
        ).fetchone()
        if not event:
            raise HTTPException(status_code=404, detail="Academic event not found.")
        if event[3] is not None:
            batch_status = conn.execute(
                "SELECT status FROM academic_schedule_batches WHERE id=? FOR UPDATE", (event[3],)
            ).fetchone()
            if not batch_status:
                raise HTTPException(status_code=409, detail="The event schedule version no longer exists.")
            event = (*event[:4], batch_status[0], event[5])
        if event[4] != "DRAFT":
            raise HTTPException(
                status_code=409,
                detail="Published or archived schedules are read-only. Generate a new draft before editing.",
            )
        before = _academic_event_snapshot(conn, event_id)
        if end_minute - start_minute < int(event[2] or 60):
            raise HTTPException(status_code=422, detail="The selected slot is shorter than the event duration.")

        hall = conn.execute(
            """SELECT id, hall_name, available_dates, available_times, capacity FROM halls
               WHERE active=TRUE AND LOWER(hall_name)=LOWER(?) LIMIT 1""",
            (new_hall,),
        ).fetchone()
        if not hall:
            raise HTTPException(status_code=422, detail="The selected hall does not exist.")
        required_seats = _academic_event_required_seats(conn, event[3], event[5])
        hall_window = _availability_window(conn, "hall", hall[0], candidate_date, hall[2], hall[3])
        conflicts = []
        if not _hall_has_capacity(hall[4], required_seats):
            conflicts.append({
                "type": "hall_capacity",
                "resource": hall[1],
                "message": f"Hall capacity is below the required {required_seats} seats.",
            })
        if hall_window is None or start_minute < _minutes(hall_window[0]) or end_minute > _minutes(hall_window[1]):
            conflicts.append({
                "type": "hall_availability",
                "resource": hall[1],
                "message": f"Hall unavailable: {hall[1]} is not available at that date or time.",
            })

        panel_rows = conn.execute(
            "SELECT member_name FROM event_panel_members WHERE event_id=?", (event_id,)
        ).fetchall()
        panel_names = {row[0] for row in panel_rows if row[0]}
        panel_names.add(event[1])
        for person_name in panel_names:
            person = conn.execute(
                """SELECT id, available_dates, available_times FROM supervisors
                   WHERE active=TRUE AND LOWER(name)=LOWER(?) LIMIT 1""",
                (person_name,),
            ).fetchone()
            if not person:
                conflicts.append({
                    "type": "staff_availability",
                    "resource": person_name,
                    "message": f"Staff availability missing: {person_name}.",
                })
                continue
            person_window = _availability_window(
                conn, "staff", person[0], candidate_date, person[1], person[2]
            )
            if person_window is None or start_minute < _minutes(person_window[0]) or end_minute > _minutes(person_window[1]):
                staff_type = "primary_supervisor_availability" if person_name == event[1] else "panel_member_availability"
                conflicts.append({
                    "type": staff_type,
                    "resource": person_name,
                    "message": f"Staff unavailable: {person_name} is not available at that date or time.",
                })

        other_events = conn.execute(
            """SELECT id, hall_name, scheduled_time, supervisor_name FROM academic_events
               WHERE id<>? AND batch_id IS NOT DISTINCT FROM ?
                 AND scheduled_date=? AND status='Scheduled'""",
            (event_id, event[3], new_date),
        ).fetchall()
        for other_id, other_hall, other_time, other_supervisor in other_events:
            other_start, other_end = _parse_time_range(other_time or "")
            try:
                overlaps = _times_overlap(time_start, time_end, other_start, other_end)
            except ValueError:
                continue
            if not overlaps:
                continue
            if (other_hall or "").strip().lower() == hall[1].strip().lower():
                conflicts.append({
                    "type": "hall_booking",
                    "resource": hall[1],
                    "conflicting_event_id": other_id,
                    "message": f"Hall already booked: {hall[1]} overlaps event #{other_id}.",
                })
            other_panel = {
                row[0] for row in conn.execute(
                    "SELECT member_name FROM event_panel_members WHERE event_id=?", (other_id,)
                ).fetchall()
            }
            other_panel.add(other_supervisor)
            collision = sorted(panel_names.intersection(other_panel))
            for person_name in collision:
                conflict_type = "primary_supervisor_booking" if person_name == event[1] else "panel_member_booking"
                conflicts.append({
                    "type": conflict_type,
                    "resource": person_name,
                    "conflicting_event_id": other_id,
                    "message": f"Staff already booked: {person_name} overlaps event #{other_id}.",
                })

        if conflicts:
            unique_conflicts = []
            seen_conflicts = set()
            for conflict in conflicts:
                key = (conflict["type"], conflict["resource"], conflict.get("conflicting_event_id"))
                if key not in seen_conflicts:
                    seen_conflicts.add(key)
                    unique_conflicts.append(conflict)
            return {
                "status": "conflict",
                "message": " ".join(conflict["message"] for conflict in unique_conflicts),
                "conflicts": unique_conflicts,
            }

        conn.execute(
            """UPDATE academic_events SET hall_id=?, hall_name=?, scheduled_date=?,
               scheduled_time=?, status='Scheduled', notes=?, updated_at=NOW() WHERE id=?""",
            (
                hall[0], hall[1], new_date, f"{time_start} - {time_end}",
                "Manually rescheduled after availability and conflict validation.", event_id,
            ),
        )
        after = _academic_event_snapshot(conn, event_id)
        _audit_academic_event(
            conn, event_id, event[3], "RESCHEDULE", _user.username, before, after,
            str(body.get("reason") or "Manual conflict-checked reschedule"),
        )
        conn.commit()
        return {"status": "success", "event_id": event_id}
    finally:
        conn.close()


# ── Export Schedule to Excel ───────────────────────────────────────────────────
@app.get("/api/academic/events/export-calendar")
def export_events_calendar(
    batch_id: int | None = Query(default=None, ge=1),
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    from fastapi.responses import StreamingResponse

    conn = get_db_connection()
    try:
        selected_batch_id = batch_id if batch_id is not None else _active_academic_batch_id(conn)
        rows = [] if selected_batch_id is None else conn.execute(
            """SELECT id, event_type, group_id, hall_name, scheduled_date, scheduled_time
               FROM academic_events WHERE batch_id=? AND status='Scheduled'
               ORDER BY scheduled_date, scheduled_time""",
            (selected_batch_id,),
        ).fetchall()

        def ics_escape(value):
            return (str(value or "").replace("\\", "\\\\").replace(";", "\\;")
                    .replace(",", "\\,").replace("\n", "\\n"))

        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//IPMS//Academic Scheduler//EN", "CALSCALE:GREGORIAN"]
        for event_id, event_type, group_id, hall_name, scheduled_date, scheduled_time in rows:
            start, end = _parse_time_range(scheduled_time)
            date_part = str(scheduled_date).replace("-", "")
            lines.extend([
                "BEGIN:VEVENT", f"UID:academic-{event_id}@ipms.local", f"DTSTAMP:{stamp}",
                f"DTSTART:{date_part}T{start.replace(':', '')}00",
                f"DTEND:{date_part}T{end.replace(':', '')}00",
                f"SUMMARY:{ics_escape(event_type)} - {ics_escape(group_id)}",
                f"LOCATION:{ics_escape(hall_name)}", "END:VEVENT",
            ])
        lines.append("END:VCALENDAR")
        return StreamingResponse(
            io.BytesIO(("\r\n".join(lines) + "\r\n").encode("utf-8")),
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=academic_schedule.ics"},
        )
    finally:
        conn.close()


@app.get("/api/academic/events/export-excel")
def export_events_excel(
    batch_id: int | None = Query(default=None, ge=1),
    _user: AuthenticatedUser = Depends(require_roles("staff", "supervisor")),
):
    from fastapi.responses import StreamingResponse
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    conn = get_db_connection()
    selected_batch_id = batch_id if batch_id is not None else _active_academic_batch_id(conn)
    where_sql = "WHERE ae.batch_id=?" if selected_batch_id is not None else "WHERE ae.batch_id IS NULL"
    rows = conn.execute(
        f"""SELECT ae.id, ae.event_type, ae.group_id, ae.group_topic, ae.supervisor_name,
                  ae.match_score, ae.hall_name, ae.scheduled_date, ae.scheduled_time,
                  ae.duration_minutes, ae.status
           FROM academic_events ae {where_sql} ORDER BY ae.scheduled_date, ae.event_type""",
        (selected_batch_id,) if selected_batch_id is not None else (),
    ).fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Academic Schedule"

    # ── Styles ────────────────────────────────────────────────────────────────
    hdr_fill = PatternFill("solid", fgColor="2D3478")
    hdr_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    prop_fill = PatternFill("solid", fgColor="3B4DB8")
    pp1_fill  = PatternFill("solid", fgColor="B45309")
    pp2_fill  = PatternFill("solid", fgColor="065F46")
    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    EVENT_COLOR = {
        "Proposal Presentation": PatternFill("solid", fgColor="EEF0FF"),
        "PP1": PatternFill("solid", fgColor="FEF3C7"),
        "PP2": PatternFill("solid", fgColor="D1FAE5"),
        "Viva": PatternFill("solid", fgColor="FCE7F3"),
    }

    # ── Headers ───────────────────────────────────────────────────────────────
    headers = ["#", "Event Type", "Group ID", "Research Topic", "Primary Supervisor",
               "AI Match %", "Hall / Venue", "Scheduled Date", "Time Slot",
               "Duration (min)", "Status", "Panel Member 1 (Prof/Dr)", "Panel Member 2 (Prof/Dr)",
               "Panel Member 3 (Lecturer)", "Panel Member 4 (Instructor)"]
    col_widths = [4, 22, 14, 38, 22, 12, 18, 16, 14, 14, 12, 22, 22, 22, 22]

    for ci, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = hdr_font; cell.fill = hdr_fill
        cell.alignment = center; cell.border = thin
        ws.column_dimensions[ws.cell(row=1, column=ci).column_letter].width = w

    ws.row_dimensions[1].height = 32

    # ── Data rows ─────────────────────────────────────────────────────────────
    for ri, r in enumerate(rows, start=2):
        ev_id, ev_type, gid, topic, sup_name, match, hall, sdate, stime, dur, status = r
        panel = conn.execute(
            "SELECT member_name, member_role FROM event_panel_members WHERE event_id=? ORDER BY id",
            (ev_id,)
        ).fetchall()
        panel_names = [p[0] for p in panel]
        while len(panel_names) < 4: panel_names.append("")

        row_data = [
            ri - 1, ev_type, gid, topic, sup_name,
            f"{round((match or 0)*100, 1)}%", hall, sdate, stime, dur, status,
            panel_names[0], panel_names[1], panel_names[2], panel_names[3]
        ]
        row_fill = EVENT_COLOR.get(ev_type, PatternFill("solid", fgColor="F8F9FA"))
        for ci, val in enumerate(row_data, start=1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill = row_fill; cell.border = thin
            cell.alignment = center
        ws.row_dimensions[ri].height = 22

    conn.close()

    # Return as downloadable file
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=academic_schedule.xlsx"}
    )


# ── Update / Override One Event ───────────────────────────────────────────────
@app.put("/api/academic/events/{event_id}")
async def update_academic_event(
    event_id: int,
    request: Request,
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    body = await request.json()
    conn = get_db_connection()
    try:
        row = conn.execute(
            """SELECT e.batch_id, COALESCE(b.status, 'DRAFT')
               FROM academic_events e LEFT JOIN academic_schedule_batches b ON b.id=e.batch_id
               WHERE e.id=? FOR UPDATE OF e""",
            (event_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Academic event not found.")
        if row[1] != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft schedules can be edited.")
        forbidden = {"supervisor_name", "hall_name", "scheduled_date", "scheduled_time"}.intersection(body)
        if forbidden:
            raise HTTPException(
                status_code=422,
                detail="Use the conflict-checked reschedule action to change staff, hall, date or time.",
            )
        status = str(body.get("status", "Scheduled"))
        if status not in {"Scheduled", "Unscheduled", "Completed", "Cancelled"}:
            raise HTTPException(status_code=422, detail="Invalid event status.")
        before = _academic_event_snapshot(conn, event_id)
        conn.execute(
            """UPDATE academic_events SET status=?, notes=?, updated_at=NOW() WHERE id=?""",
            (status, str(body.get("notes", "")), event_id),
        )
        after = _academic_event_snapshot(conn, event_id)
        _audit_academic_event(
            conn, event_id, row[0], "UPDATE", _user.username, before, after,
            str(body.get("reason") or "Status or notes update"),
        )
        conn.commit()
        return {"status": "ok"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete All Events (reset) ─────────────────────────────────────────────────
@app.delete("/api/academic/events/reset")
def reset_academic_events(
    batch_id: int = Query(..., ge=1),
    _user: AuthenticatedUser = Depends(require_roles("staff")),
):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT status FROM academic_schedule_batches WHERE id=? FOR UPDATE", (batch_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Schedule version not found.")
        if row[0] != "DRAFT":
            raise HTTPException(status_code=409, detail="Only a draft schedule can be reset.")
        deleted = conn.execute("DELETE FROM academic_events WHERE batch_id=?", (batch_id,)).rowcount
        conn.commit()
        return {"status": "ok", "batch_id": batch_id, "events_deleted": deleted}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



# ── PART 4: ADAPTIVE REBALANCING (NOVELTY 12) ──────────────────────────────
class RebalanceApplyRequest(BaseModel):
    project_id: str
    task_id: int
    from_member: str
    to_member: str
    reason: str

@app.get("/api/schedule/rebalance/recommendations")
def get_rebalance_recommendations(project_id: str = "demo_project_01"):
    # 1. Fetch current tasks and workloads
    conn = get_db_connection()

    conn.execute("SELECT task_id, task_name, assigned_to, effort_hours, status FROM task_assignments WHERE project_id = ?", (project_id,))
    tasks = conn.execute("SELECT task_id, task_name, assigned_to, effort_hours, status FROM task_assignments WHERE project_id = ?", (project_id,)).fetchall()

    conn.close()

    if not tasks:
        return {"recommendations": []}

    member_workload = {}
    pending_tasks = []
    
    for t in tasks:
        tid, tname, assignee, effort, status = t
        if assignee not in member_workload: member_workload[assignee] = 0.0
        if status != "COMPLETED":
            member_workload[assignee] += effort
            if status == "NOT_STARTED":
                pending_tasks.append(t)

    if not member_workload:
        return {"recommendations": []}

    avg_workload = sum(member_workload.values()) / len(member_workload)
    
    def calculate_imbalance(workloads):
        if not workloads or avg_workload == 0: return 0
        return (max(workloads.values()) - min(workloads.values())) / avg_workload

    current_imbalance = calculate_imbalance(member_workload)
    recommendations = []
    
    # 2. Find overloaded members (Experimental Configurable Threshold: 30%)
    for overloaded_member, wl in member_workload.items():
        if wl > avg_workload * 1.30:
            movable = [t for t in pending_tasks if t[2] == overloaded_member]
            if not movable: continue
            
            best_transfer = None
            best_imbalance = current_imbalance
            
            # Evaluate all possible transfers to find the one minimizing imbalance
            for task in movable:
                tid, tname, assignee, effort, status = task
                for candidate in member_workload.keys():
                    if candidate == overloaded_member: continue
                    
                    sim_wl = member_workload.copy()
                    sim_wl[overloaded_member] -= effort
                    sim_wl[candidate] += effort
                    
                    sim_imbalance = calculate_imbalance(sim_wl)
                    if sim_imbalance < best_imbalance:
                        best_imbalance = sim_imbalance
                        best_transfer = (task, candidate, sim_wl)
            
            if best_transfer:
                target_task, best_alt, final_wl = best_transfer
                alt_wl = member_workload[best_alt]
                
                # Formal ACS Equation: ACS = 100(w_c * Capacity + w_p * Performance)
                # Cold-Start: w_p = 0. Capacity = 1 - (wl / max_wl)
                max_possible = max(member_workload.values()) or 1
                capacity_score = 1.0 - (alt_wl / max_possible)
                adaptive_score = round(100 * capacity_score, 1)
                
                recommendations.append({
                    "task_id": target_task[0],
                    "task_name": target_task[1],
                    "from_member": overloaded_member,
                    "from_workload": round(wl, 1),
                    "to_member": best_alt,
                    "to_workload": round(alt_wl, 1),
                    "adaptive_score": adaptive_score,
                    "reason": f"Optimization: Moving '{target_task[1]}' reduces team imbalance from {current_imbalance:.2f} to {best_imbalance:.2f}."
                })
            
    return {"recommendations": recommendations}

@app.post("/api/schedule/rebalance/apply")
def apply_rebalance(req: RebalanceApplyRequest):
    conn = get_db_connection()

    conn.execute("UPDATE task_assignments SET assigned_to = ? WHERE task_id = ? AND project_id = ?",
               (req.to_member, req.task_id, req.project_id))
               
    conn.execute("""INSERT INTO task_assignment_history 
                  (project_id, task_id, from_member, to_member, method, reason, created_at, approved_by) 
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
               (req.project_id, req.task_id, req.from_member, req.to_member, "ADAPTIVE_REBALANCE", req.reason, datetime.now().isoformat(), "Supervisor"))
               

    conn.commit()
    conn.close()
    return {"status": "success", "message": "Task reassigned successfully"}


def _schedule_history_summary(row) -> dict:
    """Convert one persisted schedule version into the history API shape."""
    try:
        stored = json.loads(row[3]) if isinstance(row[3], str) else row[3]
    except (TypeError, json.JSONDecodeError):
        stored = []
    research_topic = ""
    if isinstance(stored, dict):
        research_topic = str(
            stored.get("research_topic") or stored.get("topic") or ""
        ).strip()
    schedule = stored.get("schedule", []) if isinstance(stored, dict) else stored
    if not isinstance(schedule, list):
        schedule = []
    else:
        # Older rows predate explicit collaboration/parallel flags. Normalize
        # them at read time so their History Gantt retains the All Members lane.
        # A corrupt legacy task must not make the entire History listing fail.
        schedule = _normalize_schedule_ownership(
            [task for task in schedule if isinstance(task, dict)]
        )

    total_effort = round(sum(float(task.get("effort_hours", 0) or 0) for task in schedule), 1)
    valid_dates = [
        (task.get("start_date"), task.get("end_date"))
        for task in schedule
        if task.get("start_date") and task.get("end_date")
    ]
    total_days = 0
    if valid_dates:
        try:
            first_day = min(datetime.fromisoformat(start).date() for start, _ in valid_dates)
            last_day = max(datetime.fromisoformat(end).date() for _, end in valid_dates)
            total_days = max(1, (last_day - first_day).days + 1)
        except (TypeError, ValueError):
            total_days = max(
                (int(task.get("duration_days", 0) or 0) for task in schedule),
                default=0,
            )

    assigned_members = sorted({
        str(task.get("assigned_to"))
        for task in schedule
        if task.get("assigned_to")
        and str(task.get("assigned_to")).lower() not in {"all members", "unassigned"}
    })
    # New versions store the exact generation/assignment roster separately;
    # unassigned Gantt rows cannot reconstruct it from task ownership alone.
    try:
        saved_members = json.loads(row[5]) if len(row) > 5 and row[5] else None
    except (TypeError, json.JSONDecodeError):
        saved_members = None
    if saved_members is None and isinstance(stored, dict):
        saved_members = stored.get("team_members")
    if isinstance(saved_members, list):
        members = list(dict.fromkeys(
            member.strip() for member in saved_members
            if isinstance(member, str) and member.strip()
        ))
    else:
        members = assigned_members
    return {
        "id": row[0],
        "project_id": row[1],
        "research_topic": research_topic,
        "version": row[2],
        "created_at": row[4],
        "schedule": schedule,
        "total_tasks": len(schedule),
        "total_effort_hours": total_effort,
        "total_duration_days": total_days,
        "team_members": members,
        "team_size": len(members),
    }


@app.get("/api/schedule/history")
def get_schedule_history(group_id: str | None = None):
    """List persisted PostgreSQL schedule versions, newest first."""
    conn = get_db_connection()
    try:
        if group_id and group_id.strip():
            rows = conn.execute(
                """SELECT id, project_id, version, schedule_json, created_at, team_members_json
                   FROM schedule_versions
                   WHERE project_id ILIKE ?
                   ORDER BY created_at DESC, id DESC LIMIT 100""",
                (f"%{group_id.strip()}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, project_id, version, schedule_json, created_at, team_members_json
                   FROM schedule_versions
                   ORDER BY created_at DESC, id DESC LIMIT 100"""
            ).fetchall()
        return {
            "status": "success",
            "history": [_schedule_history_summary(row) for row in rows],
        }
    finally:
        conn.close()


@app.delete("/api/schedule/history/{history_id}")
def delete_schedule_history(history_id: int):
    """Delete exactly one persisted schedule version."""
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM schedule_versions WHERE id=?", (history_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Schedule history entry not found.")
        conn.execute("DELETE FROM schedule_versions WHERE id=?", (history_id,))
        conn.commit()
        return {"status": "success", "deleted_id": history_id}
    finally:
        conn.close()


def _remove_duplicate_api_routes() -> None:
    """Keep verified progress routes; otherwise keep the latest duplicate."""
    verified_keys = {
        (getattr(route, "path", None), tuple(sorted(getattr(route, "methods", ()) or ())))
        for route in app.router.routes
        if getattr(getattr(route, "endpoint", None), "__module__", "") == "progress_tracking"
    }
    seen = set()
    unique_reversed = []
    for route in reversed(app.router.routes):
        methods = tuple(sorted(getattr(route, "methods", ()) or ()))
        key = (getattr(route, "path", None), methods)
        endpoint_module = getattr(getattr(route, "endpoint", None), "__module__", "")
        if key in verified_keys and endpoint_module != "progress_tracking":
            continue
        if key in seen and key[0] and key[0].startswith("/api/"):
            continue
        seen.add(key)
        unique_reversed.append(route)
    app.router.routes[:] = list(reversed(unique_reversed))


_remove_duplicate_api_routes()


if __name__ == "__main__":

    import uvicorn

    uvicorn.run("main:app", host=os.getenv("IPMS_BIND_HOST", "127.0.0.1"), port=8000, reload=False)

