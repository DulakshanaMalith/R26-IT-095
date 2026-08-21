"""Verify Exposia preprocessing, training, and saved model artifacts."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"
REPORT_PATH = RESULTS_DIR / "training_pipeline_verification.txt"

REQUIRED_DATASETS = {
    "weakness_dataset_final.csv": {
        "path": PROCESSED_DIR / "weakness_dataset_final.csv",
        "columns": {"annotated_text", "tag"},
    },
    "feedback_dataset_final.csv": {
        "path": PROCESSED_DIR / "feedback_dataset_final.csv",
        "columns": {"annotated_text", "tag", "comment_text"},
    },
    "exposia_grading_dataset.csv": {
        "path": PROCESSED_DIR / "exposia_grading_dataset.csv",
        "columns": {"text", "total_score"},
    },
}

PRODUCTION_MODELS = {
    "weakness_svm_model.pkl": MODELS_DIR / "weakness_svm_model.pkl",
    "feedback_embeddings.pkl": MODELS_DIR / "feedback_embeddings.pkl",
    "semantic_grading_model.pkl": MODELS_DIR / "semantic_grading_model.pkl",
}

EXPERIMENTAL_MODELS = {
    "sentence_bert_classifier.pkl": MODELS_DIR / "sentence_bert_classifier.pkl",
}

REQUIRED_RESULTS = {
    "svm_results.txt": RESULTS_DIR / "svm_results.txt",
    "semantic_grading_results.txt": RESULTS_DIR / "semantic_grading_results.txt",
    "feedback_retrieval_demo.txt": RESULTS_DIR / "feedback_retrieval_demo.txt",
}

WEAKNESS_SAMPLE = "The methodology does not explain data collection clearly."
GRADING_SAMPLE = (
    "This academic proposal investigates how digital feedback tools can improve "
    "undergraduate research writing. The study presents a focused research "
    "question, reviews relevant literature on formative assessment, and proposes "
    "a mixed-methods design using survey responses, interview data, and rubric "
    "scores. Data collection procedures are described, ethical approval is "
    "considered, and the timeline explains how analysis will be completed before "
    "submission. The proposal also identifies limitations related to sample size "
    "and access to participants, while explaining how these risks will be managed."
)


def add_section(lines: list[str], title: str) -> None:
    """Append a readable section heading to the report."""
    lines.extend(["", title, "-" * len(title)])


def record_warning(warnings: list[str], message: str) -> None:
    """Store and print a warning without stopping verification."""
    warnings.append(message)
    print(f"WARNING: {message}")


def file_status(path: Path) -> str:
    """Return a concise existence and size status for a path."""
    if not path.exists():
        return "MISSING"
    return f"FOUND ({path.stat().st_size} bytes)"


def inspect_dataset(
    name: str,
    path: Path,
    required_columns: set[str],
    lines: list[str],
    warnings: list[str],
) -> None:
    """Load a dataset and report structural preprocessing evidence."""
    print(f"\nDataset: {name}")
    lines.append(f"{name}: {file_status(path)}")

    if not path.exists():
        record_warning(warnings, f"Dataset missing: {path}")
        return

    try:
        dataframe = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        record_warning(warnings, f"Dataset is empty and could not be loaded: {path}")
        lines.append(f"  Load error: {exc}")
        return
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        record_warning(warnings, f"Dataset could not be loaded: {path} ({exc})")
        lines.append(f"  Load error: {exc}")
        return

    missing_values = int(dataframe.isna().sum().sum())
    duplicate_rows = int(dataframe.duplicated().sum())
    missing_columns = sorted(required_columns.difference(dataframe.columns))

    print(f"  Shape: {dataframe.shape}")
    print(f"  Columns: {list(dataframe.columns)}")
    print(f"  Missing values count: {missing_values}")
    print(f"  Duplicate rows count: {duplicate_rows}")

    lines.extend(
        [
            f"  Shape: {dataframe.shape}",
            f"  Columns: {', '.join(map(str, dataframe.columns))}",
            f"  Missing values count: {missing_values}",
            f"  Duplicate rows count: {duplicate_rows}",
        ]
    )

    if missing_columns:
        message = f"{name} is missing required columns: {', '.join(missing_columns)}"
        record_warning(warnings, message)
        lines.append(f"  Required columns: FAILED ({', '.join(missing_columns)})")
    else:
        lines.append("  Required columns: OK")


def load_pickle_artifact(
    name: str,
    path: Path,
    lines: list[str],
    warnings: list[str],
) -> Any | None:
    """Load a pickle artifact and record whether it is backend-usable."""
    lines.append(f"{name}: {file_status(path)}")
    if not path.exists():
        record_warning(warnings, f"Model artifact missing: {path}")
        return None

    try:
        with path.open("rb") as file:
            artifact = pickle.load(file)
    except (pickle.PickleError, EOFError, AttributeError, ImportError, OSError) as exc:
        record_warning(warnings, f"Could not load model artifact {path}: {exc}")
        lines.append(f"  Load status: FAILED ({exc})")
        return None
    except Exception as exc:  # Defensive: third-party pickle imports can fail broadly.
        record_warning(warnings, f"Could not load model artifact {path}: {exc}")
        lines.append(f"  Load status: FAILED ({exc})")
        return None

    lines.append(f"  Load status: OK ({type(artifact).__name__})")
    print(f"Loaded model artifact: {name} ({type(artifact).__name__})")
    return artifact


def predict_with_model(model: Any, sample_text: str) -> str:
    """Run a simple sklearn-style text prediction."""
    prediction = model.predict([sample_text])
    if hasattr(prediction, "tolist"):
        prediction = prediction.tolist()
    if isinstance(prediction, (list, tuple)):
        return str(prediction[0])
    return str(prediction)


def test_inference(
    models: dict[str, Any | None],
    lines: list[str],
    warnings: list[str],
) -> None:
    """Run lightweight inference checks on the saved model artifacts."""
    weakness_model = models.get("weakness_svm_model.pkl")
    if weakness_model is None:
        lines.append("Weakness SVM inference: SKIPPED")
    else:
        try:
            prediction = predict_with_model(weakness_model, WEAKNESS_SAMPLE)
        except Exception as exc:
            record_warning(warnings, f"Weakness SVM inference failed: {exc}")
            lines.append(f"Weakness SVM inference: FAILED ({exc})")
        else:
            lines.append(f"Weakness SVM inference: OK -> {prediction}")
            print(f"Weakness SVM prediction: {prediction}")

    grading_model = models.get("semantic_grading_model.pkl")
    if grading_model is None:
        lines.append("Semantic grading inference: SKIPPED")
    else:
        try:
            prediction = predict_with_model(grading_model, GRADING_SAMPLE)
        except Exception as exc:
            record_warning(warnings, f"Semantic grading inference failed: {exc}")
            lines.append(f"Semantic grading inference: FAILED ({exc})")
        else:
            lines.append(f"Semantic grading inference: OK -> {prediction}")
            print(f"Semantic grading prediction: {prediction}")

    feedback_artifact = models.get("feedback_embeddings.pkl")
    required_keys = {"embeddings", "annotated_texts", "comments", "model_name"}
    if feedback_artifact is None:
        lines.append("Feedback embeddings structure: SKIPPED")
    elif not isinstance(feedback_artifact, dict):
        message = "feedback_embeddings.pkl is not a dictionary artifact."
        record_warning(warnings, message)
        lines.append(f"Feedback embeddings structure: FAILED ({message})")
    else:
        missing_keys = sorted(required_keys.difference(feedback_artifact))
        if missing_keys:
            message = "feedback_embeddings.pkl missing keys: " + ", ".join(missing_keys)
            record_warning(warnings, message)
            lines.append(f"Feedback embeddings structure: FAILED ({', '.join(missing_keys)})")
        else:
            embedding_count = len(feedback_artifact["embeddings"])
            text_count = len(feedback_artifact["annotated_texts"])
            comment_count = len(feedback_artifact["comments"])
            model_name = feedback_artifact["model_name"]
            lines.extend(
                [
                    "Feedback embeddings structure: OK",
                    f"  Embeddings: {embedding_count}",
                    f"  Annotated texts: {text_count}",
                    f"  Comments: {comment_count}",
                    f"  Model name: {model_name}",
                ]
            )
            print("Feedback embeddings contain required keys.")

    sentence_bert_artifact = models.get("sentence_bert_classifier.pkl")
    if sentence_bert_artifact is None:
        lines.append("Sentence-BERT classifier artifact: SKIPPED")
    elif isinstance(sentence_bert_artifact, dict):
        keys = ", ".join(sorted(map(str, sentence_bert_artifact.keys())))
        lines.append(f"Sentence-BERT classifier artifact: OK keys -> {keys}")
    else:
        lines.append(
            "Sentence-BERT classifier artifact: OK "
            f"({type(sentence_bert_artifact).__name__})"
        )


def inspect_result_file(
    name: str,
    path: Path,
    lines: list[str],
    warnings: list[str],
) -> None:
    """Verify that an evaluation or demo report exists and is not empty."""
    lines.append(f"{name}: {file_status(path)}")
    if not path.exists():
        record_warning(warnings, f"Result file missing: {path}")
        lines.append("  Availability: FAILED")
        return

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        record_warning(warnings, f"Could not read result file {path}: {exc}")
        lines.append(f"  Availability: FAILED ({exc})")
        return

    if content.strip():
        lines.append("  Availability: OK (not empty)")
        print(f"Result file available: {name}")
    else:
        record_warning(warnings, f"Result file is empty: {path}")
        lines.append("  Availability: FAILED (empty)")


def build_report_header() -> list[str]:
    """Create the report title and context block."""
    return [
        "ResearchPilot / Exposia Training Pipeline Verification",
        "=======================================================",
        f"Project root: {ROOT_DIR}",
        f"Processed folder: {PROCESSED_DIR}",
        f"Models folder: {MODELS_DIR}",
        f"Results folder: {RESULTS_DIR}",
    ]


def main() -> None:
    """Verify datasets, model artifacts, inference, and result reports."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    report_lines = build_report_header()

    add_section(report_lines, "Dataset Status and Preprocessing Evidence")
    for dataset_name, config in REQUIRED_DATASETS.items():
        inspect_dataset(
            dataset_name,
            config["path"],
            config["columns"],
            report_lines,
            warnings,
        )

    add_section(report_lines, "Production Model Load Status")
    loaded_models = {
        model_name: load_pickle_artifact(model_name, path, report_lines, warnings)
        for model_name, path in PRODUCTION_MODELS.items()
    }

    add_section(report_lines, "Experimental Model Load Status")
    experimental_models = {
        model_name: load_pickle_artifact(model_name, path, report_lines, warnings)
        for model_name, path in EXPERIMENTAL_MODELS.items()
    }
    report_lines.append(
        "sentence_bert_classifier.pkl is retained for research comparison only. "
        "It is not loaded by the FastAPI production runtime."
    )
    loaded_models.update(experimental_models)

    add_section(report_lines, "Inference Test Results")
    test_inference(loaded_models, report_lines, warnings)

    add_section(report_lines, "Evaluation Report Availability")
    for result_name, path in REQUIRED_RESULTS.items():
        inspect_result_file(result_name, path, report_lines, warnings)

    add_section(report_lines, "Warnings")
    if warnings:
        report_lines.extend(f"- {warning}" for warning in warnings)
    else:
        report_lines.append("No warnings.")

    add_section(report_lines, "Final Conclusion")
    if warnings:
        report_lines.append(
            "Verification completed with warnings. Review the warnings above before "
            "treating the pipeline as fully backend-ready."
        )
    else:
        report_lines.append(
            "Verification passed. Preprocessing outputs, saved models, inference "
            "checks, and evaluation reports are present and usable."
        )

    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"\nVerification report saved to: {REPORT_PATH}")
    print("TRAINING PIPELINE VERIFICATION COMPLETED")


if __name__ == "__main__":
    main()
