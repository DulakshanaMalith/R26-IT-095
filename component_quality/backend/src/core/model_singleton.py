import threading
import torch
from sentence_transformers import SentenceTransformer

# Limit PyTorch threads to prevent CPU thrashing under high concurrent load
torch.set_num_threads(2)

_model_instance: SentenceTransformer | None = None
_model_lock = threading.Lock()
_encode_semaphore = threading.Semaphore(2)

def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                try:
                    _model_instance = SentenceTransformer(model_name, local_files_only=True)
                except (OSError, ValueError):
                    _model_instance = SentenceTransformer(model_name)
    return _model_instance

def encode_with_semaphore(model: SentenceTransformer, *args, **kwargs):
    """Wrap model.encode to bound concurrent PyTorch operations."""
    with _encode_semaphore:
        return model.encode(*args, **kwargs)
