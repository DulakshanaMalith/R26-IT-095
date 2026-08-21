"""Finalize Exposia datasets for downstream machine-learning experiments."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT_DIR / "processed"
RESULTS_DIR = ROOT_DIR / "results"

WEAKNESS_INPUT = PROCESSED_DIR / "weakness_dataset.csv"
FEEDBACK_INPUT = PROCESSED_DIR / "feedback_dataset.csv"
WEAKNESS_OUTPUT = PROCESSED_DIR / "weakness_dataset_final.csv"
FEEDBACK_OUTPUT = PROCESSED_DIR / "feedback_dataset_final.csv"
SUMMARY_OUTPUT = RESULTS_DIR / "final_dataset_summary.txt"


def load_dataset(path: Path, required_columns: set[str]) -> pd.DataFrame:
    """Load a CSV dataset and validate its required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Required input dataset not found: {path}")

    try:
        dataframe = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"Input dataset is empty: {path}") from exc
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Could not read dataset {path}: {exc}") from exc

    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{path.name} is missing required columns: {missing}")

    return dataframe


def clean_weakness_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Clean annotation text and labels for weakness detection."""
    cleaned = dataframe.dropna(subset=["annotated_text", "tag"]).copy()
    cleaned["annotated_text"] = cleaned["annotated_text"].astype(str).str.strip()
    cleaned["tag"] = cleaned["tag"].astype(str).str.strip()
    cleaned = cleaned[
        (cleaned["annotated_text"] != "") & (cleaned["tag"] != "")
    ]
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    return cleaned


def clean_feedback_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Clean annotation-comment pairs for feedback generation."""
    cleaned = dataframe.dropna(
        subset=["annotated_text", "tag", "comment_text"]
    ).copy()
    for column in ("annotated_text", "tag", "comment_text"):
        cleaned[column] = cleaned[column].astype(str).str.strip()

    cleaned = cleaned[
        (cleaned["annotated_text"] != "")
        & (cleaned["tag"] != "")
        & (cleaned["comment_text"] != "")
    ]
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    return cleaned


def format_tag_distribution(dataframe: pd.DataFrame) -> str:
    """Return a stable, human-readable tag distribution."""
    return dataframe["tag"].value_counts().to_string()


def build_summary(
    weakness_original: pd.DataFrame,
    weakness_final: pd.DataFrame,
    feedback_original: pd.DataFrame,
    feedback_final: pd.DataFrame,
) -> str:
    """Build the final dataset audit summary."""
    weakness_removed = len(weakness_original) - len(weakness_final)
    feedback_removed = len(feedback_original) - len(feedback_final)

    return "\n".join(
        [
            "Exposia Final Dataset Summary",
            "=============================",
            "",
            "Weakness Detection Dataset",
            "--------------------------",
            f"Original rows: {len(weakness_original)}",
            f"Final rows: {len(weakness_final)}",
            f"Removed records: {weakness_removed}",
            f"Final dataset size: {weakness_final.shape}",
            "Tag distribution:",
            format_tag_distribution(weakness_final),
            "",
            "Feedback Generation Dataset",
            "---------------------------",
            f"Original rows: {len(feedback_original)}",
            f"Final rows: {len(feedback_final)}",
            f"Removed records: {feedback_removed}",
            f"Final dataset size: {feedback_final.shape}",
            "Tag distribution:",
            format_tag_distribution(feedback_final),
        ]
    )


def print_dataset_results(
    name: str,
    original: pd.DataFrame,
    final: pd.DataFrame,
) -> None:
    """Print finalization results for one dataset."""
    print(f"\n{name}")
    print("-" * len(name))
    print(f"Original shape: {original.shape}")
    print(f"Final shape: {final.shape}")
    print("Tag distribution:")
    print(format_tag_distribution(final))


def main() -> None:
    """Finalize both datasets and save their audit summary."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    weakness_original = load_dataset(
        WEAKNESS_INPUT,
        {"annotated_text", "tag"},
    )
    feedback_original = load_dataset(
        FEEDBACK_INPUT,
        {"annotated_text", "tag", "comment_text"},
    )

    weakness_final = clean_weakness_dataset(weakness_original)
    feedback_final = clean_feedback_dataset(feedback_original)

    try:
        weakness_final.to_csv(WEAKNESS_OUTPUT, index=False)
        feedback_final.to_csv(FEEDBACK_OUTPUT, index=False)

        summary = build_summary(
            weakness_original,
            weakness_final,
            feedback_original,
            feedback_final,
        )
        SUMMARY_OUTPUT.write_text(summary + "\n", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not save finalized outputs: {exc}") from exc

    print_dataset_results(
        "Weakness Detection Dataset",
        weakness_original,
        weakness_final,
    )
    print_dataset_results(
        "Feedback Generation Dataset",
        feedback_original,
        feedback_final,
    )

    print("\nDATASET FINALIZATION COMPLETED")
    print(f"Weakness dataset: {WEAKNESS_OUTPUT}")
    print(f"Feedback dataset: {FEEDBACK_OUTPUT}")
    print(f"Summary report: {SUMMARY_OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Dataset finalization failed: {error}")
        raise SystemExit(1) from error
