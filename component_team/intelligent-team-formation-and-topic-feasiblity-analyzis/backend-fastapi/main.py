from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from deap import base, creator, tools, algorithms
import pandas as pd
import os
import random
import joblib
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict 

app = FastAPI(
    title="Intelligent Project Management ML API",
    description="Microservice for Team Formation and Topic Feasibility",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NEW: GLOBAL MEMORY POOL FOR LIVE STUDENTS ---
# This holds students created via the NLP form so the Optimizer can draft them!
custom_students_pool = []

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
# 2. Load the Trained ML Models into Memory
# ---------------------------------------------------------
MODELS_DIR = "./models"
MODEL_PATH = os.path.join(MODELS_DIR, "feasibility_model.pkl")

try:
    feasibility_model = joblib.load(MODEL_PATH)
    print("🧠 Predictive Feasibility Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load ML model: {e}")
    feasibility_model = None

try:
    sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("🧠 SBERT Semantic NLP Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load SBERT model: {e}")
    sbert_model = None

# ---------------------------------------------------------
# 2.5 DEAP Genetic Algorithm Blueprint (NSGA-II)
# ---------------------------------------------------------
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

class TeamFormationRequest(BaseModel):
    max_team_size: int
    max_groups: int
    total_students: int
    topic_requirements: Dict[str, int] 

class NLPProfileRequest(BaseModel):
    studentId: str
    gender: str
    religion: str
    livingCity: str
    projectHistory: str

# ---------------------------------------------------------
# 4. API Endpoints
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {"message": "Intelligent Team Formation ML Engine is Online 🚀"}

@app.post("/api/ml/feasibility-score")
def calculate_feasibility(data: FeasibilityRequest):
    if feasibility_model is None:
        raise HTTPException(status_code=500, detail="ML Model not loaded on server.")

    input_vector = [[
        data.Hours_Studied, data.Attendance, data.Previous_Scores, data.Motivation_Level,
        data.Skill_React, data.Skill_NodeJS, data.Skill_Python, data.Skill_MongoDB
    ]]
    predicted_score = float(feasibility_model.predict(input_vector)[0])
    feasibility_percentage = min(max((predicted_score / 100) * 100, 0), 100)

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
    if df_students is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")

    max_allowed_students = data.max_groups * data.max_team_size
    effective_total = min(data.total_students, max_allowed_students)

    if effective_total > len(df_students):
         raise HTTPException(status_code=400, detail="Requested more students than available in database.")

    # --- NEW: POOL GENERATION STRATEGY ---
    # 1. Grab all custom students submitted via the NLP form FIRST
    pool = []
    for cs in custom_students_pool:
        if len(pool) < effective_total:
            pool.append(cs.copy())
            
    # 2. Fill the remaining spots with random students from the CSV dataset
    remaining_slots = effective_total - len(pool)
    if remaining_slots > 0:
        csv_sample = df_students.sample(remaining_slots).to_dict('records')
        pool.extend(csv_sample)
    # -------------------------------------

    reqs = data.topic_requirements

    mock_genders = ["Male", "Female", "Non-binary"]
    mock_religions = ["Buddhism", "Hinduism", "Islam", "Christianity", "Other"]
    mock_cities = ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo"]

    for i, student in enumerate(pool):
        # Only assign a random ID if they don't already have one from the NLP form!
        if 'student_id' not in student:
            student['student_id'] = f"STU-{random.randint(1000,9999)}"
            
        student['power_score'] = (student.get('Previous_Scores', 75) / 100) + (student.get('Attendance', 80) / 100)
        student['pool_idx'] = i 
        
        if 'gender' not in student:
            student['gender'] = random.choice(mock_genders)
        if 'religion' not in student:
            student['religion'] = random.choice(mock_religions)
        if 'livingCity' not in student:
            student['livingCity'] = random.choice(mock_cities)
        
        for tech in reqs.keys():
            col_name = f"Skill_{tech}"
            if col_name not in student:
                student[col_name] = random.randint(1, 5)

    num_teams = max(1, effective_total // data.max_team_size)

    def calculate_simpsons_diversity(team_members):
        if not team_members:
            return 0.0
        N = len(team_members)
        composite_counts = {}
        for m in team_members:
            signature = f"{m.get('gender')}-{m.get('religion')}-{m.get('livingCity')}"
            composite_counts[signature] = composite_counts.get(signature, 0) + 1
        
        sum_of_squares = sum((n / N) ** 2 for n in composite_counts.values())
        return 1.0 - sum_of_squares

    def evaluate_teams(individual):
        teams = [individual[i:i + data.max_team_size] for i in range(0, len(individual), data.max_team_size)]
        
        total_deficit = 0
        total_redundancy = 0
        team_powers = []
        team_diversities = [] 

        for team_indices in teams:
            team_members = [pool[idx] for idx in team_indices]
            
            for tech, req_score in reqs.items():
                col_name = f"Skill_{tech}"
                team_avg_skill = sum(m[col_name] for m in team_members) / len(team_members)
                
                total_deficit += max(0, req_score - team_avg_skill)
                total_redundancy += max(0, team_avg_skill - req_score)
            
            avg_power = sum(m['power_score'] for m in team_members) / len(team_members)
            team_powers.append(avg_power)
            team_diversities.append(calculate_simpsons_diversity(team_members))

        power_imbalance = np.var(team_powers) * 100 
        avg_class_diversity = sum(team_diversities) / len(team_diversities) if team_diversities else 0.0

        return (total_deficit, total_redundancy, power_imbalance, avg_class_diversity)

    toolbox = base.Toolbox()
    toolbox.register("indices", random.sample, range(effective_total), effective_total)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.indices)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    
    toolbox.register("evaluate", evaluate_teams)
    toolbox.register("mate", tools.cxPartialyMatched)
    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.1)
    toolbox.register("select", tools.selNSGA2) 

    pop = toolbox.population(n=50) 
    algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=30, verbose=False)

    best_ind = tools.selBest(pop, 1)[0]
    final_teams_indices = [best_ind[i:i + data.max_team_size] for i in range(0, len(best_ind), data.max_team_size)]
    formatted_teams = []

    for i, t_indices in enumerate(final_teams_indices):
        members = [pool[idx] for idx in t_indices]
        
        avg_hours = sum(m.get('Hours_Studied', 15) for m in members) / len(members)
        avg_attendance = sum(m.get('Attendance', 80) for m in members) / len(members)
        avg_scores = sum(m.get('Previous_Scores', 75) for m in members) / len(members)
        avg_motivation = sum(m.get('Motivation_Level', 80) for m in members) / len(members)
        
        avg_react = sum(m.get('Skill_React', 1) for m in members) / len(members)
        avg_node = sum(m.get('Skill_NodeJS', 1) for m in members) / len(members)
        avg_python = sum(m.get('Skill_Python', 1) for m in members) / len(members)
        avg_mongo = sum(m.get('Skill_MongoDB', 1) for m in members) / len(members)
        
        team_vector = [[avg_hours, avg_attendance, avg_scores, avg_motivation, avg_react, avg_node, avg_python, avg_mongo]]
        
        if feasibility_model is not None:
            predicted_score = float(feasibility_model.predict(team_vector)[0])
            base_feasibility = min(max((predicted_score / 100) * 100, 0), 100)
            
            team_deficit = 0
            for tech, req_score in reqs.items():
                col_name = f"Skill_{tech}"
                team_avg_skill = sum(m.get(col_name, 1) for m in members) / len(members)
                
                if team_avg_skill < req_score:
                    team_deficit += (req_score - team_avg_skill)
            
            penalty_multiplier = 10.0
            total_penalty = team_deficit * penalty_multiplier
            feasibility_percentage = max(base_feasibility - total_penalty, 0.0)
            
            print(f"\n🧠 DIAGNOSTICS FOR TEAM-{i+1}:")
            print(f"  -> Base Score: {base_feasibility:.2f}% | Penalty: -{total_penalty:.2f}% | Final: {feasibility_percentage:.2f}%")
            
            if feasibility_percentage >= 70:
                risk_level = "Low Risk"
            elif feasibility_percentage >= 50:
                risk_level = "Medium Risk"
            else:
                risk_level = "High Risk"
        else:
            feasibility_percentage = 0.0
            risk_level = "Model Error"
            
        dynamic_tech_scores = {}
        for tech in reqs.keys():
            col_name = f"Skill_{tech}"
            dynamic_tech_scores[tech] = sum(m.get(col_name, 1) for m in members)
        
        formatted_teams.append({
            "team_id": f"Team-{i+1}",
            "members": [{
                "student_id": m['student_id'],
                "power_score": round(m['power_score'], 2),
                "demographics": f"{m.get('gender')} • {m.get('religion')} • {m.get('livingCity')}"
            } for m in members],
            "stats": {
                "avg_power": round(sum(m['power_score'] for m in members) / len(members), 2),
                "diversity_score": round(calculate_simpsons_diversity(members), 2),
                "dynamic_tech_scores": dynamic_tech_scores, 
                "feasibility_score": round(feasibility_percentage, 2),
                "risk_level": risk_level
            }
        })

    return {
        "algorithm": "NSGA-II + XGBoost Pipeline",
        "total_teams_formed": num_teams,
        "teams": formatted_teams
    }

