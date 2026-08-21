# Deployment Documentation

## Current Deployment State

The repository contains local development scripts only. There is no Dockerfile, Docker Compose file, production process manager config, cloud deployment manifest, or CI/CD pipeline in the current codebase.

## Environment Variables

Defined in `.env.example`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Environment label. |
| `APP_HOST` | `0.0.0.0` in example, `127.0.0.1` default in code | Uvicorn bind host. |
| `APP_PORT` | `9000` | Uvicorn port. |
| `MODEL_DIR` | `models` | Directory containing pickle artifacts. |
| `DATA_DIR` | `data` | Directory containing runtime history JSON. |
| `ALLOWED_ORIGINS` | localhost frontend origins | CORS allowlist. |
| `PYTHON_EXE` | unset | Optional override used by `start_backend.ps1`. |

Frontend environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:9000` | Backend API base URL. |

## Local Backend

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\start_backend.ps1
```

`start_backend.ps1`:

- Loads `.env` values into process environment when not already set.
- Creates `logs/`.
- Runs `python -m uvicorn app:app --host $APP_HOST --port $APP_PORT`.
- Appends combined output to `logs/backend.combined.log`.

Manual equivalent:

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 9000
```

## Local Frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Vite serves at `http://127.0.0.1:5173` according to `frontend/vite.config.js`.

## Required Artifacts

Before the backend can run successfully, these should exist:

| Artifact | How to create |
| --- | --- |
| `models/weakness_svm_model.pkl` | `python train_svm_classifier.py` |
| `models/feedback_embeddings.pkl` | `python train_feedback_retrieval.py` |
| `models/semantic_grading_model.pkl` | `python train_semantic_grading_model.py` |
| `processed/*.csv` | `python preprocessing.py`, then finalization/analysis scripts as needed |

## Optional spaCy Model

Knowledge graph extraction works without spaCy, but higher-quality extraction requires:

```powershell
python -m spacy download en_core_web_sm
```

Note: `spacy` is not listed in `requirements.txt`, so install it separately if needed.

## Production Considerations

To productionize this project, add:

- Authentication and authorization.
- A transactional database instead of JSON history files.
- Safe model artifact distribution and integrity checks.
- Docker or another reproducible runtime image.
- Reverse proxy/TLS configuration.
- CI/CD for tests, linting, frontend build, and model artifact checks.
- File-locking or database writes for concurrent usage.
- Secret management for environment-specific configuration.

