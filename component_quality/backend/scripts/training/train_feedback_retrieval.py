"""Build a Sentence-BERT retrieval component for academic feedback.

The saved retrieval artifact contains annotation embeddings and their related
comments. The public ``get_feedback`` function retrieves the most semantically
similar examples for a new academic-writing query.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = ROOT_DIR / "processed" / "feedback_dataset_final.csv"
MODELS_DIR = ROOT_DIR / "models"
RESULTS_DIR = ROOT_DIR / "results"
EMBEDDINGS_PATH = MODELS_DIR / "feedback_embeddings.pkl"
DEMO_PATH = RESULTS_DIR / "feedback_retrieval_demo.txt"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
REQUIRED_COLUMNS = {"annotated_text", "tag", "comment_text"}

_embedding_model: SentenceTransformer | None = None
_retrieval_artifact: dict[str, Any] | None = None


def load_feedback_dataset(path: Path) -> pd.DataFrame:
    """Load, validate, and clean annotation-comment feedback pairs."""
    if not path.exists():
        raise FileNotFoundError(
            f"Feedback dataset not found: {path}\n"
            "Run analyze_feedback_dataset.py before this script."
        )

    dataframe = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Dataset is missing required columns: {missing}")

    dataframe = dataframe[["annotated_text", "tag", "comment_text"]].dropna().copy()
    for column in REQUIRED_COLUMNS:
        dataframe[column] = dataframe[column].astype(str).str.strip()

    dataframe = dataframe[
        (dataframe["annotated_text"] != "")
        & (dataframe["tag"] != "")
        & (dataframe["comment_text"] != "")
    ].reset_index(drop=True)

    if dataframe.empty:
        raise ValueError("No valid feedback records remain after cleaning.")

    return dataframe


def load_embedding_model(model_name: str) -> SentenceTransformer:
    """Prefer cached model files, with an online fallback for first-time use."""
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except (OSError, ValueError):
        return SentenceTransformer(model_name)


def build_retrieval_index(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Generate normalized Sentence-BERT embeddings and their metadata."""
    global _embedding_model

    print(f"Loading embedding model: {MODEL_NAME}")
    _embedding_model = load_embedding_model(MODEL_NAME)
    print(f"Generating embeddings for {len(dataframe)} annotations...")
    embeddings = _embedding_model.encode(
        dataframe["annotated_text"].tolist(),
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return {
        "model_name": MODEL_NAME,
        "normalize_embeddings": True,
        "embeddings": embeddings,
        "annotated_texts": dataframe["annotated_text"].tolist(),
        "tags": dataframe["tag"].tolist(),
        "comments": dataframe["comment_text"].tolist(),
    }


def load_retrieval_resources() -> tuple[SentenceTransformer, dict[str, Any]]:
    """Lazily load the embedding model and saved retrieval artifact."""
    global _embedding_model, _retrieval_artifact

    if _retrieval_artifact is None:
        if not EMBEDDINGS_PATH.exists():
            raise FileNotFoundError(
                f"Retrieval artifact not found: {EMBEDDINGS_PATH}\n"
                "Run this script once to create the feedback embeddings."
            )
        with EMBEDDINGS_PATH.open("rb") as file:
            _retrieval_artifact = pickle.load(file)

    if _embedding_model is None:
        _embedding_model = load_embedding_model(_retrieval_artifact["model_name"])

    return _embedding_model, _retrieval_artifact


def get_feedback(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return the most similar annotations and comments for a query."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    model, artifact = load_retrieval_resources()
    query_embedding = model.encode(
        [query.strip()],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    similarities = cosine_similarity(query_embedding, artifact["embeddings"])[0]
    result_count = min(top_k, len(similarities))
    top_indices = similarities.argsort()[::-1][:result_count]

    return [
        {
            "annotated_text": artifact["annotated_texts"][index],
            "tag": artifact["tags"][index],
            "comment_text": artifact["comments"][index],
            "similarity_score": float(similarities[index]),
        }
        for index in top_indices
    ]


def format_demo(query: str, matches: list[dict[str, Any]]) -> str:
    """Format one query and its retrieved feedback for display and saving."""
    lines = [f"Query: {query}", "-" * 80]
    for rank, match in enumerate(matches, start=1):
        lines.extend(
            [
                f"Match {rank}",
                f"Tag: {match['tag']}",
                f"Similarity score: {match['similarity_score']:.4f}",
                f"Matched annotation: {match['annotated_text']}",
                f"Retrieved feedback: {match['comment_text']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def main() -> None:
    """Build the retrieval index and demonstrate five sample queries."""
    global _retrieval_artifact

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dataframe = load_feedback_dataset(DATASET_PATH)
    print(f"Loaded {len(dataframe)} complete feedback records.")

    _retrieval_artifact = build_retrieval_index(dataframe)
    with EMBEDDINGS_PATH.open("wb") as file:
        pickle.dump(_retrieval_artifact, file)
    print(f"Embeddings saved to: {EMBEDDINGS_PATH}")

    sample_queries = [
        "The research question is too broad and needs a clearer scope.",
        "This claim is unsupported and requires a citation.",
        "The methodology does not explain how participants will be selected.",
        "The project schedule is incomplete and may not be realistic.",
        "This paragraph is difficult to understand because the language is unclear.",
    ]

    demo_sections = []
    for query in sample_queries:
        matches = get_feedback(query, top_k=3)
        section = format_demo(query, matches)
        demo_sections.append(section)
        print("\n" + section)

    demo_output = "\n\n".join(demo_sections) + "\n"
    DEMO_PATH.write_text(demo_output, encoding="utf-8")
    print(f"\nRetrieval demo saved to: {DEMO_PATH}")


if __name__ == "__main__":
    main()
