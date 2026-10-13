import random
from typing import Dict, List, Tuple
from deap import base, creator, tools
from app.models.cohort_import import CohortImportData
from app.services.evaluation_metrics import (
    calculate_front_metrics,
    get_nondominated_points,
)
from app.services.nsga2_optimizer import (
    canonicalize_individual,
    individual_to_assignment,
    mutate_swap_between_teams,
)
from app.services.team_formation_objectives import (
    evaluate_assignment,
)

ObjectivePoint = Tuple[float, float]

def _ensure_weighted_deap_types() -> None:
    if not hasattr(
        creator,
        "FitnessWeightedBaselineV1",
    ):
        creator.create(
            "FitnessWeightedBaselineV1",
            base.Fitness,
            weights=(-1.0,),
        )

    if not hasattr(
        creator,
        "IndividualWeightedBaselineV1",
    ):
        creator.create(
            "IndividualWeightedBaselineV1",
            list,
            fitness=creator.FitnessWeightedBaselineV1,
        )

def _get_project_segments(
    data: CohortImportData,
) -> List[Tuple[int, int]]:
    segments = []
    offset = 0

    for project in data.projects:
        end = offset + project.team_size
        segments.append(
            (offset, end)
        )
        offset = end

    if offset != len(data.students):
        raise ValueError(
            "Project team sizes do not consume "
            "all students."
        )

    return segments

def _evaluate_chromosome(
    data: CohortImportData,
    chromosome: List[int],
) -> Tuple[float, float, Dict]:
    assignment = individual_to_assignment(
        data=data,
        individual=chromosome,
    )

    result = evaluate_assignment(
        data=data,
        assignment=assignment,
    )

    f1 = float(
        result[
            "technical_requirement_deficit"
        ]
    )

    f2 = float(
        result[
            "preference_dissatisfaction"
        ]
    )

    return (
        f1,
        f2,
        assignment,
    )

def _build_front_from_points(
    point_assignments: Dict[
        ObjectivePoint,
        Dict,
    ],
) -> List[Dict]:
    nondominated_points = (
        get_nondominated_points(
            point_assignments.keys()
        )
    )

    return [
        {
            "technical_requirement_deficit": (
                point[0]
            ),
            "preference_dissatisfaction": (
                point[1]
            ),
            "example_assignment": (
                point_assignments[
                    point
                ]
            ),
        }
        for point in nondominated_points
    ]

def run_random_search(
    data: CohortImportData,
    evaluation_budget: int = 16650,
    seed: int = 42,
) -> Dict:
    if evaluation_budget < 1:
        raise ValueError(
            "Evaluation budget must "
            "be at least 1."
        )

    rng = random.Random(
        seed
    )

    student_count = len(
        data.students
    )

    point_assignments: Dict[
        ObjectivePoint,
        Dict,
    ] = {}

    for _ in range(
        evaluation_budget
    ):
        chromosome = rng.sample(
            range(student_count),
            student_count,
        )

        canonicalize_individual(
            data=data,
            individual=chromosome,
        )

        (
            f1,
            f2,
            assignment,
        ) = _evaluate_chromosome(
            data=data,
            chromosome=chromosome,
        )

        point = (
            round(f1, 12),
            round(f2, 12),
        )

        if point not in point_assignments:
            point_assignments[
                point
            ] = assignment

    pareto_front = (
        _build_front_from_points(
            point_assignments
        )
    )

    metrics = (
        calculate_front_metrics(
            pareto_front
        )
    )

    return {
        "algorithm": "Random Search",
        "seed": seed,
        "evaluation_budget": (
            evaluation_budget
        ),
        "evaluations": (
            evaluation_budget
        ),
        "unique_objective_point_count": (
            len(point_assignments)
        ),
        "pareto_point_count": (
            len(pareto_front)
        ),
        "pareto_front": (
            pareto_front
        ),
        "metrics": metrics,
    }

def _evaluate_weighted_individual(
    data: CohortImportData,
    individual,
    weight: float,
) -> None:
    (
        f1,
        f2,
        _,
    ) = _evaluate_chromosome(
        data=data,
        chromosome=individual,
    )

    scalar_objective = (
        weight * f1
        + (1.0 - weight) * f2
    )

    individual.fitness.values = (
        scalar_objective,
    )

    individual.raw_f1 = f1
    individual.raw_f2 = f2

