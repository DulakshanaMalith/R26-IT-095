import sys
import logging
import json
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.ensemble import RandomForestRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

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

def build_models():
    models = {}
    
    # A. Mean Baseline
    models["A_Mean_Baseline"] = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')), # tfidf doesn't matter for dummy
        ("reg", DummyRegressor(strategy="mean"))
    ])
    
    # B. Ridge
    models["B_Ridge"] = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("reg", Ridge(random_state=42))
    ])
    
    # C. ElasticNet
    models["C_ElasticNet"] = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("reg", ElasticNet(random_state=42))
    ])
    
    # D. RandomForestRegressor
    models["D_RandomForest"] = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("reg", RandomForestRegressor(n_estimators=100, random_state=42))
    ])
    
    return models

def run_study(df: pd.DataFrame, models: dict, seeds: list, exp_dir: Path):
    logger.info("Running Grading Model Improvement Study...")
    
    all_results = {name: [] for name in models}
    
    for seed in seeds:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_idx, test_idx = next(gss.split(df["text"], df["score"], df["author"]))
        
        X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["score"]
        X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["score"]
        
        for name, model in models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)
            
            all_results[name].append({
                "mae": float(mae),
                "rmse": float(rmse),
                "r2": float(r2),
                "pred_mean": float(np.mean(y_pred)),
                "pred_std": float(np.std(y_pred)),
                "pred_min": float(np.min(y_pred)),
                "pred_max": float(np.max(y_pred))
            })
            
    # Aggregate
    final_report = {}
    for name in models:
        final_report[name] = calculate_aggregates(all_results[name])
        
    with (exp_dir / "grading_model_study.json").open("w") as f:
        json.dump(final_report, f, indent=4)
        
    logger.info("Grading study completed.")

def main():
    script_dir = Path(__file__).resolve().parent
    processed_dir = (script_dir / "../data/processed").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    
    seeds = list(range(42, 62)) # Exact 20 seeds
    
    logger.info("Loading Final Grading dataset...")
    df = pd.read_csv(processed_dir / "grading_final_dataset.csv").dropna(subset=["text", "score"])
    
    models = build_models()
    run_study(df, models, seeds, exp_dir)

if __name__ == "__main__":
    main()
