import json
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "feedback" / "weakness_vs_strength.csv"
OUT_DIR = ROOT_DIR / "results" / "ablation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_data():
    df = pd.read_csv(DATA_PATH)
    # Ensure columns exist
    df["span_text"] = df["span_text"].fillna("").astype(str).str.strip()
    df["comment_text"] = df["comment_text"].fillna("").astype(str).str.strip()
    df["context_before"] = df["context_before"].fillna("").astype(str).str.strip()
    df["context_after"] = df["context_after"].fillna("").astype(str).str.strip()
    
    # Create the exact ablation inputs
    df["span_only"] = df["span_text"]
    df["context_only"] = df["context_before"] + " " + df["context_after"]
    df["span_context"] = df["context_before"] + " " + df["span_text"] + " " + df["context_after"]
    df["comment_only"] = df["comment_text"]
    df["span_comment"] = df["span_text"] + " [SEP] " + df["comment_text"]
    df["full_input"] = df["span_context"] + " [SEP] " + df["comment_text"]
    
    # Strip spaces
    for c in ["context_only", "span_context", "span_comment", "full_input"]:
        df[c] = df[c].str.replace(r"\s+", " ", regex=True).str.strip()
        
    # Drop rows without annotation tag
    df = df[df["annotation_tag"].isin(["Weakness", "Strength"])].reset_index(drop=True)
    return df

def calculate_metrics(y_true, y_pred) -> dict:
    acc = accuracy_score(y_true, y_pred)
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    per_class_p, per_class_r, per_class_f, _ = precision_recall_fscore_support(y_true, y_pred, zero_division=0)
    return {
        "accuracy": acc,
        "macro_f1": f,
        "per_class_f1": per_class_f.tolist(),
        "per_class_p": per_class_p.tolist(),
        "per_class_r": per_class_r.tolist()
    }

def run_experiment(name, df, train_idx, test_idx, input_col, label_col="annotation_tag", group_col="author", shuffle_train=False, extract_features=False):
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()
    
    if shuffle_train:
        train_df[label_col] = np.random.permutation(train_df[label_col].values)
        
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000)),
        ("classifier", LinearSVC(class_weight="balanced", random_state=42, max_iter=2000)),
    ])
    
    # CV
    gkf = GroupKFold(n_splits=5)
    cv_scores = []
    
    # X and y for train
    X_train_full = train_df[input_col].values
    y_train_full = train_df[label_col].values
    groups_train = train_df[group_col].values
    
    for tr_f, val_f in gkf.split(X_train_full, y_train_full, groups_train):
        X_tr = X_train_full[tr_f]
        y_tr = y_train_full[tr_f]
        X_v = X_train_full[val_f]
        y_v = y_train_full[val_f]
        
        pipeline.fit(X_tr, y_tr)
        preds = pipeline.predict(X_v)
        score = precision_recall_fscore_support(y_v, preds, average="macro", zero_division=0)[2]
        cv_scores.append(score)
        
    cv_mean = np.mean(cv_scores)
    cv_std = np.std(cv_scores)
    
    # Final train and evaluate on test
    pipeline.fit(X_train_full, y_train_full)
    
    train_preds = pipeline.predict(X_train_full)
    test_preds = pipeline.predict(test_df[input_col].values)
    
    train_metrics = calculate_metrics(y_train_full, train_preds)
    test_metrics = calculate_metrics(test_df[label_col].values, test_preds)
    
    baseline_acc = (test_df[label_col] == test_df[label_col].mode()[0]).mean()
    
    res = {
        "experiment": name,
        "input_features": input_col,
        "train_macro_f1": train_metrics["macro_f1"],
        "cv_macro_f1": cv_mean,
        "cv_macro_f1_std": cv_std,
        "test_macro_f1": test_metrics["macro_f1"],
        "test_accuracy": test_metrics["accuracy"],
        "baseline_accuracy": baseline_acc,
        "generalization_gap": train_metrics["macro_f1"] - test_metrics["macro_f1"],
        "per_class": {
            "labels": ["Strength", "Weakness"], # sorted alphabetically
            "precision": test_metrics["per_class_p"],
            "recall": test_metrics["per_class_r"],
            "f1": test_metrics["per_class_f1"]
        }
    }
    
    if extract_features:
        features = pipeline.named_steps["tfidf"].get_feature_names_out()
        coef = pipeline.named_steps["classifier"].coef_[0]
        # Sort coefficients
        top_positive_idx = np.argsort(coef)[-30:][::-1]
        top_negative_idx = np.argsort(coef)[:30]
        
        pos_features = [(features[i], coef[i]) for i in top_positive_idx]
        neg_features = [(features[i], coef[i]) for i in top_negative_idx]
        
        res["top_positive_features"] = pos_features
        res["top_negative_features"] = neg_features
        
    return res

def feature_extraction_to_csv(results, outfile):
    rows = []
    for r in results:
        if "top_positive_features" in r:
            for feat, coef in r["top_positive_features"]:
                rows.append({"model": r["experiment"], "feature": feat, "coef": coef, "type": "positive"})
            for feat, coef in r["top_negative_features"]:
                rows.append({"model": r["experiment"], "feature": feat, "coef": coef, "type": "negative"})
                
    if rows:
        pd.DataFrame(rows).to_csv(outfile, index=False)
        print(f"Saved {outfile}")

