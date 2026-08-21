import sys
import logging
import json
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# Import our dataset generator from the previous script
try:
    from scripts.robustness_eval import build_weakness_dataset
except ImportError:
    # If the previous script wasn't explicitly saved as a module, just load the generator locally
    import re
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
    # A. LinearSVC (Baseline)
    mod_a = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
        ("clf", LinearSVC(class_weight="balanced", random_state=42))
    ])
    
    # B. LogisticRegression
    mod_b = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
        ("clf", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000))
    ])
    
    # C. LinearSVC + Char Features
    char_word_features = FeatureUnion([
        ("word_tfidf", TfidfVectorizer(max_features=3000, ngram_range=(1,2))),
        ("char_tfidf", TfidfVectorizer(analyzer="char_wb", max_features=3000, ngram_range=(3,5)))
    ])
    mod_c = Pipeline([
        ("features", char_word_features),
        ("clf", LinearSVC(class_weight="balanced", random_state=42))
    ])
    
    return {"A_LinearSVC": mod_a, "B_LogisticRegression": mod_b, "C_LinearSVC_CharFeatures": mod_c}

def run_study(df: pd.DataFrame, models: dict, seeds: list, exp_dir: Path):
    logger.info("Running Weakness Model Improvement Study...")
    
    all_results = {name: [] for name in models}
    
    for seed in seeds:
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        train_idx, test_idx = next(gss.split(df["text"], df["label"], df["author"]))
        
        X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["label"]
        X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["label"]
        
        for name, model in models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            
            acc = accuracy_score(y_test, y_pred)
            p, r, f1_macro, _ = precision_recall_fscore_support(y_test, y_pred, average="macro", zero_division=0)
            _, _, f1_weight, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted", zero_division=0)
            
            all_results[name].append({
                "accuracy": acc,
                "macro_precision": p,
                "macro_recall": r,
                "macro_f1": f1_macro,
                "weighted_f1": f1_weight
            })
            
    # Aggregate
    final_report = {}
    for name in models:
        final_report[name] = calculate_aggregates(all_results[name])
        
    with (exp_dir / "weakness_model_study.json").open("w") as f:
        json.dump(final_report, f, indent=4)
        
    logger.info("Weakness study completed.")

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    
    seeds = list(range(42, 62)) # Exact 20 seeds
    
    logger.info("Building dataset...")
    df = build_weakness_dataset(raw_dir)
    
    models = build_models()
    run_study(df, models, seeds, exp_dir)

if __name__ == "__main__":
    main()
