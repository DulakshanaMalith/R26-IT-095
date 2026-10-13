import sys
import logging
import json
import re
from pathlib import Path

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
    return full_text.strip()

def main():
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / "../training/data/raw/exposes").resolve()
    data_out = (script_dir / "data/reviewer_eval_set.jsonl").resolve()
    
    records = []
    
    # Sort for deterministic iteration
    author_dirs = sorted(raw_dir.iterdir())
    
    for author_dir in author_dirs:
        if not author_dir.is_dir(): continue
        author = author_dir.name
        
        # Must have annotations
        ann_file = author_dir / "annotations.json"
        if not ann_file.exists(): continue
        
        # Must have scores
        scores_file = author_dir / "scores.json"
        if not scores_file.exists(): continue
        
        # Load final text
        text = load_document_texts(author_dir, "final")
        if not text: continue
        
        # Extract ground truth weakness annotations
        with ann_file.open("r", encoding="utf-8") as f:
            annotations = json.load(f)
            
        gt_weaknesses = []
        for ann in annotations:
            if ann.get("tag") == "Weakness":
                exact_text = ""
                selectors = ann.get("selectors", {}).get("target", [])
                for target in selectors:
                    for sel in target.get("selector", []):
                        if sel.get("type") == "TextQuoteSelector":
                            exact_text = sel.get("exact", "")
                if not exact_text:
                    exact_text = ann.get("text", "")
                if exact_text:
                    gt_weaknesses.append({
                        "exact_text": exact_text,
                        "comment": ann.get("comment", "")
                    })
        
        # Extract ground truth score
        with scores_file.open("r", encoding="utf-8") as f:
            scores_data = json.load(f)
        gt_score = None
        gt_criteria = {}
        for sd in scores_data:
            if sd.get("type") == "final":
                gt_score = sd.get("scores", {}).get("total")
                gt_criteria = sd.get("criteria", {})
                break
                
        if gt_score is None: continue
        
        eval_id = f"EVAL_{author.replace(' ', '_').upper()}"
        
        records.append({
            "evaluation_id": eval_id,
            "author_id": author,
            "proposal_id": f"prop_{author.replace(' ', '_').lower()}",
            "source_file": "final/proposal.tex",
            "proposal_text": text,
            "metadata": {
                "ground_truth_weaknesses": gt_weaknesses,
                "ground_truth_score": gt_score,
                "ground_truth_criteria": gt_criteria
            }
        })
        
        # Stop at 10 proposals for the evaluation set
        if len(records) >= 10:
            break
            
    logger.info(f"Built evaluation dataset with {len(records)} proposals.")
    
    with data_out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

if __name__ == "__main__":
    main()
