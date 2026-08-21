"""Exploratory data analysis for the processed Exposia reports dataset."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_PATH = ROOT_DIR / "processed" / "exposia_reports.csv"
SUMMARY_PATH = ROOT_DIR / "processed" / "eda_summary.txt"
PLOTS_DIR = ROOT_DIR / "processed" / "plots"

REQUIRED_COLUMNS = {"draft_text", "final_text"}


def word_count(text: object) -> int:
    """Count whitespace-separated words, treating missing text as empty."""
    if pd.isna(text):
        return 0
    return len(str(text).split())


def validate_dataset(dataframe: pd.DataFrame) -> None:
    """Ensure the input contains the columns required for this analysis."""
    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Required columns missing from reports CSV: {missing}")


def save_plots(dataframe: pd.DataFrame) -> None:
    """Create and save word-count distribution and comparison plots."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 6))
    plt.hist(dataframe["draft_word_count"], bins=20, color="#287271", edgecolor="white")
    plt.title("Draft Word Count Distribution")
    plt.xlabel("Word count")
    plt.ylabel("Number of reports")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "draft_word_count_distribution.png", dpi=300)
    plt.close()

    plt.figure(figsize=(9, 6))
    plt.hist(dataframe["final_word_count"], bins=20, color="#D17B49", edgecolor="white")
    plt.title("Final Word Count Distribution")
    plt.xlabel("Word count")
    plt.ylabel("Number of reports")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "final_word_count_distribution.png", dpi=300)
    plt.close()

    plt.figure(figsize=(8, 8))
    plt.scatter(
        dataframe["draft_word_count"],
        dataframe["final_word_count"],
        color="#3C5488",
        alpha=0.75,
        edgecolors="white",
        linewidths=0.5,
    )
    comparison_limit = max(
        dataframe["draft_word_count"].max(),
        dataframe["final_word_count"].max(),
    )
    plt.plot(
        [0, comparison_limit],
        [0, comparison_limit],
        linestyle="--",
        color="#555555",
        label="No change",
    )
    plt.title("Draft vs Final Word Count")
    plt.xlabel("Draft word count")
    plt.ylabel("Final word count")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "draft_vs_final_comparison.png", dpi=300)
    plt.close()


def build_summary(
    dataframe: pd.DataFrame,
    average_draft: float,
    average_final: float,
    average_improvement: float,
) -> str:
    """Build the terminal and text-file EDA summary."""
    missing_values = dataframe.isna().sum()
    summary_statistics = dataframe.describe().to_string()

    return "\n".join(
        [
            "Exposia Exploratory Data Analysis",
            "=================================",
            f"Number of reports: {len(dataframe)}",
            f"Dataset shape: {dataframe.shape}",
            f"Average draft word count: {average_draft:.2f}",
            f"Average final word count: {average_final:.2f}",
            f"Average improvement (final - draft): {average_improvement:.2f}",
            "",
            "Missing values per column",
            "-------------------------",
            missing_values.to_string(),
            "",
            "Summary statistics",
            "------------------",
            summary_statistics,
        ]
    )


def main() -> None:
    """Run the complete exploratory data analysis workflow."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not REPORTS_PATH.exists():
        raise FileNotFoundError(
            f"Reports dataset not found: {REPORTS_PATH}\n"
            "Run preprocessing.py before running this script."
        )

    dataframe = pd.read_csv(REPORTS_PATH)
    validate_dataset(dataframe)

    print("First 5 rows")
    print("------------")
    print(dataframe.head().to_string(index=False, max_colwidth=60))
    print(f"\nNumber of reports: {len(dataframe)}")

    dataframe["draft_word_count"] = dataframe["draft_text"].apply(word_count)
    dataframe["final_word_count"] = dataframe["final_text"].apply(word_count)
    dataframe["word_count_improvement"] = (
        dataframe["final_word_count"] - dataframe["draft_word_count"]
    )

    average_draft = dataframe["draft_word_count"].mean()
    average_final = dataframe["final_word_count"].mean()
    average_improvement = dataframe["word_count_improvement"].mean()

    save_plots(dataframe)
    summary = build_summary(
        dataframe,
        average_draft,
        average_final,
        average_improvement,
    )
    SUMMARY_PATH.write_text(summary + "\n", encoding="utf-8")

    print("\n" + summary)
    print(f"\nSummary saved to: {SUMMARY_PATH}")
    print(f"Plots saved to: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
