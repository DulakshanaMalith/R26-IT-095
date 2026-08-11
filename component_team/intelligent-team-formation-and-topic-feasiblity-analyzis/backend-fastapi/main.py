from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Literal
import numpy as np
from deap import base, creator, tools, algorithms
import pandas as pd
import os
import random
import joblib
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from skill_catalog import SKILL_KEYS, get_skill_column

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

custom_students_pool = []

# =========================================================
# DATASET
# =========================================================

PROCESSED_DIR = "./data/processed"
FACTORS_PATH = os.path.join(PROCESSED_DIR, "cleaned_student_factors.csv")

try:
    df_students = pd.read_csv(FACTORS_PATH)
    print(
        f"✅ Data loaded successfully! Database contains "
        f"{len(df_students)} student profiles."
    )
except Exception as e:
    print(f"❌ Error loading data: {e}. Make sure you ran preprocess.py!")
    df_students = None

# =========================================================
# MODELS
# =========================================================

MODELS_DIR = "./models"
MODEL_PATH = os.path.join(MODELS_DIR, "feasibility_model.pkl")

try:
    feasibility_model = joblib.load(MODEL_PATH)
    print("🧠 Predictive Feasibility Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load ML model: {e}")
    feasibility_model = None

try:
    sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
    print("🧠 SBERT Semantic NLP Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load SBERT model: {e}")
    sbert_model = None

# =========================================================
# DEAP BLUEPRINT
# =========================================================

if not hasattr(creator, "FitnessMulti"):
    creator.create(
        "FitnessMulti",
        base.Fitness,
        weights=(-1.0, -1.0, -1.0, 1.0)
    )

if not hasattr(creator, "Individual"):
    creator.create(
        "Individual",
        list,
        fitness=creator.FitnessMulti
    )

# =========================================================
# HELPERS
# =========================================================

MOTIVATION_ENCODING = {
    "High": 0,
    "Low": 1,
    "Medium": 2
}

def encode_motivation(value: str) -> int:
    if value not in MOTIVATION_ENCODING:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid motivation level: {value}"
        )
    return MOTIVATION_ENCODING[value]

# =========================================================
# REQUEST SCHEMAS
# =========================================================

class FeasibilityRequest(BaseModel):
    Hours_Studied: float = Field(ge=0, le=100)
    Attendance: float = Field(ge=0, le=100)
    Previous_Scores: float = Field(ge=0, le=100)
    Motivation_Level: float
    Skill_React: int = Field(ge=1, le=5)
    Skill_NodeJS: int = Field(ge=1, le=5)
    Skill_Python: int = Field(ge=1, le=5)
    Skill_MongoDB: int = Field(ge=1, le=5)

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
    Hours_Studied: float = Field(ge=0, le=100)
    Attendance: float = Field(ge=0, le=100)
    Previous_Scores: float = Field(ge=0, le=100)
    Motivation_Level: Literal["Low", "Medium", "High"]
    projectHistory: str

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def read_root():
    return {
        "message": "Intelligent Team Formation ML Engine is Online 🚀"
    }

# =========================================================
# FEASIBILITY ENDPOINT
# =========================================================

@app.post("/api/ml/feasibility-score")
def calculate_feasibility(data: FeasibilityRequest):
    if feasibility_model is None:
        raise HTTPException(
            status_code=500,
            detail="ML Model not loaded on server."
        )

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

    predicted_score = float(feasibility_model.predict(input_vector)[0])
    feasibility_percentage = min(max(predicted_score, 0), 100)

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

# =========================================================
# TEAM OPTIMIZATION
# =========================================================

