"""Train a TF-IDF Random Forest baseline for semantic grading."""

from __future__ import annotations

import math
import pickle
import shutil
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = ROOT_DIR / "processed" / "exposia_grading_dataset.csv"
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"
MODEL_PATH = MODELS_DIR / "semantic_grading_model.pkl"
MODEL_BACKUP_PATH = MODELS_DIR / "semantic_grading_model_before_tuning.pkl"
RESULTS_PATH = RESULTS_DIR / "semantic_grading_results.txt"

TEST_SIZE = 0.20
RANDOM_STATE = 42
REQUIRED_COLUMNS = {"text", "total_score"}
SEARCH_ITERATIONS = 60


def load_and_clean_dataset(path: Path) -> tuple[pd.DataFrame, int]:
    """Load, validate, and clean report text and numeric target scores."""
    if not path.exists():
        raise FileNotFoundError(
            f"Grading dataset not found: {path}\n"
            "Run preprocessing.py before this script."
        )

    try:
        dataframe = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"Grading dataset is empty: {path}") from exc
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc

    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Grading dataset is missing required columns: {missing}")

    original_rows = len(dataframe)
    cleaned = dataframe[["text", "total_score"]].dropna().copy()
    cleaned["text"] = cleaned["text"].astype(str).str.strip()
    cleaned["total_score"] = pd.to_numeric(cleaned["total_score"], errors="coerce")
    cleaned = cleaned.dropna(subset=["total_score"])
    cleaned = cleaned[cleaned["text"] != ""]
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)

    if len(cleaned) < 5:
        raise ValueError("Too few valid grading records remain for model training.")

    return cleaned, original_rows


