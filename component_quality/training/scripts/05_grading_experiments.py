import json
import logging
import sys
import re
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    if not isinstance(text, str): return ""
    return re.sub(r'\s+', ' ', text).strip()

def extract_latex_text(latex_content: str) -> str:
    text = re.sub(r'%.*?\n', '\n', latex_content)
    text = re.sub(r'\\begin\{.*?\}', '', text)
    text = re.sub(r'\\end\{.*?\}', '', text)
    text = re.sub(r'\\[a-zA-Z]+\*?\{(.*?)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+\*?', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def build_grading_datasets(raw_dir: Path) -> dict:
    exposes_dir = raw_dir / "exposes"
    records_final = {}
    records_draft = {}
    
    for author_dir in exposes_dir.iterdir():
        if not author_dir.is_dir(): continue
        author = author_dir.name
        
        scores_file = author_dir / "scores.json"
        if not scores_file.exists(): continue
        
        try:
            with scores_file.open("r", encoding="utf-8") as f:
                scores = json.load(f)
        except Exception:
            continue
            
        for score_record in scores:
            score_type = score_record.get("type")
            if score_type not in ["draft", "final"]: continue
            
            total_score = score_record.get("scores", {}).get("total")
            if total_score is None: continue
            
            doc_dir = author_dir / score_type
            doc_text = ""
            
            if doc_dir.exists():
                tex_files = list(doc_dir.glob("*.tex"))
                if tex_files:
                    with tex_files[0].open("r", encoding="utf-8", errors="ignore") as tf:
                        doc_text = extract_latex_text(tf.read())
            
            doc_text = clean_text(doc_text)
            if not doc_text: continue
            
            # Aggregate by author+type to handle multiple reviews
            target_dict = records_final if score_type == "final" else records_draft
            if author not in target_dict:
                target_dict[author] = {"author": author, "type": score_type, "text": doc_text, "scores": []}
                
            target_dict[author]["scores"].append(total_score)
            
    # Resolve multiple scores via mean
    final_dataset = []
    for r in records_final.values():
        mean_score = np.mean(r["scores"])
        final_dataset.append({"author": r["author"], "type": r["type"], "text": r["text"], "score": mean_score})
        
    draft_dataset = []
    for r in records_draft.values():
        mean_score = np.mean(r["scores"])
        draft_dataset.append({"author": r["author"], "type": r["type"], "text": r["text"], "score": mean_score})
        
    return {
        "final": pd.DataFrame(final_dataset),
        "draft": pd.DataFrame(draft_dataset)
    }

def evaluate_grading_models(df: pd.DataFrame) -> dict:
    if df.empty: return {}
    df = df.dropna(subset=["text", "score"])
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df["text"], df["score"], df["author"]))
    
    X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["score"]
    X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["score"]
    
    results = {"samples": len(df), "authors": df["author"].nunique()}
    
    # 1. Mean Baseline
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    y_pred_dummy = dummy.predict(X_test)
    results["Mean_Baseline"] = {
        "MAE": mean_absolute_error(y_test, y_pred_dummy),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred_dummy)),
        "R2": r2_score(y_test, y_pred_dummy)
    }
    
    # 2. Ridge
    ridge = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("ridge", Ridge(random_state=42))
    ])
    ridge.fit(X_train, y_train)
    y_pred_ridge = ridge.predict(X_test)
    results["Ridge"] = {
        "MAE": mean_absolute_error(y_test, y_pred_ridge),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred_ridge)),
        "R2": r2_score(y_test, y_pred_ridge)
    }
    
    # 3. RandomForest
    rf = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("rf", RandomForestRegressor(n_estimators=100, random_state=42))
    ])
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    results["RandomForest"] = {
        "MAE": mean_absolute_error(y_test, y_pred_rf),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred_rf)),
        "R2": r2_score(y_test, y_pred_rf)
    }
    
    return results

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    processed_dir = (script_dir / "../data/processed").resolve()
    
    logger.info("Building grading datasets...")
    datasets = build_grading_datasets(raw_dir)
    
    df_final = datasets["final"]
    df_draft = datasets["draft"]
    
    df_final.to_csv(processed_dir / "grading_final_dataset.csv", index=False)
    df_draft.to_csv(processed_dir / "grading_draft_dataset.csv", index=False)
    
    logger.info(f"Final Dataset: N={len(df_final)}, Draft Dataset: N={len(df_draft)}")
    logger.info(f"Final Score Distribution: Mean={df_final['score'].mean():.2f}, Std={df_final['score'].std():.2f}")
    
    logger.info("Evaluating models on Final-only dataset...")
    res = evaluate_grading_models(df_final)
    
    with (exp_dir / "grading_formulation_comparison.json").open("w") as f:
        json.dump(res, f, indent=4)
        
    md_content = "# Grading Formulation Comparison (Final Only)\n\n"
    md_content += f"| Model | MAE | RMSE | R2 |\n|---|---|---|---|\n"
    for model_name in ["Mean_Baseline", "Ridge", "RandomForest"]:
        m_res = res[model_name]
        md_content += f"| {model_name} | {m_res['MAE']:.3f} | {m_res['RMSE']:.3f} | {m_res['R2']:.3f} |\n"
        
    with (exp_dir / "grading_formulation_comparison.md").open("w") as f:
        f.write(md_content)
        
    logger.info("Grading experiments completed.")

if __name__ == "__main__":
    main()
