
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
