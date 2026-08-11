from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Literal
import numpy as np
from deap import base, creator, tools
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
    allow_headers=["*"]
)

# Live students created using the SBERT onboarding interface.
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
# DEAP MULTI-OBJECTIVE BLUEPRINT
# =========================================================

if not hasattr(creator, "FitnessMulti"):
    creator.create(
        "FitnessMulti",
        base.Fitness,
        weights=(
            -1.0,  # Technical deficit -> minimize
            -1.0,  # Skill redundancy -> minimize
            -1.0,  # Academic imbalance -> minimize
            1.0    # Diversity -> maximize
        )
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

    predicted_score = float(
        feasibility_model.predict(input_vector)[0]
    )

    feasibility_percentage = min(
        max(predicted_score, 0),
        100
    )

    if feasibility_percentage >= 70:
        risk_level = "Low Risk (Highly Feasible)"
    elif feasibility_percentage >= 50:
        risk_level = "Medium Risk (Feasible with support)"
    else:
        risk_level = "High Risk (Not Recommended)"

    return {
        "predicted_score": round(predicted_score, 2),
        "feasibility_percentage": round(
            feasibility_percentage,
            2
        ),
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

    if not data.topic_requirements:
        raise HTTPException(
            status_code=400,
            detail="At least one topic requirement is required."
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

    invalid_requirements = {
        skill: score
        for skill, score in data.topic_requirements.items()
        if score < 1 or score > 5
    }

    if invalid_requirements:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Topic requirement values must be between 1 and 5.",
                "invalid_requirements": invalid_requirements
            }
        )

    max_allowed_students = (
        data.max_groups * data.max_team_size
    )

    effective_total = min(
        data.total_students,
        max_allowed_students
    )

    total_available_students = (
        len(df_students) +
        len(custom_students_pool)
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

    # Prioritize students created through SBERT onboarding.
    for custom_student in custom_students_pool:
        if len(pool) >= effective_total:
            break

        pool.append(
            custom_student.copy()
        )

    remaining_slots = (
        effective_total -
        len(pool)
    )

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
    # PREPARE AND VALIDATE STUDENT PROFILES
    # =====================================================

    for i, student in enumerate(pool):
        if (
            "student_id" not in student
            or pd.isna(student["student_id"])
        ):
            student["student_id"] = f"POOL-{i + 1:04d}"

        if (
            "profile_source" not in student
            or pd.isna(student["profile_source"])
        ):
            student["profile_source"] = "unknown"

        # Synthetic dataset uses capitalized column names.
        if "gender" not in student and "Gender" in student:
            student["gender"] = student["Gender"]

        if "religion" not in student and "Religion" in student:
            student["religion"] = student["Religion"]

        if "livingCity" not in student and "LivingCity" in student:
            student["livingCity"] = student["LivingCity"]

        # -------------------------------------------------
        # Demographic validation
        # -------------------------------------------------

        missing_demographics = []

        for field in [
            "gender",
            "religion",
            "livingCity"
        ]:
            if field not in student:
                missing_demographics.append(field)
                continue

            value = student[field]

            if (
                pd.isna(value)
                or str(value).strip() == ""
            ):
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
        # Academic validation
        # -------------------------------------------------

        required_academic_fields = [
            "Hours_Studied",
            "Attendance",
            "Previous_Scores",
            "Motivation_Level"
        ]

        missing_academic_fields = []

        for field in required_academic_fields:
            if (
                field not in student
                or pd.isna(student[field])
            ):
                missing_academic_fields.append(field)

        if missing_academic_fields:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Student profile contains missing "
                        "academic information."
                    ),
                    "student_id": student["student_id"],
                    "missing_fields": missing_academic_fields
                }
            )

        student["power_score"] = (
            float(student["Previous_Scores"]) / 100
        ) + (
            float(student["Attendance"]) / 100
        )

        student["pool_idx"] = i

        # -------------------------------------------------
        # Validate ALL 16 skills.
        #
        # Redundancy calculation uses the complete skill
        # profile, not only skills requested by the topic.
        # -------------------------------------------------

        missing_skills = []

        for tech in SKILL_KEYS:
            col_name = get_skill_column(tech)

            if (
                col_name not in student
                or pd.isna(student[col_name])
            ):
                missing_skills.append(tech)
                continue

            try:
                skill_value = int(
                    student[col_name]
                )
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
                composite_counts.get(
                    signature,
                    0
                ) + 1
            )

        sum_of_squares = sum(
            (count / total_members) ** 2
            for count in composite_counts.values()
        )

        return 1.0 - sum_of_squares

    # =====================================================
    # SKILL REDUNDANCY
    # =====================================================

    def calculate_skill_redundancy(team_members):
        """
        Calculate average pairwise similarity between
        student skill profiles.

        0.0 = highly different/complementary profiles.
        1.0 = highly similar/redundant profiles.
        """

        if len(team_members) < 2:
            return 0.0

        skill_vectors = []

        for member in team_members:
            vector = np.array(
                [
                    float(
                        member[
                            get_skill_column(skill)
                        ]
                    ) - 1.0
                    for skill in SKILL_KEYS
                ],
                dtype=float
            )

            skill_vectors.append(vector)

        similarities = []

        for i in range(len(skill_vectors)):
            for j in range(
                i + 1,
                len(skill_vectors)
            ):
                vector_a = skill_vectors[i]
                vector_b = skill_vectors[j]

                norm_a = np.linalg.norm(
                    vector_a
                )

                norm_b = np.linalg.norm(
                    vector_b
                )

                if norm_a == 0 or norm_b == 0:
                    similarity = 0.0
                else:
                    similarity = float(
                        np.dot(
                            vector_a,
                            vector_b
                        )
                        / (
                            norm_a *
                            norm_b
                        )
                    )

                similarities.append(
                    similarity
                )

        if not similarities:
            return 0.0

        return float(
            np.mean(similarities)
        )

    # =====================================================
    # FITNESS FUNCTION
    # =====================================================

    def evaluate_teams(individual):
        teams = [
            individual[
                i:
                i + data.max_team_size
            ]
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

            # ---------------------------------------------
            # Objective 1:
            # Technical deficit
            # ---------------------------------------------

            for tech, req_score in reqs.items():
                col_name = get_skill_column(
                    tech
                )

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

            # ---------------------------------------------
            # Objective 2:
            # Skill redundancy
            # ---------------------------------------------

            total_redundancy += (
                calculate_skill_redundancy(
                    team_members
                )
            )

            # ---------------------------------------------
            # Objective 3:
            # Academic balance
            # ---------------------------------------------

            avg_power = (
                sum(
                    member["power_score"]
                    for member in team_members
                )
                / len(team_members)
            )

            team_powers.append(
                avg_power
            )

            # ---------------------------------------------
            # Objective 4:
            # Diversity
            # ---------------------------------------------

            team_diversities.append(
                calculate_simpsons_diversity(
                    team_members
                )
            )

        power_imbalance = (
            np.var(team_powers) * 100
            if team_powers
            else 0.0
        )

        avg_class_diversity = (
            sum(team_diversities)
            / len(team_diversities)
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
    # DEAP TOOLBOX
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

    toolbox.register(
        "evaluate",
        evaluate_teams
    )

    toolbox.register(
        "mate",
        tools.cxPartialyMatched
    )

    toolbox.register(
        "mutate",
        tools.mutShuffleIndexes,
        indpb=0.1
    )

    toolbox.register(
        "select",
        tools.selNSGA2
    )

    # =====================================================
    # PROPER NSGA-II PARAMETERS
    # =====================================================

    POPULATION_SIZE = 50
    GENERATIONS = 30
    CROSSOVER_PROBABILITY = 0.5
    MUTATION_PROBABILITY = 0.2

    # selTournamentDCD requires the number selected to be
    # divisible by four when selecting almost the entire
    # population. With population 50, use 48 parents.
    PARENT_SELECTION_SIZE = 48

    # =====================================================
    # INITIAL POPULATION
    # =====================================================

    population = toolbox.population(
        n=POPULATION_SIZE
    )

    invalid_individuals = [
        individual
        for individual in population
        if not individual.fitness.valid
    ]

    fitness_values = map(
        toolbox.evaluate,
        invalid_individuals
    )

    for individual, fitness in zip(
        invalid_individuals,
        fitness_values
    ):
        individual.fitness.values = fitness

    # NSGA-II ranking + initial crowding distance.
    population = toolbox.select(
        population,
        len(population)
    )

    # Persistent non-dominated archive.
    pareto_front = tools.ParetoFront()
    pareto_front.update(population)

    # =====================================================
    # CONVERGENCE HISTORY
    # =====================================================

    convergence_history = []

    def save_generation_metrics(
        generation,
        current_population
    ):
        fitness_matrix = np.array(
            [
                individual.fitness.values
                for individual
                in current_population
            ],
            dtype=float
        )

        convergence_history.append({
            "generation": generation,

            "best_technical_deficit": round(
                float(
                    np.min(
                        fitness_matrix[:, 0]
                    )
                ),
                4
            ),

            "best_skill_redundancy": round(
                float(
                    np.min(
                        fitness_matrix[:, 1]
                    )
                ),
                4
            ),

            "best_academic_imbalance": round(
                float(
                    np.min(
                        fitness_matrix[:, 2]
                    )
                ),
                4
            ),

            "best_diversity": round(
                float(
                    np.max(
                        fitness_matrix[:, 3]
                    )
                ),
                4
            ),

            "pareto_archive_size":
                len(pareto_front)
        })

    save_generation_metrics(
        0,
        population
    )

    # =====================================================
    # PROPER NSGA-II EVOLUTIONARY LOOP
    # =====================================================

    for generation in range(
        1,
        GENERATIONS + 1
    ):
        # -------------------------------------------------
        # Parent selection using dominance and crowding
        # -------------------------------------------------

        offspring = tools.selTournamentDCD(
            population,
            PARENT_SELECTION_SIZE
        )

        offspring = list(
            map(
                toolbox.clone,
                offspring
            )
        )

        # -------------------------------------------------
        # Crossover
        # -------------------------------------------------

        for child1, child2 in zip(
            offspring[::2],
            offspring[1::2]
        ):
            if (
                random.random()
                < CROSSOVER_PROBABILITY
            ):
                toolbox.mate(
                    child1,
                    child2
                )

                del child1.fitness.values
                del child2.fitness.values

        # -------------------------------------------------
        # Mutation
        # -------------------------------------------------

        for mutant in offspring:
            if (
                random.random()
                < MUTATION_PROBABILITY
            ):
                toolbox.mutate(
                    mutant
                )

                if mutant.fitness.valid:
                    del mutant.fitness.values

        # -------------------------------------------------
        # Evaluate newly changed offspring
        # -------------------------------------------------

        invalid_offspring = [
            individual
            for individual in offspring
            if not individual.fitness.valid
        ]

        offspring_fitness = map(
            toolbox.evaluate,
            invalid_offspring
        )

        for individual, fitness in zip(
            invalid_offspring,
            offspring_fitness
        ):
            individual.fitness.values = fitness

        # -------------------------------------------------
        # Environmental selection
        #
        # Parents + offspring compete together.
        # NSGA-II keeps the best non-dominated solutions
        # using crowding distance to preserve diversity.
        # -------------------------------------------------

        population = toolbox.select(
            population + offspring,
            POPULATION_SIZE
        )

        pareto_front.update(
            population
        )

        save_generation_metrics(
            generation,
            population
        )

    # =====================================================
    # SELECT BALANCED SOLUTION FROM PARETO FRONT
    # =====================================================

    if len(pareto_front) == 0:
        raise HTTPException(
            status_code=500,
            detail=(
                "NSGA-II completed without producing "
                "a Pareto solution."
            )
        )

    pareto_solutions = list(
        pareto_front
    )

    pareto_fitness = np.array(
        [
            solution.fitness.values
            for solution
            in pareto_solutions
        ],
        dtype=float
    )

    def normalize_minimization(values):
        min_value = float(
            np.min(values)
        )

        max_value = float(
            np.max(values)
        )

        if max_value == min_value:
            return np.zeros_like(
                values,
                dtype=float
            )

        return (
            values - min_value
        ) / (
            max_value - min_value
        )

    def normalize_maximization(values):
        min_value = float(
            np.min(values)
        )

        max_value = float(
            np.max(values)
        )

        if max_value == min_value:
            return np.zeros_like(
                values,
                dtype=float
            )

        return (
            max_value - values
        ) / (
            max_value - min_value
        )

    normalized_deficit = (
        normalize_minimization(
            pareto_fitness[:, 0]
        )
    )

    normalized_redundancy = (
        normalize_minimization(
            pareto_fitness[:, 1]
        )
    )

    normalized_academic = (
        normalize_minimization(
            pareto_fitness[:, 2]
        )
    )

    normalized_diversity = (
        normalize_maximization(
            pareto_fitness[:, 3]
        )
    )

    # Equal weighting across the four objectives.
    balanced_distances = np.sqrt(
        (
            normalized_deficit ** 2
            + normalized_redundancy ** 2
            + normalized_academic ** 2
            + normalized_diversity ** 2
        ) / 4.0
    )

    recommended_index = int(
        np.argmin(
            balanced_distances
        )
    )

    recommended_solution = (
        pareto_solutions[
            recommended_index
        ]
    )

    recommended_fitness = (
        recommended_solution
        .fitness
        .values
    )

    print(
        f"\n🧬 NSGA-II COMPLETE: "
        f"Pareto archive contains "
        f"{len(pareto_solutions)} solutions."
    )

    print(
        "🎯 Recommended balanced solution -> "
        f"Deficit={recommended_fitness[0]:.4f}, "
        f"Redundancy={recommended_fitness[1]:.4f}, "
        f"Academic Imbalance={recommended_fitness[2]:.4f}, "
        f"Diversity={recommended_fitness[3]:.4f}"
    )

    # =====================================================
    # BUILD FINAL RECOMMENDED TEAMS
    # =====================================================

    final_team_indices = [
        recommended_solution[
            i:
            i + data.max_team_size
        ]
        for i in range(
            0,
            len(recommended_solution),
            data.max_team_size
        )
    ]

    formatted_teams = []

    for team_index, member_indices in enumerate(
        final_team_indices
    ):
        members = [
            pool[idx]
            for idx in member_indices
        ]

        if not members:
            continue

        # =================================================
        # TEAM ACADEMIC VALUES FOR LEGACY XGBOOST MODEL
        # =================================================

        avg_hours = (
            sum(
                float(
                    member["Hours_Studied"]
                )
                for member in members
            )
            / len(members)
        )

        avg_attendance = (
            sum(
                float(
                    member["Attendance"]
                )
                for member in members
            )
            / len(members)
        )

        avg_scores = (
            sum(
                float(
                    member["Previous_Scores"]
                )
                for member in members
            )
            / len(members)
        )

        avg_motivation = (
            sum(
                float(
                    member["Motivation_Level"]
                )
                for member in members
            )
            / len(members)
        )

        avg_react = (
            sum(
                member[
                    get_skill_column(
                        "React"
                    )
                ]
                for member in members
            )
            / len(members)
        )

        avg_node = (
            sum(
                member[
                    get_skill_column(
                        "NodeJS"
                    )
                ]
                for member in members
            )
            / len(members)
        )

        avg_python = (
            sum(
                member[
                    get_skill_column(
                        "Python"
                    )
                ]
                for member in members
            )
            / len(members)
        )

        avg_mongo = (
            sum(
                member[
                    get_skill_column(
                        "MongoDB"
                    )
                ]
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
        # EXISTING XGBOOST + TOPIC PENALTY LOGIC
        # =================================================
        #
        # This remains temporarily unchanged.
        # We will redesign the feasibility methodology
        # separately after the optimizer is stable.
        # =================================================

        if feasibility_model is not None:
            predicted_score = float(
                feasibility_model.predict(
                    team_vector
                )[0]
            )

            base_feasibility = min(
                max(
                    predicted_score,
                    0
                ),
                100
            )

            team_deficit = 0.0

            for tech, req_score in reqs.items():
                col_name = get_skill_column(
                    tech
                )

                team_avg_skill = (
                    sum(
                        member[col_name]
                        for member in members
                    )
                    / len(members)
                )

                if team_avg_skill < req_score:
                    team_deficit += (
                        req_score -
                        team_avg_skill
                    )

            penalty_multiplier = 10.0

            total_penalty = (
                team_deficit *
                penalty_multiplier
            )

            feasibility_percentage = max(
                base_feasibility -
                total_penalty,
                0.0
            )

            print(
                f"\n🧠 DIAGNOSTICS FOR "
                f"TEAM-{team_index + 1}:"
            )

            print(
                f"  -> Base Score: "
                f"{base_feasibility:.2f}% "
                f"| Penalty: "
                f"-{total_penalty:.2f}% "
                f"| Final: "
                f"{feasibility_percentage:.2f}%"
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
        # DYNAMIC TOPIC SKILL SCORES
        # =================================================

        dynamic_tech_scores = {}

        for tech in reqs.keys():
            col_name = get_skill_column(
                tech
            )

            dynamic_tech_scores[tech] = sum(
                member[col_name]
                for member in members
            )

        # =================================================
        # TEAM RESPONSE
        # =================================================

        formatted_teams.append({
            "team_id":
                f"Team-{team_index + 1}",

            "members": [
                {
                    "student_id":
                        member["student_id"],

                    "profile_source":
                        member["profile_source"],

                    "power_score":
                        round(
                            member[
                                "power_score"
                            ],
                            2
                        ),

                    "demographics":
                        (
                            f"{member['gender']} • "
                            f"{member['religion']} • "
                            f"{member['livingCity']}"
                        )
                }
                for member in members
            ],

            "stats": {
                "avg_power":
                    round(
                        sum(
                            member[
                                "power_score"
                            ]
                            for member
                            in members
                        )
                        / len(members),
                        2
                    ),

                "diversity_score":
                    round(
                        calculate_simpsons_diversity(
                            members
                        ),
                        3
                    ),

                "skill_redundancy":
                    round(
                        calculate_skill_redundancy(
                            members
                        ),
                        3
                    ),

                "dynamic_tech_scores":
                    dynamic_tech_scores,

                "feasibility_score":
                    round(
                        feasibility_percentage,
                        2
                    ),

                "risk_level":
                    risk_level
            }
        })

    # =====================================================
    # PARETO FRONT PREVIEW
    # =====================================================

    pareto_preview = []

    for index, solution in enumerate(
        pareto_solutions[:10]
    ):
        fitness = solution.fitness.values

        pareto_preview.append({
            "solution": index + 1,

            "technical_deficit":
                round(
                    float(fitness[0]),
                    4
                ),

            "skill_redundancy":
                round(
                    float(fitness[1]),
                    4
                ),

            "academic_imbalance":
                round(
                    float(fitness[2]),
                    4
                ),

            "diversity":
                round(
                    float(fitness[3]),
                    4
                )
        })

    # =====================================================
    # FINAL API RESPONSE
    # =====================================================

    return {
        "algorithm":
            "NSGA-II Multi-Objective Team Formation + XGBoost Pipeline",

        "total_students_used":
            effective_total,

        "total_teams_formed":
            len(formatted_teams),

        "optimization": {
            "population_size":
                POPULATION_SIZE,

            "generations":
                GENERATIONS,

            "crossover_probability":
                CROSSOVER_PROBABILITY,

            "mutation_probability":
                MUTATION_PROBABILITY,

            "pareto_front_size":
                len(pareto_solutions),

            "recommended_selection_method":
                (
                    "Equal-weight normalized distance "
                    "from the ideal objective point"
                ),

            "recommended_objectives": {
                "technical_deficit":
                    round(
                        float(
                            recommended_fitness[0]
                        ),
                        4
                    ),

                "skill_redundancy":
                    round(
                        float(
                            recommended_fitness[1]
                        ),
                        4
                    ),

                "academic_imbalance":
                    round(
                        float(
                            recommended_fitness[2]
                        ),
                        4
                    ),

                "diversity":
                    round(
                        float(
                            recommended_fitness[3]
                        ),
                        4
                    ),

                "normalized_ideal_distance":
                    round(
                        float(
                            balanced_distances[
                                recommended_index
                            ]
                        ),
                        4
                    )
            },

            "pareto_front_preview":
                pareto_preview,

            "convergence_history":
                convergence_history
        },

        "teams":
            formatted_teams
    }

# =========================================================
# SBERT SKILL EXTRACTION
# =========================================================

@app.post("/api/ml/extract-skills")
def extract_skills_from_text(
    data: NLPProfileRequest
):
    if sbert_model is None:
        raise HTTPException(
            status_code=500,
            detail="SBERT Model not loaded."
        )

    history_embedding = (
        sbert_model.encode(
            [data.projectHistory]
        )
    )

    extracted_vector = {}
    raw_scores = {}

    for skill in SKILL_KEYS:
        skill_embedding = (
            sbert_model.encode(
                [skill]
            )
        )

        similarity = cosine_similarity(
            history_embedding,
            skill_embedding
        )[0][0]

        raw_scores[skill] = float(
            similarity
        )

        # Existing SBERT threshold mapping.
        # These thresholds will be validated later.
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

    encoded_motivation = (
        encode_motivation(
            data.Motivation_Level
        )
    )

    new_student = {
        "student_id":
            data.studentId,

        "profile_source":
            "sbert_live",

        "gender":
            data.gender,

        "religion":
            data.religion,

        "livingCity":
            data.livingCity,

        "Hours_Studied":
            float(
                data.Hours_Studied
            ),

        "Attendance":
            float(
                data.Attendance
            ),

        "Previous_Scores":
            float(
                data.Previous_Scores
            ),

        "Motivation_Level":
            encoded_motivation
    }

    new_student.update(
        extracted_vector
    )

    # If the same student ID is submitted again during
    # testing, update the existing live profile instead of
    # creating multiple copies.
    existing_index = next(
        (
            index
            for index, student
            in enumerate(
                custom_students_pool
            )
            if student.get(
                "student_id"
            ) == data.studentId
        ),
        None
    )

    if existing_index is None:
        custom_students_pool.append(
            new_student
        )
    else:
        custom_students_pool[
            existing_index
        ] = new_student

    print(
        f"\n✅ SUCCESS: Added/updated "
        f"{data.studentId} "
        f"in the live drafting pool!"
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
        "student_id":
            data.studentId,

        "gender":
            data.gender,

        "religion":
            data.religion,

        "livingCity":
            data.livingCity,

        "academic_profile": {
            "Hours_Studied":
                data.Hours_Studied,

            "Attendance":
                data.Attendance,

            "Previous_Scores":
                data.Previous_Scores,

            "Motivation_Level":
                data.Motivation_Level,

            "Motivation_Encoded":
                encoded_motivation
        },

        "extracted_skills":
            extracted_vector,

        "raw_similarity_scores":
            raw_scores,

        "message":
            "NLP Vector Extraction Complete"
    }