import os
import re
import string
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor


DATASET_PATH = Path("data/raw/datasets/asap2/ASAP2_train_sourcetexts.csv")
MODEL_DIR = Path("models/scorers")
MODEL_PATH = MODEL_DIR / "xgboost_tfidf_model.joblib"
VECTORIZER_PATH = MODEL_DIR / "tfidf_vectorizer.joblib"
METRICS_PATH = MODEL_DIR / "model_metrics.txt"

RANDOM_STATE = 42
MIN_TEXT_LENGTH = 150
CONSISTENCY_THRESHOLDS = (0.5, 1.0)

PREVIOUS_BASELINE = {
    "mae": 0.5114,
    "rmse": 0.6540,
    "r2": 0.5985,
    "consistency_0_5": 57.64,
}

PUNCTUATION_TABLE = str.maketrans({mark: " " for mark in string.punctuation})
STOPWORDS = set(ENGLISH_STOP_WORDS)


def _build_lemmatizer():
    try:
        from nltk.stem import WordNetLemmatizer

        lemmatizer = WordNetLemmatizer()
        lemmatizer.lemmatize("tests")
        return lemmatizer.lemmatize, "nltk-wordnet"
    except Exception:
        return _simple_lemmatize, "lightweight-suffix"


def _simple_lemmatize(token):
    if len(token) <= 4:
        return token

    for suffix in ("ingly", "edly", "ing", "edly", "ed", "ies", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            if suffix == "ies":
                return f"{token[:-3]}y"
            return token[: -len(suffix)]

    return token


LEMMATIZE, LEMMATIZER_NAME = _build_lemmatizer()


def normalize_spelling_light(text):
    contractions = {
        "can't": "cannot",
        "won't": "will not",
        "n't": " not",
        "'re": " are",
        "'s": " is",
        "'d": " would",
        "'ll": " will",
        "'t": " not",
        "'ve": " have",
        "'m": " am",
    }
    for source, target in contractions.items():
        text = text.replace(source, target)

    # Reduce noisy repeated characters while preserving normal double letters.
    return re.sub(r"(.)\1{2,}", r"\1\1", text)


def clean_text(text):
    text = str(text or "").lower()
    text = normalize_spelling_light(text)
    text = text.translate(PUNCTUATION_TABLE)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = []
    for token in text.split():
        if token in STOPWORDS or len(token) <= 1:
            continue
        if token.isdigit():
            continue
        tokens.append(LEMMATIZE(token))

    return " ".join(tokens)


def make_vectorizer():
    return TfidfVectorizer(
        ngram_range=(1, 3),
        max_features=25000,
        min_df=3,
        max_df=0.90,
        sublinear_tf=True,
        stop_words="english",
        dtype=np.float32,
    )


def make_xgboost_model():
    return XGBRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=8,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.05,
        reg_lambda=2.0,
        objective="reg:squarederror",
        eval_metric="rmse",
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def regression_metrics(y_true, predictions):
    predictions = np.asarray(predictions)
    y_true = np.asarray(y_true)
    return {
        "mae": mean_absolute_error(y_true, predictions),
        "rmse": np.sqrt(mean_squared_error(y_true, predictions)),
        "r2": r2_score(y_true, predictions),
        "consistency_0_5": (np.abs(predictions - y_true) <= 0.5).mean() * 100,
        "consistency_1_0": (np.abs(predictions - y_true) <= 1.0).mean() * 100,
    }


def print_metrics(title, metrics):
    print(f"\n{title}")
    print("-" * len(title))
    print(f"MAE: {metrics['mae']:.4f}")
    print(f"RMSE: {metrics['rmse']:.4f}")
    print(f"R2 Score: {metrics['r2']:.4f}")
    print(f"Consistency within +/-0.5: {metrics['consistency_0_5']:.2f}%")
    print(f"Consistency within +/-1.0: {metrics['consistency_1_0']:.2f}%")


def print_distribution(label, values):
    series = pd.Series(values)
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Count: {len(series)}")
    print(f"Mean: {series.mean():.4f}")
    print(f"Std: {series.std():.4f}")
    print(f"Min: {series.min():.4f}")
    print(f"25%: {series.quantile(0.25):.4f}")
    print(f"50%: {series.quantile(0.50):.4f}")
    print(f"75%: {series.quantile(0.75):.4f}")
    print(f"Max: {series.max():.4f}")


def load_and_clean_dataset():
    print("Loading dataset...")
    df = pd.read_csv(DATASET_PATH)

    print("Cleaning dataset...")
    df = df[["full_text", "score"]].dropna()
    df["full_text"] = df["full_text"].astype(str)
    df = df[df["full_text"].str.len() > MIN_TEXT_LENGTH]
    df["clean_text"] = df["full_text"].apply(clean_text)
    df = df[df["clean_text"].str.split().str.len() >= 30]
    df = df.drop_duplicates(subset=["clean_text", "score"])

    print(f"Text lemmatizer: {LEMMATIZER_NAME}")
    print(f"Training samples after cleaning: {len(df)}")
    print_distribution("Score Distribution", df["score"])

    return df


def run_cross_validation(X, y):
    print("\nUsing 3-fold cross-validation for faster demo/training execution.")
    print("\nRunning 3-fold cross-validation...")
    pipeline = Pipeline(
        [
            ("tfidf", make_vectorizer()),
            ("xgb", make_xgboost_model()),
        ]
    )
    cv = KFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_validate(
        pipeline,
        X,
        y,
        cv=cv,
        scoring={"mae": "neg_mean_absolute_error", "r2": "r2"},
        n_jobs=1,
        return_train_score=True,
    )

    cv_summary = {
        "mean_train_mae": -scores["train_mae"].mean(),
        "mean_test_mae": -scores["test_mae"].mean(),
        "mean_train_r2": scores["train_r2"].mean(),
        "mean_test_r2": scores["test_r2"].mean(),
    }

    print(f"CV Train MAE: {cv_summary['mean_train_mae']:.4f}")
    print(f"CV Test MAE: {cv_summary['mean_test_mae']:.4f}")
    print(f"CV Test MAE Std: {scores['test_mae'].std():.4f}")
    print(f"CV Train R2: {cv_summary['mean_train_r2']:.4f}")
    print(f"CV Test R2: {cv_summary['mean_test_r2']:.4f}")
    print(f"CV Test R2 Std: {scores['test_r2'].std():.4f}")

    return cv_summary


def train_tfidf_xgboost(X, y):
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )

    print("\nTrain/Test Split")
    print("----------------")
    print(f"Train size: {len(X_train)}")
    print(f"Test size: {len(X_test)}")

    vectorizer = make_vectorizer()
    print("\nVectorizing text with TF-IDF...")
    X_train_vectorized = vectorizer.fit_transform(X_train)
    X_test_vectorized = vectorizer.transform(X_test)
    print(f"Vocabulary size: {len(vectorizer.vocabulary_)}")

    print("\nTraining XGBoost regressor...")
    model = make_xgboost_model()
    model.fit(X_train_vectorized, y_train)

    train_predictions = model.predict(X_train_vectorized)
    test_predictions = model.predict(X_test_vectorized)

    train_metrics = regression_metrics(y_train, train_predictions)
    test_metrics = regression_metrics(y_test, test_predictions)

    print_metrics("Train Metrics", train_metrics)
    print_metrics("Test Metrics", test_metrics)
    print_distribution("Prediction Distribution", test_predictions)

    overfit_gap = test_metrics["mae"] - train_metrics["mae"]
    r2_gap = train_metrics["r2"] - test_metrics["r2"]
    overfit_warning = overfit_gap > 0.15 or r2_gap > 0.15
    if overfit_warning:
        print("\nWARNING: Possible overfitting detected.")
        print(f"MAE gap (test - train): {overfit_gap:.4f}")
        print(f"R2 gap (train - test): {r2_gap:.4f}")
    else:
        print("\nOverfitting check: no major train/test gap detected.")

    return {
        "model": model,
        "vectorizer": vectorizer,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "overfit_warning": overfit_warning,
        "overfit_gap": overfit_gap,
        "r2_gap": r2_gap,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "vocabulary_size": len(vectorizer.vocabulary_),
    }


