import os
import time
import random
import joblib
import numpy as np
import pandas as pd
from deap import base, creator, tools
from skill_catalog import SKILL_KEYS, get_skill_column

DATA_PATH = "./data/processed/cleaned_student_factors.csv"
MODEL_PATH = "./models/academic_performance_model.pkl"
RESULTS_DIR = "./results"

TOTAL_STUDENTS = 12
TEAM_SIZE = 4
RUNS = 30

TOPIC_REQUIREMENTS = {
    "React": 4,
    "NodeJS": 3,
    "Python": 2,
    "MongoDB": 4
}

NSGA_POPULATION = 50
NSGA_GENERATIONS = 30
CROSSOVER_PROBABILITY = 0.5
MUTATION_PROBABILITY = 0.2
PARENT_SELECTION_SIZE = 48

ACADEMIC_FEATURES = [
    "Hours_Studied",
    "Attendance",
    "Previous_Scores",
    "Motivation_Level"
]

if not hasattr(creator, "BaselineFitnessMulti"):
    creator.create(
        "BaselineFitnessMulti",
        base.Fitness,
        weights=(-1.0, -1.0, -1.0, 1.0)
    )

if not hasattr(creator, "BaselineIndividual"):
    creator.create(
        "BaselineIndividual",
        list,
        fitness=creator.BaselineFitnessMulti
    )

def predict_academic(model, student):
    frame = pd.DataFrame([{
        "Hours_Studied": float(student["Hours_Studied"]),
        "Attendance": float(student["Attendance"]),
        "Previous_Scores": float(student["Previous_Scores"]),
        "Motivation_Level": float(student["Motivation_Level"])
    }], columns=ACADEMIC_FEATURES)

    score = float(model.predict(frame)[0])
    return min(max(score, 0.0), 100.0)

def prepare_pool(df, model, seed):
    sample = df.sample(
        n=TOTAL_STUDENTS,
        random_state=seed
    ).to_dict("records")

    for index, student in enumerate(sample):
        student["student_id"] = (
            str(student["student_id"])
            if "student_id" in student and not pd.isna(student["student_id"])
            else f"EXP-{seed}-{index + 1:04d}"
        )

        if "gender" not in student and "Gender" in student:
            student["gender"] = student["Gender"]

        if "religion" not in student and "Religion" in student:
            student["religion"] = student["Religion"]

        if "livingCity" not in student and "LivingCity" in student:
            student["livingCity"] = student["LivingCity"]

        for field in ["gender", "religion", "livingCity"]:
            if (
                field not in student
                or pd.isna(student[field])
                or str(student[field]).strip() == ""
            ):
                raise ValueError(
                    f"{student['student_id']} is missing demographic field {field}"
                )

        for field in ACADEMIC_FEATURES:
            if field not in student or pd.isna(student[field]):
                raise ValueError(
                    f"{student['student_id']} is missing academic field {field}"
                )

            student[field] = float(student[field])

        for skill in SKILL_KEYS:
            column = get_skill_column(skill)

            if column not in student or pd.isna(student[column]):
                raise ValueError(
                    f"{student['student_id']} is missing skill {skill}"
                )

            student[column] = int(student[column])

        student["academic_preparedness"] = predict_academic(
            model,
            student
        )

    return sample

def split_teams(permutation):
    return [
        permutation[i:i + TEAM_SIZE]
        for i in range(
            0,
            len(permutation),
            TEAM_SIZE
        )
    ]

def team_technical_deficit(team_indices, pool):
    if not team_indices:
        return float(
            sum(TOPIC_REQUIREMENTS.values())
        )

    team = [
        pool[i]
        for i in team_indices
    ]

    deficit = 0.0

    for skill, required in TOPIC_REQUIREMENTS.items():
        column = get_skill_column(skill)

        average = sum(
            member[column]
            for member in team
        ) / len(team)

        deficit += max(
            0.0,
            required - average
        )

    return float(deficit)

