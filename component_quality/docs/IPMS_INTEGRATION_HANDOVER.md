# IPMS Integration Handover for ResearchPilot

This document is a technical handover for integrating the current ResearchPilot system into a parent IPMS platform. It is documentation-only and describes verified implementation details from the repository plus proposed integration contracts. Proposed items are clearly labeled and are not currently implemented.

No credentials, local environment values, private data, model artifacts, databases, datasets, source code, or tests are copied into this document.

## Table of Contents

1. [System Identity and Current Status](#1-system-identity-and-current-status)
2. [Repository Map](#2-repository-map)
3. [Architecture](#3-architecture)
4. [Backend Startup and Application Lifecycle](#4-backend-startup-and-application-lifecycle)
5. [Frontend Startup and Architecture](#5-frontend-startup-and-architecture)
6. [Complete API Contract](#6-complete-api-contract)
7. [Data Model and Persistence](#7-data-model-and-persistence)
8. [Authentication and Authorization](#8-authentication-and-authorization)
9. [ML and NLP Pipeline](#9-ml-and-nlp-pipeline)
10. [Proposal Analysis Workflow](#10-proposal-analysis-workflow)
11. [Resource Recommendation and Clickable Links](#11-resource-recommendation-and-clickable-links)
12. [Supervisor Workflow](#12-supervisor-workflow)
13. [Final PDF Generation](#13-final-pdf-generation)
14. [Resend Email Delivery](#14-resend-email-delivery)
15. [Proposal Version and Improvement Tracking](#15-proposal-version-and-improvement-tracking)
16. [Analytics and History](#16-analytics-and-history)
17. [Parent IPMS Integration Contract](#17-parent-ipms-integration-contract)
18. [Recommended Integration Flows](#18-recommended-integration-flows)
19. [Proposed Integration Endpoints](#19-proposed-integration-endpoints)
20. [Webhooks and Synchronization](#20-webhooks-and-synchronization)
21. [Error Handling](#21-error-handling)
22. [Security Handover](#22-security-handover)
23. [Deployment and Networking](#23-deployment-and-networking)
24. [Testing and Verification](#24-testing-and-verification)
25. [Integration Acceptance Checklist](#25-integration-acceptance-checklist)
26. [Integration Risks and Decisions](#26-integration-risks-and-decisions)
27. [Step-by-Step Implementation Plan](#27-step-by-step-implementation-plan)
28. [Developer Quick Start](#28-developer-quick-start)
29. [Glossary](#29-glossary)
30. [Evidence Appendix](#30-evidence-appendix)

---

## 1. System Identity and Current Status

ResearchPilot is a standalone academic proposal review application. Its product role is **Automated Quality Assessment and Adaptive Mentorship**: it helps evaluate research proposal quality, detect missing proposal structure, classify likely weaknesses, retrieve similar prior feedback, recommend learning resources, produce semantic grading/readiness signals, support supervisor review, generate final feedback PDFs, and optionally email approved feedback.

### Current Standalone Architecture

The current system is a browser-to-FastAPI application:

| Part | Implemented technology | Evidence |
| --- | --- | --- |
| Frontend | React + Vite | `frontend/package.json`, `frontend/src/main.jsx`, `frontend/src/App.jsx` |
| Backend | FastAPI | `backend/src/api/main.py` |
| API client | Fetch-based JavaScript module | `frontend/src/api.js` |
| Supervisor workflow database | PostgreSQL | `backend/src/db/session.py`, Alembic revisions |
| Legacy histories | JSON files | `backend/src/api/services/core_logic.py`, `backend/src/core/knowledge_graph.py` |
| ML runtime | scikit-learn, sentence-transformers, joblib artifacts | `backend/src/api/services/core_logic.py`, `backend/src/core/feedback_retrieval.py` |
| PDF generation | ReportLab | `backend/src/api/services/core_logic.py` |
| Email delivery | Resend SDK | `backend/src/api/services/resend_service.py` |

### Implemented

| Capability | Status | Evidence |
| --- | --- | --- |
| Text analysis | Implemented | `POST /analyze` in `backend/src/api/routers/analysis.py` |
| PDF text extraction in browser | Implemented | `pdfjs-dist` usage in `frontend/src/pages/Analyzer.jsx` |
| DOCX text extraction | Not found | No frontend/backend DOCX parser found in inspected paths |
| Proposal validation | Implemented | `backend/src/core/document_validator.py` |
| Weakness prediction | Implemented | `predict_tag` in `core_logic.py`; `POST /predict-weakness` |
| Feedback retrieval | Implemented | `backend/src/core/feedback_retrieval.py` |
| Resource recommendation | Implemented | `backend/src/core/resource_recommender.py` |
| Semantic grading | Implemented | `POST /grade-report`; `load_grading_model` |
| Knowledge graph | Implemented locally | `backend/src/core/knowledge_graph.py` |
| Supervisor students/proposals/versions | Implemented | `backend/src/api/routers/supervisor.py` |
| AI review draft | Implemented as deterministic structured draft from analysis evidence | `generate_structured_supervisor_review_draft` |
| Optional LLM review | Implemented separately | `backend/src/reviewer/service.py`, `POST /review` |
| Supervisor-edited draft | Implemented | `PUT /versions/{version_id}/supervisor-review-draft` |
| Final feedback PDF | Implemented | `GET /versions/{version_id}/final-feedback.pdf` |
| Clickable resource links in PDF | Implemented in current PDF generator | `generate_supervisor_final_feedback_pdf` |
| Email feedback through Resend | Implemented when configured | `POST /versions/{version_id}/send-feedback` |
| Delivery status | Implemented | `GET /versions/{version_id}/feedback-delivery` |
| Review outcome | Implemented | `GET/POST /versions/{version_id}/review-outcome` |
| Improvement tracking | Implemented | `backend/src/api/services/improvement_tracking.py` |
| Parent IPMS REST/API integration | Not implemented | No `/integrations/ipms/*`, webhook, SSO, sync, or parent client module found |

### Partially Implemented or Prototype-Grade

| Area | Current state |
| --- | --- |
| Authentication | Backend cookie auth exists, but frontend development bypass flags are enabled in `frontend/src/App.jsx` |
| Authorization | Some `/me/*` and `my-supervisor-review` routes depend on current supervisor identity; many legacy supervisor endpoints accept explicit supervisor IDs |
| LLM RAG | Reviewer RAG code exists, but its expected CSV path was not present in inspected repository layout |
| Criteria-enhanced LLM review | Criteria module exists, but configured paths appear inconsistent with current data layout |
| Persistence | PostgreSQL is runtime persistence; legacy JSON/SQLite files are migration sources only |
| Deployment | Local development-oriented; production topology is proposed in this document |

### Three Integrations to Keep Separate

| Concept | What it means | Current status |
| --- | --- | --- |
| ResearchPilot internal FastAPI-React integration | Frontend calls backend endpoints through `frontend/src/api.js` | Implemented |
| ResearchPilot standalone operation | Local frontend/backend/database/models/reports run as a self-contained app | Implemented for development/demo |
| Parent IPMS integration | Parent IPMS owns identity/context/data and invokes or embeds ResearchPilot | Not implemented |

---

## 2. Repository Map

Ignore `venv`, `node_modules`, caches, compiled outputs, and generated runtime files unless explicitly mentioned below.

### Top-Level Repository

| Path | Responsibility | Important files/functions | Integration developer action |
| --- | --- | --- | --- |
| `backend/` | FastAPI backend and Python services | `src/api/main.py`, routers, services, tests | Main integration backend work |
| `frontend/` | React/Vite frontend | `src/App.jsx`, `src/api.js`, pages/components | Parent navigation/auth/design work |
| `training/` | Processed datasets, experiments, model artifacts | `scripts/*.py`, `models/*.pkl`, `data/processed/*.csv` | Read and document; do not edit artifacts casually |
| `experiments/` | Reviewer experiments and evaluation data/results | `run_controlled_reviewer_experiment.py` | Reference only unless extending experiments |
| `backend/docs/` | Existing backend docs | `api.md`, `architecture.md`, etc. | Update later to resolve mismatches |
| `docs/` | Root project handover docs | This file | Integration documentation |

### Backend Entry Point

| Path | Responsibility | Inputs | Outputs | Dependencies |
| --- | --- | --- | --- | --- |
| `backend/src/api/main.py` | Creates FastAPI app, configures CORS, initializes DB, mounts reports, registers routers | Environment, model artifacts, DB path | Running ASGI app | FastAPI, routers, `core_logic.lifespan`, `initialize_configured_database` |

Important functions:

| Function | Purpose |
| --- | --- |
| `lifespan(app)` | Loads ML model through `model_lifespan`, opens PostgreSQL session support; Alembic owns schema creation |
| `root()` | `GET /` health/status endpoint |
| `include_routes(router)` | Registers routers concretely |

### Backend Routers

| Path | Responsibility | Important endpoints | Integration notes |
| --- | --- | --- | --- |
| `backend/src/api/routers/analysis.py` | Main analysis, feedback, grading, report endpoints | `/analyze`, `/predict-weakness`, `/generate-feedback`, `/grade-report`, `/generate-report` | Core service contract for IPMS proposal analysis |
| `backend/src/api/routers/resources.py` | Resource recommendations | `/recommend-resources` | May be called independently or through `/analyze` |
| `backend/src/api/routers/knowledge_graph.py` | Concept graph generation/history | `/knowledge-graph`, `/knowledge-graph-history` | Optional IPMS feature |
| `backend/src/api/routers/review.py` | Optional LLM review | `/review` | Requires LLM configuration for real provider calls |
| `backend/src/api/routers/history.py` | JSON history access | `/analysis-history`, `/grading-history` | Useful locally; parent IPMS should prefer database/integration APIs |
| `backend/src/api/routers/analytics.py` | Analytics aggregation | `/grading-analytics`, `/supervisor-analytics` | Could feed IPMS dashboards |
| `backend/src/api/routers/auth.py` | Local auth | `/auth/login`, `/auth/register`, etc. | Should be adapted/replaced for parent auth |
| `backend/src/api/routers/supervisor.py` | Supervisor workflow | students, proposals, versions, drafts, PDF, email, outcome, improvement | Main integration area |

### Schemas

`backend/src/api/schemas.py` contains Pydantic request/response models. Integration-critical schemas include:

| Schema | Used for |
| --- | --- |
| `AnalyzeRequest`, `AnalysisResponse` | Full proposal analysis |
| `GradeReportRequest`, `GradeReportResponse` | Semantic grading/readiness |
| `ResourceRequest`, `ResourceResponse` | Resource recommendation |
| `KnowledgeGraphRequest`, `KnowledgeGraphResponse` | Knowledge graph |
| `GenerateReportRequest`, `GenerateReportResponse` | General report |
| `CreateStudentRequest`, `StudentResponse` | Student records |
| `CreateProposalRequest`, `ProposalResponse` | Proposals |
| `CreateProposalVersionRequest`, `CreateRevisedProposalVersionRequest`, `ProposalVersionResponse` | Proposal versions |
| `SupervisorReviewDraftRequest`, `SupervisorReviewDraftResponse` | AI draft |
| `SaveSupervisorEditedReviewDraftRequest`, `SupervisorEditedReviewDraftResponse` | Supervisor-edited draft |
| `SendFeedbackRequest`, `FeedbackDeliveryResponse` | Email delivery |
| `ReviewOutcomeRequest`, `ReviewOutcomeResponse` | Complete review or request revision |
| `SupervisorReviewRequest`, `SupervisorReviewResponse` | Supervisor review record |
| `SupervisorAnalyticsResponse` | Analytics |

### Services

| Path | Responsibility | Important functions |
| --- | --- | --- |
| `backend/src/api/services/core_logic.py` | Analysis orchestration, history, grading, readiness, PDF reports | `predict_tag`, `retrieve_feedback`, `get_recommended_resources`, `grade_report_text`, `generate_feedback_pdf`, `generate_supervisor_final_feedback_pdf` |
| `backend/src/api/services/improvement_tracking.py` | Version snapshot comparison and best-version selection | `build_proposal_improvement`, `select_best_available_version` |
| `backend/src/api/services/resend_service.py` | Resend email delivery | `send_feedback_email`, `validate_configuration`, `validate_email_address`, `sanitized_error` |
| `backend/src/api/services/email_service.py` | Legacy/secondary email service path | Needs confirmation before production use |

### Database Layer

| Path | Responsibility | Important functions |
| --- | --- | --- |
| `backend/src/db/session.py` | Reads `DATABASE_URL`, creates SQLAlchemy PostgreSQL sessions | `initialize_configured_database`, `get_db_connection` |
| Alembic revisions | Create PostgreSQL schema | `alembic upgrade head` |
| `backend/src/db/repositories.py` | Data access helpers | `create_student`, `create_proposal`, `create_proposal_version`, `create_analysis`, `save_supervisor_review_draft`, `create_notification_log` |
| `backend/src/db/connection.py` | Connection helper | Needs confirmation for exact usage in runtime |

### ML and NLP Core

| Path | Responsibility | Important functions/classes |
| --- | --- | --- |
| `backend/src/core/document_validator.py` | Proposal validity, missing sections, confidence | `ProposalValidationResult`, `validate_proposal_document`, `detect_sections` |
| `backend/src/core/semantic_transformer.py` | Scikit-learn-compatible SentenceTransformer wrapper | `SemanticTransformer` |
| `backend/src/core/feedback_retrieval.py` | Semantic feedback retrieval | `load_retrieval_resources`, `get_feedback` |
| `backend/src/core/resource_recommender.py` | Catalog/keyword-based resource recommendation | `recommend_resources`, `score_resource`, `is_valid_resource_url` |
| `backend/src/core/knowledge_graph.py` | Local concept graph extraction | `analyze_knowledge_graph`, `save_graph_history` |

### Reviewer Module

| Path | Responsibility |
| --- | --- |
| `backend/src/reviewer/service.py` | Runs optional LLM review modes |
| `backend/src/reviewer/providers.py` | OpenAI-compatible provider abstraction |
| `backend/src/reviewer/schemas.py` | Structured review schema |
| `backend/src/reviewer/evidence.py` | Evidence-span validation |
| `backend/src/reviewer/retrieval.py` | Optional RAG examples |
| `backend/src/reviewer/criteria.py` | Optional criteria loading |
| `backend/prompts/reviewer_system_v1.txt` | System prompt |
| `backend/prompts/reviewer_user_v1.txt` | User prompt |

### Frontend

| Path | Responsibility |
| --- | --- |
| `frontend/src/main.jsx` | React entry point |
| `frontend/src/App.jsx` | Routes, layout, auth bypass flags |
| `frontend/src/api.js` | Backend API client and base URL |
| `frontend/src/pages/Analyzer.jsx` | Main analysis/review workspace |
| `frontend/src/pages/MyStudents.jsx` | Student management |
| `frontend/src/pages/SupervisorWorkspace.jsx` | Proposal workspace |
| `frontend/src/pages/ProposalImprovement.jsx` | Improvement tracking |
| `frontend/src/pages/SupervisorAnalytics.jsx` | Analytics UI |
| `frontend/src/pages/History.jsx` | History UI |
| `frontend/src/components/*.jsx` | Cards, modals, charts, layout components |
| `frontend/src/charts/*.jsx` | Recharts-based chart components |

### Runtime and Generated Files

Do not commit or manually edit these except through deliberate maintenance:

| Path/pattern | Role |
| --- | --- |
| `backend/data/*.json` | Local analysis/grading/graph history |
| configured PostgreSQL Database file | Supervisor workflow runtime state |
| `backend/reports/*.pdf` | Generated report files |
| `training/models/*.pkl` | Serialized model/embedding artifacts |
| `frontend/dist/` | Production build output if generated |
| logs under `backend/logs/` | Runtime logs |

---

## 3. Architecture

### 3.1 Overall Component Architecture

```mermaid
flowchart LR
    Browser[Browser: React/Vite] --> APIClient[frontend/src/api.js]
    APIClient --> FastAPI[FastAPI app: backend/src/api/main.py]
    FastAPI --> AnalysisRouter[analysis.py]
    FastAPI --> SupervisorRouter[supervisor.py]
    FastAPI --> AuthRouter[auth.py]
    FastAPI --> ReviewRouter[review.py]
    AnalysisRouter --> Core[core_logic.py]
    SupervisorRouter --> Core
    SupervisorRouter --> Repos[db/repositories.py]
    AuthRouter --> Auth[api/auth.py]
    Auth --> Repos
    Repos --> DB[(PostgreSQL via DATABASE_URL)]
    Core --> Weakness[weakness_svm_model.pkl]
    Core --> Grader[semantic_grading_model.pkl]
    Core --> Feedback[feedback_retrieval.py]
    Feedback --> Embeddings[feedback_embeddings.pkl]
    Core --> Resources[resource_recommender.py]
    Core --> Reports[backend/reports/*.pdf]
    Core --> Histories[backend/data/*.json]
    ReviewRouter --> Reviewer[reviewer/service.py]
    Reviewer --> Provider[reviewer/providers.py]
    Provider --> LLM[Optional LLM API]
    SupervisorRouter --> Resend[resend_service.py]
```

### 3.2 Proposal Analysis Request Flow

```mermaid
sequenceDiagram
    participant FE as Analyzer.jsx
    participant API as POST /analyze
    participant CL as core_logic.py
    participant V as document_validator.py
    participant M as Weakness model
    participant R as feedback_retrieval.py
    participant LR as resource_recommender.py
    participant H as PostgreSQL history tables

    FE->>API: AnalyzeRequest { text, metadata }
    API->>CL: clean_text + validate_research_proposal_text
    CL->>V: validate_proposal_document
    V-->>CL: valid, confidence, missing_sections
    CL->>M: predict([prepared_text])
    M-->>CL: model_predicted_tag
    CL->>CL: analysis_tag_from_validation
    CL->>R: get_feedback(text, top_k=3)
    R-->>CL: retrieved_feedback[]
    CL->>LR: recommend_resources(...)
    LR-->>CL: recommended_resources[]
    CL->>H: save_analysis_record
    API-->>FE: AnalysisResponse
```

### 3.3 Supervisor Review and Report Generation Flow

```mermaid
sequenceDiagram
    participant FE as Analyzer/Supervisor UI
    participant API as supervisor.py
    participant DB as PostgreSQL
    participant CL as core_logic.py
    participant PDF as ReportLab

    FE->>API: Create proposal/version
    API->>DB: proposals, proposal_versions
    FE->>API: POST /versions/{id}/analyze
    API->>CL: Run analysis pipeline
    API->>DB: analyses
    FE->>API: POST /versions/{id}/review-draft
    API->>DB: ai_supervisor_review_drafts
    FE->>API: PUT /versions/{id}/supervisor-review-draft
    API->>DB: supervisor_review_drafts
    FE->>API: GET /versions/{id}/final-feedback.pdf
    API->>DB: load student/proposal/version/analysis/draft
    API->>CL: generate_supervisor_final_feedback_pdf
    CL->>PDF: Build PDF with clickable resources
    API-->>FE: application/pdf
```

### 3.4 Email Delivery Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as POST /versions/{id}/send-feedback
    participant DB as PostgreSQL
    participant PDF as Final PDF generator
    participant RS as resend_service.py
    participant Provider as Resend

    FE->>API: SendFeedbackRequest
    API->>DB: Load required records
    API->>PDF: Generate or locate final PDF
    API->>DB: Create notification_logs row
    API->>RS: send_feedback_email with PDF attachment
    RS->>Provider: Emails.send
    Provider-->>RS: message id or error
    RS-->>API: delivery result
    API->>DB: Update notification status
    API-->>FE: FeedbackDeliveryResponse
```

### 3.5 Proposal-Version Improvement-Tracking Flow

```mermaid
sequenceDiagram
    participant FE as ProposalImprovement.jsx
    participant API as GET /proposals/{proposal_id}/improvement
    participant IT as improvement_tracking.py
    participant DB as PostgreSQL
    participant J as JSON histories

    FE->>API: Request improvement
    API->>IT: build_proposal_improvement
    IT->>DB: proposal + ordered versions
    IT->>DB: latest analysis per version
    IT->>J: load grading and analysis histories
    IT->>IT: build snapshots
    IT->>IT: compare adjacent versions
    IT->>IT: select_best_available_version
    API-->>FE: versions, comparisons, best_version
```

### 3.6 Proposed Parent IPMS Integration Architecture

Proposed, not currently implemented:

```mermaid
flowchart LR
    IPMS[Parent IPMS] --> Gateway[API Gateway / Reverse Proxy]
    Gateway --> RPAPI[ResearchPilot FastAPI]
    IPMS --> RPUI[ResearchPilot UI Embedded or Linked]
    RPUI --> RPAPI
    Gateway --> AuthAdapter[IPMS Auth Adapter]
    RPAPI --> RPDB[(ResearchPilot DB)]
    RPAPI --> ObjectStore[(Proposed report/file object storage)]
    RPAPI --> Models[Local/managed ML artifacts]
    RPAPI --> WebhookOut[Webhook sender]
    WebhookOut --> IPMS
    IPMS --> WebhookIn[Proposed /integrations/ipms/webhooks]
    WebhookIn --> RPAPI
```

---

## 4. Backend Startup and Application Lifecycle

### Entry Module

The backend ASGI module is:

```text
src.api.main:app
```

Evidence:

| File | Evidence |
| --- | --- |
| `backend/start_backend.ps1` | Runs `python -m uvicorn src.api.main:app --host $appHost --port $appPort` |
| `backend/src/api/main.py` | Defines `app = FastAPI(...)` |

### FastAPI Creation

`backend/src/api/main.py` creates:

```python
FastAPI(
    title="ResearchPilot API",
    description="Backend services for Exposia autonomous academic proposal review",
    version="2.0.0",
    lifespan=lifespan,
)
```

### Router Registration

`main.py` includes routers from:

| Router module | Prefix behavior |
| --- | --- |
| `analysis.py` | Paths at root, such as `/analyze` |
| `resources.py` | `/recommend-resources` |
| `knowledge_graph.py` | `/knowledge-graph`, `/knowledge-graph-history` |
| `history.py` | history paths |
| `analytics.py` | analytics paths |
| `supervisor.py` | supervisor workflow paths at root |
| `auth.py` | `/auth/*` because router has auth prefix |
| `review.py` | `/review` |

### CORS

`main.py` configures `CORSMiddleware` for local frontend origins including localhost and `127.0.0.1` on Vite-style ports. `backend/.env.example` also shows an `ALLOWED_ORIGINS` variable, but current `main.py` should be reviewed before assuming that env var drives CORS dynamically.

### Static Report Serving

`main.py` mounts:

```text
/reports -> REPORTS_DIR
```

`REPORTS_DIR` is defined in `backend/src/api/services/core_logic.py` as the backend reports directory. This is convenient for local downloads but should be protected or replaced with signed object-storage URLs in production.

### Startup Initialization

At startup:

1. `core_logic.lifespan` loads the weakness model into `app.state.weakness_model`.
2. `DATABASE_URL` configures PostgreSQL runtime sessions; Alembic initializes schema.
3. The configured path is stored on `app.state.database_path`.
4. If no database path is configured, supervisor data APIs return HTTP 503.

### Model Loading

| Model | Path variable | Loader | Failure behavior |
| --- | --- | --- | --- |
| Weakness classifier | `MODEL_PATH = MODEL_DIR / "weakness_svm_model.pkl"` | `joblib.load` in `load_svm_model` | Startup failure if artifact missing/invalid |
| Semantic grader | `GRADING_MODEL_PATH = MODEL_DIR / "semantic_grading_model.pkl"` | Lazy `joblib.load` in `load_grading_model` | 503 when grading model missing |
| Feedback embeddings | `training/models/feedback_embeddings.pkl` in `feedback_retrieval.py` | `joblib.load` | Runtime retrieval failure if missing/invalid |

### Local Startup Command

From `backend/`:

```powershell
.\start_backend.ps1
```

Equivalent direct command:

```powershell
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 9000
```

Default host/port in service code:

| Setting | Default |
| --- | --- |
| `APP_HOST` | `127.0.0.1` |
| `APP_PORT` | `9000` |

### Health Endpoint

| Method | Path | Expected response |
| --- | --- | --- |
| `GET` | `/` | `{"message": "Exposia AI Backend is running"}` |

### Sanitized Backend `.env` Template

Use placeholders only:

```dotenv
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=9000
MODEL_DIR=../training/models
DATA_DIR=data
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/researchpilot
APP_AUTH_SECRET=replace-with-long-random-secret
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

LLM_PROVIDER=openai
LLM_MODEL=replace-with-model-name
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2000
OPENAI_API_KEY=replace-with-secret

EMAIL_ENABLED=false
EMAIL_PROVIDER=resend
RESEND_API_KEY=replace-with-secret
EMAIL_FROM=ResearchPilot <verified-sender@example.edu>
```

---

## 5. Frontend Startup and Architecture

### Framework and Build Tool

| Item | Evidence |
| --- | --- |
| React | `react` and `react-dom` in `frontend/package.json` |
| Vite | `vite` and `@vitejs/plugin-react` in `frontend/package.json` |
| Router | `react-router-dom` in `frontend/package.json` |
| Charts | `recharts` in `frontend/package.json` |
| PDF extraction | `pdfjs-dist` in `frontend/package.json` and `Analyzer.jsx` |

### Entry Point and Routes

| File | Role |
| --- | --- |
| `frontend/src/main.jsx` | React mounting entry |
| `frontend/src/App.jsx` | Main route configuration and shell context |

Important routes:

| Route | Page | Purpose |
| --- | --- | --- |
| `/dashboard` | `Dashboard` | Dashboard |
| `/students` | `MyStudents` | Student list |
| `/students/:studentId/analyze` | `Analyzer` | Student-scoped analyzer |
| `/students/:studentId/proposals/:proposalId/improvement` | `ProposalImprovement` | Proposal version comparison |
| `/students/:studentId/proposal` | `SupervisorWorkspace` | Student proposal workspace |
| `/login` | `Login` | Local login UI |
| `/signup` | `Signup` | Local signup UI |
| `/analyzer` | `Analyzer` | General analyzer |
| `/workspace` | `SupervisorWorkspace` | General workspace |
| `/tracking` | `ImprovementTracking` | Tracking screen |
| `/analytics` | `SupervisorAnalytics` | Analytics |
| `/history` | `History` | History |

### API Client Configuration

`frontend/src/api.js` sets:

```javascript
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:9000";
```

It also contains:

| Constant | Current behavior |
| --- | --- |
| `TEMP_DEV_SUPERVISOR_ID` | Reads `VITE_DEMO_SUPERVISOR_ID` |
| `TEMP_USE_LEGACY_SUPERVISOR_DATA = true` | Uses legacy explicit supervisor ID endpoints |

### State Management

The frontend uses component-local React state and props. No Redux/Zustand/global state library was found. `Analyzer.jsx` holds most workflow state, including selected student/proposal/version, extracted text, analysis result, grade, recommendations, review draft, delivery status, and review outcome.

### PDF and DOCX Handling

| Type | Current behavior |
| --- | --- |
| PDF | Browser-side extraction using `pdfjs-dist` in `Analyzer.jsx` |
| DOCX | Not implemented in inspected frontend/backend paths |
| Plain text | Supported through textarea/input flow |

### Development and Build Commands

From `frontend/`:

```powershell
npm install
npm run dev
npm run build
npm run preview
npm test
```

Scripts are verified in `frontend/package.json`.

### Frontend Locations Likely to Change for IPMS

| Parent-supplied concern | Files to modify |
| --- | --- |
| Authentication | `frontend/src/App.jsx`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/Signup.jsx`, `frontend/src/api.js` |
| User identity | `frontend/src/App.jsx`, `frontend/src/api.js` |
| Student identity/context | `frontend/src/pages/MyStudents.jsx`, `frontend/src/pages/Analyzer.jsx`, `frontend/src/api.js` |
| Supervisor identity | `frontend/src/App.jsx`, `frontend/src/api.js`, supervisor pages |
| Navigation | `frontend/src/App.jsx`, `frontend/src/components/Sidebar.jsx`, `frontend/src/components/Topbar.jsx` |
| API base URL | `frontend/src/api.js`, `frontend/.env.example` |
| Shared design/layout | `frontend/src/App.css`, `frontend/src/components/*.jsx` |
| Embedded IPMS launch | `frontend/src/App.jsx`, route/context parsing |

---

## 6. Complete API Contract

Authentication labels below:

| Label | Meaning |
| --- | --- |
| Public | No backend auth dependency found |
| Cookie auth | Uses `get_current_supervisor` |
| DB required | Requires `DATABASE_URL` and PostgreSQL connectivity |
| Legacy explicit ID | Accepts path/body `supervisor_id`; not current-user scoped |
| Optional config | Requires model/email/LLM config for success |

### Endpoint Summary Table

| Method | Path | Purpose | Auth | Request body | Query params | Response schema/status | DB effects | Frontend caller | Integration relevance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/` | Health/status | Public | none | none | dict, 200 | none | `checkBackendStatus` | health |
| `POST` | `/auth/login` | Login | DB required | `LoginRequest` | none | `SupervisorIdentityResponse`, 200 | cookie set | `loginSupervisor` | replace/adapt |
| `POST` | `/auth/dev-login` | Dev login | DB required | none | none | `SupervisorIdentityResponse`, 200 | cookie set | `devLoginSupervisor` | disable prod |
| `POST` | `/auth/register` | Register supervisor | DB required | `RegisterSupervisorRequest` | none | `SupervisorIdentityResponse`, 201 | users/profile insert | `registerSupervisor` | likely parent-owned |
| `GET` | `/auth/me` | Current supervisor | Cookie auth, DB required | none | none | `SupervisorIdentityResponse`, 200 | none | `getCurrentSupervisor` | identity |
| `POST` | `/auth/logout` | Logout | Public | none | none | dict, 200 | cookie clear | `logoutSupervisor` | replace/adapt |
| `POST` | `/predict-weakness` | Weakness tag | Public, model required | `TextRequest` | none | `WeaknessResponse`, 200 | none | `predictWeakness` | core analysis |
| `POST` | `/generate-feedback` | Similar feedback | Public | `TextRequest` | none | `FeedbackResponse`, 200 | none | `generateFeedback` | core analysis |
| `POST` | `/recommend-resources` | Learning resources | Public | `ResourceRequest` | none | `ResourceResponse`, 200 | none | `recommendResources` | core analysis |
| `POST` | `/grade-report` | Semantic grade/readiness | Public, grading model required | `GradeReportRequest` | none | `GradeReportResponse`, 200 | JSON grading history | `gradeReport` | core analysis |
| `POST` | `/generate-report` | General feedback PDF | Public | `GenerateReportRequest` | none | file/response, 200 | writes report file | `generateReport` | report |
| `POST` | `/analyze` | Full analysis | Public, model required | `AnalyzeRequest` | none | `AnalysisResponse`, 200 | JSON analysis history | `analyzeText` | primary |
| `POST` | `/knowledge-graph` | Concept graph | Public | `KnowledgeGraphRequest` | none | `KnowledgeGraphResponse`, 200 | JSON graph history | `createKnowledgeGraph` | optional |
| `GET` | `/knowledge-graph-history` | Graph history | Public | none | none | `HistoryResponse`, 200 | none | `getKnowledgeGraphHistory` | local history |
| `GET` | `/grading-history` | Grading history | Public | none | none | `HistoryResponse`, 200 | none | `getGradingHistory` | local history |
| `DELETE` | `/grading-history` | Clear grading history | Public | none | none | dict, 200 | writes JSON | `clearGradingHistory` | admin/local only |
| `GET` | `/analysis-history` | Analysis history | Public | none | none | `HistoryResponse`, 200 | none | `getAnalysisHistory` | local history |
| `DELETE` | `/analysis-history/{analysis_id}` | Delete one analysis | Public | none | path id | dict, 200 | writes JSON | `deleteAnalysisHistoryRecord` | admin/local only |
| `DELETE` | `/analysis-history` | Clear analysis history | Public | none | none | dict, 200 | writes JSON | `clearAnalysisHistory` | admin/local only |
| `GET` | `/grading-analytics` | Grading analytics | Public | none | none | dict, 200 | reads JSON | `getGradingAnalytics` | dashboard |
| `GET` | `/supervisor-analytics` | Supervisor analytics | Public/DB+JSON | none | none | `SupervisorAnalyticsResponse`, 200 | reads DB/JSON | `getSupervisorAnalytics` | dashboard |
| `POST` | `/review` | Optional LLM review | Public, optional LLM config | `ReviewRequest` | none | `ReviewEndpointResponse`, 200 | none | `runLLMReview` | optional |
| `POST` | `/students` | Create student | DB required | `CreateStudentRequest` | none | `StudentResponse`, 201 | insert student | `createStudent` | parent-owned data |
| `GET` | `/me/students` | Current supervisor students | Cookie auth, DB required | none | none | list | `getCurrentSupervisorStudents` | none | identity-scoped |
| `GET` | `/me/dashboard` | Current dashboard | Cookie auth, DB required | none | none | `SupervisorDashboardResponse`, 200 | none | `getCurrentSupervisorDashboard` | identity-scoped |
| `POST` | `/me/students` | Add current supervisor student | Cookie auth, DB required | `CreateStudentRequest` | none | `StudentResponse`, 201 | insert/assign | `createCurrentSupervisorStudent` | identity-scoped |
| `DELETE` | `/me/students/{student_id}` | Remove current assignment | Cookie auth, DB required | none | path id | `AssignmentResponse`, 200 | assignment inactive | `removeCurrentSupervisorStudent` | identity-scoped |
| `POST` | `/supervisors/{supervisor_id}/students` | Add student for supervisor | Legacy explicit ID, DB required | `CreateStudentRequest` | path id | `StudentResponse`, 201 | insert/assign | `createSupervisorStudent` | replace with parent auth |
| `GET` | `/students/{student_id}` | Get student | DB required | none | path id | `StudentResponse`, 200 | none | `getStudent` | context |
| `POST` | `/supervisors/{supervisor_id}/students/{student_id}/assignments` | Assign student | Legacy explicit ID, DB required | `CreateAssignmentRequest` | path ids | `AssignmentResponse`, 201 | insert assignment | `assignStudentToSupervisor` | parent sync |
| `DELETE` | `/supervisors/{supervisor_id}/students/{student_id}` | Remove assignment | Legacy explicit ID, DB required | none | path ids | `AssignmentResponse`, 200 | update assignment | `removeSupervisorStudent` | parent sync |
| `GET` | `/supervisors/{supervisor_id}/students` | List students | Legacy explicit ID, DB required | none | path id | list, 200 | none | `getSupervisorStudents` | parent sync |
| `POST` | `/students/{student_id}/proposals` | Create proposal | DB required | `CreateProposalRequest` | path id | `ProposalResponse`, 201 | insert proposal | `createStudentProposal` | proposal sync |
| `GET` | `/students/{student_id}/proposals` | List proposals | DB required | none | path id | list, 200 | none | `getStudentProposals` | proposal sync |
| `GET` | `/proposals/{proposal_id}` | Get proposal | DB required | none | path id | `ProposalResponse`, 200 | none | `getProposal` | proposal sync |
| `DELETE` | `/proposals/{proposal_id}` | Delete proposal tree | DB required | none | path id, possible supervisor id | dict, 200 | deletes proposal tree | `deleteProposal` | dangerous/admin |
| `GET` | `/proposals/{proposal_id}/improvement` | Improvement tracking | DB required | none | path id | dict, 200 | reads DB/JSON | `getProposalImprovement` | integration-critical |
| `POST` | `/proposals/{proposal_id}/versions` | Create version | DB required | `CreateProposalVersionRequest` | path id | `ProposalVersionResponse`, 201 | insert version/update current | `createProposalVersion` | version sync |
| `POST` | `/proposals/{proposal_id}/revised-versions` | Create revision after revision request | DB required | `CreateRevisedProposalVersionRequest` | path id | `ProposalVersionResponse`, 201 | insert version/update current | `createRevisedProposalVersion` | version sync |
| `GET` | `/proposals/{proposal_id}/versions` | List versions | DB required | none | path id | list, 200 | none | `getProposalVersions` | version sync |
| `GET` | `/versions/{version_id}` | Get version | DB required | none | path id | `ProposalVersionResponse`, 200 | none | `getProposalVersion` | version sync |
| `GET` | `/versions/{version_id}/analyses` | List version analyses | DB required | none | path id | list, 200 | none | `getVersionAnalyses` | evidence |
| `POST` | `/versions/{version_id}/analyses/link` | Link JSON analysis to version | DB required | `LinkVersionAnalysisRequest` | path id | dict, 201 | insert analysis | `linkVersionAnalysis` | compatibility |
| `POST` | `/versions/{version_id}/analyze` | Analyze stored version | DB required, model required | none | path id | `VersionAnalysisResponse`, 201 | insert analysis + histories | `analyzeProposalVersion` | primary IPMS candidate |
| `GET` | `/versions/{version_id}/review-draft` | Get AI draft | DB required | none | `analysis_id` | `SupervisorReviewDraftResponse`, 200 | none | `getVersionReviewDraft` | review |
| `POST` | `/versions/{version_id}/review-draft` | Generate AI draft | DB required | `SupervisorReviewDraftRequest` | path id | `SupervisorReviewDraftResponse`, 201 | insert draft | `generateVersionReviewDraft` | review |
| `GET` | `/versions/{version_id}/supervisor-review-draft` | Get edited draft | DB required | none | `analysis_id`, `supervisor_id` | `SupervisorEditedReviewDraftResponse`, 200 | none | `getSupervisorReviewDraft` | review |
| `PUT` | `/versions/{version_id}/supervisor-review-draft` | Save edited draft | DB required | `SaveSupervisorEditedReviewDraftRequest` | path id | `SupervisorEditedReviewDraftResponse`, 200 | upsert draft | `saveSupervisorReviewDraft` | review |
| `GET` | `/versions/{version_id}/final-feedback.pdf` | Download final PDF | DB required | none | `analysis_id`, `supervisor_id` | PDF, 200 | writes report file | `downloadSupervisorFinalFeedbackPdf` | report |
| `POST` | `/versions/{version_id}/send-feedback` | Email final PDF | DB required, email config | `SendFeedbackRequest` | path id | `FeedbackDeliveryResponse`, 200 | notification log | `sendFeedbackToStudent` | email |
| `GET` | `/versions/{version_id}/feedback-delivery` | Get delivery status | DB required | none | `analysis_id`, `supervisor_id` | `FeedbackDeliveryResponse`, 200 | none | `getFeedbackDelivery` | email status |
| `GET` | `/versions/{version_id}/review-outcome` | Get outcome | DB required | none | `analysis_id`, `supervisor_id` | `ReviewOutcomeResponse`, 200 | none | `getReviewOutcome` | state |
| `POST` | `/versions/{version_id}/review-outcome` | Save outcome | DB required | `ReviewOutcomeRequest` | path id | `ReviewOutcomeResponse`, 201 | supervisor_reviews row | `saveReviewOutcome` | state |
| `GET` | `/versions/{version_id}/supervisor-reviews` | List reviews | DB required | none | path id | list, 200 | none | `getVersionSupervisorReviews` | review |
| `POST` | `/versions/{version_id}/supervisor-reviews` | Save review | DB required | `SupervisorReviewRequest` | path id | `SupervisorReviewResponse`, 201 | insert/update review | `saveVersionSupervisorReview` | review |
| `POST` | `/versions/{version_id}/my-supervisor-review` | Save current supervisor review | Cookie auth, DB required | `SupervisorReviewRequest` | path id | `SupervisorReviewResponse`, 201 | insert/update review | `saveMyVersionSupervisorReview` | identity-scoped |

### Integration-Critical Endpoint Examples

#### Login: current local auth

Implemented endpoint:

```http
POST /auth/login
```

Sanitized request:

```json
{
  "email": "supervisor@example.edu",
  "password": "replace-with-password"
}
```

Sanitized success response:

```json
{
  "user_id": "user-uuid",
  "supervisor_id": "supervisor-uuid",
  "email": "supervisor@example.edu",
  "display_name": "Supervisor Name",
  "role": "supervisor"
}
```

IPMS note: parent integration should not depend on local ResearchPilot passwords if IPMS already owns identity.

#### Create student

```http
POST /students
```

```json
{
  "academic_student_id": "STUDENT-001",
  "full_name": "Student Name",
  "email": "student@example.edu",
  "program": "BSc Example Program",
  "cohort": "2026"
}
```

Parent IPMS note: student profiles should usually be parent-owned and synchronized, not manually duplicated.

#### Create proposal

```http
POST /students/{student_id}/proposals
```

```json
{
  "title": "Example Research Proposal"
}
```

#### Create proposal version

```http
POST /proposals/{proposal_id}/versions
```

```json
{
  "original_filename": "proposal-v1.pdf",
  "source_type": "pdf",
  "original_file_path": "ipms-or-local-reference",
  "extracted_text": "Extracted proposal text...",
  "edited_text": "Optional edited text..."
}
```

#### Analyze stored version

```http
POST /versions/{version_id}/analyze
```

Sanitized response shape:

```json
{
  "analysis": {
    "analysis_id": "analysis-uuid",
    "request_id": "request-uuid",
    "predicted_tag": "Weakness",
    "model_predicted_tag": "Strength",
    "classification_reason": "Validation detected missing sections...",
    "retrieved_feedback": [],
    "recommended_resources": [],
    "document_validation": {
      "is_valid": true,
      "status": "warning",
      "missing_sections": ["Methodology"]
    }
  },
  "semantic_grade": {
    "predicted_score": 31.2,
    "max_score": 42,
    "percentage_score": 74.3
  },
  "knowledge_graph": {
    "nodes": [],
    "edges": [],
    "missing_concepts": []
  }
}
```

#### Generate AI supervisor draft

```http
POST /versions/{version_id}/review-draft
```

```json
{
  "analysis_id": "analysis-uuid"
}
```

#### Save supervisor-edited draft

```http
PUT /versions/{version_id}/supervisor-review-draft
```

```json
{
  "analysis_id": "analysis-uuid",
  "supervisor_id": "supervisor-uuid",
  "overall_assessment": "The proposal is promising but needs a clearer methodology.",
  "strengths": ["Clear topic"],
  "areas_requiring_improvement": ["Methodology section needs more detail"],
  "methodology_feedback": "Describe sampling, data collection, and analysis steps.",
  "evaluation_validation_feedback": "Add measurable evaluation criteria.",
  "recommendations": ["Revise methodology before panel review"],
  "suggested_revision_instructions": ["Add a methodology subsection"]
}
```

#### Download final feedback PDF

```http
GET /versions/{version_id}/final-feedback.pdf?analysis_id=analysis-uuid&supervisor_id=supervisor-uuid
```

Response: `application/pdf`.

#### Send feedback email

```http
POST /versions/{version_id}/send-feedback
```

```json
{
  "analysis_id": "analysis-uuid",
  "supervisor_id": "supervisor-uuid"
}
```

#### Get improvement tracking

```http
GET /proposals/{proposal_id}/improvement
```

Sanitized response fragment:

```json
{
  "proposal_id": "proposal-uuid",
  "versions": [],
  "comparisons": [],
  "best_version": {
    "version_id": "version-uuid",
    "version_number": 2,
    "confidence": "medium",
    "reasons": ["Higher readiness percentage than earlier versions"]
  },
  "latest_is_best": true
}
```

### Missing Required Parent Integration Endpoints

No implemented endpoints were found for:

| Missing endpoint type | Status |
| --- | --- |
| Parent IPMS proposal sync | Not implemented |
| Parent IPMS version sync | Not implemented |
| Parent IPMS webhook receiver | Not implemented |
| Parent IPMS result callback/webhook sender | Not implemented |
| Parent JWT validation endpoint/middleware | Not implemented |
| Parent-owned report lookup by external report ID | Not implemented |
| Idempotency-key handling for parent requests | Not implemented |

---

## 7. Data Model and Persistence

### PostgreSQL tables

Schema evidence is in `backend/src/db/schema.py`.

| Table | Purpose | Primary key | Important columns | Foreign keys/relationships | Repository functions |
| --- | --- | --- | --- | --- | --- |
| `users` | Login users | `user_id` | `email`, `password_hash`, `role`, `display_name`, `created_at`, `updated_at`, `is_active` | one-to-one with `supervisor_profiles` through `user_id` | `create_user`, `get_user`, `get_user_by_email`, `create_supervisor_account` |
| `supervisor_profiles` | Supervisor metadata | `supervisor_id` | `user_id`, `department`, `title` | `user_id -> users.user_id` | `create_supervisor_profile`, `get_supervisor_profile`, `get_supervisor_identity_by_user_id` |
| `students` | Student records | `student_id` | `academic_student_id`, `full_name`, `email`, `program`, `cohort`, timestamps, `active` | assigned through `supervisor_student_assignments` | `create_student`, `get_student`, `get_student_by_academic_id` |
| `supervisor_student_assignments` | Supervisor-student link | `assignment_id` | `supervisor_id`, `student_id`, `assignment_role`, `assigned_at`, `active` | FK to supervisor and student | `assign_supervisor_to_student`, `get_supervisor_students`, `remove_supervisor_student_assignment` |
| `proposals` | Proposal container | `proposal_id` | `student_id`, `title`, `status`, `current_version_id`, timestamps | `student_id -> students.student_id` | `create_proposal`, `get_proposal`, `get_student_proposals`, `delete_proposal_tree` |
| `proposal_versions` | Draft/revision version | `version_id` | `proposal_id`, `version_number`, `original_filename`, `source_type`, `original_file_path`, `extracted_text`, `edited_text`, timestamps, `status` | `proposal_id -> proposals.proposal_id` | `create_proposal_version`, `create_revised_proposal_version_after_revision_request`, `get_proposal_versions` |
| `analyses` | Analysis linked to version | `analysis_id` | `proposal_id`, `version_id`, `request_id`, `created_at`, `source`, `input_text_snapshot` | proposal/version FKs | `create_analysis`, `get_analysis`, `get_version_analyses` |
| `ai_supervisor_review_drafts` | Generated draft and evidence | `draft_id` | `proposal_id`, `version_id`, `analysis_id`, `draft_json`, `evidence_json`, `llm_metadata_json`, timestamps | proposal/version/analysis FKs | `create_ai_supervisor_review_draft`, `get_ai_supervisor_review_draft` |
| `supervisor_review_drafts` | Supervisor edited feedback draft | `review_id` | `version_id`, `analysis_id`, `supervisor_id`, JSON feedback fields, timestamps | version/analysis/supervisor/AI draft FKs | `get_supervisor_review_draft`, `save_supervisor_review_draft` |
| `supervisor_reviews` | Final review/outcome | `review_id` | `proposal_id`, `version_id`, `supervisor_id`, `decision`, `overall_comment`, timestamps | proposal/version/supervisor FKs | `create_supervisor_review`, `update_supervisor_review`, `get_latest_supervisor_review`, `save_current_supervisor_review` |
| `notification_logs` | Feedback email delivery audit | `notification_id` | student/proposal/version/analysis/supervisor IDs, recipient, subject, type, status, sent/error/provider fields, report reference | multiple FKs | `create_notification_log`, `update_notification_log_status`, `get_feedback_delivery_notifications` |

### ER Diagram

```mermaid
erDiagram
    users ||--o| supervisor_profiles : has
    supervisor_profiles ||--o{ supervisor_student_assignments : assigns
    students ||--o{ supervisor_student_assignments : assigned
    students ||--o{ proposals : owns
    proposals ||--o{ proposal_versions : versions
    proposals ||--o{ analyses : analyzed
    proposal_versions ||--o{ analyses : linked
    proposals ||--o{ supervisor_reviews : reviewed
    proposal_versions ||--o{ supervisor_reviews : reviewed
    supervisor_profiles ||--o{ supervisor_reviews : writes
    analyses ||--o{ ai_supervisor_review_drafts : supports
    proposal_versions ||--o{ ai_supervisor_review_drafts : draft_for
    ai_supervisor_review_drafts ||--o{ supervisor_review_drafts : edited_from
    analyses ||--o{ supervisor_review_drafts : evidence_for
    supervisor_profiles ||--o{ supervisor_review_drafts : edits
    supervisor_review_drafts ||--o{ notification_logs : delivered
    supervisor_reviews ||--o{ notification_logs : records
```

### Relationship Summary

| Relationship | Current implementation |
| --- | --- |
| Student-to-supervisor | `supervisor_student_assignments` links active supervisors to active students |
| Proposal-to-version | `proposal_versions.proposal_id`; `proposals.current_version_id` points to current version |
| Version-to-analysis | `analyses.version_id` and `analyses.proposal_id`; explicit link endpoint exists |
| Analysis-to-review | Draft tables store `analysis_id`; supervisor review/outcome also version/proposal scoped |
| Final report-to-delivery | `notification_logs.report_reference` stores generated report reference |
| Improvement tracking | Built from proposal versions, latest analysis links, and JSON grading/analysis histories |

### JSON Persistence

| JSON file | Source |
| --- | --- |
| `analysis_history_records` | `core_logic.save_analysis_record` writes PostgreSQL rows; JSON file is migration source only |
| `grading_records` | `core_logic.save_grading_record` writes PostgreSQL rows; JSON file is migration source only |
| `knowledge_graph_records` | `knowledge_graph.save_graph_history` writes PostgreSQL rows; JSON file is migration source only |

### Parent IPMS Ownership Recommendation

| Data | Recommended source of truth |
| --- | --- |
| Users | Parent IPMS |
| Authentication | Parent IPMS |
| Student profile | Parent IPMS |
| Supervisor profile and assignment | Parent IPMS |
| Proposal metadata | Parent IPMS |
| Proposal files | Parent IPMS or object store owned by IPMS |
| ResearchPilot analysis result | ResearchPilot, with summary mirrored to IPMS |
| Supervisor edited feedback | ResearchPilot unless IPMS has review module |
| Final report file | Shared object storage or ResearchPilot-owned storage with signed URL |
| Delivery records | Owner decision required; usually system that sends email owns delivery audit |
| Analytics | ResearchPilot computes; IPMS displays summary |

---

## 8. Authentication and Authorization

### Current Local Authentication

Evidence: `backend/src/api/auth.py` and `backend/src/api/routers/auth.py`.

| Feature | Current behavior |
| --- | --- |
| Login method | Email/password through `/auth/login` |
| Registration | `/auth/register` creates supervisor account/profile |
| Password storage | PBKDF2-SHA256 with `260000` iterations |
| Hash format | Prefix `pbkdf2_sha256` |
| Session mechanism | HMAC-signed base64 JSON cookie |
| Cookie name | `researchpilot_session` |
| Session lifetime | 8 hours |
| Cookie flags | `httponly=True`, `samesite=lax`, `secure=False` |
| Current supervisor dependency | `get_current_supervisor` |

### Current Authorization Limitations

| Limitation | Evidence/impact |
| --- | --- |
| Frontend bypass | `TEMP_DEV_LOGIN_BYPASS = true`, `TEMP_FRONTEND_AUTH_DISABLED = true` in `frontend/src/App.jsx` |
| Legacy explicit IDs | `frontend/src/api.js` has `TEMP_USE_LEGACY_SUPERVISOR_DATA = true` and passes supervisor IDs to legacy endpoints |
| Mixed route protection | `/me/*` routes use `get_current_supervisor`, but many `/supervisors/{supervisor_id}/*` routes do not |
| Cookie `secure=False` | Local-only behavior, not suitable for HTTPS production |
| Secret fallback | `APP_AUTH_SECRET` fallback exists in code; production should require explicit secret |

### Parent IPMS Auth Options

| Option | Description | Pros | Cons |
| --- | --- | --- | --- |
| 1. Shared JWT validation | IPMS issues JWT; ResearchPilot validates issuer/audience/signature and maps roles | Best user experience, no duplicate login, good auditability | Requires agreed claims, key rotation, middleware |
| 2. Parent-issued short-lived service token | IPMS backend calls ResearchPilot with short-lived token plus user context | Simpler for server-to-server sync | Less suitable for direct browser use unless combined with gateway |
| 3. API gateway authentication | Gateway validates identity and injects trusted headers/claims | Centralized security and routing | ResearchPilot must trust gateway network boundary and validate headers carefully |
| 4. Separate ResearchPilot login | Keep current email/password login | Minimal change | Duplicate users, weak UX, harder authorization consistency |

### Recommendation

Use **shared JWT validation** for user-facing flows, optionally behind an API gateway. The parent IPMS should issue short-lived access tokens with stable claims for user ID, role, supervisor ID, student access scope, proposal ID, and token expiry. ResearchPilot should validate tokens server-side and replace legacy explicit-supervisor endpoints with current-identity-scoped authorization.

Recommended claims:

```json
{
  "iss": "https://ipms.example.edu",
  "aud": "researchpilot",
  "sub": "ipms-user-id",
  "role": "supervisor",
  "supervisor_id": "ipms-supervisor-id",
  "allowed_student_ids": ["ipms-student-id"],
  "exp": 1893456000
}
```

This is proposed, not currently implemented.

---

## 9. ML and NLP Pipeline

### Model Identity Warning

The repository contains both historical training scripts and current runtime artifacts. Do not assume the filename or older README is correct.

| Feature | Historical/training-report implementation | Current deployed artifact |
| --- | --- | --- |
| Weakness classifier | TF-IDF + LinearSVC in `training/scripts/02_train.py`, `backend/scripts/training/train_svm_classifier.py`, and `training/models/training_report.json` | `SemanticTransformer` + `LogisticRegression` in `training/models/weakness_svm_model.pkl` |
| Semantic grader | TF-IDF + RandomForest in `training/scripts/02_train.py`, `backend/scripts/training/train_semantic_grading_model.py`, and `training/models/training_report.json` | `TfidfVectorizer` + `Ridge` in `training/models/semantic_grading_model.pkl` |

### 9.1 TF-IDF + Linear SVM Weakness/Tag Classifier

| Item | Details |
| --- | --- |
| Status | Historical/candidate pipeline; not the inspected deployed artifact |
| Training scripts | `training/scripts/02_train.py`, `backend/scripts/training/train_svm_classifier.py`, `training/scripts/04_weakness_experiments.py`, `training/scripts/09_weakness_study.py` |
| Dataset | `training/data/processed/weakness_dataset.csv` |
| Columns | `author`, `text`, `tag`, `label` |
| Preprocessing | Processed CSV generated from Exposia data preparation scripts |
| Split | `GroupShuffleSplit` by `author` in training scripts |
| Feature extraction | `TfidfVectorizer`, commonly `max_features=5000`, word n-grams in some scripts |
| Algorithm | `LinearSVC(class_weight="balanced", random_state=42)` in candidate scripts |
| Artifact path in historical script | `training/models/weakness_svm_model.pkl` |
| Endpoint using runtime model | `/predict-weakness`, `/analyze`, `/versions/{version_id}/analyze` |
| Limitations | Historical metrics do not prove current deployed artifact behavior |

### 9.2 Current Runtime Weakness Classifier

| Item | Details |
| --- | --- |
| Status | Current deployed artifact |
| Artifact | `training/models/weakness_svm_model.pkl` |
| Actual pipeline | `SemanticTransformer` + `LogisticRegression` |
| Runtime loader | `load_svm_model` in `backend/src/api/services/core_logic.py` |
| Inference function | `predict_tag(request, text)` |
| Text limit | `MODEL_TEXT_LIMIT = 12000` characters |
| Preprocessing | `prepare_model_text` normalizes control characters/whitespace and truncates |
| Output | Raw model tag, later adjusted by validation into `predicted_tag` |
| Promotion script | `training/scripts/13_promote_models.py` |
| Hyperparameters | `LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)` |

### 9.3 Sentence-BERT Feedback Retrieval

| Item | Details |
| --- | --- |
| Status | Current runtime retrieval |
| Core file | `backend/src/core/feedback_retrieval.py` |
| Artifact | `training/models/feedback_embeddings.pkl` |
| Model | `all-MiniLM-L6-v2` |
| Dataset | `training/data/processed/feedback_corpus.csv` |
| Columns | `author`, `annotated_text`, `comment_text`, `tag` |
| Runtime loading | `load_retrieval_resources` |
| Inference | Encode query, cosine similarity against artifact embeddings |
| Output | `annotated_text`, `tag`, `comment_text`, `similarity_score` |
| Endpoint | `/generate-feedback`, `/analyze`, `/versions/{version_id}/analyze` |
| Limitation | Requires local embedding model/artifact availability |

### 9.4 TF-IDF + Random Forest Semantic Grader

| Item | Details |
| --- | --- |
| Status | Historical/candidate pipeline; not the inspected deployed artifact |
| Training scripts | `training/scripts/02_train.py`, `backend/scripts/training/train_semantic_grading_model.py`, `training/scripts/05_grading_experiments.py`, `training/scripts/11_grading_study.py` |
| Dataset | `training/data/processed/grading_dataset.csv` and final/draft variants |
| Columns | `author`, `type`, `text`, `score` |
| Split | `GroupShuffleSplit` by `author` in training scripts |
| Feature extraction | `TfidfVectorizer`, commonly `max_features=3000` or `10000` |
| Algorithm | `RandomForestRegressor(n_estimators=100, random_state=42)` in historical scripts |
| Artifact path | `training/models/semantic_grading_model.pkl` in historical script |
| Limitation | Current deployed artifact inspected as Ridge, not RandomForest |

### 9.5 Current Runtime Semantic Grader

| Item | Details |
| --- | --- |
| Status | Current deployed artifact |
| Artifact | `training/models/semantic_grading_model.pkl` |
| Actual pipeline | `TfidfVectorizer` + `Ridge` |
| Runtime loader | `load_grading_model` in `core_logic.py` |
| Inference function | `grade_report_text(text)` |
| Max score | `GRADING_MAX_SCORE = 42` |
| Endpoint | `/grade-report`, `/versions/{version_id}/analyze` |
| Output | raw predicted score, max score, percentage, labels/readiness payload |
| Limitation | Small processed grading dataset; grade is advisory |

### 9.6 Section Scoring and Completeness

| Item | Details |
| --- | --- |
| Type | Deterministic rules |
| File | `backend/src/api/services/core_logic.py` |
| Functions | `calculate_section_scores`, `score_section`, `calculate_completeness_from_missing`, `calculate_final_readiness` |
| Inputs | Proposal text and validator missing sections |
| Outputs | section scores, completeness percentage, readiness label |
| Limitation | Rule/keyword-based; can miss unusual but valid section wording |

### 9.7 Knowledge Graph and Concept Extraction

| Item | Details |
| --- | --- |
| Type | NLP/rule extraction |
| File | `backend/src/core/knowledge_graph.py` |
| Optional dependency | spaCy `en_core_web_sm` |
| Fallback | Regex noun-phrase extraction |
| Output | concepts/nodes, edges, missing/implicit concepts |
| Endpoint | `/knowledge-graph` |
| Limitation | Local concept graph, not an ontology or graph database |

### 9.8 Resource Recommendation

| Item | Details |
| --- | --- |
| Type | Catalog-based and keyword/missing-section scored |
| File | `backend/src/core/resource_recommender.py` |
| Data source | In-code `RESOURCE_LIBRARY` |
| Output fields | `category`, `title`, `description`, `url`, `score`, `keyword_score`, `matched_keywords` |
| Endpoint | `/recommend-resources`, included in `/analyze` |
| Limitation | Not personalized by external learner profile unless integration adds context |

### Training and Inference Flow

```mermaid
flowchart TB
    Raw[Raw Exposia data] --> Prep[backend/src/exposia + training scripts]
    Prep --> WeakCSV[weakness_dataset.csv]
    Prep --> FeedCSV[feedback_corpus.csv]
    Prep --> GradeCSV[grading_dataset.csv]
    WeakCSV --> WeakTrain[Weakness experiments/promote scripts]
    FeedCSV --> EmbedTrain[Sentence-BERT embedding generation]
    GradeCSV --> GradeTrain[Grading experiments/promote scripts]
    WeakTrain --> WeakArtifact[weakness_svm_model.pkl]
    EmbedTrain --> FeedArtifact[feedback_embeddings.pkl]
    GradeTrain --> GradeArtifact[semantic_grading_model.pkl]
    WeakArtifact --> Runtime[FastAPI runtime]
    FeedArtifact --> Runtime
    GradeArtifact --> Runtime
    Runtime --> Endpoints[/analyze and version analysis]
```

---

## 10. Proposal Analysis Workflow

| Step | Frontend | API | Backend/core | Model/rule | Stored output | Failure conditions |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Select student/proposal | `Analyzer.jsx`, `MyStudents.jsx` | student/proposal endpoints | `supervisor.py`, repositories | DB lookup | selected IDs | missing DB, 404 |
| 2. Load/upload version | `Analyzer.jsx` | version endpoints | repositories | none | `proposal_versions` | empty text, missing proposal |
| 3. Extract text | `Analyzer.jsx` | none before submit | `pdfjs-dist` client-side | PDF parser | frontend text state | unsupported file, PDF parsing error |
| 4. Validate document | `Analyzer.jsx` calls API | `/analyze` or `/versions/{id}/analyze` | `validate_research_proposal_text` | `document_validator.py` | validation payload | 422 invalid |
| 5. Detect sections | same | same | `detect_sections`, completeness helpers | deterministic rules | missing sections, completeness | weak section headings |
| 6. Predict weakness | same | same | `predict_tag` | weakness model | raw/final tags | model missing, bad artifact |
| 7. Retrieve feedback | same | same | `retrieve_feedback` | MiniLM retrieval | `retrieved_feedback` | embeddings/model missing |
| 8. Recommend resources | same | same | `get_recommended_resources` | catalog scoring | `recommended_resources` | no matching resources |
| 9. Knowledge graph | `Analyzer.jsx` | `/knowledge-graph` or version analysis | `analyze_knowledge_graph` | spaCy/fallback | graph history/version response | invalid text |
| 10. Semantic grading | `Analyzer.jsx` | `/grade-report` or version analysis | `grade_report_text` | grading model + rules | grading history/version response | grading model missing |
| 11. Save analysis | API client | `/analyze`, link endpoint, version analysis | `save_analysis_record`, `create_analysis` | none | PostgreSQL | DB write failure |
| 12. Display | `Analyzer.jsx`, cards/components | responses | frontend state | none | UI only | response mismatch |

DOCX note: the requested workflow mentions PDF/DOCX. Current implementation shows PDF extraction through `pdfjs-dist`; DOCX handling was not found and should be added if IPMS sends DOCX files.

---

## 11. Resource Recommendation and Clickable Links

Resource recommendation is implemented in `backend/src/core/resource_recommender.py`.

### How Weaknesses Become Resource Recommendations

1. Analysis produces `predicted_tag`, `classification_reason`, `retrieved_feedback`, and validation missing sections.
2. `recommend_resources` receives weakness text, feedback text, optional missing sections, and `top_k`.
3. Missing sections are mapped through `MISSING_SECTION_MAPPING`.
4. Catalog resources are scored by keyword matches.
5. Valid HTTP/HTTPS URLs are retained.

### Recommendation Type

| Question | Current answer |
| --- | --- |
| Hard-coded? | The catalog is hard-coded in `RESOURCE_LIBRARY` |
| Keyword-based? | Yes |
| ML-based? | No |
| External API-based? | No |
| Personalized by IPMS profile? | Not currently |

### URL Validation and Schema

`is_valid_resource_url` accepts only `http` and `https` URLs with a host.

Current resource result schema:

```json
{
  "category": "Methodology",
  "title": "Methodology guide",
  "description": "Short learning-resource description",
  "url": "https://example.edu/resource",
  "score": 3,
  "keyword_score": 2,
  "matched_keywords": ["methodology"]
}
```

### Frontend and PDF Links

| Surface | Behavior |
| --- | --- |
| Frontend | Resource cards/links are rendered from API resource objects |
| General report | `generate_feedback_pdf` can include resource lines |
| Supervisor final PDF | `generate_supervisor_final_feedback_pdf` includes learning resources and clickable valid links |

### IPMS Integration Requirement

When passing analysis or report data through IPMS, preserve the full resource object, especially `url`. Do not convert resources to plain text too early.

Recommended IPMS summary field:

```json
{
  "recommended_resources": [
    {
      "category": "Methodology",
      "title": "Methodology guide",
      "description": "Short learning-resource description",
      "url": "https://example.edu/resource",
      "score": 3,
      "matched_keywords": ["methodology"]
    }
  ]
}
```

---

## 12. Supervisor Workflow

### State Diagram

```mermaid
stateDiagram-v2
    [*] --> StudentSelected
    StudentSelected --> ProposalCreated
    ProposalCreated --> VersionUploaded
    VersionUploaded --> VersionAnalyzed
    VersionAnalyzed --> AiDraftGenerated
    AiDraftGenerated --> SupervisorDraftSaved
    SupervisorDraftSaved --> FinalPdfGenerated
    FinalPdfGenerated --> FeedbackSent
    FinalPdfGenerated --> ReviewCompleted
    FinalPdfGenerated --> RevisionRequested
    FeedbackSent --> ReviewCompleted
    FeedbackSent --> RevisionRequested
    RevisionRequested --> RevisedVersionUploaded
    RevisedVersionUploaded --> VersionAnalyzed
```

### Transitions

| Transition | Prior state | Endpoint | Body | DB update | Response | Frontend action | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Create/select student | none | `POST /students` or supervisor student endpoints | `CreateStudentRequest` | `students`, assignments | `StudentResponse` | Student appears | 409 duplicate, 503 DB |
| Create proposal | student exists | `POST /students/{student_id}/proposals` | `CreateProposalRequest` | `proposals` | `ProposalResponse` | Proposal selected | 404 student, 503 DB |
| Upload version | proposal exists | `POST /proposals/{proposal_id}/versions` | `CreateProposalVersionRequest` | `proposal_versions`, proposal current | `ProposalVersionResponse` | Version selected | 404/409/422 |
| Analyze version | version exists | `POST /versions/{version_id}/analyze` | none | `analyses`, JSON histories | `VersionAnalysisResponse` | Results display | 422 validation, 503 model/DB |
| Generate AI draft | analysis exists | `POST /versions/{version_id}/review-draft` | `analysis_id` | `ai_supervisor_review_drafts` | draft response | Draft appears | 404 evidence missing |
| Save supervisor draft | draft/evidence exists | `PUT /versions/{version_id}/supervisor-review-draft` | edited content | `supervisor_review_drafts` | edited draft | Final feedback ready | 422 invalid/missing supervisor |
| Download final PDF | saved draft exists | `GET /versions/{version_id}/final-feedback.pdf` | none | report file written | PDF | Browser downloads | 404 missing artifacts |
| Send feedback | final PDF possible, email config | `POST /versions/{version_id}/send-feedback` | `SendFeedbackRequest` | `notification_logs` | `FeedbackDeliveryResponse` | Delivery status shown | 422 no recipient, 503 config, 502 provider |
| Get delivery status | version exists | `GET /versions/{version_id}/feedback-delivery` | none | none | `FeedbackDeliveryResponse` | Status panel | no status if unsent |
| Complete review | final feedback ready | `POST /versions/{version_id}/review-outcome` | `ReviewOutcomeRequest` | `supervisor_reviews` | `ReviewOutcomeResponse` | Marks complete | 422 invalid transition |
| Request revision | final feedback ready | `POST /versions/{version_id}/review-outcome` | `ReviewOutcomeRequest` | `supervisor_reviews` | `ReviewOutcomeResponse` | Enables revised upload | 422 invalid transition |

---

## 13. Final PDF Generation

### Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /generate-report` | General analysis PDF |
| `GET /versions/{version_id}/final-feedback.pdf` | Supervisor final feedback PDF |

### Module and Functions

| Function | File |
| --- | --- |
| `generate_feedback_pdf` | `backend/src/api/services/core_logic.py` |
| `generate_supervisor_final_feedback_pdf` | `backend/src/api/services/core_logic.py` |
| `_final_feedback_artifacts` | `backend/src/api/routers/supervisor.py` |

### Required Data for Supervisor Final PDF

| Data | Source |
| --- | --- |
| Student | PostgreSQL `students` |
| Proposal | PostgreSQL `proposals` |
| Version | PostgreSQL `proposal_versions` |
| Analysis | PostgreSQL `analyses`, `analysis_history_records`, and `grading_records` |
| Edited feedback | PostgreSQL `supervisor_review_drafts` |
| Resources | Analysis evidence / recommended resources |
| Retrieved feedback | Analysis evidence |

### Output Path and File Naming

PDFs are written under `REPORTS_DIR`, which maps to the backend reports directory. Filenames are built by helper functions such as `build_report_filename` and `build_final_feedback_filename`, using safe filename parts.

### ReportLab Usage

ReportLab builds structured PDF content. Current final reports include supervisor-approved feedback, proposal metadata, proposal structure evidence, and learning resources. Valid resource URLs are rendered as links.

### Sanitized Report Generation Request

For general report:

```json
{
  "analysis_id": "analysis-uuid",
  "input_text": "Proposal text...",
  "predicted_tag": "Weakness",
  "retrieved_feedback": [],
  "recommended_resources": [],
  "semantic_grade": {
    "predicted_score": 31.2,
    "max_score": 42,
    "percentage_score": 74.3
  }
}
```

For supervisor final report, use the GET endpoint with query parameters:

```http
GET /versions/{version_id}/final-feedback.pdf?analysis_id=analysis-uuid&supervisor_id=supervisor-uuid
```

### Access Limitation

Reports are statically served under `/reports`. In parent IPMS production integration, do not expose report files as unprotected static URLs. Prefer authenticated download endpoints or signed object-storage URLs.

---

## 14. Resend Email Delivery

### Provider and Package

| Item | Value |
| --- | --- |
| Provider | Resend |
| Python package | `resend==2.36.0` in `backend/requirements.txt` |
| Service file | `backend/src/api/services/resend_service.py` |

### Required Environment Variables

```dotenv
EMAIL_ENABLED=true
EMAIL_PROVIDER=resend
RESEND_API_KEY=replace-with-secret
EMAIL_FROM=ResearchPilot <verified-sender@example.edu>
```

Never include real API keys or credentials in docs, logs, frontend code, or committed files.

### Delivery Behavior

| Concern | Current implementation |
| --- | --- |
| Sender verification | `validate_sender_address`; provider may reject unverified sender |
| Recipient validation | `validate_email_address` |
| Attachment | `EmailAttachment` with PDF bytes |
| Encoding | PDF is base64 encoded before sending |
| Message ID | Parsed by `_message_id_from_response` |
| Status persistence | `notification_logs` |
| Retry behavior | No automatic retry loop found; failed status recorded |
| Error classification | auth, sender verification, recipient restriction, timeout, connection, generic delivery |
| Log sanitization | recipient is masked; sender domain and attachment metadata logged |

### Development and Production Configuration

| Environment | Recommendation |
| --- | --- |
| Development | Keep `EMAIL_ENABLED=false` unless using a verified sandbox setup |
| Staging | Use Resend test domain/sender rules and non-real recipients where possible |
| Production | Use verified sender domain, secret manager, monitored delivery failures, retry/dead-letter strategy |

Parent IPMS must decide whether ResearchPilot sends email directly or returns report metadata for IPMS to send through its own notification system.

---

## 15. Proposal Version and Improvement Tracking

### Version Representation

Proposal versions are rows in `proposal_versions`:

| Field | Meaning |
| --- | --- |
| `version_id` | Internal UUID |
| `proposal_id` | Parent proposal |
| `version_number` | Sequential V1, V2, V3... |
| `original_filename` | Uploaded source filename |
| `source_type` | Example: `pdf`, `text` |
| `extracted_text` | Extracted proposal text |
| `edited_text` | Optional edited text |
| `status` | Version state |

`create_revised_proposal_version_after_revision_request` enforces revision workflow conditions for revised versions.

### Analysis Links

Analyses are linked through `analyses.version_id`. `improvement_tracking.py` uses the latest analysis per version, with the documented rule:

```text
latest PostgreSQL analyses.created_at per version, with analysis_id as a stable tie-breaker
```

### Comparison Behavior

`build_proposal_improvement` compares adjacent snapshots:

| Signal | Meaning |
| --- | --- |
| resolved missing sections | Missing in previous version, present in later version |
| newly missing sections | Present before, missing later |
| still missing sections | Missing in both |
| section score changes | Numeric section score deltas |
| readiness/completeness deltas | Percentage changes |
| overall direction | `IMPROVED`, `REGRESSED`, `MIXED`, `UNCHANGED`, `INSUFFICIENT_DATA` |

### Best Available Version

`select_best_available_version` is advisory, not an authoritative academic decision. It ranks analyzed versions using supervisor decision, missing sections, regression/resolution evidence, readiness, completeness, semantic percentage, and version recency.

Sanitized comparison fragment:

```json
{
  "from_version_number": 1,
  "to_version_number": 2,
  "overall_direction": "IMPROVED",
  "resolved_missing_sections": ["Methodology"],
  "newly_missing_sections": [],
  "still_missing_sections": ["Evaluation"],
  "readiness_delta": 12.5,
  "completeness_delta": 20.0
}
```

Partial-evidence warning: if a version has no linked analysis/grading evidence, comparison and best-version confidence can be reduced.

---

## 16. Analytics and History

### Endpoints

| Endpoint | Source data | Purpose |
| --- | --- | --- |
| `GET /grading-analytics` | `grading_records` | Grade distributions/trends |
| `GET /supervisor-analytics` | PostgreSQL workflow and history tables | Supervisor-facing aggregate analytics |
| `GET /analysis-history` | `analysis_history_records` | Local analysis records |
| `GET /grading-history` | `grading_records` | Local grading records |
| `GET /knowledge-graph-history` | `knowledge_graph_records` | Local graph records |

### Limitations

| Limitation | Impact |
| --- | --- |
| JSON histories are local files | Not ideal for multi-instance production |
| Analytics may mix raw model and validator-adjusted tags | Interpret weakness counts carefully |
| Supervisor analytics are not fully parent-auth scoped | Needs IPMS identity integration |
| Delete-history endpoints are public | Should be admin-protected or disabled in production |

### Surfacing in Parent IPMS

Recommended approach: ResearchPilot computes analysis/review/improvement summaries and exposes read-only integration endpoints for IPMS dashboards. IPMS should not read JSON files or internal PostgreSQL tables directly.

---

## 17. Parent IPMS Integration Contract

Proposed, not currently implemented.

### Ownership Model

| Domain | Owner recommendation |
| --- | --- |
| Users/authentication | Parent IPMS |
| Roles and permissions | Parent IPMS issues claims; ResearchPilot enforces |
| Student profiles | Parent IPMS |
| Supervisor assignments | Parent IPMS |
| Proposal metadata | Parent IPMS |
| Proposal files | Parent IPMS or shared object storage |
| Proposal text extracted for analysis | ResearchPilot may cache a snapshot |
| Analysis results | ResearchPilot owns detailed result; IPMS stores summary |
| Supervisor review content | Needs decision; current ResearchPilot owns |
| Feedback reports | Shared ownership; store immutable generated PDF reference |
| Delivery records | System that sends email owns primary delivery status |
| Analytics | ResearchPilot computes; IPMS displays |

### Data Mapping Table

| Parent IPMS field | ResearchPilot field | Type | Required | Source of truth | Validation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `ipms_user_id` | `users.user_id` or auth claim `sub` | string | yes | IPMS | non-empty | Prefer claim, not local user row |
| `ipms_student_id` | `students.student_id` or external mapping | string | yes | IPMS | stable ID | Add external ID mapping before production |
| `academic_student_id` | `students.academic_student_id` | string | yes | IPMS | unique | Current DB enforces unique academic ID |
| `student_email` | `students.email` | string/email | optional for analysis, required for email | IPMS | email format | Do not expose unnecessarily |
| `student_name` | `students.full_name` | string | yes | IPMS | non-empty | Can be mirrored |
| `program` | `students.program` | string | optional | IPMS | controlled values if available | Current schema free text |
| `cohort` | `students.cohort` | string | optional | IPMS | free text/year | Current schema free text |
| `ipms_supervisor_id` | `supervisor_profiles.supervisor_id` or claim | string | yes | IPMS | stable ID | Current local UUID may differ |
| `proposal_id` | `proposals.proposal_id` | string | yes | IPMS ideally | stable ID | Need external/internal mapping |
| `title` | `proposals.title` | string | yes | IPMS | non-empty | Current proposal create only requires title |
| `version_id` | `proposal_versions.version_id` | string | yes | shared mapping | stable ID | Can be ResearchPilot-generated or IPMS-provided in proposed API |
| `version_number` | `proposal_versions.version_number` | integer | yes | ResearchPilot/IPMS agreement | positive integer | Current backend auto-increments |
| `file_url` | `proposal_versions.original_file_path` | string/URL | optional | IPMS/object store | URL/path reference | Current field is generic text |
| `file_content` | `proposal_versions.extracted_text` | string | yes if no file fetch | IPMS sends or ResearchPilot extracts | min length/valid proposal | Store analysis snapshot |
| `analysis_id` | `analyses.analysis_id` | string | generated | ResearchPilot | UUID/string | Return to IPMS |
| `review_id` | `supervisor_reviews.review_id` | string | generated | ResearchPilot | UUID/string | Return to IPMS |
| `report_id` | `notification_logs.report_reference` or proposed reports table | string | generated | ResearchPilot | immutable | Current schema has no separate reports table |
| `delivery_status` | `notification_logs.status` | string | optional | sender system | enum | `SENT`, `FAILED`, etc. |
| timestamps | `created_at`, `updated_at`, `sent_at` | ISO string | yes | creating system | ISO-8601 | Use UTC |

---

## 18. Recommended Integration Flows

### Flow A: Open ResearchPilot from IPMS

| Item | Recommendation |
| --- | --- |
| API direction | Browser opens ResearchPilot route; backend validates IPMS token |
| Caller | IPMS frontend |
| Receiver | ResearchPilot frontend/backend |
| Authentication | Shared JWT or gateway-authenticated request |
| Payload/context | user ID, role, supervisor ID, student/proposal/version context |
| Expected response | ResearchPilot opens scoped workspace |
| Idempotency | Not required for view open |
| Failure handling | expired token -> redirect to IPMS login; unauthorized student -> 403 |

### Flow B: Analyze a Proposal Version

| Item | Recommendation |
| --- | --- |
| API direction | IPMS backend -> ResearchPilot backend |
| Caller | IPMS service |
| Receiver | Proposed integration endpoint or existing `/versions/{id}/analyze` after sync |
| Authentication | Service token or shared JWT |
| Payload | proposal/version IDs, extracted text or file URL |
| Expected response | analysis ID, status, summary, missing sections, readiness |
| Idempotency | Required using version ID + content hash or idempotency key |
| Failure handling | 422 invalid document; 503 model unavailable; retry transient failures |

### Flow C: Supervisor Review

| Item | Recommendation |
| --- | --- |
| API direction | Browser -> ResearchPilot |
| Caller | Supervisor user |
| Receiver | ResearchPilot backend |
| Authentication | Shared JWT with supervisor role/scope |
| Payload | analysis ID, edited review fields |
| Expected response | saved review draft/outcome |
| Idempotency | Save draft can be upsert by supervisor/version/analysis |
| Failure handling | 403 if not assigned; 404 if analysis missing |

### Flow D: Return Result to IPMS

| Item | Recommendation |
| --- | --- |
| API direction | ResearchPilot -> IPMS callback or IPMS polls ResearchPilot |
| Caller | ResearchPilot webhook sender or IPMS dashboard |
| Receiver | IPMS or ResearchPilot |
| Authentication | Signed webhook or service token |
| Payload | analysis summary, review status, report URL/reference |
| Expected response | acknowledgment |
| Idempotency | Event ID/idempotency key |
| Failure handling | retry with backoff, dead-letter/manual reconciliation |

### Flow E: New Proposal Version

| Item | Recommendation |
| --- | --- |
| API direction | IPMS -> ResearchPilot |
| Caller | IPMS when a new version is submitted |
| Receiver | Proposed version sync endpoint |
| Authentication | Service token |
| Payload | proposal ID, version number, file/text |
| Expected response | ResearchPilot version ID, analysis status |
| Idempotency | version ID + version number + content hash |
| Failure handling | duplicate version -> return existing mapping; analysis failure -> expose retry |

---

## 19. Proposed Integration Endpoints

All endpoints in this section are **Proposed - not currently implemented**.

| Method/path | Purpose | Auth | Idempotency | Request schema | Response schema | DB mapping | Error codes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST /integrations/ipms/proposals/sync` | Upsert parent proposal metadata | service JWT | `Idempotency-Key` + `ipms_proposal_id` | proposal sync object | internal proposal mapping | `students`, `proposals` | 400, 401, 403, 409, 422 |
| `POST /integrations/ipms/versions/sync` | Upsert proposal version and extracted text/file ref | service JWT | content hash + version ID | version sync object | internal version mapping | `proposal_versions` | 400, 401, 403, 404, 409, 422 |
| `POST /integrations/ipms/versions/{version_id}/analyze` | Analyze synced version | service/user JWT | version ID + content hash | optional analysis options | analysis summary | `analyses`, histories | 401, 403, 404, 422, 503 |
| `GET /integrations/ipms/analyses/{analysis_id}/summary` | Read safe analysis summary | JWT | not required | none | analysis summary | `analyses` + histories | 401, 403, 404 |
| `GET /integrations/ipms/proposals/{proposal_id}/improvement` | Read improvement summary | JWT | not required | none | improvement response | proposal versions/analyses | 401, 403, 404 |
| `GET /integrations/ipms/reports/{report_id}` | Authenticated report download/redirect | JWT | not required | none | PDF or signed URL | report reference/logs | 401, 403, 404, 410 |
| `POST /integrations/ipms/webhooks` | Receive parent events | signed webhook | event ID | webhook envelope | ack | mapping tables | 400, 401, 409, 422 |

Example proposed version sync:

```json
{
  "ipms_proposal_id": "ipms-proposal-123",
  "ipms_version_id": "ipms-version-2",
  "version_number": 2,
  "title": "Example Proposal",
  "source_type": "pdf",
  "file_url": "https://ipms.example.edu/files/proposal-v2.pdf",
  "extracted_text": "Proposal text snapshot...",
  "submitted_at": "2026-08-24T10:00:00Z"
}
```

---

## 20. Webhooks and Synchronization

Webhooks are proposed, not currently implemented.

### Proposed Events

| Event | Direction | Meaning |
| --- | --- | --- |
| `proposal.created` | IPMS -> ResearchPilot | New proposal exists |
| `proposal.version.created` | IPMS -> ResearchPilot | New proposal version submitted |
| `analysis.completed` | ResearchPilot -> IPMS | Analysis completed |
| `analysis.failed` | ResearchPilot -> IPMS | Analysis failed |
| `review.saved` | ResearchPilot -> IPMS | Supervisor draft saved |
| `review.completed` | ResearchPilot -> IPMS | Review completed |
| `revision.requested` | ResearchPilot -> IPMS | Supervisor requested revision |
| `report.generated` | ResearchPilot -> IPMS | Final PDF generated |
| `feedback.sent` | ResearchPilot -> IPMS | Email sent |
| `feedback.failed` | ResearchPilot -> IPMS | Email failed |

### Proposed Event Envelope

```json
{
  "event_id": "evt-uuid",
  "event_type": "analysis.completed",
  "source": "researchpilot",
  "occurred_at": "2026-08-24T10:00:00Z",
  "entity": {
    "type": "analysis",
    "id": "analysis-uuid"
  },
  "correlation": {
    "ipms_proposal_id": "ipms-proposal-123",
    "ipms_version_id": "ipms-version-2"
  },
  "data": {}
}
```

### Synchronization Requirements

| Concern | Recommendation |
| --- | --- |
| Signature verification | HMAC or asymmetric signature per event |
| Replay prevention | Store `event_id`; reject duplicates |
| Retries | Exponential backoff for transient errors |
| Idempotency | All writes keyed by parent IDs and event ID |
| Dead letter | Store failed events for manual replay |
| Reconciliation | Scheduled compare endpoint or admin tool |

---

## 21. Error Handling

| Error type | Recommended HTTP code | Current/proposed safe message |
| --- | ---: | --- |
| Validation error | 422 | Submitted proposal text is not a valid research proposal. |
| Unauthorized | 401 | Authentication required. |
| Forbidden | 403 | You are not authorized to access this proposal. |
| Missing student | 404 | Student was not found. |
| Missing proposal | 404 | Proposal was not found. |
| Missing version | 404 | Proposal version was not found. |
| Missing model artifact | 503 | Analysis service is not available. |
| Unsupported document type | 415 | Unsupported document type. Upload PDF or text. |
| Analysis failure | 500/503 | Analysis could not be completed. |
| PDF failure | 500 | Feedback report could not be generated. |
| Email configuration failure | 503 | Email delivery is not configured. |
| Provider rejection | 502 | Email provider rejected the request. |
| Duplicate/idempotent request | 200/409 | Request has already been processed. |
| Database failure | 500/503 | Data service is unavailable. |
| Parent IPMS unavailable | 502/503 | Parent IPMS is temporarily unavailable. |
| Rate limit | 429 | Too many requests. Try again later. |

Safe client-facing errors must not include stack traces, file paths, API keys, full private emails, SQL text, or provider secrets.

---

## 22. Security Handover

### Findings

| Severity | Area | Current finding | Required before production |
| --- | --- | --- | --- |
| Critical | Auth bypass | Frontend disables auth guards with development flags | Remove bypass; enforce backend auth |
| Critical | Parent authorization | Parent IPMS auth not implemented | Add JWT/gateway/service-token auth |
| High | Trusted pickle | Models loaded with `joblib.load` | Trust boundary, signed artifacts, restricted artifact source |
| High | Report access | `/reports` static serving can expose PDFs if reachable | Authenticated report endpoint or signed URLs |
| High | Secrets | `.env` loading exists; no secret manager | Use secret manager in staging/prod |
| High | Legacy explicit IDs | Supervisor ID can be passed explicitly in legacy routes | Enforce identity-scoped access |
| Medium | Cookie config | `secure=False` | Secure cookies under HTTPS |
| Medium | CORS | Localhost-oriented CORS | Environment-specific allowlist |
| Medium | File upload validation | Frontend extracts PDF; backend receives text | Validate file type/content if backend file ingestion is added |
| Medium | Filename/path traversal | PDF filename helpers exist | Continue safe filename logic; avoid user-controlled paths |
| Medium | Email recipient validation | Implemented | Keep and add allowlist/test-mode controls |
| Medium | SQL parameterization | Repository functions use parameterized SQL patterns | Maintain parameterization |
| Medium | PostgreSQL concurrency and migration archive handling | PostgreSQL runtime tables with archived legacy files | Move to DB for multi-instance production |
| Medium | PII handling | Student/review data stored locally | Add retention, access control, audit logs |
| Low | Logging | Some sanitized email logging exists | Review all logs before production |
| Low | CSRF | Cookie auth plus state-changing routes | Add CSRF or token auth if cookies remain |
| Low | XSS | React escapes text by default | Sanitize any future rich HTML |
| Low | Rate limiting | Not found | Add gateway/app rate limits |

### Required Production Fixes

1. Replace local auth with parent IPMS JWT/gateway integration.
2. Disable development auth bypass.
3. Protect report downloads.
4. Move secrets to managed storage.
5. Add role/scope checks for every supervisor/proposal endpoint.
6. Add idempotency for sync and analysis jobs.
7. Consolidate persistence for multi-instance operation.
8. Add monitoring, audit logging, backups, and retention policy.

---

## 23. Deployment and Networking

### Current Local Deployment

| Component | Local detail |
| --- | --- |
| Backend | `python -m uvicorn src.api.main:app --host 127.0.0.1 --port 9000` |
| Backend helper | `backend/start_backend.ps1` |
| Frontend | `npm run dev` |
| Frontend default | Vite, commonly `http://localhost:5173` |
| Frontend API default | `http://127.0.0.1:9000` |
| Reports | Static `/reports` mount |
| Database | PostgreSQL URL from `DATABASE_URL` |
| Models | `MODEL_DIR`, expected deployed artifacts |
| Data histories | `DATA_DIR` |

### Windows Localhost Note

The frontend default uses `127.0.0.1` rather than `localhost`, which can avoid IPv4/IPv6 localhost mismatch issues on Windows development machines.

### Required Runtime Dependencies

Backend dependencies include FastAPI, Uvicorn, Pydantic, scikit-learn, sentence-transformers, torch, pandas, numpy, ReportLab, Resend, OpenAI SDK, pypdf, and supporting libraries listed in `backend/requirements.txt`.

Frontend dependencies include React, Vite, React Router, Recharts, Lucide React, pdfjs-dist, and Playwright.

### Proposed Topologies

| Environment | Topology |
| --- | --- |
| Development | Local IPMS mock + ResearchPilot backend + Vite frontend + PostgreSQL |
| Staging | API gateway/reverse proxy, HTTPS, staging database, object storage, test email domain |
| Production | IPMS auth, gateway, ResearchPilot API service, persistent database, object storage, model artifact registry, monitoring/log aggregation |

### Production Requirements

| Concern | Recommendation |
| --- | --- |
| Reverse proxy/API gateway | Terminate HTTPS and validate parent auth |
| HTTPS | Required |
| Persistent storage | Use managed DB and object storage |
| Secret manager | Required for auth/email/LLM keys |
| DB migrations | Adopt Alembic or equivalent |
| Health/readiness | Keep `/`; add readiness checking DB/models |
| Backups | DB and reports |
| Monitoring | App logs, metrics, error reporting |

---

## 24. Testing and Verification

No tests were executed during this documentation-only handover pass.

### Existing Backend Tests

| Test file | Feature covered | Dependency style | Safe command |
| --- | --- | --- | --- |
| `backend/tests/test_db_schema.py` | PostgreSQL schema | local temp DB | `python -m pytest tests/test_db_schema.py -q` |
| `backend/tests/test_auth.py` | Auth/session behavior | local DB/mocks | `python -m pytest tests/test_auth.py -q` |
| `backend/tests/test_analysis_resources.py` | Analysis resources | mocks/local | `python -m pytest tests/test_analysis_resources.py -q` |
| `backend/tests/test_alignment.py` | Exposia alignment | local fixtures | `python -m pytest tests/test_alignment.py -q` |
| `backend/tests/test_supervisor_version_analysis.py` | Version analysis | local DB/mocks | `python -m pytest tests/test_supervisor_version_analysis.py -q` |
| `backend/tests/test_supervisor_review_drafts.py` | Draft/final PDF/resource behavior | local DB/PDF checks | `python -m pytest tests/test_supervisor_review_drafts.py -q` |
| `backend/tests/test_supervisor_reviews.py` | Supervisor review records | local DB | `python -m pytest tests/test_supervisor_reviews.py -q` |
| `backend/tests/test_supervisor_api.py` | Supervisor API | test client | `python -m pytest tests/test_supervisor_api.py -q` |
| `backend/tests/test_supervisor_analysis_linking.py` | Analysis linking | local DB | `python -m pytest tests/test_supervisor_analysis_linking.py -q` |
| `backend/tests/test_seed_demo_data.py` | Demo seed script | local DB | `python -m pytest tests/test_seed_demo_data.py -q` |
| `backend/tests/test_resend_service.py` | Email service | mocked provider | `python -m pytest tests/test_resend_service.py -q` |
| `backend/tests/test_proposal_improvement.py` | Improvement tracking | local DB/history | `python -m pytest tests/test_proposal_improvement.py -q` |
| `backend/tests/test_llm_schema.py` | LLM schema | schema-only | `python -m pytest tests/test_llm_schema.py -q` |
| `backend/tests/test_joins.py` | Repository joins | local DB | `python -m pytest tests/test_joins.py -q` |
| `backend/tests/test_evidence_validation.py` | LLM evidence validation | local | `python -m pytest tests/test_evidence_validation.py -q` |
| `backend/tests/test_document_validator.py` | Proposal validation | local | `python -m pytest tests/test_document_validator.py -q` |

Run all backend tests from `backend/`:

```powershell
python -m pytest tests -q
```

### Existing Frontend Tests and Scripts

| Command | Purpose | Evidence |
| --- | --- | --- |
| `npm test` | Node test runner for `tests/*.test.mjs` | `frontend/package.json` |
| `npm run build` | Production build | `frontend/package.json` |
| `npm run dev` | Vite dev server | `frontend/package.json` |
| `npm run preview` | Preview build | `frontend/package.json` |

Frontend test files:

| Test file | Feature covered |
| --- | --- |
| `frontend/tests/proposalImprovementViewModel.test.mjs` | Improvement view model |
| `frontend/tests/ui-smoke.mjs` | UI smoke behavior, likely Playwright-based |

### Model Verification

Existing verification scripts include:

| Script | Purpose |
| --- | --- |
| `backend/verify_models.py` | Model artifact verification |
| `backend/scripts/evaluation/verify_training_pipeline.py` | Training pipeline verification |
| `backend/scripts/evaluation/run_demo_pipeline.py` | Demo pipeline |

Do not run scripts that send real email or call paid LLM APIs unless explicitly configured for safe test mode.

---

## 25. Integration Acceptance Checklist

### Before Integration

- [ ] Git state reviewed and unrelated changes understood.
- [ ] No committed secrets or real credentials.
- [ ] Sanitized environment examples are current.
- [ ] Backend and frontend tests have current results.
- [ ] Model artifacts are available in expected location.
- [ ] API contract reviewed with IPMS team.
- [ ] Stable external/internal ID mapping strategy agreed.

### Authentication Integration

- [ ] JWT issuer/audience/signature validation implemented.
- [ ] Role mapping agreed.
- [ ] Supervisor/student authorization enforced.
- [ ] Expired-token handling tested.
- [ ] Development auth bypass disabled.
- [ ] Legacy explicit-supervisor paths replaced or protected.

### Data Synchronization

- [ ] Student mapping implemented.
- [ ] Supervisor assignment mapping implemented.
- [ ] Proposal mapping implemented.
- [ ] Version mapping implemented.
- [ ] Duplicate/idempotent requests handled.
- [ ] Timestamps normalized to UTC.

### Functional Verification

- [ ] Proposal analysis works from IPMS context.
- [ ] Review draft generation works.
- [ ] Supervisor edit/save works.
- [ ] Final PDF downloads through protected path.
- [ ] Resource links remain clickable.
- [ ] Email behavior follows ownership decision.
- [ ] Improvement tracking updates after new version.
- [ ] Analytics visible in IPMS.

### Production Readiness

- [ ] Verified sender domain if ResearchPilot sends email.
- [ ] HTTPS enforced.
- [ ] Persistent database configured.
- [ ] Backups configured.
- [ ] Monitoring and alerting configured.
- [ ] Rate limiting configured.
- [ ] Reports protected.
- [ ] Secret manager configured.

---

## 26. Integration Risks and Decisions

| Issue | Current behavior | Integration impact | Recommended decision | Owner | Priority |
| --- | --- | --- | --- | --- | --- |
| PostgreSQL vs shared parent DB | ResearchPilot-owned PostgreSQL schema | Integration ownership must stay clear | Keep RP DB isolated behind API contract unless formally merged | Backend/IPMS architect | High |
| Local files vs object storage | Reports under backend reports dir | Static file risk, deployment coupling | Move final reports to object storage/signed URLs | Backend/devops | High |
| Internal login vs parent auth | Local cookie login exists | Duplicate identity | Replace with IPMS JWT/gateway auth | IPMS auth owner | Critical |
| Duplicated student data | ResearchPilot has `students` table | Sync conflicts | Parent owns; ResearchPilot mirrors/cache | Integration owner | High |
| Sync vs async analysis | Current endpoints are synchronous | Long model startup/inference can block UX | Support async job model for IPMS | Backend owner | Medium |
| Model startup time | Weakness model loads at startup | Readiness should wait for model | Add readiness endpoint | Backend/devops | Medium |
| Report URL ownership | Static `/reports` | Insecure direct exposure | Signed/protected report endpoint | Security owner | High |
| Email ownership | ResearchPilot can send via Resend | Duplicate notifications possible | Decide one sender: IPMS or ResearchPilot | Product owner | High |
| API versioning | No integration versioning | Contract drift | Add `/v1/integrations/ipms/*` | Integration owner | Medium |
| IPMS downtime | No webhook/retry system | Lost status updates | Add durable outbox/retry | Backend/devops | Medium |
| Backward compatibility | Frontend uses legacy endpoints | Refactor risk | Keep legacy during migration, add new scoped endpoints | Backend/frontend | Medium |

---

## 27. Step-by-Step Implementation Plan

### Phase 1: Contract Agreement

| Item | Detail |
| --- | --- |
| Objective | Agree source-of-truth ownership, IDs, auth, and payload schemas |
| Likely files | docs/spec files only initially |
| Dependencies | IPMS API documentation |
| Tests | Contract examples validated |
| Completion criteria | Signed-off OpenAPI/schema examples |
| Rollback | Documentation-only, no runtime effect |

### Phase 2: Authentication Adapter

| Item | Detail |
| --- | --- |
| Objective | Validate IPMS identity in ResearchPilot |
| Likely files | `backend/src/api/auth.py`, new dependency module, `frontend/src/App.jsx`, `frontend/src/api.js` |
| Dependencies | IPMS JWT/gateway details |
| Tests | Auth unit/integration tests |
| Completion criteria | No dev bypass; supervisor-scoped route works |
| Rollback | Restore local auth for development profile only |

### Phase 3: Identity and Data Mapping

| Item | Detail |
| --- | --- |
| Objective | Map IPMS users/students/supervisors/proposals to ResearchPilot records |
| Likely files | `backend/src/db/schema.py`, `backend/src/db/repositories.py`, new integration router |
| Dependencies | Parent ID fields |
| Tests | Duplicate/idempotency tests |
| Completion criteria | Same IPMS payload does not create duplicates |
| Rollback | Disable sync endpoint |

### Phase 4: Proposal/Version Synchronization

| Item | Detail |
| --- | --- |
| Objective | Sync proposal metadata and versions |
| Likely files | new integration router/service, repositories |
| Dependencies | File/text handoff decision |
| Tests | Version create/update tests |
| Completion criteria | V1/V2/V3 visible and ordered |
| Rollback | Manual local version creation remains |

### Phase 5: Analysis Invocation

| Item | Detail |
| --- | --- |
| Objective | Trigger analysis from synced versions |
| Likely files | `supervisor.py`, new integration router, `core_logic.py` wrappers |
| Dependencies | Model availability |
| Tests | Version analysis tests |
| Completion criteria | IPMS receives analysis summary |
| Rollback | Disable integration endpoint; keep UI analysis |

### Phase 6: Review and Report Integration

| Item | Detail |
| --- | --- |
| Objective | Supervisor review, final PDF, protected report URL |
| Likely files | `supervisor.py`, `core_logic.py`, report storage service |
| Dependencies | Storage/security decision |
| Tests | PDF/link tests |
| Completion criteria | Clickable resources preserved |
| Rollback | Keep local PDF download |

### Phase 7: Email Ownership Decision

| Item | Detail |
| --- | --- |
| Objective | Decide whether IPMS or ResearchPilot sends feedback email |
| Likely files | `resend_service.py`, supervisor send endpoint, integration callback |
| Dependencies | verified sender/domain |
| Tests | mocked email tests |
| Completion criteria | No duplicate student notifications |
| Rollback | Disable email and return report URL |

### Phase 8: Improvement Tracking Integration

| Item | Detail |
| --- | --- |
| Objective | Expose version comparison to IPMS |
| Likely files | `improvement_tracking.py`, integration router |
| Dependencies | stable version mapping |
| Tests | improvement tests |
| Completion criteria | Best Available Version summary visible in IPMS |
| Rollback | Hide IPMS improvement panel |

### Phase 9: Analytics Integration

| Item | Detail |
| --- | --- |
| Objective | Surface summary analytics in IPMS |
| Likely files | `analytics.py`, frontend dashboard, integration endpoints |
| Dependencies | analytics ownership |
| Tests | analytics aggregation tests |
| Completion criteria | scoped metrics correct |
| Rollback | local analytics only |

### Phase 10: Security Hardening

| Item | Detail |
| --- | --- |
| Objective | Close production security gaps |
| Likely files | auth, CORS, report serving, config |
| Dependencies | deployment profile |
| Tests | security/integration tests |
| Completion criteria | no public destructive endpoints, protected reports |
| Rollback | staging only, no production promotion |

### Phase 11: Staging Verification

| Item | Detail |
| --- | --- |
| Objective | End-to-end test with parent IPMS staging |
| Likely files | config/deployment |
| Dependencies | staging IPMS |
| Tests | full smoke suite |
| Completion criteria | signed acceptance checklist |
| Rollback | revert gateway route |

### Phase 12: Production Rollout

| Item | Detail |
| --- | --- |
| Objective | Controlled production release |
| Likely files | deployment config |
| Dependencies | monitoring/backups/support |
| Tests | post-deploy smoke tests |
| Completion criteria | monitored successful analysis/review/report flow |
| Rollback | route traffic back to previous IPMS behavior |

---

## 28. Developer Quick Start

### Required Software

| Tool | Purpose |
| --- | --- |
| Python | Backend runtime |
| Node.js/npm | Frontend runtime |
| Git | Source control |
| PostgreSQL tooling | Optional DB inspection |

### Backend Setup

From `backend/`:

```powershell
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
```

Use the project-specific virtual environment if already created.

### Frontend Setup

From `frontend/`:

```powershell
npm install
```

### Sanitized Environment Setup

Backend `.env` should contain placeholders like:

```dotenv
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=9000
MODEL_DIR=../training/models
DATA_DIR=data
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/researchpilot
APP_AUTH_SECRET=replace-with-secret
EMAIL_ENABLED=false
EMAIL_PROVIDER=resend
RESEND_API_KEY=replace-with-secret
EMAIL_FROM=ResearchPilot <verified-sender@example.edu>
```

Frontend `.env`:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:9000
VITE_DEMO_SUPERVISOR_ID=replace-with-demo-supervisor-id
```

### Startup Commands

Backend:

```powershell
cd backend
.\start_backend.ps1
```

Frontend:

```powershell
cd frontend
npm run dev
```

URLs:

| Service | URL |
| --- | --- |
| Backend | `http://127.0.0.1:9000` |
| Frontend | Vite dev URL, usually `http://localhost:5173` |

### Safe Smoke Test

1. Call `GET /` and expect `{"message": "Exposia AI Backend is running"}`.
2. Open the frontend.
3. Use sanitized/demo data only.
4. Run `/analyze` on a short sample proposal.
5. Verify resources contain URL fields.
6. Generate final PDF only with test data.
7. Do not send real email unless using verified test configuration.

### Common Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Supervisor APIs return 503 | `DATABASE_URL` not configured |
| Weakness prediction unavailable | model artifact missing or load failed |
| Grading unavailable | `semantic_grading_model.pkl` missing |
| Retrieval fails | feedback embeddings or SentenceTransformer unavailable |
| Frontend cannot reach backend | `VITE_API_BASE_URL`, CORS, backend not running |
| Email send fails | `EMAIL_ENABLED`, Resend key, sender verification, recipient restrictions |

### First Recommended Integration Task

Create a proposed IPMS authentication adapter and a read-only `/integrations/ipms/context` proof-of-concept endpoint that validates an IPMS token and returns the mapped user/supervisor/student/proposal context. Do this before syncing proposals or running analysis.

---

## 29. Glossary

| Term | Meaning |
| --- | --- |
| Analysis | ResearchPilot output containing validation, prediction, feedback, resources, and related evidence |
| Best Available Version | Advisory selected proposal version based on available analysis/review evidence |
| Completeness | Rule-based score from missing proposal sections |
| Evidence | Stored analysis data used to generate draft/final feedback |
| IPMS | Parent platform that should own institutional identity and proposal records |
| Proposal | Research project/proposal container |
| Proposal version | One draft/revision of a proposal |
| Readiness | Combined semantic grade and completeness score |
| ResearchPilot | Standalone proposal quality and mentorship service |
| Resource recommendation | Catalog-based learning-resource suggestion with URL |
| Supervisor draft | AI-generated or supervisor-edited feedback object |
| Validation | Deterministic check that text is a research proposal and includes expected structure |
| Webhook | Proposed event notification between IPMS and ResearchPilot |

---

## 30. Evidence Appendix

### Inspected Source Files

This handover used evidence from:

| Area | Files |
| --- | --- |
| Backend entry/startup | `backend/src/api/main.py`, `backend/start_backend.ps1`, `backend/requirements.txt`, `backend/.env.example` |
| Routers | `backend/src/api/routers/analysis.py`, `resources.py`, `knowledge_graph.py`, `history.py`, `analytics.py`, `review.py`, `auth.py`, `supervisor.py` |
| Schemas | `backend/src/api/schemas.py` |
| Auth/DB | `backend/src/api/auth.py`, `backend/src/db/session.py`, `backend/src/db/schema.py`, `backend/src/db/repositories.py` |
| Services | `backend/src/api/services/core_logic.py`, `improvement_tracking.py`, `resend_service.py` |
| Core ML/NLP | `backend/src/core/document_validator.py`, `semantic_transformer.py`, `feedback_retrieval.py`, `resource_recommender.py`, `knowledge_graph.py` |
| Reviewer | `backend/src/reviewer/service.py`, `providers.py`, `schemas.py`, `evidence.py`, `retrieval.py`, `criteria.py`, `backend/prompts/reviewer_system_v1.txt`, `backend/prompts/reviewer_user_v1.txt` |
| Frontend | `frontend/package.json`, `frontend/.env.example`, `frontend/src/App.jsx`, `frontend/src/api.js`, `frontend/src/pages/Analyzer.jsx`, `frontend/src/pages/ProposalImprovement.jsx`, `frontend/src/pages/MyStudents.jsx`, `frontend/src/pages/SupervisorWorkspace.jsx` |
| Training/models | `training/scripts/02_train.py`, `04_weakness_experiments.py`, `05_grading_experiments.py`, `09_weakness_study.py`, `10_semantic_weakness.py`, `11_grading_study.py`, `12_rubric_grading.py`, `13_promote_models.py`, `training/models/training_report.json` |
| Tests inventory | `backend/tests/*.py`, `frontend/tests/*.mjs` |

### Commands Run During This Documentation Task

Read-only inspection commands:

```powershell
rg --files -g '!venv/**' -g '!node_modules/**' -g '!**/__pycache__/**'
rg -n "@(router|app)\.(get|post|put|delete|patch)\(" backend/src/api -g "*.py"
rg -n "CREATE TABLE|CREATE INDEX|UNIQUE INDEX|FOREIGN KEY|CHECK" backend/src/db/schema.py
Get-Content -Path frontend\package.json -Raw
rg -n "^class .*\(BaseModel\)|^def |^async def |APIRouter|include_router|CORSMiddleware|StaticFiles|uvicorn|REPORTS_DIR|DATABASE_URL|MODEL_PATH|GRADING_MODEL_PATH|DATA_DIR|GRADING_MAX_SCORE" backend/src/api/main.py backend/src/api/schemas.py backend/src/api/services/core_logic.py backend/src/api/auth.py backend/src/db/session.py
rg -n "export async function|export function|const API_BASE_URL|TEMP_|VITE_|<Route|path=|pdfjs|getDocument|docx|downloadFinal|sendFinal|reviewOutcome|improvement" frontend/src/App.jsx frontend/src/api.js frontend/src/pages/Analyzer.jsx frontend/src/pages/ProposalImprovement.jsx frontend/src/pages/MyStudents.jsx frontend/src/pages/SupervisorWorkspace.jsx
Get-Content -Path backend\start_backend.ps1 -Raw
Get-Content -Path backend\requirements.txt -Raw
rg -n "^def |^async def |class |Session|COOKIE|SESSION|pbkdf2|set_cookie|delete_cookie|secure|SameSite|HTTPException|Depends|get_current_supervisor" backend/src/api/auth.py backend/src/api/routers/auth.py backend/src/api/routers/supervisor.py
rg -n "^def |^class |INSERT INTO|UPDATE |SELECT |DELETE FROM|notification_logs|proposal_versions|analyses|supervisor_review_drafts|supervisor_reviews|students|proposals" backend/src/db/repositories.py backend/src/api/services/resend_service.py backend/src/api/services/improvement_tracking.py backend/src/core/resource_recommender.py backend/src/core/feedback_retrieval.py backend/src/core/knowledge_graph.py backend/src/core/document_validator.py
rg -n "weakness_svm_model|semantic_grading_model|feedback_embeddings|rag_embeddings|LinearSVC|RandomForest|LogisticRegression|Ridge|GroupShuffleSplit|SentenceTransformer|TfidfVectorizer|joblib.dump|joblib.load" training backend/src backend/scripts -g "*.py" -g "*.json" -g "*.md"
Get-Content -Path backend\.env.example -Raw
Get-Content -Path frontend\.env.example -Raw
```

No tests were run during this documentation-only pass.

### Facts That Still Need Confirmation

| Item | Why confirmation is needed |
| --- | --- |
| Parent IPMS API contract | No parent API docs or implementation were present in this repository |
| Parent authentication method | No existing SSO/JWT/gateway integration found |
| Parent field names and IDs | Proposed mapping must be aligned with real IPMS schema |
| Production database choice | Runtime uses PostgreSQL through SQLAlchemy and Alembic |
| Report storage owner | Current local `/reports` is not enough for production |
| Email ownership | IPMS may already have notification/email service |
| DOCX requirement | Current implementation does not show DOCX extraction |
| LLM RAG data paths | Current retriever paths need correction/confirmation |
| Criteria data paths | `criteria.py` path assumptions need validation |
| Full test status | Tests were inventoried but not rerun in this pass |
