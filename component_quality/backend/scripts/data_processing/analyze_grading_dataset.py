"""Analyze the Exposia grading dataset for semantic grading development."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = ROOT_DIR / "processed" / "exposia_grading_dataset.csv"
PLOTS_DIR = ROOT_DIR / "processed" / "grading_plots"
RESULTS_DIR = ROOT_DIR / "results"
REPORT_PATH = RESULTS_DIR / "grading_dataset_analysis.txt"

REQUIRED_COLUMNS = {"text", "total_score"}


def load_dataset(path: Path) -> pd.DataFrame:
    """Load the grading CSV and validate columns required for modeling."""
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

    if dataframe.empty:
        raise ValueError("Grading dataset contains no records.")

    return dataframe


def identify_column_roles(dataframe: pd.DataFrame) -> dict[str, list[str]]:
    """Identify semantic text, score, target, and metadata columns."""
    text_columns = [
        column
        for column in ("text", "criteria_json")
        if column in dataframe.columns
    ]
    score_columns = [
        column
        for column in dataframe.columns
        if "score" in column.lower() and column != "criteria_json"
    ]
    target_variables = ["total_score"] if "total_score" in dataframe.columns else []
    metadata_columns = [
        column
        for column in dataframe.columns
        if column not in set(text_columns + score_columns)
    ]

    return {
        "text_columns": text_columns,
        "score_columns": score_columns,
        "target_variables": target_variables,
        "metadata_columns": metadata_columns,
    }


def prepare_analysis_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Create numeric scores and word-based report lengths for analysis."""
    analysis = dataframe.copy()
    analysis["numeric_total_score"] = pd.to_numeric(
        analysis["total_score"], errors="coerce"
    )
    analysis["report_length_words"] = analysis["text"].fillna("").astype(str).str.split().str.len()
    return analysis


def save_plots(dataframe: pd.DataFrame) -> None:
    """Save score, report-length, and relationship visualizations."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    valid_scores = dataframe["numeric_total_score"].dropna()
    valid_lengths = dataframe["report_length_words"].dropna()

    if valid_scores.empty:
        raise ValueError("No valid numeric total_score values are available for plots.")

    plt.figure(figsize=(9, 6))
    plt.hist(valid_scores, bins=15, color="#287271", edgecolor="white")
    plt.title("Total Score Distribution")
    plt.xlabel("Total score")
    plt.ylabel("Number of grading records")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "score_distribution.png", dpi=300)
    plt.close()

    plt.figure(figsize=(9, 6))
    plt.hist(valid_lengths, bins=20, color="#D17B49", edgecolor="white")
    plt.title("Report Length Distribution")
    plt.xlabel("Report length (words)")
    plt.ylabel("Number of grading records")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "report_length_distribution.png", dpi=300)
    plt.close()

    plot_data = dataframe.dropna(
        subset=["report_length_words", "numeric_total_score"]
    )
    plt.figure(figsize=(9, 6))
    plt.scatter(
        plot_data["report_length_words"],
        plot_data["numeric_total_score"],
        color="#3C5488",
        alpha=0.70,
        edgecolors="white",
        linewidths=0.5,
    )
    plt.title("Report Length vs Total Score")
    plt.xlabel("Report length (words)")
    plt.ylabel("Total score")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "length_vs_score.png", dpi=300)
    plt.close()


def build_report(
    original: pd.DataFrame,
    analysis: pd.DataFrame,
    column_roles: dict[str, list[str]],
) -> str:
    """Build a complete text report of grading-dataset findings."""
    missing_values = original.isna().sum()
    duplicate_count = int(original.duplicated().sum())
    report_lengths = analysis["report_length_words"]
    scores = analysis["numeric_total_score"].dropna()
    non_numeric_scores = int(analysis["numeric_total_score"].isna().sum())

    return "\n".join(
        [
            "Exposia Grading Dataset Analysis",
            "================================",
            f"Dataset shape: {original.shape}",
            f"Column names: {list(original.columns)}",
            "",
            "Column Roles",
            "------------",
            f"Text columns: {column_roles['text_columns']}",
            f"Score columns: {column_roles['score_columns']}",
            f"Target variables: {column_roles['target_variables']}",
            f"Metadata columns: {column_roles['metadata_columns']}",
            "",
            "Data Quality",
            "------------",
            "Missing values per column:",
            missing_values.to_string(),
            f"Duplicate rows: {duplicate_count}",
            f"Non-numeric or missing total scores: {non_numeric_scores}",
            "",
            "Report Length Statistics (words)",
            "--------------------------------",
            f"Average report length: {report_lengths.mean():.2f}",
            f"Minimum report length: {int(report_lengths.min())}",
            f"Maximum report length: {int(report_lengths.max())}",
            "",
            "Total Score Distribution",
            "------------------------",
            f"Mean score: {scores.mean():.2f}",
            f"Median score: {scores.median():.2f}",
            f"Standard deviation: {scores.std():.2f}",
            f"Minimum score: {scores.min():.2f}",
            f"Maximum score: {scores.max():.2f}",
            "",
            "Modeling Recommendation",
            "-----------------------",
            "Input text column: text",
            "Target score column: total_score",
            "Use submission_type and author only as metadata for grouping, splitting, or analysis.",
            "Do not use criteria_json as model input: it contains grader-assigned criterion scores",
            "and would cause target leakage. It may instead support later multi-task target design.",
        ]
    )


def main() -> None:
    """Run the complete grading dataset analysis workflow."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dataframe = load_dataset(DATASET_PATH)
    column_roles = identify_column_roles(dataframe)
    analysis = prepare_analysis_data(dataframe)

    print(f"Dataset shape: {dataframe.shape}")
    print(f"Column names: {list(dataframe.columns)}")
    print("\nFirst 10 rows:")
    print(dataframe.head(10).to_string(index=False, max_colwidth=70))

    save_plots(analysis)
    report = build_report(dataframe, analysis, column_roles)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")

    print("\n" + report)
    print(f"\nPlots saved to: {PLOTS_DIR}")
    print(f"Analysis report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        print(f"Grading dataset analysis failed: {error}")
        raise SystemExit(1) from error
