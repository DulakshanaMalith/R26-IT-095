from sklearn.base import BaseEstimator, TransformerMixin
from src.core.model_singleton import get_embedding_model, encode_with_semaphore

class SemanticTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        # model is intentionally not stored to avoid serialization issues
        # and to enforce singleton usage
        
    def fit(self, X, y=None):
        return self
        
    def transform(self, X):
        model = get_embedding_model(self.model_name)
        # Handle single strings or lists
        if isinstance(X, str):
            X = [X]
        return encode_with_semaphore(model, X, show_progress_bar=False)
