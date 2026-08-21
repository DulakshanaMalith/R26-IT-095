"""Train a Sentence-BERT classifier for Exposia annotation tags.

The script embeds annotation text with all-MiniLM-L6-v2, trains a logistic
regression classifier, evaluates it on a stratified test split, and saves both
the fitted classifier artifact and a human-readable metrics report.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = ROOT_DIR / "processed" / "weakness_dataset.csv"
MODEL_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"
MODEL_PATH = MODEL_DIR / "sentence_bert_classifier.pkl"
RESULTS_PATH = RESULTS_DIR / "sentence_bert_results.txt"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TEST_SIZE = 0.20
RANDOM_STATE = 42


def load_dataset(path: Path) -> pd.DataFrame:
    """Load and validate the annotation classification dataset."""
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Run create_weakness_dataset.py before this script."
        )

    dataframe = pd.read_csv(path)
    required_columns = {"annotated_text", "tag"}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Dataset is missing required columns: {missing}")

    dataframe = dataframe[["annotated_text", "tag"]].dropna().copy()
    dataframe["annotated_text"] = dataframe["annotated_text"].astype(str).str.strip()
    dataframe["tag"] = dataframe["tag"].astype(str).str.strip()
    dataframe = dataframe[
        (dataframe["annotated_text"] != "") & (dataframe["tag"] != "")
    ].reset_index(drop=True)

    if dataframe.empty:
        raise ValueError("No valid annotation records remain after cleaning.")

    return dataframe


def format_metrics(y_true, y_pred, label_encoder: LabelEncoder) -> str:
    """Create a clear metrics report with macro and weighted averages."""
    accuracy = accuracy_score(y_true, y_pred)
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )
    weighted_precision, weighted_recall, weighted_f1, _ = (
        precision_recall_fscore_support(
            y_true,
            y_pred,
            average="weighted",
            zero_division=0,
        )
    )
    report = classification_report(
        y_true,
        y_pred,
        labels=range(len(label_encoder.classes_)),
        target_names=label_encoder.classes_,
        zero_division=0,
    )

    return "\n".join(
        [
            "Sentence-BERT + Logistic Regression Results",
            "============================================",
            f"Embedding model: {MODEL_NAME}",
            f"Accuracy: {accuracy:.4f}",
            f"Macro precision: {macro_precision:.4f}",
            f"Macro recall: {macro_recall:.4f}",
            f"Macro F1-score: {macro_f1:.4f}",
            f"Weighted precision: {weighted_precision:.4f}",
            f"Weighted recall: {weighted_recall:.4f}",
            f"Weighted F1-score: {weighted_f1:.4f}",
            "",
            "Classification Report",
            "---------------------",
            report,
        ]
    )


def main() -> None:
    """Run training, evaluation, and artifact persistence."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dataframe = load_dataset(DATASET_PATH)
    texts = dataframe["annotated_text"].tolist()

    label_encoder = LabelEncoder()
    labels = label_encoder.fit_transform(dataframe["tag"])

    train_texts, test_texts, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=labels,
    )

    print(f"Loaded {len(dataframe)} annotation records.")
    print(f"Training records: {len(train_texts)}")
    print(f"Test records: {len(test_texts)}")
    print(f"Loading embedding model: {MODEL_NAME}")

    embedding_model = SentenceTransformer(MODEL_NAME)
    print("Generating training embeddings...")
    train_embeddings = embedding_model.encode(
        train_texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    print("Generating test embeddings...")
    test_embeddings = embedding_model.encode(
        test_texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    classifier = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    classifier.fit(train_embeddings, y_train)
    predictions = classifier.predict(test_embeddings)

    metrics_text = format_metrics(y_test, predictions, label_encoder)
    RESULTS_PATH.write_text(metrics_text + "\n", encoding="utf-8")

    artifact = {
        "classifier": classifier,
        "label_encoder": label_encoder,
        "embedding_model_name": MODEL_NAME,
        "normalize_embeddings": True,
        "random_state": RANDOM_STATE,
    }
    with MODEL_PATH.open("wb") as file:
        pickle.dump(artifact, file)

    print("\n" + metrics_text)
    print(f"\nModel saved to: {MODEL_PATH}")
    print(f"Metrics saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
