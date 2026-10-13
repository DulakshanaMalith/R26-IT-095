"""Controlled workload-allocation baseline evaluation for the IEEE paper.

The experiment uses held-out JIRA task rows and the member profiles stored with
the trained workload artifact. It compares four assignment policies on the same
resampled 20-task, four-member scenarios:

* Random assignment
* LPT least-loaded assignment
* XGBoost score only
* XGBoost + 1.40 overload guard + final whole-task rebalancing

This is a controlled resampling experiment, not a real student-cohort study.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "workload_rf.joblib"
OUTPUT_CSV = ROOT / "ieee_paper" / "workload_baseline_results.csv"
OUTPUT_TRIAL_CSV = ROOT / "ieee_paper" / "workload_baseline_trials.csv"
OUTPUT_JSON = ROOT / "ieee_paper" / "workload_baseline_summary.json"
RANDOM_SEED = 42
TRIALS = 100
TASKS_PER_TRIAL = 20
TEAM_SIZE = 4
OVERLOAD_RATIO = 1.40


EFFORT_MAP = {
    ("Bug", "Critical"): 120,
    ("Bug", "Highest"): 120,
    ("Bug", "High"): 90,
    ("Bug", "Medium"): 56,
    ("Bug", "Low"): 24,
    ("Bug", "Lowest"): 16,
    ("Suggestion", "High"): 64,
    ("Suggestion", "Medium"): 40,
    ("Suggestion", "Low"): 20,
}


def _effort(issue_type: str, priority: str) -> float:
    return float(
        EFFORT_MAP.get(
            (issue_type, priority), EFFORT_MAP.get((issue_type, "Medium"), 40)
        )
    )


def load_held_out_tasks() -> pd.DataFrame:
    """Rebuild the exact stratified test rows used by train_workload_model.py."""
    gfg = pd.read_csv(
        ROOT / "datasets" / "workload_assignment" / "GFG_FINAL.csv",
        encoding="utf-8",
        on_bad_lines="skip",
        usecols=["Issue Type", "Priority", "Resolution", "Assignee", "Created"],
    )
    gfg = gfg[gfg["Assignee"].notna()].copy()
    gfg["Created"] = pd.to_datetime(gfg["Created"], errors="coerce", utc=True)
    gfg = gfg[gfg["Created"].notna()].reset_index(drop=True)
    priority_map = {
        "Critical": 3,
        "Highest": 3,
        "High": 3,
        "Medium": 2,
        "Low": 1,
        "Lowest": 1,
    }
    gfg["task_complexity"] = gfg["Priority"].map(priority_map).fillna(2).astype(int)
    gfg["task_category"] = (gfg["Issue Type"] == "Bug").astype(int)
    gfg["task_effort_estimate"] = gfg.apply(
        lambda row: _effort(row["Issue Type"], row["Priority"]), axis=1
    )
    gfg["is_collaborative"] = 0
    gfg["resolved_fixed"] = (gfg["Resolution"] == "Fixed").astype(int)
    gfg["completed_on_time"] = gfg["resolved_fixed"]

    apache = pd.read_csv(ROOT / "datasets" / "model3_delay" / "apache_jira_delay.csv")
    apache_priority = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3}
    apache["task_complexity"] = apache["priority"].map(apache_priority).fillna(2).astype(int)
    apache["task_category"] = apache["is_bug"].astype(int)
    apache["task_effort_estimate"] = (
        apache["task_complexity"] * np.where(apache["is_bug"] == 1, 30, 20)
    ).clip(16, 120)
    apache["is_collaborative"] = 0
    apache["resolved_fixed"] = (1 - apache["delayed"]).astype(int)
    apache["completed_on_time"] = apache["resolved_fixed"]
    apache["Assignee"] = "apache_" + apache["project"]

    columns = [
        "task_effort_estimate",
        "task_category",
        "task_complexity",
        "is_collaborative",
        "resolved_fixed",
        "completed_on_time",
        "Assignee",
    ]
    combined = pd.concat([gfg[columns], apache[columns]], ignore_index=True).dropna()
    _, test_index = train_test_split(
        combined.index,
        test_size=0.2,
        stratify=combined["completed_on_time"],
        random_state=RANDOM_SEED,
    )
    return combined.loc[test_index].reset_index(drop=True)


def balance_metrics(loads: dict[str, float]) -> dict[str, float]:
    values = np.asarray(list(loads.values()), dtype=float)
    mean = float(values.mean())
    minimum = float(values.min())
    maximum = float(values.max())
    return {
        "cv_percent": float(values.std() / mean * 100) if mean else 0.0,
        "spread_hours": maximum - minimum,
        "max_to_min_ratio": maximum / minimum if minimum > 0 else float("inf"),
        "overloaded": float(maximum > minimum * OVERLOAD_RATIO + 1e-9),
    }


def objective(loads: dict[str, float]) -> tuple[float, float, float]:
    values = list(loads.values())
    maximum, minimum = max(values), min(values)
    overload_excess = max(0.0, maximum - minimum * OVERLOAD_RATIO)
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return (round(overload_excess, 9), round(maximum - minimum, 9), round(variance, 9))


def rebalance(assignments: list[dict], loads: dict[str, float]) -> int:
    """Mirror main.py's whole-task lexicographic local search."""
    members = list(loads)
    max_iterations = max(1, len(assignments) * len(members) * 4)
    moves = 0
    for _ in range(max_iterations):
        current = objective(loads)
        best = None
        for index, assignment in enumerate(assignments):
            source = assignment["member"]
            effort = assignment["effort"]
            for target in members:
                if target == source:
                    continue
                trial = dict(loads)
                trial[source] -= effort
                trial[target] += effort
                trial_objective = objective(trial)
                if trial_objective >= current:
                    continue
                key = (trial_objective, index, target)
                if best is None or key < best[0]:
                    best = (key, index, target, trial)
        if best is None:
            break
        _, index, target, trial = best
        assignments[index]["member"] = target
        loads.update(trial)
        moves += 1
    return moves


