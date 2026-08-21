import sys
import logging
from pathlib import Path
import pandas as pd
import joblib

from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.base import BaseEstimator, TransformerMixin
from sentence_transformers import SentenceTransformer

# We must define the class exactly as it will be imported by the backend.
# To make it pickle-compatible without modifying backend source, we can inject it into a module that the backend imports, or just write it into the backend and import it here.

# Let's write the transformer to backend/src/core/semantic_transformer.py
backend_src_core = Path(__file__).resolve().parent.parent.parent / "backend" / "src" / "core"
semantic_transformer_code = """
from sklearn.base import BaseEstimator, TransformerMixin
from sentence_transformers import SentenceTransformer

class SemanticTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        
    def fit(self, X, y=None):
        return self
        
    def transform(self, X):
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        # Handle single strings or lists
        if isinstance(X, str):
            X = [X]
        return self.model.encode(X, show_progress_bar=False)
"""
(backend_src_core / "semantic_transformer.py").write_text(semantic_transformer_code)

# Now add backend to path and import it so pickle registers the correct module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
from src.core.semantic_transformer import SemanticTransformer

# Also need to import build_weakness_dataset
import importlib.util
spec = importlib.util.spec_from_file_location("weakness_study", "09_weakness_study.py")
weakness_study = importlib.util.module_from_spec(spec)
sys.modules["weakness_study"] = weakness_study
spec.loader.exec_module(weakness_study)
build_weakness_dataset = weakness_study.build_weakness_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    models_dir = (script_dir / "../models").resolve()
    
    logger.info("Building dataset for semantic promotion...")
    df = build_weakness_dataset(raw_dir)
    
    logger.info("Training Pipeline...")
    pipeline = Pipeline([
        ("embedder", SemanticTransformer(model_name='all-MiniLM-L6-v2')),
        ("classifier", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000))
    ])
    
    pipeline.fit(df["text"].tolist(), df["label"].tolist())
    
    weakness_path = models_dir / "weakness_svm_model.pkl"
    joblib.dump(pipeline, weakness_path)
    
    logger.info(f"Promoted Semantic Weakness Model -> {weakness_path}")

if __name__ == "__main__":
    main()