@app.post("/api/ml/optimize-teams")
def optimize_team_formation(data: TeamFormationRequest):
    if df_students is None:
        raise HTTPException(
            status_code=500,
            detail="Dataset not loaded."
        )

    if data.max_team_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="max_team_size must be greater than zero."
        )

    if data.max_groups <= 0:
        raise HTTPException(
            status_code=400,
            detail="max_groups must be greater than zero."
        )

    if data.total_students <= 0:
        raise HTTPException(
            status_code=400,
            detail="total_students must be greater than zero."
        )

    unknown_skills = [
        skill
        for skill in data.topic_requirements.keys()
        if skill not in SKILL_KEYS
    ]

    if unknown_skills:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Topic requirements contain unknown skills.",
                "unknown_skills": unknown_skills,
                "supported_skills": SKILL_KEYS
            }
        )

    max_allowed_students = data.max_groups * data.max_team_size
    effective_total = min(data.total_students, max_allowed_students)

    total_available_students = (
        len(df_students) + len(custom_students_pool)
    )

    if effective_total > total_available_students:
        raise HTTPException(
            status_code=400,
            detail="Requested more students than are currently available."
        )

    # =====================================================
    # BUILD STUDENT POOL
    # =====================================================

    pool = []

    # Live SBERT students are prioritized first.
    for custom_student in custom_students_pool:
        if len(pool) >= effective_total:
            break
        pool.append(custom_student.copy())

    remaining_slots = effective_total - len(pool)

    if remaining_slots > 0:
        if remaining_slots > len(df_students):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Not enough dataset students are available "
                    "to fill the requested pool."
                )
            )

        csv_sample = (
            df_students
            .sample(remaining_slots)
            .to_dict("records")
        )

        pool.extend(csv_sample)

    reqs = data.topic_requirements

    # =====================================================
    # PREPARE STUDENT PROFILES
    # =====================================================

    for i, student in enumerate(pool):
        # Synthetic profiles now already contain stable IDs.
        # This fallback is only for unexpected legacy rows.
        if "student_id" not in student or pd.isna(student["student_id"]):
            student["student_id"] = f"POOL-{i + 1:04d}"

        if "profile_source" not in student or pd.isna(student["profile_source"]):
            student["profile_source"] = "unknown"

        # -------------------------------------------------
        # Normalize synthetic demographic field names
        # -------------------------------------------------

        if "gender" not in student and "Gender" in student:
            student["gender"] = student["Gender"]

        if "religion" not in student and "Religion" in student:
            student["religion"] = student["Religion"]

        if "livingCity" not in student and "LivingCity" in student:
            student["livingCity"] = student["LivingCity"]

        # -------------------------------------------------
        # Validate demographics
        # -------------------------------------------------
        #
        # The optimizer does NOT invent demographic data.
        # Synthetic simulation profiles already contain
        # synthetic demographics from preprocess.py.
        # Live SBERT students provide their own values.
        # -------------------------------------------------

        missing_demographics = []

        for field in ["gender", "religion", "livingCity"]:
            if field not in student:
                missing_demographics.append(field)
                continue

            value = student[field]

            if pd.isna(value) or str(value).strip() == "":
                missing_demographics.append(field)

        if missing_demographics:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Student profile contains missing "
                        "demographic information."
                    ),
                    "student_id": student["student_id"],
                    "profile_source": student["profile_source"],
                    "missing_demographics": missing_demographics,
                    "explanation": (
                        "The optimizer does not generate "
                        "random demographic replacement values."
                    )
                }
            )

        # -------------------------------------------------
        # Academic power score
        # -------------------------------------------------

        if (
            "Previous_Scores" not in student
            or pd.isna(student["Previous_Scores"])
            or "Attendance" not in student
            or pd.isna(student["Attendance"])
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Student profile contains missing "
                        "academic information."
                    ),
                    "student_id": student["student_id"],
                    "required_fields": [
                        "Previous_Scores",
                        "Attendance"
                    ]
                }
            )

        student["power_score"] = (
            float(student["Previous_Scores"]) / 100
        ) + (
            float(student["Attendance"]) / 100
        )

        student["pool_idx"] = i

        # =================================================
        # TECHNICAL SKILL VALIDATION
        # =================================================

        missing_skills = []

        for tech in reqs.keys():
            col_name = get_skill_column(tech)

            if col_name not in student:
                missing_skills.append(tech)
                continue

            if pd.isna(student[col_name]):
                missing_skills.append(tech)
                continue

            try:
                skill_value = int(student[col_name])
            except (TypeError, ValueError):
                missing_skills.append(tech)
                continue

            if not 1 <= skill_value <= 5:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": (
                            "Student profile contains an invalid "
                            "technical skill rating."
                        ),
                        "student_id": student["student_id"],
                        "skill": tech,
                        "value": student[col_name],
                        "expected_range": "1-5"
                    }
                )

            student[col_name] = skill_value

        if missing_skills:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Student profile contains missing "
                        "technical skill values."
                    ),
                    "student_id": student["student_id"],
                    "missing_skills": missing_skills,
                    "explanation": (
                        "The optimizer does not generate "
                        "random replacement skill values."
                    )
                }
            )

    num_teams = max(
        1,
        int(np.ceil(effective_total / data.max_team_size))
    )

    # =====================================================
    # SIMPSON DIVERSITY
    # =====================================================

    def calculate_simpsons_diversity(team_members):
        if not team_members:
            return 0.0

        total_members = len(team_members)
        composite_counts = {}

        for member in team_members:
            signature = (
                f"{member['gender']}-"
                f"{member['religion']}-"
                f"{member['livingCity']}"
            )

            composite_counts[signature] = (
                composite_counts.get(signature, 0) + 1
            )

        sum_of_squares = sum(
            (count / total_members) ** 2
            for count in composite_counts.values()
        )

        return 1.0 - sum_of_squares

    # =====================================================
    # FITNESS FUNCTION
    # =====================================================

    def evaluate_teams(individual):
        teams = [
            individual[i:i + data.max_team_size]
            for i in range(
                0,
                len(individual),
                data.max_team_size
            )
        ]

        total_deficit = 0.0
        total_redundancy = 0.0
        team_powers = []
        team_diversities = []

        for team_indices in teams:
            team_members = [
                pool[idx]
                for idx in team_indices
            ]

            if not team_members:
                continue

            for tech, req_score in reqs.items():
                col_name = get_skill_column(tech)

                team_avg_skill = (
                    sum(
                        member[col_name]
                        for member in team_members
                    )
                    / len(team_members)
                )

                total_deficit += max(
                    0,
                    req_score - team_avg_skill
                )

                # Existing redundancy objective.
                # This will be redesigned later.
                total_redundancy += max(
                    0,
                    team_avg_skill - req_score
                )

            avg_power = (
                sum(
                    member["power_score"]
                    for member in team_members
                )
                / len(team_members)
            )

            team_powers.append(avg_power)

            team_diversities.append(
                calculate_simpsons_diversity(team_members)
            )

        power_imbalance = (
            np.var(team_powers) * 100
            if team_powers
            else 0.0
        )

        avg_class_diversity = (
            sum(team_diversities) / len(team_diversities)
            if team_diversities
            else 0.0
        )

        return (
            total_deficit,
            total_redundancy,
            power_imbalance,
            avg_class_diversity
        )

    # =====================================================
    # DEAP
    # =====================================================

    toolbox = base.Toolbox()

    toolbox.register(
        "indices",
        random.sample,
        range(effective_total),
        effective_total
    )

    toolbox.register(
        "individual",
        tools.initIterate,
        creator.Individual,
        toolbox.indices
    )

    toolbox.register(
        "population",
        tools.initRepeat,
        list,
        toolbox.individual
    )

    toolbox.register("evaluate", evaluate_teams)
    toolbox.register("mate", tools.cxPartialyMatched)
    toolbox.register(
        "mutate",
        tools.mutShuffleIndexes,
        indpb=0.1
    )
    toolbox.register("select", tools.selNSGA2)

    # =====================================================
    # EXISTING EVOLUTIONARY PROCESS
    # =====================================================
    #
    # We are intentionally preserving Gemini's current
    # eaSimple implementation until the next milestone.
    # =====================================================

    pop = toolbox.population(n=50)

    algorithms.eaSimple(
        pop,
        toolbox,
        cxpb=0.5,
        mutpb=0.2,
        ngen=30,
        verbose=False
    )

    best_individual = tools.selBest(pop, 1)[0]

    # =====================================================
    # BUILD FINAL TEAMS
    # =====================================================

    final_team_indices = [
        best_individual[i:i + data.max_team_size]
        for i in range(
            0,
            len(best_individual),
            data.max_team_size
        )
    ]

    formatted_teams = []

    for team_index, member_indices in enumerate(final_team_indices):
        members = [
            pool[idx]
            for idx in member_indices
        ]

        if not members:
            continue

        avg_hours = (
            sum(
                float(member.get("Hours_Studied", 15))
                for member in members
            )
            / len(members)
        )

        avg_attendance = (
            sum(
                float(member.get("Attendance", 80))
                for member in members
            )
            / len(members)
        )

        avg_scores = (
            sum(
                float(member.get("Previous_Scores", 75))
                for member in members
            )
            / len(members)
        )

        avg_motivation = (
            sum(
                float(member.get("Motivation_Level", 2))
                for member in members
            )
            / len(members)
        )

        avg_react = (
            sum(
                member[get_skill_column("React")]
                for member in members
            )
            / len(members)
        )

        avg_node = (
            sum(
                member[get_skill_column("NodeJS")]
                for member in members
            )
            / len(members)
        )

        avg_python = (
            sum(
                member[get_skill_column("Python")]
                for member in members
            )
            / len(members)
        )

        avg_mongo = (
            sum(
                member[get_skill_column("MongoDB")]
                for member in members
            )
            / len(members)
        )

        team_vector = [[
            avg_hours,
            avg_attendance,
            avg_scores,
            avg_motivation,
            avg_react,
            avg_node,
            avg_python,
            avg_mongo
        ]]

        # =================================================
        # EXISTING XGBOOST FEASIBILITY LOGIC
        # =================================================

        if feasibility_model is not None:
            predicted_score = float(
                feasibility_model.predict(team_vector)[0]
            )

            base_feasibility = min(
                max(predicted_score, 0),
                100
            )

            team_deficit = 0.0

            for tech, req_score in reqs.items():
                col_name = get_skill_column(tech)

                team_avg_skill = (
                    sum(
                        member[col_name]
                        for member in members
                    )
                    / len(members)
                )

                if team_avg_skill < req_score:
                    team_deficit += (
                        req_score - team_avg_skill
                    )

            penalty_multiplier = 10.0
            total_penalty = team_deficit * penalty_multiplier

            feasibility_percentage = max(
                base_feasibility - total_penalty,
                0.0
            )

            print(
                f"\n🧠 DIAGNOSTICS FOR TEAM-{team_index + 1}:"
            )

            print(
                f"  -> Base Score: {base_feasibility:.2f}% "
                f"| Penalty: -{total_penalty:.2f}% "
                f"| Final: {feasibility_percentage:.2f}%"
            )

            if feasibility_percentage >= 70:
                risk_level = "Low Risk"
            elif feasibility_percentage >= 50:
                risk_level = "Medium Risk"
            else:
                risk_level = "High Risk"
        else:
            feasibility_percentage = 0.0
            risk_level = "Model Error"

        # =================================================
        # DYNAMIC TECHNOLOGY SCORES
        # =================================================

        dynamic_tech_scores = {}

        for tech in reqs.keys():
            col_name = get_skill_column(tech)

            dynamic_tech_scores[tech] = sum(
                member[col_name]
                for member in members
            )

        formatted_teams.append({
            "team_id": f"Team-{team_index + 1}",

            "members": [
                {
                    "student_id": member["student_id"],
                    "profile_source": member["profile_source"],
                    "power_score": round(
                        member["power_score"],
                        2
                    ),
                    "demographics": (
                        f"{member['gender']} • "
                        f"{member['religion']} • "
                        f"{member['livingCity']}"
                    )
                }
                for member in members
            ],

            "stats": {
                "avg_power": round(
                    sum(
                        member["power_score"]
                        for member in members
                    ) / len(members),
                    2
                ),

                "diversity_score": round(
                    calculate_simpsons_diversity(members),
                    2
                ),

                "dynamic_tech_scores": dynamic_tech_scores,

                "feasibility_score": round(
                    feasibility_percentage,
                    2
                ),

                "risk_level": risk_level
            }
        })

    return {
        "algorithm": "NSGA-II + XGBoost Pipeline",
        "total_students_used": effective_total,
        "total_teams_formed": len(formatted_teams),
        "teams": formatted_teams
    }