def model_probabilities(model, rows: list[tuple[str, dict, dict, float]]) -> dict[str, float]:
    """Score several task-member pairs in one model call."""
    feature_rows = []
    labels = []
    for label, task, profile, assigned_hours in rows:
        average_effort = max(float(profile["member_avg_effort"]), 1.0)
        task_count = round(
            (float(profile["open_hours"]) + assigned_hours) / average_effort, 1
        )
        labels.append(label)
        feature_rows.append(
            {
                "task_effort_estimate": float(task["task_effort_estimate"]),
                "task_category": float(task["task_category"]),
                "task_complexity": float(task["task_complexity"]),
                "member_completion_rate": float(profile["member_completion_rate"]),
                "member_current_workload": task_count,
                "member_avg_effort": average_effort,
                "is_collaborative": 0.0,
            }
        )
    probabilities = model.predict_proba(pd.DataFrame(feature_rows))[:, 1]
    return {label: float(probability) for label, probability in zip(labels, probabilities)}


def assign(policy: str, tasks: list[dict], profiles: dict[str, dict], model, rng) -> dict:
    members = sorted(profiles)
    loads = {member: 0.0 for member in members}
    assignments: list[dict] = []
    guard_overrides = 0

    for task in sorted(tasks, key=lambda item: item["task_effort_estimate"], reverse=True):
        scores = model_probabilities(
            model,
            [(member, task, profiles[member], loads[member]) for member in members],
        )
        if policy == "random":
            chosen = str(rng.choice(members))
        elif policy == "lpt":
            chosen = min(members, key=lambda member: (loads[member], member))
        else:
            chosen = max(members, key=lambda member: (scores[member], -members.index(member)))
            if policy == "hybrid":
                least_loaded = min(members, key=lambda member: (loads[member], member))
                if loads[chosen] > loads[least_loaded] * OVERLOAD_RATIO:
                    chosen = least_loaded
                    guard_overrides += 1

        effort = float(task["task_effort_estimate"])
        assignments.append({"task": task, "member": chosen, "effort": effort})
        loads[chosen] += effort

    moves = rebalance(assignments, loads) if policy == "hybrid" else 0
    final_scores = list(
        model_probabilities(
            model,
            [
                (str(index), item["task"], profiles[item["member"]], loads[item["member"]])
                for index, item in enumerate(assignments)
            ],
        ).values()
    )
    metrics = balance_metrics(loads)
    return {
        **metrics,
        "mean_final_pair_score_pct": float(np.mean(final_scores) * 100),
        "guard_overrides": guard_overrides,
        "rebalance_moves": moves,
    }