def team_skill_redundancy(team_indices, pool):
    if len(team_indices) < 2:
        return 0.0

    vectors = []

    for idx in team_indices:
        member = pool[idx]

        vectors.append(
            np.array([
                float(
                    member[
                        get_skill_column(skill)
                    ]
                ) - 1.0
                for skill in SKILL_KEYS
            ], dtype=float)
        )

    similarities = []

    for i in range(len(vectors)):
        for j in range(
            i + 1,
            len(vectors)
        ):
            a = vectors[i]
            b = vectors[j]

            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            similarity = (
                0.0
                if norm_a == 0 or norm_b == 0
                else float(
                    np.dot(a, b)
                    / (norm_a * norm_b)
                )
            )

            similarities.append(
                similarity
            )

    return (
        float(np.mean(similarities))
        if similarities
        else 0.0
    )

def team_diversity(team_indices, pool):
    if not team_indices:
        return 0.0

    team = [
        pool[idx]
        for idx in team_indices
    ]

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

def team_technical_feasibility(team_indices, pool):
    if not team_indices:
        return 0.0

    team = [
        pool[i]
        for i in team_indices
    ]

    ratios = []

    for skill, required in TOPIC_REQUIREMENTS.items():
        column = get_skill_column(skill)

        average = sum(
            member[column]
            for member in team
        ) / len(team)

        ratios.append(
            min(
                1.0,
                average / float(required)
            )
        )

    return (
        float(np.mean(ratios) * 100)
        if ratios
        else 0.0
    )

def evaluate_grouping(permutation, pool):
    teams = split_teams(permutation)

    deficits = [
        team_technical_deficit(
            team,
            pool
        )
        for team in teams
    ]

    redundancies = [
        team_skill_redundancy(
            team,
            pool
        )
        for team in teams
    ]

    team_academic = [
        float(
            np.mean([
                pool[idx][
                    "academic_preparedness"
                ]
                for idx in team
            ])
        )
        for team in teams
        if team
    ]

    diversities = [
        team_diversity(
            team,
            pool
        )
        for team in teams
    ]

    technical_feasibilities = [
        team_technical_feasibility(
            team,
            pool
        )
        for team in teams
    ]

    return {
        "technical_deficit":
            float(
                sum(deficits)
            ),

        "skill_redundancy_total":
            float(
                sum(redundancies)
            ),

        "skill_redundancy_avg":
            float(
                np.mean(redundancies)
            ),

        "academic_imbalance":
            float(
                np.var(team_academic)
            )
            if team_academic
            else 0.0,

        "diversity":
            float(
                np.mean(diversities)
            )
            if diversities
            else 0.0,

        "technical_feasibility":
            float(
                np.mean(
                    technical_feasibilities
                )
            )
            if technical_feasibilities
            else 0.0
    }

def random_grouping(pool, seed):
    rng = random.Random(seed)

    permutation = list(
        range(len(pool))
    )

    rng.shuffle(
        permutation
    )

    return permutation

def greedy_grouping(pool):
    team_count = int(
        np.ceil(
            len(pool)
            / TEAM_SIZE
        )
    )

    teams = [
        []
        for _ in range(
            team_count
        )
    ]

    def strength(idx):
        member = pool[idx]

        return sum(
            min(
                1.0,
                member[
                    get_skill_column(
                        skill
                    )
                ]
                / float(required)
            )
            for skill, required
            in TOPIC_REQUIREMENTS.items()
        )

    ordered_students = sorted(
        range(len(pool)),
        key=strength,
        reverse=True
    )

    for student_idx in ordered_students:
        candidates = []

        for team_idx, team in enumerate(
            teams
        ):
            if len(team) >= TEAM_SIZE:
                continue

            before = team_technical_deficit(
                team,
                pool
            )

            after = team_technical_deficit(
                team + [student_idx],
                pool
            )

            improvement = (
                before - after
            )

            academic_sum = sum(
                pool[idx][
                    "academic_preparedness"
                ]
                for idx in team
            )

            candidates.append((
                improvement,
                -len(team),
                -academic_sum,
                -team_idx,
                team_idx
            ))

        if not candidates:
            raise RuntimeError(
                "Greedy algorithm could not place a student."
            )

        chosen_team = max(
            candidates
        )[-1]

        teams[
            chosen_team
        ].append(
            student_idx
        )

    return [
        idx
        for team in teams
        for idx in team
    ]

