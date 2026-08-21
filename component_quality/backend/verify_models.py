import sys
from pathlib import Path
import joblib

def main():
    models_dir = Path("../training/models")
    
    # 1. Test Weakness SVM
    try:
        weakness_svm = joblib.load(models_dir / "weakness_svm_model.pkl")
        pred = weakness_svm.predict(["This is a test sentence that is poorly written."])
        print(f"Weakness SVM Prediction: {pred[0]}")
    except Exception as e:
        print(f"Failed to load weakness SVM: {e}")
        sys.exit(1)
        
    # 2. Test Semantic Grader
    try:
        grader = joblib.load(models_dir / "semantic_grading_model.pkl")
        pred = grader.predict(["This is a test expose text with some content."])
        print(f"Semantic Grader Prediction: {pred[0]}")
    except Exception as e:
        print(f"Failed to load semantic grader: {e}")
        sys.exit(1)
        
    # 3. Test Feedback Embeddings
    try:
        embeddings = joblib.load(models_dir / "feedback_embeddings.pkl")
        print(f"Feedback Embeddings: Model={embeddings['model_name']}, Count={len(embeddings['texts'])}")
    except Exception as e:
        print(f"Failed to load feedback embeddings: {e}")
        sys.exit(1)

    print("All models loaded successfully and are compatible!")

if __name__ == "__main__":
    main()
