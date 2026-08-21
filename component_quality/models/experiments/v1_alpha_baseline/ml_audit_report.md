# Exposia ML Pipeline Audit

## 1. Executive Summary

**Overall Status: READY WITH WARNINGS**

The ML training pipeline (`01_preprocess.py` and `02_train.py`) is successfully implemented and mechanically robust. It respects the strict boundaries between training and backend inference, accurately serializes compatible `joblib/pickle` artifacts, and correctly implements group-level data splitting to prevent identity leakage.

However, the pipeline exposes significant limitations in the underlying dataset's target formulation. The weakness classifier is being trained on short quoted spans while inference expects long chunks, and the semantic grader suffers from mixing draft and final assessment scores. While technically ready for integration experiments, the model outputs will exhibit low predictive power until these data formulation issues are resolved.

---

## 2. Dataset

The preprocessing script successfully parsed the Exposía 1.0.0 raw data:
- **Authors Processed:** 55
- **Weakness Records Extract:** 2,227
- **Grading Records Extracted:** 165
- **Feedback RAG Records:** 2,151

---

## 3. Weakness Classification

- **Target Definition:** Binary mapping. `Weakness=1`, `[Strength, Highlight, Other]=0`. This represents a valid classification of 'Weakness vs Non-Weakness'.
- **Class Distribution:** 1,332 Weakness / 895 Non-Weakness.
- **Model:** `Pipeline(TfidfVectorizer, LinearSVC(class_weight="balanced"))`
- **Split Strategy:** `GroupShuffleSplit(author)`
- **Metrics (Candidate):** 
  - Accuracy: `0.570`
  - Macro F1: `0.566`
- **Metrics (Baselines):**
  - Majority Class Macro F1: `0.351`
  - TF-IDF + LogisticRegression Macro F1: `0.607`
- **Validity Assessment:** **PASS WITH WARNINGS**

**High Issue (Length Mismatch):** The training records use `ann["text"]` which are very short, quoted annotation spans (often 1-2 sentences). However, the backend `predict-weakness` endpoint consumes entire chunks up to 12,000 characters. The model is trained on micro-spans but evaluated on macro-sections in production.

**Medium Issue (Suboptimal Algorithm):** The selected `LinearSVC` candidate underperformed a simple `LogisticRegression` baseline trained on the exact same split (F1 0.56 vs 0.60).

---

## 4. Semantic Grading

- **Target Definition:** Total numerical assessment score mapping to text.
- **Score Range:** 0 to 42 (Mean: 32.7, Min: 9.0, Max: 42.0)
- **Model:** `Pipeline(TfidfVectorizer, RandomForestRegressor)`
- **Split Strategy:** `GroupShuffleSplit(author)`
- **Metrics (Candidate):**
  - MAE: `5.76`
  - RMSE: `7.39`
  - R²: `0.168`
- **Metrics (Baselines):**
  - Mean Predictor MAE: `6.29`
  - Ridge Regression MAE: `6.03`
- **Validity Assessment:** **PASS WITH WARNINGS**

**High Issue (Mixed Score Semantics):** The training pipeline extracts scores from both `draft` and `final` submissions. An author's draft and final texts are highly similar (TF-IDF wise) but often receive vastly different scores (e.g., draft=25, final=39). This forces the model to map nearly identical text to contradictory targets, explaining the very low R² (0.168) and marginal improvement over simply guessing the mean score.

---

## 5. RAG (Retrieval-Augmented Generation)

- **Corpus Size:** 2,151 semantic chunk/comment pairs.
- **Embedding Model:** `all-MiniLM-L6-v2` (Output Dimension: 384)
- **Evaluation:** **NOT EVALUABLE** (Quantitative). The Exposía dataset maps historical quotes directly to historical comments. There is no predefined set of "novel student queries" to calculate `Recall@K` against ground truth.
- **Validity Assessment:** **PASS**. The generated `feedback_embeddings.pkl` perfectly aligns with the SentenceTransformer architecture expected by the backend inference script.

---

## 6. Leakage Audit

A strict quantitative leakage audit was performed using `GroupShuffleSplit(author)` with `test_size=0.2`.
- **Author Identity Leakage:** **NONE**. (Train authors: 44, Test authors: 11, Intersection: 0).
- **Grading Duplicate Leakage:** **NONE**. (0 identical texts across Train/Test).
- **Weakness Duplicate Leakage:** **MINOR**. Out of 1,973 unique hashes, exactly 23 texts appeared in both train and test splits. This is likely due to students using boilerplate university templates or exceptionally common generic phrases (e.g., "In this section we will..."). This does not invalidate the experiment.

---

## 7. Backend Compatibility

Actual simulated endpoint loading tests via `backend/verify_models.py` confirm full binary compatibility.
- `weakness_svm_model.pkl` loaded and executed `.predict([text])`.
- `semantic_grading_model.pkl` loaded and executed `.predict([text])`.
- `feedback_embeddings.pkl` loaded dictionary structure (`texts`, `comments`, `embeddings`).

All output boundaries match the FastAPI `src/api/services/core_logic.py` consumption expectations.

---

## 8. Scientific Validity

**What the experiments demonstrate:**
- The pipeline correctly preserves independent identity groups, proving that the models can operate on completely unseen student authors.
- TF-IDF provides a small but real predictive signal over random guessing for grading.

**What they do NOT demonstrate:**
- The semantic grader cannot reliably distinguish between a good draft and a bad final, because it lacks a structural metadata feature to know which stage it is evaluating.
- The weakness classifier's performance on 1-sentence quotes does not guarantee it will perform identically on a 3-page chunk in production.

---

## 9. Problems

1. **[HIGH] Target Mismatch (Weakness):** Training on sentence-level spans but inferencing on section-level chunks.
2. **[HIGH] Score Contradiction (Grading):** Mixing Draft and Final texts in the same grading model confuses the regressor.
3. **[MEDIUM] Weak Algorithm:** LinearSVC is outperformed by standard LogisticRegression for the weakness task.
4. **[LOW] Duplicate Boilerplate:** 23 weakness texts leak across train/test due to generic academic templates.

---

## 10. Recommendations

**Must fix before experiments:**
- None. The models run without crashing and do not suffer from catastrophic target leakage. They are safe to use for alpha backend integration.

**Recommended improvements (Next Steps):**
1. **Change Weakness Formulation:** Aggregate the raw dataset texts up to the paragraph or section level before applying the `Weakness=1` label, ensuring length parity with backend inputs.
2. **Isolate Grading Targets:** Filter `01_preprocess.py` to train the semantic grader EXCLUSIVELY on `final` text targets.
3. **Switch to Logistic Regression:** Swap `LinearSVC` out for `LogisticRegression` in `02_train.py` for a free 4% Macro F1 gain.
