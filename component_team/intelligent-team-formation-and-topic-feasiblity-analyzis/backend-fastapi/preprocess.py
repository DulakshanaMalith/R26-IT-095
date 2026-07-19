import pandas as pd
import numpy as np
import os

# Define our directories
raw_dir = "./data/raw"
processed_dir = "./data/processed"

# Ensure the processed directory exists before we try to save to it
os.makedirs(processed_dir, exist_ok=True)

print("🚀 Starting Data Preprocessing Pipeline...\n" + "="*50)

# ---------------------------------------------------------
# 1. Process Student Performance Factors (The Big Dataset)
# ---------------------------------------------------------
factors_file = os.path.join(raw_dir, "StudentPerformanceFactors.csv")
if os.path.exists(factors_file):
    print("🧹 Cleaning Student Performance Factors...")
    df_factors = pd.read_csv(factors_file)

    # IMPUTATION: Fill missing values with the Mode (the most frequent answer)
    cols_with_na = ['Teacher_Quality', 'Parental_Education_Level', 'Distance_from_Home']
    for col in cols_with_na:
        mode_val = df_factors[col].mode()[0]
        df_factors[col] = df_factors[col].fillna(mode_val)

    # FEATURE ENGINEERING: Inject Synthetic Technical Skills & Diversity Groups
    # To test team formation, we need to pretend these students know the tech stack.
    # We assign a random skill level from 1 (Novice) to 5 (Expert) for each tech.
    np.random.seed(42) # Ensures the random numbers are the same every time you run it
    df_factors['Skill_React'] = np.random.randint(1, 6, df_factors.shape[0])
    df_factors['Skill_NodeJS'] = np.random.randint(1, 6, df_factors.shape[0])
    df_factors['Skill_Python'] = np.random.randint(1, 6, df_factors.shape[0])
    df_factors['Skill_MongoDB'] = np.random.randint(1, 6, df_factors.shape[0])
    
    # NEW: Inject Synthetic Ethnicity/Cultural Groups for the Simpson's Diversity Index
    cultural_groups = ["Group A", "Group B", "Group C", "Group D"]
    df_factors['Ethnicity_Group'] = np.random.choice(cultural_groups, size=df_factors.shape[0])

    # ENCODING: Convert text columns (like "Low", "High", "Male", "Female") to numbers
    cat_columns = df_factors.select_dtypes(include=['object']).columns
    for col in cat_columns:
        # Skip encoding the Ethnicity_Group so it remains readable as Group A, B, etc.
        if col != 'Ethnicity_Group':
            df_factors[col] = df_factors[col].astype('category').cat.codes

    # Save the math-ready data
    out_path = os.path.join(processed_dir, "cleaned_student_factors.csv")
    df_factors.to_csv(out_path, index=False)
    print(f"✅ Saved cleaned factors data to: {out_path} (Shape: {df_factors.shape})")

# ---------------------------------------------------------
# 2. Process xAPI Educational Data (The Engagement Dataset)
# ---------------------------------------------------------
xapi_file = os.path.join(raw_dir, "xAPI-Edu-Data.csv")
if os.path.exists(xapi_file):
    print("\n🧹 Cleaning xAPI Educational Data...")
    df_xapi = pd.read_csv(xapi_file)

    # ENCODING: This entire dataset is text. We convert it all to numerical codes.
    # For example, Gender 'M' and 'F' will become 0 and 1.
    cat_columns_xapi = df_xapi.select_dtypes(include=['object']).columns
    for col in cat_columns_xapi:
        df_xapi[col] = df_xapi[col].astype('category').cat.codes

    # Save the math-ready data
    out_path_xapi = os.path.join(processed_dir, "cleaned_xapi_data.csv")
    df_xapi.to_csv(out_path_xapi, index=False)
    print(f"✅ Saved cleaned xAPI data to: {out_path_xapi} (Shape: {df_xapi.shape})")

    # ---------------------------------------------------------
# 3. Process Higher Education Data (The Small Dataset)
# ---------------------------------------------------------
higher_ed_file = os.path.join(raw_dir, "Higher Education Students Performance Evaluation2.csv")
if os.path.exists(higher_ed_file):
    print("\n🧹 Cleaning Higher Education Data...")
    df_higher_ed = pd.read_csv(higher_ed_file)

    # ENCODING: Convert text columns (if any) to numbers
    cat_columns_ed = df_higher_ed.select_dtypes(include=['object']).columns
    for col in cat_columns_ed:
        df_higher_ed[col] = df_higher_ed[col].astype('category').cat.codes

    # Save the math-ready data
    out_path_ed = os.path.join(processed_dir, "cleaned_higher_ed_data.csv")
    df_higher_ed.to_csv(out_path_ed, index=False)
    print(f"✅ Saved cleaned Higher Ed data to: {out_path_ed} (Shape: {df_higher_ed.shape})")

print("\n🎉 Preprocessing Complete! Data is inside /data/processed and ready for algorithms.")