def run_masking_test(df, train_idx, test_idx):
    train_df = df.iloc[train_idx].copy()
    test_df = df.iloc[test_idx].copy()
    
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=5000)),
        ("classifier", LinearSVC(class_weight="balanced", random_state=42, max_iter=2000)),
    ])
    pipeline.fit(train_df["span_comment"].values, train_df["annotation_tag"].values)
    
    # Original
    orig_preds = pipeline.predict(test_df["span_comment"].values)
    orig_f1 = precision_recall_fscore_support(test_df["annotation_tag"].values, orig_preds, average="macro")[2]
    
    # Mask target words
    patterns = r"(?i)\b(weakness(es)?|weak point|weak|strength(s)?|strong point|strong)\b"
    masked_comments = test_df["comment_text"].str.replace(patterns, "[MASK]", regex=True)
    masked_input = test_df["span_text"] + " [SEP] " + masked_comments
    mask_preds = pipeline.predict(masked_input.values)
    mask_f1 = precision_recall_fscore_support(test_df["annotation_tag"].values, mask_preds, average="macro")[2]
    
    # Remove comment
    no_comment_input = test_df["span_text"] + " [SEP] "
    no_comment_preds = pipeline.predict(no_comment_input.values)
    no_comment_f1 = precision_recall_fscore_support(test_df["annotation_tag"].values, no_comment_preds, average="macro")[2]
    
    res = {
        "original_f1": orig_f1,
        "masked_f1": mask_f1,
        "no_comment_f1": no_comment_f1
    }
    
    with open(OUT_DIR / "comment_masking.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Saved comment_masking.json")

def main():
    df = load_data()
    
    # 1. FIXED SPLIT
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(df, groups=df["author"]))
    
    with open(OUT_DIR / "fixed_split.json", "w") as f:
        json.dump({"train_ids": train_idx.tolist(), "test_ids": test_idx.tolist()}, f)
    print("Saved fixed_split.json")
    
    # 2. ABLATION EXPERIMENTS
    experiments = [
        {"name": "span_only", "col": "span_only"},
        {"name": "context_only", "col": "context_only"},
        {"name": "span_context", "col": "span_context"},
        {"name": "comment_only", "col": "comment_only"},
        {"name": "span_comment", "col": "span_comment"},
        {"name": "full_input", "col": "full_input"}
    ]
    
    summary = []
    feature_results = []
    
    for exp in experiments:
        extract = exp["name"] in ["span_only", "comment_only", "span_comment"]
        res = run_experiment(exp["name"], df, train_idx, test_idx, exp["col"], extract_features=extract)
        
        # Save individual JSON and MD
        with open(OUT_DIR / f"{exp['name']}.json", "w") as f:
            json.dump(res, f, indent=2)
            
        md = f"# {exp['name']}\nTest Macro F1: {res['test_macro_f1']:.4f}\n"
        with open(OUT_DIR / f"{exp['name']}.md", "w") as f:
            f.write(md)
            
        summary.append(res)
        if extract:
            feature_results.append(res)
            
    # Save feature analysis
    feature_extraction_to_csv(feature_results, OUT_DIR / "tfidf_feature_analysis.csv")
    
    # Save summary CSV
    summary_df = pd.DataFrame([{k: v for k, v in s.items() if not isinstance(v, (dict, list))} for s in summary])
    summary_df.to_csv(OUT_DIR / "ablation_summary.csv", index=False)
    print("Saved ablation_summary.csv")
    
    # Save summary MD
    md_lines = ["| Input | Train F1 | CV F1 | Test F1 | Accuracy |", "|---|---|---|---|---|"]
    for s in summary:
        md_lines.append(f"| {s['experiment']} | {s['train_macro_f1']:.4f} | {s['cv_macro_f1']:.4f} | {s['test_macro_f1']:.4f} | {s['test_accuracy']:.4f} |")
    
    with open(OUT_DIR / "ablation_summary.md", "w") as f:
        f.write("\n".join(md_lines))
    print("Saved ablation_summary.md")
    
    # 3. RANDOM LABEL SANITY CHECK
    sanity_res = {}
    for exp_name in ["span_only", "comment_only", "span_comment"]:
        col = [e["col"] for e in experiments if e["name"] == exp_name][0]
        res = run_experiment(exp_name + "_shuffled", df, train_idx, test_idx, col, shuffle_train=True)
        sanity_res[exp_name] = {
            "test_macro_f1_real": [s["test_macro_f1"] for s in summary if s["experiment"] == exp_name][0],
            "test_macro_f1_shuffled": res["test_macro_f1"]
        }
        
    with open(OUT_DIR / "random_label_sanity_check.json", "w") as f:
        json.dump(sanity_res, f, indent=2)
    print("Saved random_label_sanity_check.json")
    
    # 4. COMMENT MASKING TEST
    run_masking_test(df, train_idx, test_idx)
    
    # 5. REVIEWER GROUP SENSITIVITY
    df["review_id"] = df["review_id"].fillna("unknown_review").astype(str)
    res_reviewer = run_experiment("span_comment_reviewer_cv", df, train_idx, test_idx, "span_comment", group_col="review_id")
    print(f"Review-Group CV F1: {res_reviewer['cv_macro_f1']:.4f}")
    
    print("Ablation run complete.")

if __name__ == "__main__":
    main()
