"""Train an explicitly experimental, time-aware JIRA resolution proxy.

This is NOT a student-suitability model. Only Sourcetree-for-Windows Jira
issues are used (GFG_FINAL.csv is a misleading legacy filename);
Apache's different ``not delayed`` label and project pseudo-members are excluded.
All member-history features use information observable before each issue's
creation time. The hold-out is the latest 20% of eligible issues by creation.
The old mixed-label artifact is preserved for audit but is not loaded by the
live scheduler unless an explicitly validated replacement is configured.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "datasets" / "workload_assignment" / "GFG_FINAL.csv"
MODEL_PATH = ROOT / "models" / "workload_proxy_v2.joblib"
REPORT_PATH = ROOT / "ieee_paper" / "workload_proxy_v2_results.json"
FEATURES = [
    "task_effort_estimate", "task_category", "task_complexity",
    "member_completion_rate", "member_current_workload",
    "member_avg_effort", "is_collaborative",
]
PRIORITY = {"Critical": 3, "Highest": 3, "High": 3, "Medium": 2, "Low": 1, "Lowest": 1}
EFFORT = {
    ("Bug", "Critical"): 120, ("Bug", "Highest"): 120,
    ("Bug", "High"): 90, ("Bug", "Medium"): 56,
    ("Bug", "Low"): 24, ("Bug", "Lowest"): 16,
    ("Suggestion", "High"): 64, ("Suggestion", "Medium"): 40,
    ("Suggestion", "Low"): 20,
}


def _estimated_effort(issue_type: str, priority: str) -> float:
    return float(EFFORT.get((issue_type, priority), EFFORT.get((issue_type, "Medium"), 40)))


def build_dataset(path: Path = DATA_PATH) -> pd.DataFrame:
    source = pd.read_csv(
        path, on_bad_lines="skip", low_memory=False,
        usecols=["Assignee", "Created", "Resolved", "Resolution", "Issue Type", "Priority"],
    )
    source = source[source["Assignee"].notna()].copy()
    source["Created"] = pd.to_datetime(source["Created"], errors="coerce", utc=True)
    source["Resolved"] = pd.to_datetime(source["Resolved"], errors="coerce", utc=True)
    source = source[source["Created"].notna()].sort_values("Created", kind="stable")
    source["task_category"] = source["Issue Type"].eq("Bug").astype(int)
    source["task_complexity"] = source["Priority"].map(PRIORITY).fillna(2).astype(int)
    source["task_effort_estimate"] = [
        _estimated_effort(kind, priority)
        for kind, priority in zip(source["Issue Type"], source["Priority"])
    ]

    history: dict[str, list[tuple]] = {}
    records = []
    for row in source.itertuples(index=False):
        member = str(row.Assignee)
        created = row.Created
        prior = [item for item in history.get(member, []) if item[0] < created]
        closed_before = [item for item in prior if pd.notna(item[1]) and item[1] < created]
        open_before = [item for item in prior if pd.isna(item[1]) or item[1] >= created]
        completion_rate = (
            sum(item[2] for item in closed_before) / len(closed_before)
            if closed_before else 0.5
        )
        average_effort = float(np.mean([item[3] for item in prior])) if prior else 40.0
        records.append({
            "created": created,
            "assignee": member,
            "task_effort_estimate": float(row.task_effort_estimate),
            "task_category": float(row.task_category),
            "task_complexity": float(row.task_complexity),
            "member_completion_rate": float(completion_rate),
            "member_current_workload": float(len(open_before)),
            "member_avg_effort": average_effort,
            "is_collaborative": 0.0,
            "fixed": int(row.Resolution == "Fixed"),
        })
        history.setdefault(member, []).append(
            (created, row.Resolved, int(row.Resolution == "Fixed"), float(row.task_effort_estimate))
        )
    return pd.DataFrame.from_records(records).sort_values("created", kind="stable").reset_index(drop=True)


def _estimator(y: pd.Series) -> XGBClassifier:
    positives = int(y.sum())
    negatives = len(y) - positives
    return XGBClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=5,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=(negatives / positives if positives else 1.0),
        random_state=42, n_jobs=1, eval_metric="logloss",
    )


def train() -> dict:
    dataset = build_dataset()
    if len(dataset) < 100 or dataset["fixed"].nunique() != 2:
        raise ValueError("Not enough GFG issues with both snapshot-status classes.")
    split = int(len(dataset) * 0.8)
    training, test = dataset.iloc[:split], dataset.iloc[split:]
    if training["fixed"].nunique() != 2 or test["fixed"].nunique() != 2:
        raise ValueError("The chronological train/test split lacks both outcome classes.")
    model = _estimator(training["fixed"])
    model.fit(training[FEATURES], training["fixed"])
    predictions = model.predict(test[FEATURES])

    folds = []
    for train_index, valid_index in TimeSeriesSplit(n_splits=5).split(training):
        fold_train = training.iloc[train_index]
        fold_valid = training.iloc[valid_index]
        if fold_train["fixed"].nunique() != 2:
            continue
        fold_model = _estimator(fold_train["fixed"])
        fold_model.fit(fold_train[FEATURES], fold_train["fixed"])
        folds.append(float(accuracy_score(fold_valid["fixed"], fold_model.predict(fold_valid[FEATURES]))))

    # Deployment defaults come from training history only; these identities
    # are issue-tracker assignees, not student IDs.
    member_stats = training.groupby("assignee").agg(
        member_completion_rate=("fixed", "mean"),
        member_current_workload=("member_current_workload", "last"),
        member_avg_effort=("task_effort_estimate", "mean"),
    ).reset_index().rename(columns={"assignee": "Assignee"})
    report = {
        "target": "Fixed by dataset export versus not Fixed by export (GFG JIRA)",
        "validated_for_student_assignment": False,
        "split_method": "Chronological 80/20 by issue creation; as-of member histories",
        "total_rows": len(dataset),
        "train_rows": len(training), "test_rows": len(test),
        "assignees": int(dataset["assignee"].nunique()),
        "test_class_counts": {
            str(int(label)): int(count)
            for label, count in test["fixed"].value_counts().sort_index().items()
        },
        "majority_class_baseline_accuracy": round(
            float(test["fixed"].value_counts(normalize=True).max()), 4
        ),
        "accuracy": round(float(accuracy_score(test["fixed"], predictions)), 4),
        "weighted_f1": round(float(f1_score(test["fixed"], predictions, average="weighted")), 4),
        "confusion_matrix": confusion_matrix(test["fixed"], predictions).tolist(),
        "time_cv_accuracy": [round(value, 4) for value in folds],
        "limitations": [
            "Only a small number of JIRA assignees; no student data or suitability labels.",
            "Unresolved issues are treated as not Fixed at export; censoring and issue age bias this snapshot-status label.",
            "Fixed status is not a measure of expertise or on-time delivery.",
            "The historical issue export may not represent prospective student workloads.",
        ],
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model, "features": FEATURES, "algorithm": "XGBClassifier",
        "target": report["target"], "validated_for_student_assignment": False,
        "member_stats": member_stats,
        "global_defaults": {"cr": 0.5, "wl": 0.0, "ae": 40.0},
    }, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
