import os
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_PATH = ROOT_DIR / "data" / "feedback" / "weakness_vs_strength.csv"
EMBEDDINGS_PATH = ROOT_DIR.parent / "training" / "models" / "rag_embeddings.pkl"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

class RAGRetriever:
    def __init__(self):
        self.model = None
        self.df = None
        self.embeddings = None
        self._load_or_build_index()

    def _load_model(self):
        if self.model is None:
            try:
                self.model = SentenceTransformer(MODEL_NAME, local_files_only=True)
            except Exception:
                self.model = SentenceTransformer(MODEL_NAME)

    def _load_or_build_index(self):
        if not DATA_PATH.exists():
            logger.warning(f"RAG data path not found: {DATA_PATH}. Retrieval will not work.")
            return

        if EMBEDDINGS_PATH.exists():
            try:
                with open(EMBEDDINGS_PATH, "rb") as f:
                    data = pickle.load(f)
                self.df = data["df"]
                self.embeddings = data["embeddings"]
                self._load_model()
                return
            except Exception as e:
                logger.warning(f"Failed to load cached embeddings: {e}. Rebuilding...")

        # Rebuild
        logger.info("Building RAG embeddings. This may take a moment...")
        self.df = pd.read_csv(DATA_PATH)
        # Drop rows missing crucial texts
        self.df = self.df.dropna(subset=["span_text", "comment_text"])
        self.df = self.df.reset_index(drop=True)

        self._load_model()
        self.embeddings = self.model.encode(
            self.df["span_text"].tolist(),
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(EMBEDDINGS_PATH, "wb") as f:
            pickle.dump({"df": self.df, "embeddings": self.embeddings}, f)

    def retrieve_similar_feedback(
        self,
        query_text: str,
        excluded_author_ids: Optional[List[str]] = None,
        top_k: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Retrieves similar historical feedback while enforcing isolation.
        """
        if self.df is None or self.embeddings is None:
            return []

        # Generate query embedding
        self._load_model()
        query_emb = self.model.encode([query_text], normalize_embeddings=True, convert_to_numpy=True)

        # Calculate similarities
        sims = cosine_similarity(query_emb, self.embeddings)[0]

        # Filter out excluded authors and low similarity
        valid_indices = []
        for i, sim in enumerate(sims):
            if sim < min_similarity:
                continue
            if excluded_author_ids and str(self.df.at[i, "author"]) in excluded_author_ids:
                continue
            valid_indices.append(i)

        if not valid_indices:
            return []

        valid_indices = np.array(valid_indices)
        valid_sims = sims[valid_indices]
        
        # Get top k
        top_k_idx = valid_indices[np.argsort(valid_sims)[::-1][:top_k]]

        results = []
        for idx in top_k_idx:
            row = self.df.iloc[idx]
            results.append({
                "example_id": str(row.get("annotation_id", idx)),
                "span_text": str(row.get("span_text", "")),
                "historical_comment": str(row.get("comment_text", "")),
                "annotation_tag": str(row.get("annotation_tag", "")),
                "similarity_score": float(sims[idx])
            })

        return results

_retriever_instance = None
def get_retriever() -> RAGRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
    return _retriever_instance

def format_rag_examples_for_prompt(examples: List[Dict[str, Any]]) -> str:
    """Formats retrieved examples into a string block for the LLM prompt."""
    if not examples:
        return ""
        
    block = "### HISTORICAL REFERENCE EXAMPLES\n"
    block += "These examples are from past proposals. They show how reviewers identify weaknesses and strengths.\n"
    block += "DO NOT copy these comments. Use them only to understand patterns of academic feedback.\n\n"
    
    for i, ex in enumerate(examples, 1):
        block += f"--- Example {i} ({ex['annotation_tag'].upper()}) ---\n"
        block += f"Proposal Text Span: \"{ex['span_text']}\"\n"
        block += f"Reviewer Comment: {ex['historical_comment']}\n\n"
        
    return block
