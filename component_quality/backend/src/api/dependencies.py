import pickle
import logging
from pathlib import Path
from typing import Any

from src.core.feedback_retrieval import load_retrieval_resources

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = ROOT_DIR.parent / "training" / "models"
MODEL_PATH = MODEL_DIR / "weakness_svm_model.pkl"
GRADING_MODEL_PATH = MODEL_DIR / "semantic_grading_model.pkl"

class ModelManager:
    weakness_model = None
    grading_model = None

    @classmethod
    def load_models(cls):
        logger.info("Loading semantic grading model...")
        if GRADING_MODEL_PATH.exists():
            with GRADING_MODEL_PATH.open("rb") as file:
                cls.grading_model = pickle.load(file)
                logger.info("Semantic grading model loaded.")
        else:
            logger.warning(f"Semantic grading model not found at {GRADING_MODEL_PATH}")

        logger.info("Loading weakness classification pipeline...")
        if MODEL_PATH.exists():
            with MODEL_PATH.open("rb") as file:
                cls.weakness_model = pickle.load(file)
                logger.info("Weakness pipeline loaded.")
        else:
            logger.warning(f"Weakness model not found at {MODEL_PATH}")

        logger.info("Pre-loading retrieval models...")
        try:
            load_retrieval_resources()
            logger.info("Retrieval models loaded.")
        except Exception as e:
            logger.error(f"Error loading retrieval models: {e}")

def get_weakness_model():
    return ModelManager.weakness_model

def get_grading_model():
    return ModelManager.grading_model
