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

# UPDATE: Schema changed to accept the multi-dimensional demographics
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

@app.get("/api/ml/vector-profile/random")
def get_random_student_vector():
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

    pool = df_students.sample(effective_total).to_dict('records')
    reqs = data.topic_requirements

    # Lists to simulate demographic data if it's missing from the CSV
    mock_genders = ["Male", "Female", "Non-binary"]
    mock_religions = ["Buddhism", "Hinduism", "Islam", "Christianity", "Other"]
    mock_cities = ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo"]

    for i, student in enumerate(pool):
        student['student_id'] = f"STU-{random.randint(1000,9999)}"
        student['power_score'] = (student['Previous_Scores'] / 100) + (student['Attendance'] / 100)
        student['pool_idx'] = i 
        
        # Inject mock demographics for the Simpson's Math
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

    # UPDATE: Multi-dimensional Novelty Diversity Math
    def calculate_simpsons_diversity(team_members):
        if not team_members:
            return 0.0
        N = len(team_members)
        composite_counts = {}
        for m in team_members:
            # Create a composite signature (e.g., "Male-Buddhism-Colombo")
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
                team_total_skill = sum(m[col_name] for m in team_members)
                
                total_deficit += max(0, req_score - team_total_skill)
                total_redundancy += max(0, team_total_skill - req_score)
            
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
        
        avg_hours = sum(m['Hours_Studied'] for m in members) / len(members)
        avg_attendance = sum(m['Attendance'] for m in members) / len(members)
        avg_scores = sum(m['Previous_Scores'] for m in members) / len(members)
        avg_motivation = sum(m['Motivation_Level'] for m in members) / len(members)
        avg_react = sum(m['Skill_React'] for m in members) / len(members)
        avg_node = sum(m['Skill_NodeJS'] for m in members) / len(members)
        avg_python = sum(m['Skill_Python'] for m in members) / len(members)
        avg_mongo = sum(m['Skill_MongoDB'] for m in members) / len(members)
        
        team_vector = [[avg_hours, avg_attendance, avg_scores, avg_motivation, avg_react, avg_node, avg_python, avg_mongo]]
        
        if feasibility_model is not None:
            predicted_score = float(feasibility_model.predict(team_vector)[0])
            feasibility_percentage = min(max((predicted_score / 100) * 100, 0), 100)
            
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
            dynamic_tech_scores[tech] = sum(m[col_name] for m in members)
        
        formatted_teams.append({
            "team_id": f"Team-{i+1}",
            "members": [{
                "student_id": m['student_id'],
                "power_score": round(m['power_score'], 2),
                # UPDATE: Sending the combined demographics string to React
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

# UPDATE: Return the new fields to the UI upon successful extraction
@app.post("/api/ml/extract-skills")
def extract_skills_from_text(data: NLPProfileRequest):
    if sbert_model is None:
        raise HTTPException(status_code=500, detail="SBERT Model not loaded.")

    # UPDATE: Expanded to include all the dynamic UI technologies! and more technologies
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

    return {
        "student_id": data.studentId,
        "gender": data.gender,
        "religion": data.religion,
        "livingCity": data.livingCity,
        "extracted_skills": extracted_vector,
        "raw_similarity_scores": raw_scores,
        "message": "NLP Vector Extraction Complete"
    }