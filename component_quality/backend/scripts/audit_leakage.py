import json
import re
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.feature_extraction.text import CountVectorizer

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "feedback" / "weakness_vs_strength.csv"
OUT_DIR = ROOT_DIR / "results" / "data_leakage_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_data():
    df = pd.read_csv(DATA_PATH)
    # Ensure columns exist
    df["span_text"] = df["span_text"].fillna("").astype(str).str.strip()
    df["comment_text"] = df["comment_text"].fillna("").astype(str).str.strip()
    df["context_before"] = df["context_before"].fillna("").astype(str).str.strip()
    df["context_after"] = df["context_after"].fillna("").astype(str).str.strip()
    
    df["span_context"] = df["context_before"] + " " + df["span_text"] + " " + df["context_after"]
    df["span_context"] = df["span_context"].str.replace(r"\s+", " ", regex=True).str.strip()
    
    df["span_comment"] = df["span_text"] + " [SEP] " + df["comment_text"]
    df["input_span_comment"] = df["span_text"] + " [SEP] " + df["comment_text"]
    
    df["full_context"] = df["span_context"] + " [SEP] " + df["comment_text"]
    
    return df

def exact_duplicate_audit(df):
    cols_to_check = {
        "span_text": "span_text",
        "comment_text": "comment_text",
        "span_comment": "span_comment",
        "input_span_comment": "input_span_comment",
        "full_context": "full_context"
    }
    
    results = []
    total_rows = len(df)
    
    for name, col in cols_to_check.items():
        # filter out empty
        valid_df = df[df[col] != ""]
        unique_vals = valid_df[col].nunique()
        dup_rows = len(valid_df) - unique_vals
        dup_pct = (dup_rows / total_rows) * 100 if total_rows > 0 else 0
        
        results.append({
            "field": name,
            "total_rows": total_rows,
            "unique_values": unique_vals,
            "duplicated_rows": dup_rows,
            "duplicate_percentage": round(dup_pct, 2)
        })
        
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_DIR / "exact_duplicates.csv", index=False)
    print("Saved exact_duplicates.csv")

def conflicting_label_audit(df):
    cols_to_check = ["span_text", "comment_text", "span_comment", "input_span_comment"]
    
    results = []
    for col in cols_to_check:
        valid_df = df[df[col] != ""]
        # group by the text column and count unique tags
        grouped = valid_df.groupby(col)["annotation_tag"].nunique()
        conflicts = grouped[grouped > 1]
        
        num_conflicts = len(conflicts)
        affected_rows = len(valid_df[valid_df[col].isin(conflicts.index)])
        
        results.append({
            "field": col,
            "conflicting_groups": num_conflicts,
            "affected_rows": affected_rows
        })
        
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_DIR / "conflicting_labels.csv", index=False)
    print("Saved conflicting_labels.csv")

def run_train_test_overlap(df):
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df, groups=df["author"]))
    
    train_df = df.iloc[train_idx]
    test_df = df.iloc[test_idx]
    
    fields = [
        "span_text", "comment_text", "span_comment", "input_span_comment", "span_context", 
        "annotation_id", "comment_id", "review_id", "author"
    ]
    
    results = {}
    md_lines = ["# Train/Test Overlap Audit\n"]
    md_lines.append("| Field | Train Count | Test Count | Intersection | Percentage Test Overlap |")
    md_lines.append("|---|---|---|---|---|")
    
    for f in fields:
        if f not in df.columns:
            continue
            
        train_set = set(train_df[train_df[f] != ""][f].dropna())
        test_set = set(test_df[test_df[f] != ""][f].dropna())
        
        intersection = train_set.intersection(test_set)
        
        pct = (len(intersection) / len(test_set)) * 100 if len(test_set) > 0 else 0
        
        results[f] = {
            "train_count": len(train_set),
            "test_count": len(test_set),
            "intersection_count": len(intersection),
            "percentage": round(pct, 2)
        }
        
        md_lines.append(f"| {f} | {len(train_set)} | {len(test_set)} | {len(intersection)} | {pct:.2f}% |")
        
    with open(OUT_DIR / "train_test_overlap.json", "w") as f:
        json.dump(results, f, indent=2)
        
    with open(OUT_DIR / "train_test_overlap.md", "w") as f:
        f.write("\n".join(md_lines))
        
    print("Saved train_test_overlap.json/.md")
    
    # Save group split audit specifically
    group_audit = {
        "num_train_authors": len(set(train_df["author"])),
        "num_test_authors": len(set(test_df["author"])),
        "author_intersection": len(set(train_df["author"]).intersection(set(test_df["author"])))
    }
    with open(OUT_DIR / "group_split_audit.json", "w") as f:
        json.dump(group_audit, f, indent=2)
    print("Saved group_split_audit.json")
    
    return train_df, test_df

def explicit_target_markers(df):
    patterns = {
        "weakness": r"(?i)\b(weakness(es)?|weak point|weak)\b",
        "strength": r"(?i)\b(strength(s)?|strong point|strong)\b"
    }
    
    results = []
    
    for tag in ["Weakness", "Strength"]:
        tag_df = df[df["annotation_tag"] == tag]
        total = len(tag_df)
        
        if total == 0:
            continue
            
        weak_count = tag_df["comment_text"].str.contains(patterns["weakness"], regex=True).sum()
        str_count = tag_df["comment_text"].str.contains(patterns["strength"], regex=True).sum()
        
        results.append({
            "true_label": tag,
            "total_examples": total,
            "contains_weakness_marker": int(weak_count),
            "pct_weakness_marker": round((weak_count/total)*100, 2),
            "contains_strength_marker": int(str_count),
            "pct_strength_marker": round((str_count/total)*100, 2)
        })
        
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_DIR / "explicit_target_markers.csv", index=False)
    print("Saved explicit_target_markers.csv")

def lexical_analysis(train_df):
    # Top 30 unigrams and bigrams for each class in training set
    from sklearn.feature_extraction.text import TfidfVectorizer
    
    results = []
    
    for ngram in [(1,1), (2,2)]:
        vec = TfidfVectorizer(ngram_range=ngram, stop_words="english", max_features=2000)
        X = vec.fit_transform(train_df["comment_text"])
        features = np.array(vec.get_feature_names_out())
        
        for tag in ["Weakness", "Strength"]:
            mask = (train_df["annotation_tag"] == tag).values
            if mask.sum() == 0: continue
            
            # Sum tf-idf scores
            class_scores = np.asarray(X[mask].sum(axis=0)).flatten()
            top_indices = class_scores.argsort()[-30:][::-1]
            
            for rank, idx in enumerate(top_indices):
                results.append({
                    "n": ngram[1],
                    "target_class": tag,
                    "rank": rank + 1,
                    "term": features[idx],
                    "score": class_scores[idx]
                })
                
    res_df = pd.DataFrame(results)
    res_df.to_csv(OUT_DIR / "comment_lexical_analysis.csv", index=False)
    print("Saved comment_lexical_analysis.csv")

def main():
    df = load_data()
    exact_duplicate_audit(df)
    conflicting_label_audit(df)
    train_df, test_df = run_train_test_overlap(df)
    explicit_target_markers(df)
    lexical_analysis(train_df)
    print("Audit leakage script complete.")

if __name__ == "__main__":
    main()
