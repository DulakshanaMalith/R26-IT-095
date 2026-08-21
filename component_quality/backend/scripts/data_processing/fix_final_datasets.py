"""Repair finalized Exposia datasets after manual or downstream edits."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
WEAKNESS_FINAL_PATH = ROOT_DIR / "processed" / "weakness_dataset_final.csv"
REQUIRED_COLUMNS = {"annotated_text", "tag"}


def load_weakness_dataset(path: Path) -> pd.DataFrame:
    """Load the finalized weakness dataset and validate required columns."""
    if not path.exists():
        raise FileNotFoundError(f"Weakness final dataset not found: {path}")

    try:
        dataframe = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"Weakness final dataset is empty: {path}") from exc
    except (OSError, UnicodeError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc

    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Weakness final dataset is missing columns: {missing}")

    return dataframe


def clean_weakness_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Drop missing, empty, and duplicate finalized weakness records."""
    cleaned = dataframe.dropna(subset=["annotated_text", "tag"]).copy()
    cleaned["annotated_text"] = cleaned["annotated_text"].astype(str).str.strip()
    cleaned["tag"] = cleaned["tag"].astype(str).str.strip()
    cleaned = cleaned[
        (cleaned["annotated_text"] != "") & (cleaned["tag"] != "")
    ]
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    return cleaned


def main() -> None:
    """Clean and overwrite the finalized weakness dataset."""
    dataframe = load_weakness_dataset(WEAKNESS_FINAL_PATH)
    cleaned = clean_weakness_dataset(dataframe)

    print(f"Before shape: {dataframe.shape}")
    print(f"After shape: {cleaned.shape}")

    try:
        cleaned.to_csv(WEAKNESS_FINAL_PATH, index=False)
    except OSError as exc:
        raise RuntimeError(f"Could not save cleaned dataset: {exc}") from exc

    print(f"Cleaned weakness dataset saved to: {WEAKNESS_FINAL_PATH}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Final dataset cleanup failed: {error}")
        raise SystemExit(1) from error
