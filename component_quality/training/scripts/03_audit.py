import json
import logging
import sys
import hashlib
from pathlib import Path

import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support, confusion_matrix,
    mean_absolute_error, mean_squared_error, r2_score
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def hash_text(text: str) -> str:
    """Create a hash of normalized text to check for duplicates."""
    normalized = " ".join(str(text).lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def audit_leakage(df: pd.DataFrame, text_col: str, group_col: str) -> dict:
    logger.info("Auditing Leakage...")
    df = df.dropna(subset=[text_col, group_col])
    
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df[text_col], df.get("label", df.get("score")), df[group_col]))
    
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()
    
    train_authors = set(train_df[group_col].unique())
    test_authors = set(test_df[group_col].unique())
    author_intersection = train_authors.intersection(test_authors)
    
    train_df["hash"] = train_df[text_col].apply(hash_text)
    test_df["hash"] = test_df[text_col].apply(hash_text)
    
    train_hashes = set(train_df["hash"])
    test_hashes = set(test_df["hash"])
    hash_intersection = train_hashes.intersection(test_hashes)
    
    return {
        "unique_authors_train": len(train_authors),
        "unique_authors_test": len(test_authors),
        "author_intersection": len(author_intersection),
        "unique_texts_train": len(train_hashes),
        "unique_texts_test": len(test_hashes),
        "text_intersection_across_splits": len(hash_intersection),
    }


def audit_weakness_model(df: pd.DataFrame, models_dir: Path, output_dir: Path) -> dict:
    logger.info("Auditing Weakness Model...")
    df = df.dropna(subset=["text", "label"])
    
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df["text"], df["label"], df["author"]))
    
    X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["label"]
    X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["label"]
    test_df = df.iloc[test_idx].copy()
    
    # Load candidate model
    model_path = models_dir / "weakness_svm_model.pkl"
    try:
        candidate_model = joblib.load(model_path)
    except Exception as e:
        logger.error(f"Failed to load weakness model: {e}")
        return {}
        
    y_pred = candidate_model.predict(X_test)
    
    # Candidate Metrics
    acc = accuracy_score(y_test, y_pred)
    p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(y_test, y_pred, average="macro")
    p_weighted, r_weighted, f1_weighted, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    # Baseline 1: Majority Class
    dummy = DummyClassifier(strategy="prior")
    dummy.fit(X_train, y_train)
    y_pred_dummy = dummy.predict(X_test)
    _, _, f1_dummy, _ = precision_recall_fscore_support(y_test, y_pred_dummy, average="macro", zero_division=0)
    
    # Baseline 2: Logistic Regression
    lr = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
        ("lr", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000))
    ])
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)
    _, _, f1_lr, _ = precision_recall_fscore_support(y_test, y_pred_lr, average="macro")
    
    # Error Analysis
    test_df["predicted_label"] = y_pred
    errors = test_df[test_df["label"] != test_df["predicted_label"]]
    errors.to_csv(output_dir / "weakness_errors.csv", index=False)
    
    return {
        "candidate": {
            "accuracy": acc,
            "macro_f1": f1_macro,
            "weighted_f1": f1_weighted,
            "confusion_matrix": cm,
            "support": len(y_test)
        },
        "baselines": {
            "majority_macro_f1": f1_dummy,
            "logistic_regression_macro_f1": f1_lr
        },
        "errors_count": len(errors)
    }


def audit_grading_model(df: pd.DataFrame, models_dir: Path, output_dir: Path) -> dict:
    logger.info("Auditing Semantic Grading Model...")
    df = df.dropna(subset=["text", "score"])
    
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df["text"], df["score"], df["author"]))
    
    X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["score"]
    X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["score"]
    test_df = df.iloc[test_idx].copy()
    
    # Load candidate model
    model_path = models_dir / "semantic_grading_model.pkl"
    try:
        candidate_model = joblib.load(model_path)
    except Exception as e:
        logger.error(f"Failed to load semantic grading model: {e}")
        return {}
        
    y_pred = candidate_model.predict(X_test)
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    # Baseline 1: Mean Predictor
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    y_pred_dummy = dummy.predict(X_test)
    mae_dummy = mean_absolute_error(y_test, y_pred_dummy)
    
    # Baseline 2: Ridge Regression
    ridge = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("ridge", Ridge(random_state=42))
    ])
    ridge.fit(X_train, y_train)
    y_pred_ridge = ridge.predict(X_test)
    mae_ridge = mean_absolute_error(y_test, y_pred_ridge)
    
    # Error Analysis
    test_df["predicted_score"] = y_pred
    test_df["absolute_error"] = (test_df["score"] - test_df["predicted_score"]).abs()
    errors = test_df.sort_values(by="absolute_error", ascending=False)
    errors.to_csv(output_dir / "grading_errors.csv", index=False)
    
    return {
        "candidate": {
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "mean_true": np.mean(y_test),
            "mean_pred": np.mean(y_pred),
            "std_true": np.std(y_test),
            "std_pred": np.std(y_pred)
        },
        "baselines": {
            "mean_predictor_mae": mae_dummy,
            "ridge_mae": mae_ridge
        }
    }


def audit_rag(models_dir: Path) -> dict:
    logger.info("Auditing RAG Embeddings...")
    model_path = models_dir / "feedback_embeddings.pkl"
    try:
        artifact = joblib.load(model_path)
    except Exception as e:
        logger.error(f"Failed to load RAG model: {e}")
        return {}
        
    embeddings = artifact.get("embeddings")
    
    return {
        "model_name": artifact.get("model_name"),
        "corpus_size": len(artifact.get("texts", [])),
        "embedding_dimensions": embeddings.shape if hasattr(embeddings, "shape") else None,
        "evaluable": False,
        "reason": "No ground truth queries in dataset. Must perform qualitative evaluation."
    }


def main():
    script_dir = Path(__file__).resolve().parent
    processed_dir = (script_dir / "../data/processed").resolve()
    models_dir = (script_dir / "../models").resolve()
    output_dir = (script_dir / "../models/experiments").resolve()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    weakness_df = pd.read_csv(processed_dir / "weakness_dataset.csv")
    grading_df = pd.read_csv(processed_dir / "grading_dataset.csv")
    feedback_df = pd.read_csv(processed_dir / "feedback_corpus.csv")
    
    # Leakage Audits
    weakness_leakage = audit_leakage(weakness_df, "text", "author")
    grading_leakage = audit_leakage(grading_df, "text", "author")
    
    # Model Audits
    weakness_metrics = audit_weakness_model(weakness_df, models_dir, output_dir)
    grading_metrics = audit_grading_model(grading_df, models_dir, output_dir)
    rag_metrics = audit_rag(models_dir)
    
    # Dump Individual Metrics
    with (output_dir / "weakness_metrics.json").open("w") as f:
        json.dump(weakness_metrics, f, indent=4)
        
    with (output_dir / "grading_metrics.json").open("w") as f:
        json.dump(grading_metrics, f, indent=4)
        
    with (output_dir / "rag_metrics.json").open("w") as f:
        json.dump(rag_metrics, f, indent=4)
        
    # Aggregate Report JSON Structure
    ml_audit_report = {
        "leakage": {
            "weakness": weakness_leakage,
            "grading": grading_leakage
        },
        "weakness": weakness_metrics,
        "grading": grading_metrics,
        "rag": rag_metrics
    }
    
    with (output_dir / "ml_audit_report.json").open("w") as f:
        json.dump(ml_audit_report, f, indent=4)
        
    logger.info("Audit execution complete. Metrics dumped to models/experiments/.")


if __name__ == "__main__":
    main()
