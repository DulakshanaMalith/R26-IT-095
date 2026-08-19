import os
import numpy as np
import pandas as pd

from skill_catalog import SKILL_KEYS, get_skill_column

RAW_DIR = "./data/raw"
PROCESSED_DIR = "./data/processed"

os.makedirs(PROCESSED_DIR, exist_ok=True)

print("🚀 Starting Data Preprocessing Pipeline...\n" + "=" * 50)

def get_categorical_columns(dataframe):
    """Return categorical/text columns compatible with newer pandas versions."""
    return dataframe.select_dtypes(include=["object", "string"]).columns

# =========================================================
# 1. STUDENT PERFORMANCE FACTORS
# =========================================================

factors_file = os.path.join(RAW_DIR, "StudentPerformanceFactors.csv")

if os.path.exists(factors_file):
    print("🧹 Cleaning Student Performance Factors...")

    df_factors = pd.read_csv(factors_file)

    # -----------------------------------------------------
    # Missing-value imputation
    # -----------------------------------------------------

    cols_with_na = [
        "Teacher_Quality",
        "Parental_Education_Level",
        "Distance_from_Home"
    ]

    for col in cols_with_na:
        if col in df_factors.columns:
            mode_val = df_factors[col].mode()[0]
            df_factors[col] = df_factors[col].fillna(mode_val)

    student_count = len(df_factors)

    # =====================================================
    # SYNTHETIC PROFILE IDENTIFICATION
    # =====================================================

    df_factors["student_id"] = [
        f"SIM-{i + 1:04d}"
        for i in range(student_count)
    ]

    df_factors["profile_source"] = "synthetic_simulation"

    # =====================================================
    # SYNTHETIC TECHNICAL SKILLS
    # =====================================================
    #
    # IMPORTANT:
    # The source dataset does NOT contain programming skill
    # ratings. These 1-5 values are synthetic and are used
    # only for development, simulation, algorithm testing
    # and scalability experiments.
    # =====================================================

    np.random.seed(42)

    # Preserve Gemini's original four generated sequences.
    original_skills = [
        "React",
        "NodeJS",
        "Python",
        "MongoDB"
    ]

    for skill in original_skills:
        df_factors[get_skill_column(skill)] = np.random.randint(
            1,
            6,
            student_count
        )

    # Add the remaining skills from Skill Taxonomy v1.
    remaining_skills = [
        skill
        for skill in SKILL_KEYS
        if skill not in original_skills
    ]

    for skill in remaining_skills:
        df_factors[get_skill_column(skill)] = np.random.randint(
            1,
            6,
            student_count
        )

    print(
        f"✅ Added synthetic ratings for "
        f"{len(SKILL_KEYS)} technical skills."
    )

    # =====================================================
    # SYNTHETIC DEMOGRAPHIC DATA
    # =====================================================
    #
    # These values are also synthetic.
    #
    # They exist only so the diversity objective can be
    # tested with simulation profiles.
    #
    # The optimizer itself must NOT randomly invent these
    # values during a team-formation run.
    # =====================================================

    genders = [
        "Male",
        "Female",
        "Non-binary"
    ]

    religions = [
        "Buddhism",
        "Hinduism",
        "Islam",
        "Christianity",
        "Other"
    ]

    cities = [
        "Colombo",
        "Kandy",
        "Galle",
        "Jaffna",
        "Negombo"
    ]

    df_factors["Gender"] = np.random.choice(
        genders,
        size=student_count
    )

    df_factors["Religion"] = np.random.choice(
        religions,
        size=student_count
    )

    df_factors["LivingCity"] = np.random.choice(
        cities,
        size=student_count
    )

    print("✅ Added synthetic demographic simulation values.")

    # -----------------------------------------------------
    # Preserve Gemini's previous synthetic diversity group.
    # -----------------------------------------------------

    cultural_groups = [
        "Group A",
        "Group B",
        "Group C",
        "Group D"
    ]

    df_factors["Ethnicity_Group"] = np.random.choice(
        cultural_groups,
        size=student_count
    )

    # =====================================================
    # CATEGORICAL ENCODING
    # =====================================================
    #
    # Keep profile metadata and diversity fields readable.
    # Other source-dataset categorical attributes are
    # encoded as before.
    # =====================================================

    preserve_text_columns = {
        "student_id",
        "profile_source",
        "Gender",
        "Religion",
        "LivingCity",
        "Ethnicity_Group"
    }

    categorical_columns = get_categorical_columns(df_factors)

    for col in categorical_columns:
        if col not in preserve_text_columns:
            df_factors[col] = (
                df_factors[col]
                .astype("category")
                .cat.codes
            )

    # =====================================================
    # SAVE PROCESSED DATASET
    # =====================================================

    factors_output = os.path.join(
        PROCESSED_DIR,
        "cleaned_student_factors.csv"
    )

    df_factors.to_csv(
        factors_output,
        index=False
    )

    print(
        f"✅ Saved cleaned factors data to: "
        f"{factors_output} "
        f"(Shape: {df_factors.shape})"
    )

    # =====================================================
    # VERIFY SKILLS
    # =====================================================

    expected_skill_columns = [
        get_skill_column(skill)
        for skill in SKILL_KEYS
    ]

    missing_skill_columns = [
        column
        for column in expected_skill_columns
        if column not in df_factors.columns
    ]

    if missing_skill_columns:
        print("❌ WARNING: Missing skill columns:")

        for column in missing_skill_columns:
            print(f"   - {column}")
    else:
        print(
            "✅ Verified: All 16 skill columns "
            "exist in the processed dataset."
        )

    # =====================================================
    # VERIFY DEMOGRAPHICS
    # =====================================================

    expected_demographic_columns = [
        "Gender",
        "Religion",
        "LivingCity"
    ]

    missing_demographic_columns = [
        column
        for column in expected_demographic_columns
        if column not in df_factors.columns
    ]

    if missing_demographic_columns:
        print("❌ WARNING: Missing demographic columns:")

        for column in missing_demographic_columns:
            print(f"   - {column}")
    else:
        print(
            "✅ Verified: Synthetic demographic "
            "simulation columns exist."
        )

