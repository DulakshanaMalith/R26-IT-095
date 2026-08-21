# Troubleshooting

## Backend Startup Fails

Symptom: FastAPI/Uvicorn exits and logs mention missing SVM model.

Cause: `app.py` loads `models/weakness_svm_model.pkl` during lifespan startup.

Fix:

```powershell
python train_svm_classifier.py
.\start_backend.ps1
```

## Feedback Retrieval Fails

Symptom: `/analyze` or `/generate-feedback` fails with missing retrieval artifact.

Cause: `models/feedback_embeddings.pkl` does not exist.

Fix:

```powershell
python train_feedback_retrieval.py
```

## Semantic Grading Fails

Symptom: `/grade-report` returns a server error or grading model cannot load.

Fix:

```powershell
python train_semantic_grading_model.py
```

## Frontend Shows Backend Offline

Checks:

1. Open `http://127.0.0.1:9000/`.
2. Confirm backend is running with `.\start_backend.ps1`.
3. Confirm frontend API target is correct:

```powershell
$env:VITE_API_BASE_URL
```

4. Confirm `ALLOWED_ORIGINS` contains `http://127.0.0.1:5173`.

## Proposal Is Rejected

The validator requires research-proposal signals. Include enough text and sections such as:

- Abstract or introduction
- Research gap/problem statement
- Objectives/research questions
- Methodology
- Literature review/related work
- Evaluation/metrics
- References or academic evidence

Documents that look like invoices, source code, technical tutorials, or cloud lab reports are intentionally rejected.

## Knowledge Graph Uses Fallback

Symptom: response includes `nlp_warning` about spaCy.

Cause: spaCy or `en_core_web_sm` is not installed.

Fix:

```powershell
pip install spacy
python -m spacy download en_core_web_sm
```

Fallback extraction still works, but concept quality can be lower.

## JSON History Corruption

Symptom: history appears empty after a crash or manual edit.

Cause: history loader detected invalid JSON and moved the previous file to `.corrupted.json`.

Fix:

1. Inspect `data/*.corrupted.json`.
2. Repair JSON manually if needed.
3. Replace the active `data/*_history.json` with valid JSON array content.

## Playwright Smoke Test Fails

Possible causes:

- Backend not running at `http://127.0.0.1:9000`.
- Frontend not running at `http://127.0.0.1:5173`.
- Microsoft Edge is not installed at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`.
- Test fixture buttons/text changed in the UI.

Run:

```powershell
Set-Location frontend
npm run dev
node tests/ui-smoke.mjs
```

## Rebuild All Core Artifacts

```powershell
python preprocessing.py
python finalize_datasets.py
python train_svm_classifier.py
python train_feedback_retrieval.py
python train_semantic_grading_model.py
python verify_training_pipeline.py
```

