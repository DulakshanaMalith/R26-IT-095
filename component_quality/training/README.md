# Exposía ML Training Pipeline training/README.md

This directory contains the entire model training pipeline for the Exposía backend. It takes the raw user dataset and builds reproducible, backend-compatible Machine Learning artifacts. 

## Architecture

The pipeline consists of two stages:
1. `01_preprocess.py`: Traverses the raw dataset, extracts textual data from LaTeX/PDF/HTML, maps annotations, and produces cleaned structural CSV files.
2. `02_train.py`: Consumes the preprocessed CSVs, builds Scikit-learn pipelines with TF-IDF and LinearSVC/RandomForest models, embeds feedback strings via SentenceTransformers, and generates serialized `.pkl` files.

## Dataset Structure

The preprocessing script requires the following directory structure inside `training/data/raw/exposes/`:
```text
Author Name/
├── annotations.json (Contains Weakness / Highlight / Strength flags)
├── comments.json (Contains textual feedback matched via annotationId)
├── scores.json (Contains semantic grading scores from reviewers)
├── draft/
│   └── Expose.tex / Expose.pdf
└── final/
    └── Expose.tex / Expose.pdf
```

## Formulations & Experiments

The pipeline was heavily audited and re-formulated to maximize scientific validity and inference parity.
- **Weakness Formulation:** The Weakness classifier uses a **Paragraph** level input granularity. Rather than training on short 1-sentence annotation spans, the pipeline extracts the full paragraph containing the annotation. This matches the noisy text chunks expected by the backend inference `/predict-weakness` endpoint.
- **Grading Formulation:** The Semantic Grader is strictly trained on **final** submissions. Mixing `draft` and `final` submissions previously confused the model due to overlapping TF-IDF signals with contradictory numerical scores.

## Running the Pipeline

Ensure you are in the `training/scripts` directory and have the backend environment activated.

### Step 1: Preprocessing
```bash
python 01_preprocess.py
```

### Step 2: Training Models
```bash
python 02_train.py
```
By default, models are saved into `training/models/experiments/`. 

To promote them directly to the `training/models/` directory for backend deployment, run:
```bash
python 02_train.py --promote
```

## Leakage Prevention
To prevent author-specific styling leakage, `02_train.py` strictly employs `GroupShuffleSplit` over the `author` ID. This ensures that no model sees an author's final draft in the test set if their first draft was in the training set. There is currently 0% identity leakage and 0% duplicate text leakage across the train/test boundaries.

> Note: The current dataset contains exactly 55 unique authors (approximately 44 training and 11 testing authors per split). Gathering more diverse, annotated exposés is expected to improve the reliability of the evaluation and may improve overall model performance.