else:
    print(
        f"⚠️ Student Performance Factors file not found: "
        f"{factors_file}"
    )

# =========================================================
# 2. xAPI EDUCATIONAL DATA
# =========================================================

xapi_file = os.path.join(
    RAW_DIR,
    "xAPI-Edu-Data.csv"
)

if os.path.exists(xapi_file):
    print("\n🧹 Cleaning xAPI Educational Data...")

    df_xapi = pd.read_csv(xapi_file)

    categorical_columns = get_categorical_columns(df_xapi)

    for col in categorical_columns:
        df_xapi[col] = (
            df_xapi[col]
            .astype("category")
            .cat.codes
        )

    xapi_output = os.path.join(
        PROCESSED_DIR,
        "cleaned_xapi_data.csv"
    )

    df_xapi.to_csv(
        xapi_output,
        index=False
    )

    print(
        f"✅ Saved cleaned xAPI data to: "
        f"{xapi_output} "
        f"(Shape: {df_xapi.shape})"
    )

else:
    print(
        f"\n⚠️ xAPI dataset not found: "
        f"{xapi_file}"
    )

# =========================================================
# 3. HIGHER EDUCATION STUDENT DATA
# =========================================================

higher_ed_file = os.path.join(
    RAW_DIR,
    "Higher Education Students Performance Evaluation2.csv"
)

if os.path.exists(higher_ed_file):
    print("\n🧹 Cleaning Higher Education Data...")

    df_higher_ed = pd.read_csv(higher_ed_file)

    categorical_columns = get_categorical_columns(df_higher_ed)

    for col in categorical_columns:
        df_higher_ed[col] = (
            df_higher_ed[col]
            .astype("category")
            .cat.codes
        )

    higher_ed_output = os.path.join(
        PROCESSED_DIR,
        "cleaned_higher_ed_data.csv"
    )

    df_higher_ed.to_csv(
        higher_ed_output,
        index=False
    )

    print(
        f"✅ Saved cleaned Higher Ed data to: "
        f"{higher_ed_output} "
        f"(Shape: {df_higher_ed.shape})"
    )

else:
    print(
        f"\n⚠️ Higher Education dataset not found: "
        f"{higher_ed_file}"
    )

print(
    "\n🎉 Preprocessing Complete! "
    "Data is inside /data/processed and ready for algorithms."
)