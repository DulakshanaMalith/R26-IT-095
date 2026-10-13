import sys
import logging
from pathlib import Path
import pandas as pd
import json
import re

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit

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

def generate_paragraph_weakness(raw_dir: Path) -> pd.DataFrame:
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
                
    return pd.DataFrame(records_para).drop_duplicates(subset=["author", "text"])

def train_and_promote(raw_dir: Path, processed_dir: Path, models_dir: Path):
    logger.info("Training and Promoting Optimal Formulations...")
    
    # 1. Weakness Model (Paragraph + LinearSVC)
    logger.info("Building Weakness Paragraph Dataset...")
    df_weak = generate_paragraph_weakness(raw_dir)
    df_weak = df_weak.dropna(subset=["text", "label"])
    
    svc = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
        ("classifier", LinearSVC(class_weight="balanced", random_state=42)) # Needs to have 'predict'
    ])
    svc.fit(df_weak["text"], df_weak["label"])
    
    weakness_path = models_dir / "weakness_svm_model.pkl"
    joblib.dump(svc, weakness_path)
    logger.info(f"Promoted Weakness Model -> {weakness_path}")
    
    # 2. Grading Model (Final + Ridge)
    logger.info("Loading Final Grading Dataset...")
    df_grade = pd.read_csv(processed_dir / "grading_final_dataset.csv")
    df_grade = df_grade.dropna(subset=["text", "score"])
    
    ridge = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=3000, stop_words='english')),
        ("regressor", Ridge(random_state=42)) # 'predict' returns regression score
    ])
    
    # We must patch the Ridge object to mimic the predict shape if backend expects list
    # The backend handles it: float(semantic_grading_model.predict([text])[0])
    ridge.fit(df_grade["text"], df_grade["score"])
    
    grading_path = models_dir / "semantic_grading_model.pkl"
    joblib.dump(ridge, grading_path)
    logger.info(f"Promoted Grading Model -> {grading_path}")

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../data/raw").resolve()
    processed_dir = (script_dir / "../data/processed").resolve()
    models_dir = (script_dir / "../models").resolve()
    
    train_and_promote(raw_dir, processed_dir, models_dir)

if __name__ == "__main__":
    main()