def select_balanced_pareto(pareto_solutions):
    matrix = np.array(
        [
            solution.fitness.values
            for solution
            in pareto_solutions
        ],
        dtype=float
    )

    def normalize_min(values):
        minimum = float(
            np.min(values)
        )

        maximum = float(
            np.max(values)
        )

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
        minimum = float(
            np.min(values)
        )

        maximum = float(
            np.max(values)
        )

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
        normalize_min(
            matrix[:, 0]
        ),

        normalize_min(
            matrix[:, 1]
        ),

        normalize_min(
            matrix[:, 2]
        ),

        normalize_max(
            matrix[:, 3]
        )
    ]

    distances = np.sqrt(
        sum(
            values ** 2
            for values in normalized
        )
        / 4.0
    )

    return pareto_solutions[
        int(
            np.argmin(
                distances
            )
        )
    ]

def nsga2_grouping(pool, seed):
    random.seed(seed)

    toolbox = base.Toolbox()

    toolbox.register(
        "indices",
        random.sample,
        range(len(pool)),
        len(pool)
    )

    toolbox.register(
        "individual",
        tools.initIterate,
        creator.BaselineIndividual,
        toolbox.indices
    )

    toolbox.register(
        "population",
        tools.initRepeat,
        list,
        toolbox.individual
    )

    def evaluate(individual):
        metrics = evaluate_grouping(
            individual,
            pool
        )

        return (
            metrics[
                "technical_deficit"
            ],

            metrics[
                "skill_redundancy_total"
            ],

            metrics[
                "academic_imbalance"
            ],

            metrics[
                "diversity"
            ]
        )

    toolbox.register(
        "evaluate",
        evaluate
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

    population = toolbox.population(
        n=NSGA_POPULATION
    )

    invalid = [
        individual
        for individual
        in population
        if not individual.fitness.valid
    ]

    for individual, fitness in zip(
        invalid,
        map(
            toolbox.evaluate,
            invalid
        )
    ):
        individual.fitness.values = (
            fitness
        )

    population = toolbox.select(
        population,
        len(population)
    )

    pareto = tools.ParetoFront()

    pareto.update(
        population
    )

    for _ in range(
        NSGA_GENERATIONS
    ):
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

        invalid = [
            individual
            for individual
            in offspring
            if not individual.fitness.valid
        ]

        for individual, fitness in zip(
            invalid,
            map(
                toolbox.evaluate,
                invalid
            )
        ):
            individual.fitness.values = (
                fitness
            )

        population = toolbox.select(
            population + offspring,
            NSGA_POPULATION
        )

        pareto.update(
            population
        )

    solutions = list(
        pareto
    )

    selected = (
        select_balanced_pareto(
            solutions
        )
    )

    return (
        list(selected),
        len(solutions)
    )

def run_method(method, pool, seed):
    start = time.perf_counter()

    pareto_size = None

    if method == "Random":
        grouping = random_grouping(
            pool,
            seed + 10000
        )

    elif method == "Greedy":
        grouping = greedy_grouping(
            pool
        )

    elif method == "NSGA-II":
        grouping, pareto_size = (
            nsga2_grouping(
                pool,
                seed + 20000
            )
        )

    else:
        raise ValueError(
            f"Unknown method: {method}"
        )

    runtime_ms = (
        time.perf_counter()
        - start
    ) * 1000.0

    return {
        **evaluate_grouping(
            grouping,
            pool
        ),

        "runtime_ms":
            runtime_ms,

        "pareto_front_size":
            pareto_size
    }

def main():
    print("=" * 72)
    print("RANDOM vs GREEDY vs NSGA-II BASELINE EXPERIMENT")
    print("=" * 72)

    print(
        f"Runs: {RUNS}"
    )

    print(
        f"Students per run: "
        f"{TOTAL_STUDENTS}"
    )

    print(
        f"Team size: "
        f"{TEAM_SIZE}"
    )

    print(
        f"Topic requirements: "
        f"{TOPIC_REQUIREMENTS}"
    )

    if not os.path.exists(
        DATA_PATH
    ):
        raise FileNotFoundError(
            DATA_PATH
        )

    if not os.path.exists(
        MODEL_PATH
    ):
        raise FileNotFoundError(
            MODEL_PATH
        )

    df = pd.read_csv(
        DATA_PATH
    )

    model = joblib.load(
        MODEL_PATH
    )

    if (
        TOTAL_STUDENTS
        > len(df)
    ):
        raise ValueError(
            "TOTAL_STUDENTS exceeds dataset size."
        )

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    rows = []

    for run in range(
        1,
        RUNS + 1
    ):
        seed = (
            42 + run - 1
        )

        pool = prepare_pool(
            df,
            model,
            seed
        )

        print(
            f"\nRun "
            f"{run}/{RUNS} "
            f"| seed={seed}"
        )

        for method in [
            "Random",
            "Greedy",
            "NSGA-II"
        ]:
            result = run_method(
                method,
                pool,
                seed
            )

            rows.append({
                "run":
                    run,

                "seed":
                    seed,

                "method":
                    method,

                **result
            })

            print(
                f"{method:8s} | "
                f"Deficit="
                f"{result['technical_deficit']:.4f} | "
                f"Redundancy="
                f"{result['skill_redundancy_avg']:.4f} | "
                f"AcademicVar="
                f"{result['academic_imbalance']:.4f} | "
                f"Diversity="
                f"{result['diversity']:.4f} | "
                f"TechFeas="
                f"{result['technical_feasibility']:.2f}% | "
                f"Runtime="
                f"{result['runtime_ms']:.2f}ms"
            )

    runs_df = pd.DataFrame(
        rows
    )

    metric_columns = [
        "technical_deficit",
        "skill_redundancy_avg",
        "academic_imbalance",
        "diversity",
        "technical_feasibility",
        "runtime_ms"
    ]

    summary_rows = []

    for method, group in (
        runs_df.groupby(
            "method",
            sort=False
        )
    ):
        row = {
            "method":
                method
        }

        for metric in (
            metric_columns
        ):
            row[
                f"{metric}_mean"
            ] = float(
                group[
                    metric
                ].mean()
            )

            row[
                f"{metric}_std"
            ] = float(
                group[
                    metric
                ].std(
                    ddof=1
                )
            )

        summary_rows.append(
            row
        )

    summary_df = pd.DataFrame(
        summary_rows
    )

    runs_path = os.path.join(
        RESULTS_DIR,
        "baseline_comparison_runs.csv"
    )

    summary_path = os.path.join(
        RESULTS_DIR,
        "baseline_comparison_summary.csv"
    )

    runs_df.to_csv(
        runs_path,
        index=False
    )

    summary_df.to_csv(
        summary_path,
        index=False
    )

    print(
        "\n"
        + "=" * 72
    )

    print(
        "SUMMARY"
    )

    print(
        "=" * 72
    )

    display_columns = [
        "method",
        "technical_deficit_mean",
        "skill_redundancy_avg_mean",
        "academic_imbalance_mean",
        "diversity_mean",
        "technical_feasibility_mean",
        "runtime_ms_mean"
    ]

    print(
        summary_df[
            display_columns
        ]
        .round(4)
        .to_string(
            index=False
        )
    )

    print(
        f"\n✅ Raw results: "
        f"{runs_path}"
    )

    print(
        f"✅ Summary: "
        f"{summary_path}"
    )

    print(
        "\nFor the final research "
        "experiment, change RUNS = 30 "
        "after this 5-run verification succeeds."
    )

if __name__ == "__main__":
    main()