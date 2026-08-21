import sys
import logging
import json
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import GroupShuffleSplit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sentence_transformers import SentenceTransformer

# Load dataset generator
import importlib.util
spec = importlib.util.spec_from_file_location("weakness_study", "09_weakness_study.py")
weakness_study = importlib.util.module_from_spec(spec)
sys.modules["weakness_study"] = weakness_study
spec.loader.exec_module(weakness_study)
build_weakness_dataset = weakness_study.build_weakness_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def calculate_aggregates(metrics_list: list) -> dict:
    if not metrics_list: return {}
    keys = metrics_list[0].keys()
    aggs = {}
    for k in keys:
        if isinstance(metrics_list[0][k], (int, float, np.integer, np.floating)):
            vals = [m[k] for m in metrics_list]
            aggs[k] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "min": float(np.min(vals)),
                "max": float(np.max(vals))
            }
    return aggs

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    
    seeds = list(range(42, 62)) # Exact 20 seeds
    
    logger.info("Building dataset...")
    df = build_weakness_dataset(raw_dir)
    
    logger.info("Loading SentenceTransformer for semantic baseline...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    logger.info("Embedding all paragraphs (this may take a moment)...")
    embeddings = model.encode(df["text"].tolist(), show_progress_bar=False)
    
    results = []
    
    logger.info("Running Semantic Weakness Model Study over 20 seeds...")
    for seed in seeds:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_idx, test_idx = next(gss.split(df["text"], df["label"], df["author"]))
        
        X_train, y_train = embeddings[train_idx], df.iloc[train_idx]["label"]
        X_test, y_test = embeddings[test_idx], df.iloc[test_idx]["label"]
        
        clf = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        p, r, f1_macro, _ = precision_recall_fscore_support(y_test, y_pred, average="macro", zero_division=0)
        _, _, f1_weight, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted", zero_division=0)
        
        results.append({
            "accuracy": acc,
            "macro_precision": p,
            "macro_recall": r,
            "macro_f1": f1_macro,
            "weighted_f1": f1_weight
        })
        
    final_report = {"Semantic_MiniLM_LogReg": calculate_aggregates(results)}
    
    with (exp_dir / "weakness_semantic_study.json").open("w") as f:
        json.dump(final_report, f, indent=4)
        
    logger.info("Semantic Weakness study completed.")

if __name__ == "__main__":
    main()
