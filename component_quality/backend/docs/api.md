# API Documentation

The Exposía backend exposes a highly modular REST API built with FastAPI. To maintain clean architecture, all endpoints have been extracted from `main.py` into dedicated routing modules under `src/api/routers/`.

## Base URL
When running locally via `backend/start_backend.sh`, the API is hosted at:
`http://127.0.0.1:9000`

## Routers

The API is structurally split into the following domains:

### 1. Analysis Router (`src/api/routers/analysis.py`)
Handles the core proposal processing flow.
* `POST /analyze`: Validates the text, predicts the weakness tag, retrieves feedback, and recommends resources.
* `POST /grade-report`: Estimates the semantic grade and proposal completeness.
* `POST /generate-report`: Generates a downloadable PDF report summarizing the feedback and grade.

### 2. Review Router (`src/api/routers/review.py`)
* `POST /review`: Triggers an autonomous Generative AI review using the LLM.

### 3. Resources Router (`src/api/routers/resources.py`)
* `POST /recommend-resources`: Searches the knowledge base for academic resources tailored to the proposal text.

### 4. Knowledge Graph Router (`src/api/routers/knowledge_graph.py`)
* `POST /knowledge-graph`: Extracts concepts and relationships from the proposal to build a visual graph.

### 5. History Router (`src/api/routers/history.py`)
Manages the saved JSON records of past analyses.
* `GET /analysis-history`: Fetches all saved proposal analyses.
* `DELETE /analysis-history/{id}`: Deletes a specific analysis record.
* `GET /grading-history`: Fetches all semantic grading histories.
* `GET /knowledge-graph-history`: Fetches all extracted knowledge graphs.

### 6. Analytics Router (`src/api/routers/analytics.py`)
* `GET /supervisor-analytics`: Aggregates weakness trends across all students for the dashboard.
* `GET /grading-analytics`: Aggregates readiness and completeness trends.

## Schemas
All data payloads (e.g., `AnalyzeRequest`, `GradeReportResponse`) are defined in `src/api/schemas.py`. This ensures strict input validation via Pydantic before any request reaches the core logic layer.
