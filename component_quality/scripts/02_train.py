import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import classification_report, accuracy_score, mean_absolute_error, r2_score
from sentence_transformers import SentenceTransformer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def train_weakness_classifier(df: pd.DataFrame, models_dir: Path) -> dict:
    logger.info("Training Weakness Classifier...")
    if df.empty or "text" not in df.columns or "label" not in df.columns:
        logger.error("Invalid or empty weakness dataset.")
        return {}

    # Remove completely empty texts just in case
    df = df.dropna(subset=["text", "label"])

    # GroupShuffleSplit by author to prevent leakage
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df["text"], df["label"], df["author"]))

    X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["label"]
    X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["label"]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
        ("classifier", LinearSVC(class_weight="balanced", random_state=42))
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)

    logger.info(f"Weakness Classifier Test Accuracy: {acc:.4f}")

    model_path = models_dir / "weakness_svm_model.pkl"
    joblib.dump(pipeline, model_path)
    logger.info(f"Saved weakness model to {model_path}")

    return {
        "model": "Pipeline(TfidfVectorizer, LinearSVC)",
        "accuracy": acc,
        "classification_report": report
    }


def train_semantic_grader(df: pd.DataFrame, models_dir: Path) -> dict:
    logger.info("Training Semantic Grader...")
    if df.empty or "text" not in df.columns or "score" not in df.columns:
        logger.error("Invalid or empty grading dataset.")
        return {}

    df = df.dropna(subset=["text", "score"])

    # GroupShuffleSplit by author to prevent leakage
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df["text"], df["score"], df["author"]))

    X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["score"]
    X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["score"]

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    logger.info(f"Semantic Grader Test MAE: {mae:.4f} | R2: {r2:.4f}")

    model_path = models_dir / "semantic_grading_model.pkl"
    joblib.dump(pipeline, model_path)
    logger.info(f"Saved semantic grader to {model_path}")

    return {
        "model": "Pipeline(TfidfVectorizer, RandomForestRegressor)",
        "mae": mae,
        "r2": r2
    }


def generate_feedback_embeddings(df: pd.DataFrame, models_dir: Path) -> dict:
    logger.info("Generating Feedback Embeddings...")
    if df.empty or "comment_text" not in df.columns or "annotated_text" not in df.columns:
        logger.error("Invalid or empty feedback corpus.")
        return {}

    df = df.dropna(subset=["annotated_text", "comment_text"])
    df["annotated_text"] = df["annotated_text"].astype(str)
    df["comment_text"] = df["comment_text"].astype(str)
    df["tag"] = df["tag"].astype(str)
    df["author"] = df["author"].astype(str)

    # The backend expects specific structure. RAG retrieval usually uses comment_text or annotated_text.
    # The actual retrieval logic embeds the text. Let's create an artifact that stores embeddings.
    model_name = "all-MiniLM-L6-v2"
    encoder = SentenceTransformer(model_name)
    
    # We will embed the annotated_text because the user's draft is compared to historical weaknesses.
    texts = df["annotated_text"].tolist()
    embeddings = encoder.encode(texts, show_progress_bar=True)

    artifact = {
        "model_name": model_name,
        "texts": texts,
        "comments": df["comment_text"].tolist(),
        "tags": df["tag"].tolist(),
        "authors": df["author"].tolist(),
        "embeddings": embeddings
    }

    model_path = models_dir / "feedback_embeddings.pkl"
    joblib.dump(artifact, model_path)
    logger.info(f"Saved feedback embeddings to {model_path}")

    return {
        "model": model_name,
        "corpus_size": len(texts)
    }


def main():
    parser = argparse.ArgumentParser(description="Train Exposía ML Models.")
    parser.add_argument("--processed-dir", type=str, default="../data/processed", help="Path to preprocessed CSVs.")
    parser.add_argument("--models-dir", type=str, default="../models", help="Path to save final models.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism.")
    parser.add_argument("--promote", action="store_true", help="Save directly to models/ instead of experiments/")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    processed_dir = Path(args.processed_dir)
    if not processed_dir.is_absolute():
        processed_dir = (script_dir / processed_dir).resolve()

    base_models_dir = Path(args.models_dir)
    if not base_models_dir.is_absolute():
        base_models_dir = (script_dir / base_models_dir).resolve()

    if args.promote:
        models_dir = base_models_dir
        logger.info("Promote flag set! Saving models to production directory.")
    else:
        models_dir = base_models_dir / "experiments"
        logger.info("Saving models to experiments directory (use --promote to deploy).")

    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    weakness_df = pd.DataFrame()
    grading_df = pd.DataFrame()
    feedback_df = pd.DataFrame()

    try:
        weakness_df = pd.read_csv(processed_dir / "weakness_dataset.csv")
        grading_df = pd.read_csv(processed_dir / "grading_dataset.csv")
        feedback_df = pd.read_csv(processed_dir / "feedback_corpus.csv")
    except Exception as e:
        logger.error(f"Failed to load datasets: {e}")

    # 2. Train Models
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "seed": args.seed,
        "split_strategy": "GroupShuffleSplit(author)",
    }

    report["weakness_classifier"] = train_weakness_classifier(weakness_df, models_dir)
    report["semantic_grader"] = train_semantic_grader(grading_df, models_dir)
    report["feedback_embeddings"] = generate_feedback_embeddings(feedback_df, models_dir)

    # 3. Save Report
    report_path = models_dir / "training_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
        
    logger.info(f"Training report saved to {report_path}")

if __name__ == "__main__":
    main()
