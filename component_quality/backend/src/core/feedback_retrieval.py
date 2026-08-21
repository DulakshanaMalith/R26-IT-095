import joblib
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR.parent / "training" / "models"
EMBEDDINGS_PATH = MODELS_DIR / "feedback_embeddings.pkl"

_embedding_model: SentenceTransformer | None = None
_retrieval_artifact: dict[str, Any] | None = None


def load_embedding_model(model_name: str) -> SentenceTransformer:
    """Prefer cached model files, with an online fallback for first-time use."""
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except (OSError, ValueError):
        return SentenceTransformer(model_name)


def load_retrieval_resources() -> tuple[SentenceTransformer, dict[str, Any]]:
    """Lazily load the embedding model and saved retrieval artifact."""
    global _embedding_model, _retrieval_artifact

    if _retrieval_artifact is None:
        if not EMBEDDINGS_PATH.exists():
            raise FileNotFoundError(
                f"Retrieval artifact not found: {EMBEDDINGS_PATH}\n"
                "Run train_feedback_retrieval.py once to create the feedback embeddings."
            )
        _retrieval_artifact = joblib.load(EMBEDDINGS_PATH)

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
            "annotated_text": artifact["texts"][index],
            "tag": artifact["tags"][index],
            "comment_text": artifact["comments"][index],
            "similarity_score": float(similarities[index]),
        }
        for index in top_indices
    ]