def _run_single_weight_ga(
    data: CohortImportData,
    weight: float,
    evaluation_budget: int,
    population_size: int,
    seed: int,
    crossover_probability: float,
    mutation_probability: float,
) -> Dict:
    if not (
        0.0 <= weight <= 1.0
    ):
        raise ValueError(
            "Weight must be between "
            "0 and 1."
        )

    if evaluation_budget < 4:
        raise ValueError(
            "Each weighted run requires "
            "at least 4 evaluations."
        )

    random.seed(
        seed
    )

    _ensure_weighted_deap_types()

    student_count = len(
        data.students
    )

    segments = (
        _get_project_segments(
            data
        )
    )

    actual_population_size = min(
        population_size,
        evaluation_budget,
    )

    population = []

    for _ in range(
        actual_population_size
    ):
        chromosome = random.sample(
            range(student_count),
            student_count,
        )

        canonicalize_individual(
            data=data,
            individual=chromosome,
        )

        individual = (
            creator
            .IndividualWeightedBaselineV1(
                chromosome
            )
        )

        _evaluate_weighted_individual(
            data=data,
            individual=individual,
            weight=weight,
        )

        population.append(
            individual
        )

    evaluations = len(
        population
    )

    while (
        evaluations
        < evaluation_budget
    ):
        remaining = (
            evaluation_budget
            - evaluations
        )

        offspring = []

        while (
            len(offspring)
            < actual_population_size
            and len(offspring)
            < remaining
        ):
            parents = tools.selTournament(
                population,
                2,
                tournsize=3,
            )

            child1 = (
                creator
                .IndividualWeightedBaselineV1(
                    parents[0]
                )
            )

            child2 = (
                creator
                .IndividualWeightedBaselineV1(
                    parents[1]
                )
            )

            if (
                random.random()
                < crossover_probability
            ):
                tools.cxOrdered(
                    child1,
                    child2,
                )

            if (
                random.random()
                < mutation_probability
            ):
                mutate_swap_between_teams(
                    child1,
                    segments,
                )

            if (
                random.random()
                < mutation_probability
            ):
                mutate_swap_between_teams(
                    child2,
                    segments,
                )

            canonicalize_individual(
                data=data,
                individual=child1,
            )

            canonicalize_individual(
                data=data,
                individual=child2,
            )

            offspring.append(
                child1
            )

            if (
                len(offspring)
                < actual_population_size
                and len(offspring)
                < remaining
            ):
                offspring.append(
                    child2
                )

        for individual in offspring:
            _evaluate_weighted_individual(
                data=data,
                individual=individual,
                weight=weight,
            )

        evaluations += len(
            offspring
        )

        population = tools.selBest(
            population + offspring,
            actual_population_size,
        )

    best = tools.selBest(
        population,
        1,
    )[0]

    best_assignment = (
        individual_to_assignment(
            data=data,
            individual=best,
        )
    )

    return {
        "weight": weight,
        "technical_requirement_deficit": (
            round(
                best.raw_f1,
                12,
            )
        ),
        "preference_dissatisfaction": (
            round(
                best.raw_f2,
                12,
            )
        ),
        "weighted_objective": (
            round(
                best.fitness.values[0],
                12,
            )
        ),
        "evaluations": evaluations,
        "example_assignment": (
            best_assignment
        ),
    }

def run_weighted_single_objective_search(
    data: CohortImportData,
    evaluation_budget: int = 16650,
    weights: List[float] | None = None,
    population_size: int = 120,
    crossover_probability: float = 0.9,
    mutation_probability: float = 0.2,
    seed: int = 42,
) -> Dict:
    if weights is None:
        weights = [
            0.25,
            0.50,
            0.75,
        ]

    if not weights:
        raise ValueError(
            "At least one weight "
            "is required."
        )

    if evaluation_budget < len(
        weights
    ) * 4:
        raise ValueError(
            "Evaluation budget is too "
            "small for the requested "
            "number of weights."
        )

    for weight in weights:
        if not (
            0.0 <= weight <= 1.0
        ):
            raise ValueError(
                "Every weight must be "
                "between 0 and 1."
            )

    base_budget = (
        evaluation_budget
        // len(weights)
    )

    remainder = (
        evaluation_budget
        % len(weights)
    )

    weight_results = []

    for index, weight in enumerate(
        weights
    ):
        weight_budget = (
            base_budget
            + (
                1
                if index < remainder
                else 0
            )
        )

        weight_seed = (
            seed
            + index * 100_003
        )

        result = (
            _run_single_weight_ga(
                data=data,
                weight=weight,
                evaluation_budget=(
                    weight_budget
                ),
                population_size=(
                    population_size
                ),
                seed=weight_seed,
                crossover_probability=(
                    crossover_probability
                ),
                mutation_probability=(
                    mutation_probability
                ),
            )
        )

        weight_results.append(
            result
        )

    point_assignments: Dict[
        ObjectivePoint,
        Dict,
    ] = {}

    for result in weight_results:
        point = (
            result[
                "technical_requirement_deficit"
            ],
            result[
                "preference_dissatisfaction"
            ],
        )

        if point not in point_assignments:
            point_assignments[
                point
            ] = result[
                "example_assignment"
            ]

    pareto_front = (
        _build_front_from_points(
            point_assignments
        )
    )

    metrics = (
        calculate_front_metrics(
            pareto_front
        )
    )

    return {
        "algorithm": (
            "Weighted Single-Objective GA"
        ),
        "weights": weights,
        "seed": seed,
        "evaluation_budget": (
            evaluation_budget
        ),
        "evaluations": sum(
            result["evaluations"]
            for result
            in weight_results
        ),
        "budget_distribution": [
            result["evaluations"]
            for result
            in weight_results
        ],
        "weight_results": (
            weight_results
        ),
        "pareto_point_count": (
            len(pareto_front)
        ),
        "pareto_front": (
            pareto_front
        ),
        "metrics": metrics,
    }