from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import os
import random
import joblib

app = FastAPI(
    title="Intelligent Project Management ML API",
    description="Microservice for Team Formation and Topic Feasibility",
    version="1.0.0"
)

# Allow your React frontend to communicate with this API later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change this to your React app's URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# 1. Load the Dataset into Memory
# ---------------------------------------------------------
PROCESSED_DIR = "./data/processed"
FACTORS_PATH = os.path.join(PROCESSED_DIR, "cleaned_student_factors.csv")

try:
    df_students = pd.read_csv(FACTORS_PATH)
    print(f"✅ Data loaded successfully! Database contains {len(df_students)} student profiles.")
except Exception as e:
    print(f"❌ Error loading data: {e}. Make sure you ran preprocess.py!")
    df_students = None

# ---------------------------------------------------------
# 2. Load the Trained ML Model into Memory
# ---------------------------------------------------------
MODELS_DIR = "./models"
MODEL_PATH = os.path.join(MODELS_DIR, "feasibility_model.pkl")

try:
    feasibility_model = joblib.load(MODEL_PATH)
    print("🧠 Predictive Feasibility Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load ML model: {e}")
    feasibility_model = None

# ---------------------------------------------------------
# 3. Define the Request Schema (Pydantic)
# ---------------------------------------------------------
class FeasibilityRequest(BaseModel):
    Hours_Studied: float
    Attendance: float
    Previous_Scores: float
    Motivation_Level: float
    Skill_React: int
    Skill_NodeJS: int
    Skill_Python: int
    Skill_MongoDB: int

# ---------------------------------------------------------
# 4. API Endpoints
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {"message": "Intelligent Team Formation ML Engine is Online 🚀"}

@app.get("/api/ml/vector-profile/random")
def get_random_student_vector():
    """
    Fetches a random student from our cleaned dataset and returns their 'Vector Profile'.
    """
    if df_students is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")

    random_idx = random.randint(0, len(df_students) - 1)
    student_row = df_students.iloc[random_idx]

    tech_skills = {
        "React": int(student_row['Skill_React']),
        "NodeJS": int(student_row['Skill_NodeJS']),
        "Python": int(student_row['Skill_Python']),
        "MongoDB": int(student_row['Skill_MongoDB'])
    }

    academic_vector = {
        "Previous_Scores": float(student_row['Previous_Scores']),
        "Attendance": float(student_row['Attendance']),
        "Hours_Studied": float(student_row['Hours_Studied']),
        "Motivation_Level": float(student_row['Motivation_Level'])
    }

    return {
        "student_id": f"STU-{random_idx}",
        "technical_vector": tech_skills,
        "academic_vector": academic_vector,
        "raw_data": student_row.to_dict()
    }

@app.post("/api/ml/feasibility-score")
def calculate_feasibility(data: FeasibilityRequest):
    """
    Takes a student's vector profile and predicts their project success rate.
    """
    if feasibility_model is None:
        raise HTTPException(status_code=500, detail="ML Model not loaded on server.")

    # Convert the incoming JSON request into a 2D array for the Random Forest model
    input_vector = [[
        data.Hours_Studied,
        data.Attendance,
        data.Previous_Scores,
        data.Motivation_Level,
        data.Skill_React,
        data.Skill_NodeJS,
        data.Skill_Python,
        data.Skill_MongoDB
    ]]

    # Ask the AI to predict the score based on its training
    predicted_score = feasibility_model.predict(input_vector)[0]

    # Convert the raw score into a clean "Feasibility Percentage"
    feasibility_percentage = min(max((predicted_score / 100) * 100, 0), 100)

    # Determine risk category
    if feasibility_percentage >= 75:
        risk_level = "Low Risk (Highly Feasible)"
    elif feasibility_percentage >= 50:
        risk_level = "Medium Risk (Feasible with support)"
    else:
        risk_level = "High Risk (Not Recommended)"

    return {
        "predicted_score": round(predicted_score, 2),
        "feasibility_percentage": round(feasibility_percentage, 2),
        "risk_assessment": risk_level
    }