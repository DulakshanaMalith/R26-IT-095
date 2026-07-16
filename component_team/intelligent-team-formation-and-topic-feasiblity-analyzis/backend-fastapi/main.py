from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from deap import base, creator, tools, algorithms
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
# 2.5 DEAP Genetic Algorithm Blueprint (NSGA-II)
# ---------------------------------------------------------
# We want to MINIMIZE 3 things: Skill Deficits, Redundancy, Power Imbalance
# We want to MAXIMIZE 1 thing: Cultural Diversity (+1.0)
if not hasattr(creator, "FitnessMulti"):
    creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0, -1.0, 1.0)) 

if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMulti)

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

    # Convert the incoming JSON request into a 2D array for the model
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

    # Ask the AI to predict the score based on its training (converted to standard float)
    predicted_score = float(feasibility_model.predict(input_vector)[0])

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
    NSGA-II Multi-Objective Grouping Algorithm.
    Evolves optimal teams by minimizing skill deficits, minimizing redundancy, balancing power scores, and maximizing diversity.
    """
    if df_students is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")

    if data.total_students > len(df_students):
         raise HTTPException(status_code=400, detail="Requested more students than available.")

    # 1. Grab the student pool and calculate base power scores
    pool = df_students.sample(data.total_students).to_dict('records')
    for i, student in enumerate(pool):
        student['student_id'] = f"STU-{random.randint(1000,9999)}"
        student['power_score'] = (student['Previous_Scores'] / 100) + (student['Attendance'] / 100)
        # Add index to track them during evolution
        student['pool_idx'] = i 

    num_teams = max(1, data.total_students // data.team_size)
    reqs = data.topic_requirements

    # --- NEW: Simpson's Diversity Helper Function ---
    def calculate_simpsons_diversity(team_members):
        if not team_members:
            return 0.0
        N = len(team_members)
        ethnicity_counts = {}
        for m in team_members:
            # Uses .get() to safely fall back to 'Unknown' if the dataset doesn't have the column yet
            eth = m.get('Ethnicity_Group', 'Unknown')
            ethnicity_counts[eth] = ethnicity_counts.get(eth, 0) + 1
        
        sum_of_squares = sum((n / N) ** 2 for n in ethnicity_counts.values())
        return 1.0 - sum_of_squares

    # 2. The Fitness Function (The 4 Objectives)
    def evaluate_teams(individual):
        # Decode the individual (a shuffled list of indices) into teams
        teams = [individual[i:i + data.team_size] for i in range(0, len(individual), data.team_size)]
        
        total_deficit = 0
        total_redundancy = 0
        team_powers = []
        team_diversities = [] # NEW

        for team_indices in teams:
            team_members = [pool[idx] for idx in team_indices]
            
            # Aggregate skills for this specific team
            t_react = sum(m['Skill_React'] for m in team_members)
            t_node = sum(m['Skill_NodeJS'] for m in team_members)
            t_py = sum(m['Skill_Python'] for m in team_members)
            t_mongo = sum(m['Skill_MongoDB'] for m in team_members)
            
            # Objective 1: Minimize Deficit (Are they missing required skills?)
            total_deficit += max(0, reqs.Skill_React - t_react)
            total_deficit += max(0, reqs.Skill_NodeJS - t_node)
            total_deficit += max(0, reqs.Skill_Python - t_py)
            total_deficit += max(0, reqs.Skill_MongoDB - t_mongo)
            
            # Objective 2: Minimize Redundancy (Do they have too many overlapping skills?)
            total_redundancy += max(0, t_react - reqs.Skill_React)
            total_redundancy += max(0, t_node - reqs.Skill_NodeJS)
            total_redundancy += max(0, t_py - reqs.Skill_Python)
            total_redundancy += max(0, t_mongo - reqs.Skill_MongoDB)
            
            # Objective 3: Balance Power (Calculate average power to find variance)
            avg_power = sum(m['power_score'] for m in team_members) / len(team_members)
            team_powers.append(avg_power)

            # Objective 4: Cultural Diversity (Simpson's Index)
            team_diversities.append(calculate_simpsons_diversity(team_members))

        # We want the variance between team powers to be as close to 0 as possible
        power_imbalance = np.var(team_powers) * 100 
        avg_class_diversity = sum(team_diversities) / len(team_diversities) if team_diversities else 0.0

        # RETURN 4 OBJECTIVES 
        return (total_deficit, total_redundancy, power_imbalance, avg_class_diversity)

    # 3. Setup the Evolutionary Toolbox
    toolbox = base.Toolbox()
    # An individual is just a shuffled list of student indices (e.g., [3, 11, 1, 5, ...])
    toolbox.register("indices", random.sample, range(data.total_students), data.total_students)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.indices)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    
    toolbox.register("evaluate", evaluate_teams)
    # Custom mutation: Swap two random students between teams
    toolbox.register("mate", tools.cxPartialyMatched)
    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.1)
    toolbox.register("select", tools.selNSGA2) # <-- The NSGA-II Magic!

    # 4. Run the Evolution!
    pop = toolbox.population(n=50) # Create 50 random class configurations
    algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=30, verbose=False)

    # 5. Extract the absolute best configuration (Pareto Front)
    best_ind = tools.selBest(pop, 1)[0]
    
    # 6. Format the winning DNA back into JSON for React
    final_teams_indices = [best_ind[i:i + data.team_size] for i in range(0, len(best_ind), data.team_size)]
    formatted_teams = []

    for i, t_indices in enumerate(final_teams_indices):
        members = [pool[idx] for idx in t_indices]
        
        formatted_teams.append({
            "team_id": f"Team-{i+1}",
            "members": [{
                "student_id": m['student_id'],
                "power_score": round(m['power_score'], 2),
                "ethnicity": m.get('Ethnicity_Group', 'Unknown'), # Pass back to UI
                "skills": {
                    "React": m['Skill_React'],
                    "NodeJS": m['Skill_NodeJS'],
                    "Python": m['Skill_Python'],
                    "MongoDB": m['Skill_MongoDB']
                }
            } for m in members],
            "stats": {
                "avg_power": round(sum(m['power_score'] for m in members) / len(members), 2),
                "diversity_score": round(calculate_simpsons_diversity(members), 2), # Expose to frontend
                "total_react": sum(m['Skill_React'] for m in members),
                "total_node": sum(m['Skill_NodeJS'] for m in members),
                "total_python": sum(m['Skill_Python'] for m in members),
                "total_mongo": sum(m['Skill_MongoDB'] for m in members)
            }
        })

    return {
        "algorithm": "NSGA-II Genetic Algorithm (4-Objective)",
        "total_teams_formed": num_teams,
        "teams": formatted_teams
    }