# =========================================================
# SBERT SKILL EXTRACTION
# =========================================================

@app.post("/api/ml/extract-skills")
def extract_skills_from_text(data: NLPProfileRequest):
    if sbert_model is None:
        raise HTTPException(
            status_code=500,
            detail="SBERT Model not loaded."
        )

    history_embedding = sbert_model.encode(
        [data.projectHistory]
    )

    extracted_vector = {}
    raw_scores = {}

    for skill in SKILL_KEYS:
        skill_embedding = sbert_model.encode([skill])

        similarity = cosine_similarity(
            history_embedding,
            skill_embedding
        )[0][0]

        raw_scores[skill] = float(similarity)

        # Existing Gemini thresholds.
        # These will be validated/calibrated later.
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

        extracted_vector[
            get_skill_column(skill)
        ] = score

    encoded_motivation = encode_motivation(
        data.Motivation_Level
    )

    new_student = {
        "student_id": data.studentId,
        "profile_source": "sbert_live",
        "gender": data.gender,
        "religion": data.religion,
        "livingCity": data.livingCity,
        "Hours_Studied": float(data.Hours_Studied),
        "Attendance": float(data.Attendance),
        "Previous_Scores": float(data.Previous_Scores),
        "Motivation_Level": encoded_motivation
    }

    new_student.update(extracted_vector)

    custom_students_pool.append(new_student)

    print(
        f"\n✅ SUCCESS: Added {data.studentId} "
        f"to the live drafting pool!"
    )

    print(
        "📚 Academic profile: "
        f"Hours={data.Hours_Studied}, "
        f"Attendance={data.Attendance}%, "
        f"Previous Score={data.Previous_Scores}%, "
        f"Motivation={data.Motivation_Level} "
        f"(encoded={encoded_motivation})"
    )

    return {
        "student_id": data.studentId,
        "gender": data.gender,
        "religion": data.religion,
        "livingCity": data.livingCity,

        "academic_profile": {
            "Hours_Studied": data.Hours_Studied,
            "Attendance": data.Attendance,
            "Previous_Scores": data.Previous_Scores,
            "Motivation_Level": data.Motivation_Level,
            "Motivation_Encoded": encoded_motivation
        },

        "extracted_skills": extracted_vector,
        "raw_similarity_scores": raw_scores,
        "message": "NLP Vector Extraction Complete"
    }