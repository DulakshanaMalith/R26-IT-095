"""Build an annotation-comment dataset for AI feedback generation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ANNOTATIONS_PATH = ROOT_DIR / "processed" / "exposia_annotations.csv"
COMMENTS_PATH = ROOT_DIR / "processed" / "exposia_comments.csv"
OUTPUT_PATH = ROOT_DIR / "processed" / "feedback_dataset.csv"


def load_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    """Load a CSV file and verify that its required columns are available."""
    if not path.exists():
        raise FileNotFoundError(
            f"Required dataset not found: {path}\n"
            "Run preprocessing.py before this script."
        )

    dataframe = pd.read_csv(path)
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{path.name} is missing required columns: {missing}")

    return dataframe


def find_comment_annotation_column(comments: pd.DataFrame) -> str:
    """Support both processed and source-style annotation ID column names."""
    for column_name in ("annotation_id", "annotationId"):
        if column_name in comments.columns:
            return column_name

    raise ValueError(
        "Comments dataset must contain either 'annotation_id' or 'annotationId'."
    )


def main() -> None:
    """Analyze annotation-comment links and create the feedback dataset."""
    annotations = load_csv(
        ANNOTATIONS_PATH,
        {"author", "annotation_id", "annotated_text", "tag"},
    )
    comments = load_csv(
        COMMENTS_PATH,
        {"author", "comment_text"},
    )
    comment_annotation_column = find_comment_annotation_column(comments)

    print(f"Number of annotations: {len(annotations)}")
    print(f"Number of comments: {len(comments)}")
    print(f"Annotation columns: {list(annotations.columns)}")
    print(f"Comment columns: {list(comments.columns)}")
    print(f"Comment annotation key: {comment_annotation_column}")

    # Nullable integer IDs avoid float/string mismatches introduced by CSV parsing.
    annotations["annotation_id"] = pd.to_numeric(
        annotations["annotation_id"], errors="coerce"
    ).astype("Int64")
    comments[comment_annotation_column] = pd.to_numeric(
        comments[comment_annotation_column], errors="coerce"
    ).astype("Int64")

    linked_comment_count = int(comments[comment_annotation_column].notna().sum())

    annotation_lookup = annotations[
        ["author", "annotation_id", "annotated_text", "tag"]
    ].drop_duplicates(subset=["author", "annotation_id"])

    merged = comments.merge(
        annotation_lookup,
        how="inner",
        left_on=["author", comment_annotation_column],
        right_on=["author", "annotation_id"],
        validate="many_to_one",
    )
    matched_comment_count = len(merged)

    feedback = merged[["annotated_text", "tag", "comment_text"]].copy()
    feedback = feedback.dropna(subset=["annotated_text", "tag", "comment_text"])

    for column in ("annotated_text", "tag", "comment_text"):
        feedback[column] = feedback[column].astype(str).str.strip()

    feedback = feedback[
        (feedback["annotated_text"] != "")
        & (feedback["tag"] != "")
        & (feedback["comment_text"] != "")
    ].reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    feedback.to_csv(OUTPUT_PATH, index=False)

    print(f"\nComments with an annotation ID: {linked_comment_count}")
    print(f"Comments matched to an annotation: {matched_comment_count}")
    print(f"Unmatched linked comments: {linked_comment_count - matched_comment_count}")
    print(f"\nFeedback dataset shape: {feedback.shape}")
    print("\nFirst 10 rows:")
    print(feedback.head(10).to_string(index=False, max_colwidth=80))
    print("\nTag distribution:")
    print(feedback["tag"].value_counts())
    print(f"\nFeedback dataset saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
