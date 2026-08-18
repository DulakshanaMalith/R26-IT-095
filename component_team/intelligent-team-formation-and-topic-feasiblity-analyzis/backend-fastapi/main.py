from asyncio import streams
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Literal
import numpy as np
from deap import base, creator, tools
import pandas as pd
import os, random, joblib
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from skill_catalog import SKILL_KEYS, get_skill_column
from app.routes.cohort_routes import router as cohort_router

app = FastAPI(title="Intelligent Project Management ML API", description="Microservice for Team Formation and Topic Feasibility", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(cohort_router)

custom_students_pool = []

PROCESSED_DIR = "./data/processed"
FACTORS_PATH = os.path.join(PROCESSED_DIR, "cleaned_student_factors.csv")
try:
    df_students = pd.read_csv(FACTORS_PATH)
    print(f"✅ Data loaded successfully! Database contains {len(df_students)} student profiles.")
except Exception as e:
    print(f"❌ Error loading data: {e}. Make sure you ran preprocess.py!")
    df_students = None

MODELS_DIR = "./models"
ACADEMIC_MODEL_PATH = os.path.join(MODELS_DIR, "academic_performance_model.pkl")
try:
    academic_model = joblib.load(ACADEMIC_MODEL_PATH)
    print("🧠 XGBoost Academic Performance Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load academic model: {e}")
    academic_model = None

try:
    sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
    print("🧠 SBERT Semantic NLP Model loaded successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not load SBERT model: {e}")
    sbert_model = None

if not hasattr(creator, "FitnessMulti"):
    creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0, -1.0, 1.0))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMulti)

MOTIVATION_ENCODING = {"High": 0, "Low": 1, "Medium": 2}
ACADEMIC_FEATURES = ["Hours_Studied", "Attendance", "Previous_Scores", "Motivation_Level"]

def encode_motivation(value: str) -> int:
    if value not in MOTIVATION_ENCODING:
        raise HTTPException(status_code=400, detail=f"Invalid motivation level: {value}")
    return MOTIVATION_ENCODING[value]

def predict_academic_performance(hours, attendance, previous_scores, motivation):
    if academic_model is None:
        raise HTTPException(status_code=500, detail="Academic XGBoost model not loaded on server.")
    input_frame = pd.DataFrame([{
        "Hours_Studied": float(hours),
        "Attendance": float(attendance),
        "Previous_Scores": float(previous_scores),
        "Motivation_Level": float(motivation)
    }], columns=ACADEMIC_FEATURES)
    score = float(academic_model.predict(input_frame)[0])
    return min(max(score, 0.0), 100.0)

class AcademicPreparednessRequest(BaseModel):
    Hours_Studied: float = Field(ge=0, le=100)
    Attendance: float = Field(ge=0, le=100)
    Previous_Scores: float = Field(ge=0, le=100)
    Motivation_Level: float = Field(ge=0, le=2)

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

@app.get("/")
def read_root():
    return {"message": "Intelligent Team Formation ML Engine is Online 🚀"}

@app.post("/api/ml/academic-preparedness")
@app.post("/api/ml/feasibility-score")
def calculate_academic_preparedness(data: AcademicPreparednessRequest):
    score = predict_academic_performance(data.Hours_Studied, data.Attendance, data.Previous_Scores, data.Motivation_Level)
    level = "High" if score >= 70 else "Moderate" if score >= 50 else "Low"
    return {
        "predicted_exam_score": round(score, 2),
        "academic_preparedness": round(score, 2),
        "academic_preparedness_level": level,
        "model_role": "Academic Performance Indicator",
        "target": "Exam_Score",
        "predicted_score": round(score, 2),
        "feasibility_percentage": round(score, 2),
        "risk_assessment": f"{level} Academic Preparedness",
        "compatibility_note": "feasibility_percentage is temporarily retained for frontend compatibility. This XGBoost output represents academic preparedness, not technical topic feasibility."
    }

