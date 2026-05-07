from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import random

app = FastAPI(
    title="Intelligent Project Management ML API",
    description="Microservice for Team Formation and Topic Feasibility",
    version="1.0.0"
)

# Allow your React frontend to communicate with this API later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change this to your React app's URL in production (e.g., http://localhost:5173)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the data into memory when the server starts
PROCESSED_DIR = "./data/processed"
FACTORS_PATH = os.path.join(PROCESSED_DIR, "cleaned_student_factors.csv")

try:
    df_students = pd.read_csv(FACTORS_PATH)
    print(f"✅ Data loaded successfully! Database contains {len(df_students)} student profiles.")
except Exception as e:
    print(f"❌ Error loading data: {e}. Make sure you ran preprocess.py!")
    df_students = None

@app.get("/")
def read_root():
    return {"message": "Intelligent Team Formation ML Engine is Online 🚀"}

@app.get("/api/ml/vector-profile/random")
def get_random_student_vector():
    """
    Fetches a random student from our cleaned dataset and returns their 'Vector Profile'.
    This vector is what the optimization engine will use to group teams.
    """
    if df_students is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")

    # Pick a random row (student)
    random_idx = random.randint(0, len(df_students) - 1)
    student_row = df_students.iloc[random_idx]

    # Separate their technical skills from their general performance
    # (These are the synthetic columns we added in preprocess.py!)
    tech_skills = {
        "React": int(student_row['Skill_React']),
        "NodeJS": int(student_row['Skill_NodeJS']),
        "Python": int(student_row['Skill_Python']),
        "MongoDB": int(student_row['Skill_MongoDB'])
    }

    # Their academic/behavioral vector
    academic_vector = {
        "Previous_Score": float(student_row['Previous_Scores']),
        "Attendance": float(student_row['Attendance']),
        "Hours_Studied": float(student_row['Hours_Studied']),
        "Motivation_Level": float(student_row['Motivation_Level'])
    }

    return {
        "student_id": f"STU-{random_idx}",
        "technical_vector": tech_skills,
        "academic_vector": academic_vector,
        "raw_data": student_row.to_dict() # The raw array of numbers
    }