def maybe_train_sbert_xgboost(texts, y):
    if os.getenv("SKIP_SBERT", "0") == "1":
        print("\nSkipping SBERT comparison because SKIP_SBERT=1.")
        return None

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        print(f"\nSBERT comparison skipped: sentence-transformers unavailable ({exc}).")
        return None

    print("\nTraining optional SBERT embeddings + XGBoost comparison...")
    X_train, X_test, y_train, y_test = train_test_split(
        texts,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )

    try:
        embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            local_files_only=os.getenv("SBERT_LOCAL_ONLY", "1") == "1",
        )
    except TypeError:
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as exc:
        print(f"SBERT comparison skipped: embedding model is not locally available ({exc}).")
        print("Set SBERT_LOCAL_ONLY=0 if you intentionally want to allow a download.")
        return None
    train_embeddings = embedding_model.encode(
        X_train.tolist(),
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    test_embeddings = embedding_model.encode(
        X_test.tolist(),
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    model = make_xgboost_model()
    model.fit(train_embeddings, y_train)
    predictions = model.predict(test_embeddings)
    metrics = regression_metrics(y_test, predictions)
    print_metrics("SBERT + XGBoost Test Metrics", metrics)

    return {
        "model_name": "SBERT + XGBoost",
        "test_metrics": metrics,
    }


def save_artifacts(result, cv_summary, sbert_result=None):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(result["model"], MODEL_PATH)
    joblib.dump(result["vectorizer"], VECTORIZER_PATH)

    metrics = result["test_metrics"]
    baseline_delta = {
        "mae": PREVIOUS_BASELINE["mae"] - metrics["mae"],
        "rmse": PREVIOUS_BASELINE["rmse"] - metrics["rmse"],
        "r2": metrics["r2"] - PREVIOUS_BASELINE["r2"],
        "consistency_0_5": metrics["consistency_0_5"] - PREVIOUS_BASELINE["consistency_0_5"],
    }

    recommendation = "TF-IDF + XGBoost"
    if sbert_result and sbert_result["test_metrics"]["mae"] < metrics["mae"]:
        recommendation = "SBERT + XGBoost performed better in this experiment, but runtime currently saves TF-IDF + XGBoost for API compatibility."

    metrics_text = "\n".join(
        [
            "Model: XGBoost Regressor",
            "Pipeline: TF-IDF + XGBoost",
            "Dataset: ASAP 2.0",
            f"Train size: {result['train_size']}",
            f"Test size: {result['test_size']}",
            f"Vocabulary size: {result['vocabulary_size']}",
            f"MAE: {metrics['mae']:.4f}",
            f"RMSE: {metrics['rmse']:.4f}",
            f"R2 Score: {metrics['r2']:.4f}",
            f"Consistency within +/-0.5: {metrics['consistency_0_5']:.2f}%",
            f"Consistency within +/-1.0: {metrics['consistency_1_0']:.2f}%",
            f"CV Mean MAE: {cv_summary['mean_test_mae']:.4f}",
            f"CV Mean R2: {cv_summary['mean_test_r2']:.4f}",
            f"Train MAE: {result['train_metrics']['mae']:.4f}",
            f"Train R2: {result['train_metrics']['r2']:.4f}",
            f"Overfitting warning: {result['overfit_warning']}",
            f"MAE improvement vs previous baseline: {baseline_delta['mae']:.4f}",
            f"RMSE improvement vs previous baseline: {baseline_delta['rmse']:.4f}",
            f"R2 improvement vs previous baseline: {baseline_delta['r2']:.4f}",
            f"+/-0.5 consistency delta vs previous baseline: {baseline_delta['consistency_0_5']:.2f}%",
            f"Recommended final model: {recommendation}",
            "",
        ]
    )

    METRICS_PATH.write_text(metrics_text, encoding="utf-8")
    print(f"\nSaved model: {MODEL_PATH}")
    print(f"Saved vectorizer: {VECTORIZER_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Recommended final model: {recommendation}")


def main():
    df = load_and_clean_dataset()
    X = df["clean_text"]
    y = df["score"].astype(float)

    cv_summary = run_cross_validation(X, y)
    tfidf_result = train_tfidf_xgboost(X, y)
    sbert_result = maybe_train_sbert_xgboost(X, y)

    print("\nPrevious Baseline Comparison")
    print("----------------------------")
    print(f"Previous MAE: {PREVIOUS_BASELINE['mae']:.4f}")
    print(f"Current MAE: {tfidf_result['test_metrics']['mae']:.4f}")
    print(f"Previous R2: {PREVIOUS_BASELINE['r2']:.4f}")
    print(f"Current R2: {tfidf_result['test_metrics']['r2']:.4f}")
    print(f"Previous +/-0.5 Consistency: {PREVIOUS_BASELINE['consistency_0_5']:.2f}%")
    print(f"Current +/-0.5 Consistency: {tfidf_result['test_metrics']['consistency_0_5']:.2f}%")

    save_artifacts(tfidf_result, cv_summary, sbert_result)


if __name__ == "__main__":
    main()
