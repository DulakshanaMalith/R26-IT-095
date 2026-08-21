import sys
import logging
import json
import numpy as np
import pandas as pd
from pathlib import Path
import re

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def load_document_texts(author_dir: Path, doc_type: str) -> str:
    full_text = ""
    doc_dir = author_dir / doc_type
    if doc_dir.exists():
        for tex_file in doc_dir.glob("*.tex"):
            try:
                with tex_file.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    text = re.sub(r'%.*?\n', '\n', content)
                    text = re.sub(r'\\begin\{.*?\}', '', text)
                    text = re.sub(r'\\end\{.*?\}', '', text)
                    text = re.sub(r'\\[a-zA-Z]+\*?\{(.*?)\}', r'\1', text)
                    text = re.sub(r'\\[a-zA-Z]+\*?', '', text)
                    full_text += text + "\n\n"
            except Exception:
                pass
    return full_text

def build_rubric_dataset(raw_dir: Path) -> pd.DataFrame:
    exposes_dir = raw_dir / "exposes"
    records = []
    
    for author_dir in exposes_dir.iterdir():
        if not author_dir.is_dir(): continue
        author = author_dir.name
        
        scores_file = author_dir / "scores.json"
        if not scores_file.exists(): continue
        
        with scores_file.open("r", encoding="utf-8") as f:
            scores_data = json.load(f)
            
        # We only want FINAL proposals for the grading experiment
        for sd in scores_data:
            if sd.get("type") == "final":
                text = load_document_texts(author_dir, "final")
                if not text.strip(): continue
                
                score = sd.get("scores", {}).get("total")
                if score is None: continue
                
                # Format criteria string
                criteria = sd.get("criteria", {})
                criteria_str = "Criteria Summary: "
                for k, v in criteria.items():
                    if isinstance(v, (int, float)):
                        criteria_str += f"{k} {v}, "
                        
                # Combine
                combined_text = criteria_str + "\n\nProposal Text: " + text
                
                records.append({
                    "author": author,
                    "text": combined_text,
                    "score": score
                })
                
    # Group by author to average multiple final scores if multiple graders exist
    df = pd.DataFrame(records)
    if df.empty: return df
    
    # Resolve multiple reviewers by taking mean score
    df_agg = df.groupby(["author", "text"])["score"].mean().reset_index()
    return df_agg

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
    
    logger.info("Building Rubric-Aware Dataset...")
    df = build_rubric_dataset(raw_dir)
    
    if df.empty:
        logger.error("Dataset empty, cannot run rubric-aware experiment.")
        return
        
    logger.info("Running Rubric-Aware Grading Experiment (Ridge)...")
    results = []
    
    for seed in seeds:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_idx, test_idx = next(gss.split(df["text"], df["score"], df["author"]))
        
        X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["score"]
        X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["score"]
        
        ridge = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
            ("regressor", Ridge(random_state=42))
        ])
        ridge.fit(X_train, y_train)
        y_pred = ridge.predict(X_test)
        
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        results.append({
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "pred_mean": float(np.mean(y_pred)),
            "pred_std": float(np.std(y_pred)),
            "pred_min": float(np.min(y_pred)),
            "pred_max": float(np.max(y_pred))
        })
        
    final_report = {"Rubric_Aware_Ridge": calculate_aggregates(results)}
    
    with (exp_dir / "grading_rubric_study.json").open("w") as f:
        json.dump(final_report, f, indent=4)
        
    logger.info("Rubric study completed.")

if __name__ == "__main__":
    main()
