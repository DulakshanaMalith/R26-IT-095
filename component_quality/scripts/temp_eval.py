import sys
import json
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, mean_absolute_error, mean_squared_error, r2_score
import numpy as np

# Load backend for SemanticTransformer
sys.path.insert(0, str(Path("e:/group95/daham/backend")))
import src.core.semantic_transformer

# Load weakness_study for dataset
import importlib.util
spec = importlib.util.spec_from_file_location("weakness_study", "e:/group95/daham/training/scripts/09_weakness_study.py")
weakness_study = importlib.util.module_from_spec(spec)
sys.modules["weakness_study"] = weakness_study
spec.loader.exec_module(weakness_study)
build_weakness_dataset = weakness_study.build_weakness_dataset

def main():
    base_dir = Path("e:/group95/daham/training")
    models_dir = base_dir / "models"
    data_dir = base_dir / "data/processed"
    raw_dir = base_dir / "data/raw"

    print("=== Weakness Classifier ===")
    try:
        weakness_df = build_weakness_dataset(raw_dir)
        weakness_model = joblib.load(models_dir / "weakness_svm_model.pkl")
        
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, test_idx = next(gss.split(weakness_df["text"], weakness_df["label"], weakness_df["author"]))
        
        X_train, y_train = weakness_df.iloc[train_idx]["text"].tolist(), weakness_df.iloc[train_idx]["label"].tolist()
        X_test, y_test = weakness_df.iloc[test_idx]["text"].tolist(), weakness_df.iloc[test_idx]["label"].tolist()
        
        y_pred = weakness_model.predict(X_test)
        y_train_pred = weakness_model.predict(X_train)
        
        print(f"Train samples: {len(X_train)}")
        print(f"Test samples: {len(X_test)}")
        print(f"Train Accuracy: {accuracy_score(y_train, y_train_pred):.4f}")
        print(f"Test Accuracy (Leakage Warning: model was trained on ALL data in 13_promote_models.py): {accuracy_score(y_test, y_pred):.4f}")
        
        rep = classification_report(y_test, y_pred)
        print("\nClassification Report (Test - Leaked):")
        print(rep)
        
        cm = confusion_matrix(y_test, y_pred)
        print("\nConfusion Matrix (Test - Leaked):")
        print(cm)
        
    except Exception as e:
        print(f"Error evaluating weakness: {e}")

    print("\n=== Semantic Grading Model ===")
    try:
        grading_df = pd.read_csv(data_dir / "grading_dataset.csv").dropna(subset=["text", "score"])
        grading_model = joblib.load(models_dir / "semantic_grading_model.pkl")
        
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, test_idx = next(gss.split(grading_df["text"], grading_df["score"], grading_df["author"]))
        
        X_train, y_train = grading_df.iloc[train_idx]["text"], grading_df.iloc[train_idx]["score"]
        X_test, y_test = grading_df.iloc[test_idx]["text"], grading_df.iloc[test_idx]["score"]
        
        y_pred = grading_model.predict(X_test)
        
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        print(f"Train samples: {len(X_train)}")
        print(f"Test samples: {len(X_test)}")
        print(f"Held-out Test MAE: {mae:.4f}")
        print(f"Held-out Test RMSE: {rmse:.4f}")
        print(f"Held-out Test R^2: {r2:.4f}")
    except Exception as e:
        print(f"Error evaluating grading: {e}")

if __name__ == '__main__':
    main()
