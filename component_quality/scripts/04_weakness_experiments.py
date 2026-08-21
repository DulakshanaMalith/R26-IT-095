import json
import logging
import sys
import re
from pathlib import Path
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

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

def load_document_texts(author_dir: Path) -> str:
    """Load both draft and final texts as a single corpus to search against."""
    full_text = ""
    for doc_type in ["draft", "final"]:
        doc_dir = author_dir / doc_type
        if doc_dir.exists():
            for tex_file in doc_dir.glob("*.tex"):
                try:
                    with tex_file.open("r", encoding="utf-8", errors="ignore") as f:
                        # Keep newlines for paragraph splitting
                        content = f.read()
                        # Clean latex but keep paragraphs
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
    # We clean exact match and full text just for finding the index
    clean_exact = clean_text(exact_match)
    # Finding the paragraph requires splitting by \n\n
    paragraphs = re.split(r'\n\s*\n', full_text)
    for p in paragraphs:
        if clean_exact in clean_text(p):
            return clean_text(p)
    return ""

def get_chunk(full_text: str, exact_match: str, chunk_size: int = 4000) -> str:
    clean_full = clean_text(full_text)
    clean_exact = clean_text(exact_match)
    idx = clean_full.find(clean_exact)
    if idx == -1:
        return ""
    start = max(0, idx - (chunk_size // 2))
    end = min(len(clean_full), idx + len(clean_exact) + (chunk_size // 2))
    return clean_full[start:end]

def build_datasets(raw_dir: Path) -> dict:
    exposes_dir = raw_dir / "exposes"
    records_span = []
    records_para = []
    records_chunk = []
    
    conflict_exclusions = {"para": 0, "chunk": 0}
    
    # We will aggregate annotations per paragraph/chunk to detect conflicts
    for author_dir in exposes_dir.iterdir():
        if not author_dir.is_dir(): continue
        author = author_dir.name
        
        ann_file = author_dir / "annotations.json"
        if not ann_file.exists(): continue
        
        with ann_file.open("r", encoding="utf-8") as f:
            annotations = json.load(f)
            
        full_text = load_document_texts(author_dir)
        
        # We need to map extracted texts to their labels to check conflicts
        para_labels = {}
        chunk_labels = {}
        
        for ann in annotations:
            tag = ann.get("tag")
            if tag not in ["Highlight", "Strength", "Weakness", "Other"]: continue
            label = 1 if tag == "Weakness" else 0
            
            # Find the exact text from selectors
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
            
            # 1. Span
            records_span.append({"author": author, "text": clean_exact, "label": label})
            
            # 2. Paragraph
            para = get_paragraph(full_text, clean_exact)
            if para:
                if para not in para_labels:
                    para_labels[para] = set()
                para_labels[para].add(label)
                
            # 3. Chunk
            chunk = get_chunk(full_text, clean_exact)
            if chunk:
                if chunk not in chunk_labels:
                    chunk_labels[chunk] = set()
                chunk_labels[chunk].add(label)
                
        # Resolve conflicts and append
        for p, labels in para_labels.items():
            if len(labels) > 1:
                conflict_exclusions["para"] += 1
            else:
                records_para.append({"author": author, "text": p, "label": list(labels)[0]})
                
        for c, labels in chunk_labels.items():
            if len(labels) > 1:
                conflict_exclusions["chunk"] += 1
            else:
                records_chunk.append({"author": author, "text": c, "label": list(labels)[0]})
                
    logger.info(f"Conflicts excluded -> Paragraphs: {conflict_exclusions['para']}, Chunks: {conflict_exclusions['chunk']}")
    return {
        "span": pd.DataFrame(records_span).drop_duplicates(subset=["author", "text"]),
        "paragraph": pd.DataFrame(records_para).drop_duplicates(subset=["author", "text"]),
        "chunk": pd.DataFrame(records_chunk).drop_duplicates(subset=["author", "text"])
    }

def evaluate_models(df: pd.DataFrame) -> dict:
    df = df.dropna(subset=["text", "label"])
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df["text"], df["label"], df["author"]))
    
    X_train, y_train = df.iloc[train_idx]["text"], df.iloc[train_idx]["label"]
    X_test, y_test = df.iloc[test_idx]["text"], df.iloc[test_idx]["label"]
    
    # Model A: LinearSVC
    svc = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
        ("clf", LinearSVC(class_weight="balanced", random_state=42))
    ])
    svc.fit(X_train, y_train)
    y_pred_svc = svc.predict(X_test)
    acc_svc = accuracy_score(y_test, y_pred_svc)
    _, _, f1_macro_svc, _ = precision_recall_fscore_support(y_test, y_pred_svc, average="macro")
    _, _, f1_weight_svc, _ = precision_recall_fscore_support(y_test, y_pred_svc, average="weighted")
    
    # Model B: Logistic Regression
    lr = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
        ("clf", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000))
    ])
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)
    acc_lr = accuracy_score(y_test, y_pred_lr)
    _, _, f1_macro_lr, _ = precision_recall_fscore_support(y_test, y_pred_lr, average="macro")
    _, _, f1_weight_lr, _ = precision_recall_fscore_support(y_test, y_pred_lr, average="weighted")
    
    return {
        "samples": len(df),
        "authors": df["author"].nunique(),
        "LinearSVC": {"Accuracy": acc_svc, "Macro_F1": f1_macro_svc, "Weighted_F1": f1_weight_svc},
        "LogReg": {"Accuracy": acc_lr, "Macro_F1": f1_macro_lr, "Weighted_F1": f1_weight_lr}
    }

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    exp_dir = (script_dir / "../models/experiments").resolve()
    
    logger.info("Building granular datasets...")
    datasets = build_datasets(raw_dir)
    
    results = {}
    md_content = "# Weakness Formulation Comparison\n\n| Input Granularity | Model | Samples | Authors | Accuracy | Macro F1 | Weighted F1 |\n|---|---|---|---|---|---|---|\n"
    
    for gran, df in datasets.items():
        logger.info(f"Evaluating {gran} formulation (N={len(df)})...")
        res = evaluate_models(df)
        results[gran] = res
        
        md_content += f"| {gran} | LinearSVC | {res['samples']} | {res['authors']} | {res['LinearSVC']['Accuracy']:.3f} | {res['LinearSVC']['Macro_F1']:.3f} | {res['LinearSVC']['Weighted_F1']:.3f} |\n"
        md_content += f"| {gran} | LogReg | {res['samples']} | {res['authors']} | {res['LogReg']['Accuracy']:.3f} | {res['LogReg']['Macro_F1']:.3f} | {res['LogReg']['Weighted_F1']:.3f} |\n"

    with (exp_dir / "weakness_formulation_comparison.json").open("w") as f:
        json.dump(results, f, indent=4)
        
    with (exp_dir / "weakness_formulation_comparison.md").open("w") as f:
        f.write(md_content)
        
    logger.info("Weakness experiments completed.")

if __name__ == "__main__":
    main()
