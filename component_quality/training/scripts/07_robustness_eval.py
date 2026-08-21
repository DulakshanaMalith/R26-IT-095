import sys
import logging
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import Ridge
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    mean_absolute_error, mean_squared_error, r2_score
)
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# Utilities for Weakness Paragraph parsing (since it isn't statically cached)
def clean_text(text: str) -> str:
    if not isinstance(text, str): return ""
    return re.sub(r'\s+', ' ', text).strip()

def load_document_texts(author_dir: Path) -> str:
    full_text = ""
    for doc_type in ["draft", "final"]:
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

def get_paragraph(full_text: str, exact_match: str) -> str:
    clean_exact = clean_text(exact_match)
    paragraphs = re.split(r'\n\s*\n', full_text)
    for p in paragraphs:
        if clean_exact in clean_text(p):
            return clean_text(p)
    return ""

def build_weakness_dataset(raw_dir: Path) -> pd.DataFrame:
    exposes_dir = raw_dir / "exposes"
    records_para = []
    
    for author_dir in exposes_dir.iterdir():
        if not author_dir.is_dir(): continue
        author = author_dir.name
        
        ann_file = author_dir / "annotations.json"
        if not ann_file.exists(): continue
        
        with ann_file.open("r", encoding="utf-8") as f:
            annotations = json.load(f)
            
        full_text = load_document_texts(author_dir)
        para_labels = {}
        
        for ann in annotations:
            tag = ann.get("tag")
            if tag not in ["Highlight", "Strength", "Weakness", "Other"]: continue
            label = 1 if tag == "Weakness" else 0
            
            exact_text = ""
            selectors = ann.get("selectors", {}).get("target", [])
            for target in selectors:
                for sel in target.get("selector", []):
                    if sel.get("type") == "TextQuoteSelector":
                        exact_text = sel.get("exact", "")
            if not exact_text:
                exact_text = ann.get("text", "")
                
            clean_exact = clean_text(exact_text)
            if not clean_exact: continue
            
            para = get_paragraph(full_text, clean_exact)
            if para:
                if para not in para_labels:
                    para_labels[para] = set()
                para_labels[para].add(label)
                
        for p, labels in para_labels.items():
            if len(labels) == 1:
                records_para.append({"author": author, "text": p, "label": list(labels)[0]})
                
    return pd.DataFrame(records_para).drop_duplicates(subset=["author", "text"]).dropna(subset=["text", "label"])


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
                "max": float(np.max(vals)),
                "median": float(np.median(vals))
            }
    return aggs

def run_weakness_robustness(df: pd.DataFrame, seeds: list, exp_dir: Path) -> dict:
    logger.info(f"Running Weakness Repeated Eval across {len(seeds)} seeds...")
    results = []
    errors_list = []
    
    for seed in seeds:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_idx, test_idx = next(gss.split(df["text"], df["label"], df["author"]))
        
        X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["label"]
        X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["label"]
        
        train_authors = set(df.iloc[train_idx]["author"])
        test_authors = set(df.iloc[test_idx]["author"])
        assert len(train_authors.intersection(test_authors)) == 0, f"Author leakage in seed {seed}"
        
        # Candidate
        svc = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
            ("classifier", LinearSVC(class_weight="balanced", random_state=42))
        ])
        svc.fit(X_train, y_train)
        y_pred = svc.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        p, r, f1_macro, _ = precision_recall_fscore_support(y_test, y_pred, average="macro")
        _, _, f1_weight, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")
        
        # Baseline
        dummy = DummyClassifier(strategy="prior")
        dummy.fit(X_train, y_train)
        y_pred_dummy = dummy.predict(X_test)
        _, _, f1_dummy, _ = precision_recall_fscore_support(y_test, y_pred_dummy, average="macro", zero_division=0)
        
        results.append({
            "seed": seed,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "train_authors": len(train_authors),
            "test_authors": len(test_authors),
            "accuracy": acc,
            "macro_precision": p,
            "macro_recall": r,
            "macro_f1": f1_macro,
            "weighted_f1": f1_weight,
            "baseline_macro_f1": f1_dummy
        })
        
        # Track errors
        test_df = df.iloc[test_idx].copy()
        test_df["pred"] = y_pred
        test_df["seed"] = seed
        errors = test_df[test_df["label"] != test_df["pred"]]
        errors_list.append(errors)
        
    df_results = pd.DataFrame(results)
    df_results.to_csv(exp_dir / "weakness_repeated_metrics.csv", index=False)
    
    if errors_list:
        pd.concat(errors_list).to_csv(exp_dir / "weakness_representative_errors.csv", index=False)
        
    return calculate_aggregates(results)

