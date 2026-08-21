# Machine Learning Pipeline

The machine learning architecture for Exposía is strictly divided into two distinct environments to prevent production bloat and maintain a clean separation of concerns:

## 1. The `training/` Pipeline (Research)
All model training, dataset preprocessing, and experimentation happens inside the `/training` directory at the root of the repository. This folder is completely isolated from the live backend.

### Components
* `training/data/raw/`: Store your raw datasets (PDFs, Exposés, annotations) here.
* `training/data/processed/`: Store the `.csv` outputs of your preprocessing scripts.
* `training/scripts/`: Python scripts (`01_preprocess.py`, `02_train.py`) that handle vectorization, data cleaning, and model fitting.
* `training/notebooks/`: Jupyter notebooks used for plotting confusion matrices and evaluating metrics.
* `training/requirements.txt`: Contains heavy ML dependencies (`pandas`, `matplotlib`, `jupyter`, `scikit-learn`).

### Workflow
When retraining a model:
1. Parse the new raw data using scripts in `training/scripts/`.
2. Train the updated SVM or Random Forest models.
3. Save the resulting pickled models (`.pkl`) into `training/models/`.

## 2. The `backend/` Pipeline (Inference)
The FastAPI web server located in `/backend` is strictly an **inference-only** environment. It does not train models or process raw datasets.

### Model Deployment
To deploy a new model into production:
1. Ensure you have tested the `.pkl` artifact in the `training/` pipeline.
2. Manually copy the finalized `.pkl` file from `training/models/` into `backend/models/`.
3. Restart the FastAPI server using `backend/start_backend.sh`.

### Boot Sequence
Upon startup, `backend/src/api/main.py` utilizes a FastAPI `lifespan` manager to load all `.pkl` models into memory exactly once. The loaded models are then injected into `app.state` to be efficiently accessed by the API routers (`src/api/routers/`) via the `core_logic.py` service layer.
