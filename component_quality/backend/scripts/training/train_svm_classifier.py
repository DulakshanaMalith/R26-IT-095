"""Train and evaluate a TF-IDF Linear SVM annotation classifier."""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FINAL_DATASET_PATH = ROOT_DIR / "processed" / "weakness_dataset_final.csv"
FALLBACK_DATASET_PATH = ROOT_DIR / "processed" / "weakness_dataset.csv"
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"
MODEL_PATH = MODELS_DIR / "weakness_svm_model.pkl"
RESULTS_PATH = RESULTS_DIR / "svm_results.txt"

TEST_SIZE = 0.20
RANDOM_STATE = 42


def select_dataset_path() -> Path:
    """Prefer the finalized dataset and fall back to the original dataset."""
    if FINAL_DATASET_PATH.exists():
        return FINAL_DATASET_PATH
    if FALLBACK_DATASET_PATH.exists():
        return FALLBACK_DATASET_PATH
    raise FileNotFoundError(
        "Neither weakness_dataset_final.csv nor weakness_dataset.csv was found."
    )


def load_dataset(path: Path) -> pd.DataFrame:
    """Load and validate non-empty annotation text and labels."""
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Run create_weakness_dataset.py before this script."
        )

    try:
        dataframe = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"Dataset is empty: {path}") from exc
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc
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


def build_model() -> Pipeline:
    """Create the requested TF-IDF and balanced Linear SVM pipeline."""
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=5000)),
            ("classifier", LinearSVC(class_weight="balanced")),
        ]
    )


def calculate_metrics(y_true, y_pred) -> dict[str, float]:
    """Calculate the key metrics used to compare imbalanced classifiers."""
    _, _, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )
    _, _, weighted_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="weighted",
        zero_division=0,
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
    }


def build_metrics_report(
    y_true,
    y_pred,
    metrics: dict[str, float],
    dataset_path: Path,
    dataset_size: int,
) -> str:
    """Build a readable evaluation report for imbalanced multiclass data."""
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
    classification_metrics = classification_report(
        y_true,
        y_pred,
        zero_division=0,
    )

    return "\n".join(
        [
            "TF-IDF + Linear SVM Results",
            "============================",
            f"Dataset: {dataset_path}",
            f"Dataset size: {dataset_size}",
            f"Model file path: {MODEL_PATH}",
            f"Accuracy: {metrics['accuracy']:.4f}",
            f"Macro precision: {macro_precision:.4f}",
            f"Macro recall: {macro_recall:.4f}",
            f"Macro F1-score: {metrics['macro_f1']:.4f}",
            f"Weighted precision: {weighted_precision:.4f}",
            f"Weighted recall: {weighted_recall:.4f}",
            f"Weighted F1-score: {metrics['weighted_f1']:.4f}",
            "",
            "Classification Report",
            "---------------------",
            classification_metrics,
        ]
    )


def save_and_verify_model(model: Pipeline, test_text: str) -> str:
    """Persist the full pipeline, reload it, and verify one prediction."""
    try:
        with MODEL_PATH.open("wb") as file:
            pickle.dump(model, file)
        with MODEL_PATH.open("rb") as file:
            reloaded_model = pickle.load(file)
    except (OSError, pickle.PickleError, EOFError, AttributeError) as exc:
        raise RuntimeError(f"Could not save or reload SVM model: {exc}") from exc

    prediction = str(reloaded_model.predict([test_text])[0])
    if not prediction:
        raise RuntimeError("Reloaded SVM model returned an empty prediction.")
    return prediction


def main() -> None:
    """Train, persist, reload, and evaluate the Linear SVM pipeline."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    dataset_path = select_dataset_path()
    dataframe = load_dataset(dataset_path)

    X_train, X_test, y_train, y_test = train_test_split(
        dataframe["annotated_text"],
        dataframe["tag"],
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=dataframe["tag"],
    )

    model = build_model()

    print(f"Using dataset: {dataset_path}")
    print(f"Loaded {len(dataframe)} annotation records.")
    print(f"Training records: {len(X_train)}")
    print(f"Test records: {len(X_test)}")
    print("Training TF-IDF + Linear SVM classifier...")

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    metrics = calculate_metrics(y_test, predictions)
    verification_prediction = save_and_verify_model(model, X_test.iloc[0])
    metrics_text = build_metrics_report(
        y_test,
        predictions,
        metrics,
        dataset_path,
        len(dataframe),
    )
    try:
        RESULTS_PATH.write_text(metrics_text + "\n", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not save SVM evaluation report: {exc}") from exc

    print("\n" + metrics_text)
    print(f"\nReload verification prediction: {verification_prediction}")
    print(f"Model saved to: {MODEL_PATH}")
    print(f"\nMetrics saved to: {RESULTS_PATH}")
    print("\nSVM MODEL TRAINED AND SAVED SUCCESSFULLY")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"SVM training failed: {error}")
        raise SystemExit(1) from error