def run_grading_robustness(df: pd.DataFrame, seeds: list, exp_dir: Path) -> dict:
    logger.info(f"Running Grading Repeated Eval across {len(seeds)} seeds...")
    results = []
    errors_list = []
    
    for seed in seeds:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_idx, test_idx = next(gss.split(df["text"], df["score"], df["author"]))
        
        X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["score"]
        X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["score"]
        
        train_authors = set(df.iloc[train_idx]["author"])
        test_authors = set(df.iloc[test_idx]["author"])
        assert len(train_authors.intersection(test_authors)) == 0, f"Author leakage in seed {seed}"
        
        # Candidate
        ridge = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
            ("regressor", Ridge(random_state=42))
        ])
        ridge.fit(X_train, y_train)
        y_pred = ridge.predict(X_test)
        
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        pearson = 0.0
        spearman = 0.0
        if len(y_test) > 2:
            p_res = stats.pearsonr(y_test, y_pred)
            pearson = p_res[0] if not np.isnan(p_res[0]) else 0.0
            s_res = stats.spearmanr(y_test, y_pred)
            spearman = s_res[0] if not np.isnan(s_res[0]) else 0.0
        
        # Baseline (Training set mean)
        dummy = DummyRegressor(strategy="mean")
        dummy.fit(X_train, y_train)
        y_pred_dummy = dummy.predict(X_test)
        mae_dummy = mean_absolute_error(y_test, y_pred_dummy)
        
        results.append({
            "seed": seed,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "train_authors": len(train_authors),
            "test_authors": len(test_authors),
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "pearson": pearson,
            "spearman": spearman,
            "baseline_mae": mae_dummy,
            "pred_min": float(np.min(y_pred)),
            "pred_max": float(np.max(y_pred)),
            "pred_mean": float(np.mean(y_pred)),
            "pred_std": float(np.std(y_pred))
        })
        
        # Track errors
        test_df = df.iloc[test_idx].copy()
        test_df["pred"] = y_pred
        test_df["seed"] = seed
        test_df["abs_error"] = (test_df["score"] - test_df["pred"]).abs()
        errors_list.append(test_df)
        
    df_results = pd.DataFrame(results)
    df_results.to_csv(exp_dir / "grading_repeated_metrics.csv", index=False)
    
    if errors_list:
        pd.concat(errors_list).sort_values(by="abs_error", ascending=False).to_csv(exp_dir / "grading_representative_errors.csv", index=False)
        
    return calculate_aggregates(results)

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    processed_dir = (script_dir / "../data/processed").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    
    seeds = list(range(42, 62)) # 20 seeds
    
    logger.info("Building / Loading Datasets...")
    weakness_df = build_weakness_dataset(raw_dir)
    grading_df = pd.read_csv(processed_dir / "grading_final_dataset.csv").dropna(subset=["text", "score"])
    
    weakness_aggs = run_weakness_robustness(weakness_df, seeds, exp_dir)
    grading_aggs = run_grading_robustness(grading_df, seeds, exp_dir)
    
    report = {
        "seeds_tested": len(seeds),
        "weakness": weakness_aggs,
        "grading": grading_aggs
    }
    
    with (exp_dir / "robustness_report.json").open("w") as f:
        json.dump(report, f, indent=4)
        
    logger.info("Robustness Evaluation Completed.")

if __name__ == "__main__":
    main()