def build_model() -> Pipeline:
    """Create the TF-IDF and Random Forest regression pipeline."""
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=10000)),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=300,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def build_search_model() -> RandomizedSearchCV:
    """Create a 5-fold Random Forest hyperparameter search."""
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=10000)),
            (
                "regressor",
                RandomForestRegressor(
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    parameter_grid = {
        "regressor__n_estimators": [200, 300, 500, 800],
        "regressor__max_depth": [None, 6, 10, 14, 18, 24],
        "regressor__min_samples_split": [2, 4, 6, 10, 14],
        "regressor__min_samples_leaf": [1, 2, 3, 4, 6],
        "regressor__max_features": [1.0, "sqrt", "log2", 0.5, 0.75],
        "regressor__bootstrap": [True],
    }
    cross_validation = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    return RandomizedSearchCV(
        estimator=pipeline,
        param_distributions=parameter_grid,
        n_iter=SEARCH_ITERATIONS,
        scoring="neg_mean_absolute_error",
        cv=cross_validation,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        refit=True,
        verbose=1,
        return_train_score=True,
    )


def evaluate_model(y_true, predictions) -> dict[str, float]:
    """Calculate standard regression evaluation metrics."""
    mse = mean_squared_error(y_true, predictions)
    return {
        "mae": mean_absolute_error(y_true, predictions),
        "rmse": math.sqrt(mse),
        "r2": r2_score(y_true, predictions),
    }


def tuned_model_is_better(current_metrics: dict[str, float], tuned_metrics: dict[str, float]) -> bool:
    """Require MAE improvement without RMSE or R2 regression."""
    return (
        tuned_metrics["mae"] < current_metrics["mae"]
        and tuned_metrics["rmse"] <= current_metrics["rmse"]
        and tuned_metrics["r2"] >= current_metrics["r2"]
    )


def build_tuning_results_report(
    original_rows: int,
    final_rows: int,
    train_rows: int,
    test_rows: int,
    current_metrics: dict[str, float],
    tuned_metrics: dict[str, float],
    best_params: dict[str, object],
    best_cv_mae: float,
    replaced: bool,
) -> str:
    """Build a reproducible text report for the tuning experiment."""
    return "\n".join(
        [
            "Semantic Grading Random Forest Tuning Results",
            "=============================================",
            "Model: TF-IDF + Random Forest Regressor",
            "Input column: text",
            "Target column: total_score",
            f"Random state: {RANDOM_STATE}",
            f"Original records: {original_rows}",
            f"Clean records: {final_rows}",
            f"Training records: {train_rows}",
            f"Test records: {test_rows}",
            "Cross validation: 5-fold KFold(shuffle=True, random_state=42)",
            f"Search: RandomizedSearchCV, n_iter={SEARCH_ITERATIONS}, scoring=neg_mean_absolute_error",
            "",
            "Current production model:",
            f"  MAE: {current_metrics['mae']:.4f}",
            f"  RMSE: {current_metrics['rmse']:.4f}",
            f"  R^2 Score: {current_metrics['r2']:.4f}",
            "",
            "Tuned candidate model:",
            f"  MAE: {tuned_metrics['mae']:.4f}",
            f"  RMSE: {tuned_metrics['rmse']:.4f}",
            f"  R^2 Score: {tuned_metrics['r2']:.4f}",
            f"  Best CV MAE: {best_cv_mae:.4f}",
            f"  Best hyperparameters: {best_params}",
            "",
            f"Production model replaced: {'yes' if replaced else 'no'}",
        ]
    )


def build_results_report(
    original_rows: int,
    final_rows: int,
    train_rows: int,
    test_rows: int,
    metrics: dict[str, float],
) -> str:
    """Build a reproducible text report for the baseline experiment."""
    return "\n".join(
        [
            "Semantic Grading Baseline Results",
            "=================================",
            "Model: TF-IDF + Random Forest Regressor",
            "Input column: text",
            "Target column: total_score",
            f"Random state: {RANDOM_STATE}",
            f"Original records: {original_rows}",
            f"Clean records: {final_rows}",
            f"Training records: {train_rows}",
            f"Test records: {test_rows}",
            "",
            f"MAE: {metrics['mae']:.4f}",
            f"RMSE: {metrics['rmse']:.4f}",
            f"R² Score: {metrics['r2']:.4f}",
        ]
    )


def main() -> None:
    """Tune, evaluate, and conditionally save the semantic grading model."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dataframe, original_rows = load_and_clean_dataset(DATASET_PATH)
    X_train, X_test, y_train, y_test = train_test_split(
        dataframe["text"],
        dataframe["total_score"],
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    print(f"Loaded {original_rows} records; {len(dataframe)} remain after cleaning.")
    print(f"Training records: {len(X_train)}")
    print(f"Test records: {len(X_test)}")
    print("Evaluating current production model...")

    if MODEL_PATH.exists():
        with MODEL_PATH.open("rb") as file:
            current_model = pickle.load(file)
    else:
        current_model = build_model()
        current_model.fit(X_train, y_train)

    current_predictions = current_model.predict(X_test)
    current_metrics = evaluate_model(y_test, current_predictions)

    print("Running 5-fold RandomizedSearchCV for Random Forest hyperparameters...")
    search = build_search_model()
    search.fit(X_train, y_train)
    tuned_model = search.best_estimator_
    tuned_predictions = tuned_model.predict(X_test)
    tuned_metrics = evaluate_model(y_test, tuned_predictions)
    replaced = tuned_model_is_better(current_metrics, tuned_metrics)

    report = build_tuning_results_report(
        original_rows,
        len(dataframe),
        len(X_train),
        len(X_test),
        current_metrics,
        tuned_metrics,
        search.best_params_,
        -search.best_score_,
        replaced,
    )

    try:
        if replaced:
            if MODEL_PATH.exists() and not MODEL_BACKUP_PATH.exists():
                shutil.copy2(MODEL_PATH, MODEL_BACKUP_PATH)
            with MODEL_PATH.open("wb") as file:
                pickle.dump(tuned_model, file)
        RESULTS_PATH.write_text(report + "\n", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not save model outputs: {exc}") from exc

    print("\n" + report)
    if replaced:
        print(f"\nTuned model saved to: {MODEL_PATH}")
    else:
        print(f"\nProduction model kept unchanged: {MODEL_PATH}")
    print(f"Evaluation report saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Semantic grading training failed: {error}")
        raise SystemExit(1) from error
