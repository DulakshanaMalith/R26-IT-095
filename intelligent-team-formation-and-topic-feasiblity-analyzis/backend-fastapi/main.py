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

# Allow your React frontend to communicate with this API
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
# 3. Define the Request Schemas (Pydantic)
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

class TopicRequirements(BaseModel):
    Skill_React: int
    Skill_NodeJS: int
    Skill_Python: int
    Skill_MongoDB: int

class TeamFormationRequest(BaseModel):
    team_size: int
    total_students: int
    topic_requirements: TopicRequirements

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

    # Determine risk category (Adjusted to 70% threshold)
    if feasibility_percentage >= 70:
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

@app.post("/api/ml/optimize-teams")
def optimize_team_formation(data: TeamFormationRequest):
    """
    Multi-Objective Grouping Algorithm.
    Balances technical skill coverage and academic history to form optimal project teams.
    """
    if df_students is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")

    # 1. Grab a random pool of students to simulate a class registering for this topic
    if data.total_students > len(df_students):
         raise HTTPException(status_code=400, detail="Requested more students than available in database.")
         
    pool = df_students.sample(data.total_students).to_dict('records')
    
    # 2. Calculate a "Power Score" for each student
    for student in pool:
        academic_strength = (student['Previous_Scores'] / 100) + (student['Attendance'] / 100)
        
        tech_match = 0
        if student['Skill_React'] >= data.topic_requirements.Skill_React: tech_match += 1
        if student['Skill_NodeJS'] >= data.topic_requirements.Skill_NodeJS: tech_match += 1
        if student['Skill_Python'] >= data.topic_requirements.Skill_Python: tech_match += 1
        if student['Skill_MongoDB'] >= data.topic_requirements.Skill_MongoDB: tech_match += 1
        
        student['power_score'] = academic_strength + tech_match

    # Sort students from strongest to weakest overall profile
    pool.sort(key=lambda x: x['power_score'], reverse=True)

    # 3. Initialize empty teams
    num_teams = max(1, data.total_students // data.team_size)
    teams = [{"team_id": f"Team-{i+1}", "members": [], "stats": {}} for i in range(num_teams)]

    # 4. Multi-Objective Snake Draft (Distribute talent evenly)
    direction = 1
    team_idx = 0
    
    for student in pool:
        teams[team_idx]['members'].append({
            "student_id": f"STU-{random.randint(1000,9999)}",
            "power_score": round(student['power_score'], 2),
            "skills": {
                "React": student['Skill_React'],
                "NodeJS": student['Skill_NodeJS'],
                "Python": student['Skill_Python'],
                "MongoDB": student['Skill_MongoDB']
            }
        })
        
        team_idx += direction
        if team_idx >= num_teams or team_idx < 0:
            direction *= -1
            team_idx += direction

    # 5. Calculate Aggregate Team Vectors
    for team in teams:
        team['stats'] = {
            "avg_power": round(sum(m['power_score'] for m in team['members']) / len(team['members']), 2),
            "total_react": sum(m['skills']['React'] for m in team['members']),
            "total_node": sum(m['skills']['NodeJS'] for m in team['members']),
            "total_python": sum(m['skills']['Python'] for m in team['members']),
            "total_mongo": sum(m['skills']['MongoDB'] for m in team['members'])
        }

    return {
        "algorithm": "Greedy Vector Balancing",
        "total_teams_formed": num_teams,
        "teams": teams
    }