def historical_profiles(member_stats: pd.DataFrame, rng) -> dict[str, dict]:
    indexes = rng.choice(len(member_stats), size=TEAM_SIZE, replace=False)
    profiles = {}
    for number, index in enumerate(indexes, 1):
        row = member_stats.iloc[int(index)]
        average = float(row["member_avg_effort"])
        profiles[f"M{number}"] = {
            "member_completion_rate": float(row["member_completion_rate"]),
            "member_avg_effort": average,
            # Stored training statistic is an open-task count. Convert it to
            # hours, then the operational feature builder converts it back.
            "open_hours": float(row["member_current_workload"]) * average,
        }
    return profiles


def cold_start_profiles() -> dict[str, dict]:
    return {
        f"M{number}": {
            "member_completion_rate": 0.75,
            "member_avg_effort": 40.0,
            "open_hours": 0.0,
        }
        for number in range(1, TEAM_SIZE + 1)
    }


def run() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    bundle = joblib.load(MODEL_PATH)
    model = bundle["model"]
    held_out = load_held_out_tasks()
    member_stats = bundle["member_stats"].reset_index(drop=True)
    rng = np.random.default_rng(RANDOM_SEED)
    policies = ("random", "lpt", "model_only", "hybrid")
    records = []

    for scenario in ("historical_profiles", "cold_start"):
        for trial in range(TRIALS):
            indexes = rng.choice(len(held_out), size=TASKS_PER_TRIAL, replace=False)
            tasks = held_out.iloc[indexes][
                ["task_effort_estimate", "task_category", "task_complexity"]
            ].to_dict("records")
            profiles = (
                historical_profiles(member_stats, rng)
                if scenario == "historical_profiles"
                else cold_start_profiles()
            )
            for policy in policies:
                metrics = assign(policy, tasks, profiles, model, rng)
                records.append(
                    {"scenario": scenario, "trial": trial, "policy": policy, **metrics}
                )

    results = pd.DataFrame(records)
    summary_frame = (
        results.groupby(["scenario", "policy"], sort=False)
        .agg(
            cv_mean=("cv_percent", "mean"),
            cv_std=("cv_percent", "std"),
            spread_mean=("spread_hours", "mean"),
            overload_rate=("overloaded", "mean"),
            pair_score_mean=("mean_final_pair_score_pct", "mean"),
            guard_overrides_mean=("guard_overrides", "mean"),
            rebalance_moves_mean=("rebalance_moves", "mean"),
        )
        .reset_index()
    )
    summary_frame["overload_rate"] *= 100
    numeric = summary_frame.select_dtypes(include=[np.number]).columns
    summary_frame[numeric] = summary_frame[numeric].round(2)
    paired_cv = []
    for scenario, scenario_results in results.groupby("scenario", sort=False):
        by_trial = scenario_results.pivot(index="trial", columns="policy", values="cv_percent")
        delta = by_trial["hybrid"] - by_trial["lpt"]
        paired_cv.append({
            "scenario": scenario,
            "hybrid_minus_lpt_mean_cv_points": round(float(delta.mean()), 2),
            "hybrid_minus_lpt_median_cv_points": round(float(delta.median()), 2),
            "observed_delta_2_5th_percentile": round(float(delta.quantile(0.025)), 2),
            "observed_delta_97_5th_percentile": round(float(delta.quantile(0.975)), 2),
        })
    summary = {
        "seed": RANDOM_SEED,
        "trials_per_scenario": TRIALS,
        "tasks_per_trial": TASKS_PER_TRIAL,
        "team_size": TEAM_SIZE,
        "held_out_task_rows": len(held_out),
        "member_profiles": len(member_stats),
        "paired_cv_comparison": paired_cv,
        "interpretation": "Observed paired trial differences are descriptive, not independent-team confidence intervals or evidence of student outcomes.",
        "results": summary_frame.to_dict("records"),
    }
    return summary_frame, summary, results


if __name__ == "__main__":
    frame, summary_data, trial_data = run()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False)
    trial_data.to_csv(OUTPUT_TRIAL_CSV, index=False)
    OUTPUT_JSON.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(frame.to_string(index=False))
    print(f"\nSaved: {OUTPUT_CSV}")
    print(f"Saved: {OUTPUT_TRIAL_CSV}")
    print(f"Saved: {OUTPUT_JSON}")