@app.post("/api/ml/optimize-teams")
def optimize_team_formation(data: TeamFormationRequest):
    if df_students is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded.")
    if data.max_team_size <= 0:
        raise HTTPException(status_code=400, detail="max_team_size must be greater than zero.")
    if data.max_groups <= 0:
        raise HTTPException(status_code=400, detail="max_groups must be greater than zero.")
    if data.total_students <= 0:
        raise HTTPException(status_code=400, detail="total_students must be greater than zero.")
    if not data.topic_requirements:
        raise HTTPException(status_code=400, detail="At least one topic requirement is required.")

    unknown_skills = [skill for skill in data.topic_requirements if skill not in SKILL_KEYS]
    if unknown_skills:
        raise HTTPException(status_code=400, detail={
            "message": "Topic requirements contain unknown skills.",
            "unknown_skills": unknown_skills,
            "supported_skills": SKILL_KEYS
        })

    invalid_requirements = {skill: score for skill, score in data.topic_requirements.items() if score < 1 or score > 5}
    if invalid_requirements:
        raise HTTPException(status_code=400, detail={
            "message": "Topic requirement values must be between 1 and 5.",
            "invalid_requirements": invalid_requirements
        })

    effective_total = min(data.total_students, data.max_groups * data.max_team_size)

    if effective_total > len(df_students) + len(custom_students_pool):
        raise HTTPException(status_code=400, detail="Requested more students than are currently available.")

    pool = []
    for student in custom_students_pool:
        if len(pool) >= effective_total:
            break
        pool.append(student.copy())

    remaining_slots = effective_total - len(pool)

    if remaining_slots > 0:
        if remaining_slots > len(df_students):
            raise HTTPException(status_code=400, detail="Not enough dataset students are available to fill the requested pool.")
        pool.extend(df_students.sample(remaining_slots).to_dict("records"))

    reqs = data.topic_requirements

    for i, student in enumerate(pool):
        if "student_id" not in student or pd.isna(student["student_id"]):
            student["student_id"] = f"POOL-{i + 1:04d}"

        if "profile_source" not in student or pd.isna(student["profile_source"]):
            student["profile_source"] = "unknown"

        if "gender" not in student and "Gender" in student:
            student["gender"] = student["Gender"]

        if "religion" not in student and "Religion" in student:
            student["religion"] = student["Religion"]

        if "livingCity" not in student and "LivingCity" in student:
            student["livingCity"] = student["LivingCity"]

        missing_demographics = [
            field for field in ["gender", "religion", "livingCity"]
            if field not in student or pd.isna(student[field]) or str(student[field]).strip() == ""
        ]

        if missing_demographics:
            raise HTTPException(status_code=400, detail={
                "message": "Student profile contains missing demographic information.",
                "student_id": student["student_id"],
                "profile_source": student["profile_source"],
                "missing_demographics": missing_demographics,
                "explanation": "The optimizer does not generate random demographic replacement values."
            })

        academic_fields = ["Hours_Studied", "Attendance", "Previous_Scores", "Motivation_Level"]

        missing_academic = [
            field for field in academic_fields
            if field not in student or pd.isna(student[field])
        ]

        if missing_academic:
            raise HTTPException(status_code=400, detail={
                "message": "Student profile contains missing academic information.",
                "student_id": student["student_id"],
                "missing_fields": missing_academic
            })

        for field in academic_fields:
            student[field] = float(student[field])

        student["academic_preparedness"] = predict_academic_performance(
            student["Hours_Studied"],
            student["Attendance"],
            student["Previous_Scores"],
            student["Motivation_Level"]
        )

        student["power_score"] = student["Previous_Scores"] / 100 + student["Attendance"] / 100
        student["pool_idx"] = i

        missing_skills = []

        for tech in SKILL_KEYS:
            col = get_skill_column(tech)

            if col not in student or pd.isna(student[col]):
                missing_skills.append(tech)
                continue

            try:
                value = int(student[col])
            except (TypeError, ValueError):
                missing_skills.append(tech)
                continue

            if not 1 <= value <= 5:
                raise HTTPException(status_code=400, detail={
                    "message": "Student profile contains an invalid technical skill rating.",
                    "student_id": student["student_id"],
                    "skill": tech,
                    "value": student[col],
                    "expected_range": "1-5"
                })

            student[col] = value

        if missing_skills:
            raise HTTPException(status_code=400, detail={
                "message": "Student profile contains missing technical skill values.",
                "student_id": student["student_id"],
                "missing_skills": missing_skills,
                "explanation": "The optimizer does not generate random replacement skill values."
            })

        def calculate_simpsons_diversity(team):
            if not team:
                return 0.0

            attribute_scores = []

            for field in ["gender", "religion", "livingCity"]:
                counts = {}

                for member in team:
                    value = str(member[field]).strip()
                    counts[value] = counts.get(value, 0) + 1

                n = len(team)

                simpson_score = 1.0 - sum(
                    (count / n) ** 2
                    for count in counts.values()
                )

                attribute_scores.append(simpson_score)

            return float(np.mean(attribute_scores))

    def calculate_skill_redundancy(team):
        if len(team) < 2:
            return 0.0

        vectors = [
            np.array([
                float(member[get_skill_column(skill)]) - 1.0
                for skill in SKILL_KEYS
            ], dtype=float)
            for member in team
        ]

        similarities = []

        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                a = vectors[i]
                b = vectors[j]

                norm_a = np.linalg.norm(a)
                norm_b = np.linalg.norm(b)

                if norm_a == 0 or norm_b == 0:
                    similarity = 0.0
                else:
                    similarity = float(
                        np.dot(a, b)
                        / (norm_a * norm_b)
                    )

                similarities.append(similarity)

        return float(np.mean(similarities)) if similarities else 0.0

    def calculate_technical_topic_feasibility(team):
        details = []
        ratios = []

        for tech, required in reqs.items():
            col = get_skill_column(tech)

            team_average = sum(
                member[col]
                for member in team
            ) / len(team)

            coverage_ratio = min(
                1.0,
                team_average / float(required)
            )

            ratios.append(coverage_ratio)

            details.append({
                "skill": tech,
                "required_level": int(required),
                "team_average": round(float(team_average), 3),
                "coverage_ratio": round(float(coverage_ratio), 4),
                "coverage_percent": round(float(coverage_ratio * 100), 2)
            })

        technical_feasibility = (
            float(np.mean(ratios)) * 100
            if ratios
            else 0.0
        )

        return technical_feasibility, details

    def calculate_team_academic_preparedness(team):
        scores = [
            float(member["academic_preparedness"])
            for member in team
        ]

        predictions = [
            {
                "student_id": member["student_id"],
                "predicted_exam_score": round(
                    float(member["academic_preparedness"]),
                    2
                )
            }
            for member in team
        ]

        if not scores:
            return 0.0, 0.0, predictions

        return (
            float(np.mean(scores)),
            float(np.std(scores)),
            predictions
        )

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
        team_academic_scores = []
        team_diversities = []

        for indices in teams:
            team = [
                pool[idx]
                for idx in indices
            ]

            if not team:
                continue

            for tech, required in reqs.items():
                col = get_skill_column(tech)

                team_average = sum(
                    member[col]
                    for member in team
                ) / len(team)

                total_deficit += max(
                    0.0,
                    required - team_average
                )

            total_redundancy += calculate_skill_redundancy(team)

            team_academic_scores.append(
                sum(
                    member["academic_preparedness"]
                    for member in team
                ) / len(team)
            )

            team_diversities.append(
                calculate_simpsons_diversity(team)
            )

        academic_imbalance = (
            float(np.var(team_academic_scores))
            if team_academic_scores
            else 0.0
        )

        diversity = (
            sum(team_diversities) / len(team_diversities)
            if team_diversities
            else 0.0
        )

        return (
            total_deficit,
            total_redundancy,
            academic_imbalance,
            diversity
        )

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
    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.1)
    toolbox.register("select", tools.selNSGA2)

    POPULATION_SIZE = 50
    GENERATIONS = 30
    CROSSOVER_PROBABILITY = 0.5
    MUTATION_PROBABILITY = 0.2
    PARENT_SELECTION_SIZE = 48

    population = toolbox.population(
        n=POPULATION_SIZE
    )

    invalid = [
        individual
        for individual in population
        if not individual.fitness.valid
    ]

    for individual, fitness in zip(
        invalid,
        map(toolbox.evaluate, invalid)
    ):
        individual.fitness.values = fitness

    population = toolbox.select(
        population,
        len(population)
    )

    pareto_front = tools.ParetoFront()
    pareto_front.update(population)

    convergence_history = []

    def save_generation_metrics(generation):
        matrix = np.array([
            individual.fitness.values
            for individual in population
        ], dtype=float)

        convergence_history.append({
            "generation": generation,
            "best_technical_deficit": round(
                float(np.min(matrix[:, 0])),
                4
            ),
            "best_skill_redundancy": round(
                float(np.min(matrix[:, 1])),
                4
            ),
            "best_academic_imbalance": round(
                float(np.min(matrix[:, 2])),
                4
            ),
            "best_diversity": round(
                float(np.max(matrix[:, 3])),
                4
            ),
            "pareto_archive_size": len(pareto_front)
        })

    save_generation_metrics(0)

    for generation in range(1, GENERATIONS + 1):
        offspring = list(
            map(
                toolbox.clone,
                tools.selTournamentDCD(
                    population,
                    PARENT_SELECTION_SIZE
                )
            )
        )

        for child1, child2 in zip(
            offspring[::2],
            offspring[1::2]
        ):
            if random.random() < CROSSOVER_PROBABILITY:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        for mutant in offspring:
            if random.random() < MUTATION_PROBABILITY:
                toolbox.mutate(mutant)

                if mutant.fitness.valid:
                    del mutant.fitness.values

        invalid = [
            individual
            for individual in offspring
            if not individual.fitness.valid
        ]

        for individual, fitness in zip(
            invalid,
            map(toolbox.evaluate, invalid)
        ):
            individual.fitness.values = fitness

        population = toolbox.select(
            population + offspring,
            POPULATION_SIZE
        )

        pareto_front.update(population)
        save_generation_metrics(generation)

    if not pareto_front:
        raise HTTPException(
            status_code=500,
            detail="NSGA-II completed without producing a Pareto solution."
        )

    pareto_solutions = list(pareto_front)

    fitness_matrix = np.array([
        solution.fitness.values
        for solution in pareto_solutions
    ], dtype=float)

    def normalize_min(values):
        minimum = float(np.min(values))
        maximum = float(np.max(values))

        if maximum == minimum:
            return np.zeros_like(
                values,
                dtype=float
            )

        return (
            values - minimum
        ) / (
            maximum - minimum
        )

    def normalize_max(values):
        minimum = float(np.min(values))
        maximum = float(np.max(values))

        if maximum == minimum:
            return np.zeros_like(
                values,
                dtype=float
            )

        return (
            maximum - values
        ) / (
            maximum - minimum
        )

    normalized = [
        normalize_min(fitness_matrix[:, 0]),
        normalize_min(fitness_matrix[:, 1]),
        normalize_min(fitness_matrix[:, 2]),
        normalize_max(fitness_matrix[:, 3])
    ]

    balanced_distances = np.sqrt(
        sum(values ** 2 for values in normalized)
        / 4.0
    )

    recommended_index = int(
        np.argmin(
            balanced_distances
        )
    )

    recommended_solution = pareto_solutions[
        recommended_index
    ]

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

    for team_index, indices in enumerate(
        final_team_indices
    ):
        members = [
            pool[idx]
            for idx in indices
        ]

        if not members:
            continue

        (
            academic_preparedness,
            academic_std,
            academic_predictions
        ) = calculate_team_academic_preparedness(
            members
        )

        (
            technical_feasibility,
            technical_coverage
        ) = calculate_technical_topic_feasibility(
            members
        )

        academic_level = (
            "High"
            if academic_preparedness >= 70
            else "Moderate"
            if academic_preparedness >= 50
            else "Low"
        )

        if technical_feasibility >= 70:
            risk_level = "Low Risk"
            technical_fit = "High"
        elif technical_feasibility >= 50:
            risk_level = "Medium Risk"
            technical_fit = "Moderate"
        else:
            risk_level = "High Risk"
            technical_fit = "Low"

        print(
            f"\n🧠 DIAGNOSTICS FOR "
            f"TEAM-{team_index + 1}:"
        )

        print(
            f"  -> Academic Preparedness: "
            f"{academic_preparedness:.2f}% "
            f"| Technical Topic Feasibility: "
            f"{technical_feasibility:.2f}%"
        )

        dynamic_tech_scores = {
            tech: sum(
                member[
                    get_skill_column(
                        tech
                    )
                ]
                for member in members
            )
            for tech in reqs
        }

        formatted_teams.append({
            "team_id": f"Team-{team_index + 1}",
            "members": [
                {
                    "student_id": member["student_id"],
                    "profile_source": member["profile_source"],
                    "academic_preparedness": round(
                        float(
                            member[
                                "academic_preparedness"
                            ]
                        ),
                        2
                    ),
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
                    calculate_simpsons_diversity(
                        members
                    ),
                    3
                ),
                "skill_redundancy": round(
                    calculate_skill_redundancy(
                        members
                    ),
                    3
                ),
                "dynamic_tech_scores": dynamic_tech_scores,
                "technical_topic_feasibility": round(
                    technical_feasibility,
                    2
                ),
                "technical_fit": technical_fit,
                "technical_coverage": technical_coverage,
                "academic_preparedness": round(
                    academic_preparedness,
                    2
                ),
                "academic_preparedness_level": academic_level,
                "academic_prediction_std": round(
                    academic_std,
                    2
                ),
                "individual_academic_predictions": academic_predictions,
                "feasibility_score": round(
                    technical_feasibility,
                    2
                ),
                "risk_level": risk_level
            }
        })

    pareto_preview = [
        {
            "solution": index + 1,
            "technical_deficit": round(
                float(
                    solution
                    .fitness
                    .values[0]
                ),
                4
            ),
            "skill_redundancy": round(
                float(
                    solution
                    .fitness
                    .values[1]
                ),
                4
            ),
            "academic_imbalance": round(
                float(
                    solution
                    .fitness
                    .values[2]
                ),
                4
            ),
            "diversity": round(
                float(
                    solution
                    .fitness
                    .values[3]
                ),
                4
            )
        }
        for index, solution
        in enumerate(
            pareto_solutions[:10]
        )
    ]

    return {
        "algorithm": "NSGA-II Multi-Objective Team Formation + SBERT + XGBoost Academic Preparedness",
        "total_students_used": effective_total,
        "total_teams_formed": len(formatted_teams),
        "score_interpretation": {
            "academic_preparedness": "Average of individual XGBoost-predicted Exam_Score values using four academic features.",
            "technical_topic_feasibility": "Equal-weight mean of capped team-average skill coverage ratios across the topic's required skills.",
            "overall_combined_feasibility": "Not calculated. Academic preparedness and technical topic feasibility are intentionally reported separately."
        },
        "optimization": {
            "population_size": POPULATION_SIZE,
            "generations": GENERATIONS,
            "crossover_probability": CROSSOVER_PROBABILITY,
            "mutation_probability": MUTATION_PROBABILITY,
            "pareto_front_size": len(pareto_solutions),
            "recommended_selection_method": "Equal-weight normalized distance from the ideal objective point",
            "recommended_objectives": {
                "technical_deficit": round(
                    float(
                        recommended_fitness[0]
                    ),
                    4
                ),
                "skill_redundancy": round(
                    float(
                        recommended_fitness[1]
                    ),
                    4
                ),
                "academic_imbalance": round(
                    float(
                        recommended_fitness[2]
                    ),
                    4
                ),
                "diversity": round(
                    float(
                        recommended_fitness[3]
                    ),
                    4
                ),
                "normalized_ideal_distance": round(
                    float(
                        balanced_distances[
                            recommended_index
                        ]
                    ),
                    4
                )
            },
            "pareto_front_preview": pareto_preview,
            "convergence_history": convergence_history
        },
        "teams": formatted_teams
    }

@app.post("/api/ml/extract-skills")
def extract_skills_from_text(data: NLPProfileRequest):
    if sbert_model is None:
        raise HTTPException(
            status_code=500,
            detail="SBERT Model not loaded."
        )

    history_embedding = sbert_model.encode([
        data.projectHistory
    ])

    extracted_vector = {}
    raw_scores = {}

    for skill in SKILL_KEYS:
        similarity = cosine_similarity(
            history_embedding,
            sbert_model.encode([
                skill
            ])
        )[0][0]

        raw_scores[skill] = float(
            similarity
        )

        score = (
            5 if similarity >= 0.40
            else 4 if similarity >= 0.28
            else 3 if similarity >= 0.18
            else 2 if similarity >= 0.12
            else 1
        )

        extracted_vector[
            get_skill_column(
                skill
            )
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
        "Hours_Studied": float(
            data.Hours_Studied
        ),
        "Attendance": float(
            data.Attendance
        ),
        "Previous_Scores": float(
            data.Previous_Scores
        ),
        "Motivation_Level": encoded_motivation
    }

    new_student.update(
        extracted_vector
    )

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
        f"📚 Academic profile: "
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