@app.post("/api/ml/extract-skills")
def extract_skills_from_text(data: NLPProfileRequest):
    if sbert_model is None:
        raise HTTPException(status_code=500, detail="SBERT Model not loaded.")

    target_skills = [
        "React", "HTML/CSS", "Angular", "Vue", 
        "NodeJS", "Express", "Java", "PHP", "FastAPI",
        "MongoDB", "MySQL", "PostgreSQL", "Firebase",
        "Python", "TensorFlow", "Pandas"
    ]
    
    history_embedding = sbert_model.encode([data.projectHistory])
    
    extracted_vector = {}
    raw_scores = {}
    
    for skill in target_skills:
        skill_embedding = sbert_model.encode([skill])
        similarity = cosine_similarity(history_embedding, skill_embedding)[0][0]
        raw_scores[skill] = float(similarity)
        
        if similarity >= 0.40:
            score = 5
        elif similarity >= 0.28:
            score = 4
        elif similarity >= 0.18:
            score = 3
        elif similarity >= 0.12:
            score = 2
        else:
            score = 1
            
        extracted_vector[f"Skill_{skill}"] = score

    # --- NEW: SAVE TO GLOBAL MEMORY POOL ---
    # Create a new student object using the UI data and SBERT skills
    new_student = {
        "student_id": data.studentId,
        "gender": data.gender,
        "religion": data.religion,
        "livingCity": data.livingCity,
        # Give them strong academic baseline stats for the XGBoost model
        "Hours_Studied": 20.0,
        "Attendance": 90.0,
        "Previous_Scores": 85.0,
        "Motivation_Level": 88.0
    }
    # Merge the extracted skills into this student's profile
    for skill_name, val in extracted_vector.items():
        new_student[skill_name] = val
        
    custom_students_pool.append(new_student)
    print(f"\n✅ SUCCESS: Added {data.studentId} to the live drafting pool!")
    # ---------------------------------------

    return {
        "student_id": data.studentId,
        "gender": data.gender,
        "religion": data.religion,
        "livingCity": data.livingCity,
        "extracted_skills": extracted_vector,
        "raw_similarity_scores": raw_scores,
        "message": "NLP Vector Extraction Complete"
    }