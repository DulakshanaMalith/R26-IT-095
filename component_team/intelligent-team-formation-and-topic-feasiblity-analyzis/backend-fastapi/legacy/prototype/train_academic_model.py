import os
import json
import joblib
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, KFold, cross_validate
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

DATA_PATH = "./data/processed/cleaned_student_factors.csv"
MODELS_DIR = "./models"
MODEL_PATH = os.path.join(MODELS_DIR, "academic_performance_model.pkl")
METADATA_PATH = os.path.join(MODELS_DIR, "academic_performance_model_metadata.json")

FEATURES = [
    "Hours_Studied",
    "Attendance",
    "Previous_Scores",
    "Motivation_Level"
]

TARGET = "Exam_Score"

RANDOM_STATE = 42

print("=====================================================")
print("ACADEMIC PERFORMANCE MODEL TRAINING")
print("=====================================================")

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"Dataset not found: {DATA_PATH}. Run preprocess.py first."
    )

df = pd.read_csv(DATA_PATH)

print(f"✅ Dataset loaded: {len(df)} rows")

required_columns = FEATURES + [TARGET]
missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )

working_df = df[required_columns].copy()

# Motivation encoding used by the existing project:
# High = 0
# Low = 1
# Medium = 2
if not pd.api.types.is_numeric_dtype(
    working_df["Motivation_Level"]
):
    motivation_mapping = {
        "High": 0,
        "Low": 1,
        "Medium": 2
    }

    working_df["Motivation_Level"] = (
        working_df["Motivation_Level"]
        .astype(str)
        .str.strip()
        .map(motivation_mapping)
    )

for column in required_columns:
    working_df[column] = pd.to_numeric(
        working_df[column],
        errors="coerce"
    )

before_drop = len(working_df)

working_df = working_df.dropna(
    subset=required_columns
).reset_index(drop=True)

removed_rows = before_drop - len(working_df)

if removed_rows > 0:
    print(
        f"⚠️ Removed {removed_rows} rows containing "
        f"missing/invalid academic values."
    )

if len(working_df) < 50:
    raise ValueError(
        "Not enough valid rows remain for reliable model training."
    )

X = working_df[FEATURES]
y = working_df[TARGET]

print("\nFeatures used:")
for feature in FEATURES:
    print(f"  - {feature}")

print(f"\nTarget: {TARGET}")
print(
    "\nIMPORTANT: Technical skill columns are NOT used "
    "to train this model."
)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE
)

model_params = {
    "objective": "reg:squarederror",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 4,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": RANDOM_STATE,
    "n_jobs": -1
}

model = XGBRegressor(**model_params)

print("\n🧠 Training XGBoost academic model...")

model.fit(
    X_train,
    y_train
)

predictions = model.predict(
    X_test
)

mae = mean_absolute_error(
    y_test,
    predictions
)

rmse = np.sqrt(
    mean_squared_error(
        y_test,
        predictions
    )
)

r2 = r2_score(
    y_test,
    predictions
)

# Simple baseline:
# predict the training-set mean exam score for everyone.
baseline_prediction = np.full(
    len(y_test),
    y_train.mean()
)

baseline_mae = mean_absolute_error(
    y_test,
    baseline_prediction
)

print("\n=====================================================")
print("HOLD-OUT TEST RESULTS")
print("=====================================================")

print(f"Test rows: {len(X_test)}")
print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R²:   {r2:.4f}")
print(f"Mean-prediction baseline MAE: {baseline_mae:.4f}")

if mae < baseline_mae:
    improvement = (
        (baseline_mae - mae)
        / baseline_mae
    ) * 100

    print(
        f"✅ XGBoost improves MAE over the mean baseline "
        f"by {improvement:.2f}%."
    )
else:
    improvement = (
        (baseline_mae - mae)
        / baseline_mae
    ) * 100

    print(
        "⚠️ XGBoost did not outperform the simple "
        "mean-prediction baseline on this split."
    )

print("\n=====================================================")
print("5-FOLD CROSS-VALIDATION")
print("=====================================================")

cv = KFold(
    n_splits=5,
    shuffle=True,
    random_state=RANDOM_STATE
)

cv_model = XGBRegressor(
    **model_params
)

cv_results = cross_validate(
    cv_model,
    X,
    y,
    cv=cv,
    scoring={
        "mae": "neg_mean_absolute_error",
        "r2": "r2"
    },
    n_jobs=1
)

cv_mae_scores = -cv_results["test_mae"]
cv_r2_scores = cv_results["test_r2"]

cv_mae_mean = float(
    np.mean(cv_mae_scores)
)

cv_mae_std = float(
    np.std(cv_mae_scores)
)

cv_r2_mean = float(
    np.mean(cv_r2_scores)
)

cv_r2_std = float(
    np.std(cv_r2_scores)
)

print(
    f"CV MAE: "
    f"{cv_mae_mean:.4f} ± {cv_mae_std:.4f}"
)

print(
    f"CV R²:  "
    f"{cv_r2_mean:.4f} ± {cv_r2_std:.4f}"
)

print("\n=====================================================")
print("FEATURE IMPORTANCE")
print("=====================================================")

feature_importance = sorted(
    zip(
        FEATURES,
        model.feature_importances_
    ),
    key=lambda item: item[1],
    reverse=True
)

feature_importance_dict = {}

for feature, importance in feature_importance:
    feature_importance_dict[feature] = float(
        importance
    )

    print(
        f"{feature}: "
        f"{importance:.4f}"
    )

os.makedirs(
    MODELS_DIR,
    exist_ok=True
)

joblib.dump(
    model,
    MODEL_PATH
)

metadata = {
    "model_type": "XGBRegressor",
    "model_role": "Academic Performance Indicator",
    "target": TARGET,
    "features": FEATURES,
    "technical_skills_used_for_training": False,
    "training_rows": int(
        len(working_df)
    ),
    "train_rows": int(
        len(X_train)
    ),
    "test_rows": int(
        len(X_test)
    ),
    "random_state": RANDOM_STATE,
    "holdout_metrics": {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "baseline_mae": float(
            baseline_mae
        ),
        "mae_improvement_percent": float(
            improvement
        )
    },
    "cross_validation": {
        "folds": 5,
        "mae_mean": cv_mae_mean,
        "mae_std": cv_mae_std,
        "r2_mean": cv_r2_mean,
        "r2_std": cv_r2_std
    },
    "feature_importance": feature_importance_dict,
    "hyperparameters": model_params
}

with open(
    METADATA_PATH,
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        metadata,
        file,
        indent=4
    )

print("\n=====================================================")
print("TRAINING COMPLETE")
print("=====================================================")

print(
    f"✅ Academic model saved to:\n"
    f"   {MODEL_PATH}"
)

print(
    f"✅ Model metadata saved to:\n"
    f"   {METADATA_PATH}"
)

print(
    "\nThe existing feasibility_model.pkl "
    "has NOT been overwritten."
)