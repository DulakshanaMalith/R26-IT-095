import random
from typing import Dict, List, Set, Tuple
from deap import base, creator, tools
from app.models.cohort_import import CohortImportData
from app.services.baseline_team_formation import (
    build_preference_greedy_assignment,
    build_technical_greedy_assignment,
)
from app.services.team_formation_objectives import (
    TeamAssignment,
    evaluate_assignment,
)

ObjectivePoint = Tuple[float, float]
CanonicalAssignment = Tuple[
    Tuple[str, Tuple[str, ...]],
    ...
]

def _ensure_deap_types() -> None:
    if not hasattr(
        creator,
        "FitnessTeamFormationV1",
    ):
        creator.create(
            "FitnessTeamFormationV1",
            base.Fitness,
            weights=(-1.0, -1.0),
        )

    if not hasattr(
        creator,
        "IndividualTeamFormationV1",
    ):
        creator.create(
            "IndividualTeamFormationV1",
            list,
            fitness=creator.FitnessTeamFormationV1,
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

def canonicalize_individual(
    data: CohortImportData,
    individual: List[int],
) -> List[int]:
    segments = _get_project_segments(
        data
    )

    for start, end in segments:
        individual[start:end] = sorted(
            individual[start:end]
        )

    return individual

def mutate_swap_between_teams(
    individual: List[int],
    segments: List[Tuple[int, int]],
):
    if len(segments) < 2:
        return (individual,)

    team_a, team_b = random.sample(
        range(len(segments)),
        2,
    )

    start_a, end_a = segments[
        team_a
    ]

    start_b, end_b = segments[
        team_b
    ]

    position_a = random.randrange(
        start_a,
        end_a,
    )

    position_b = random.randrange(
        start_b,
        end_b,
    )

    individual[
        position_a
    ], individual[
        position_b
    ] = (
        individual[position_b],
        individual[position_a],
    )

    return (individual,)

def individual_to_assignment(
    data: CohortImportData,
    individual: List[int],
) -> TeamAssignment:
    student_ids = [
        student.student_id
        for student in data.students
    ]

    if len(individual) != len(
        student_ids
    ):
        raise ValueError(
            "Individual length does not match "
            "the number of students."
        )

    if sorted(individual) != list(
        range(len(student_ids))
    ):
        raise ValueError(
            "Individual is not a valid "
            "student permutation."
        )

    assignment: TeamAssignment = {}
    offset = 0

    for project in data.projects:
        end = (
            offset
            + project.team_size
        )

        assignment[
            project.project_id
        ] = [
            student_ids[index]
            for index
            in individual[offset:end]
        ]

        offset = end

    if offset != len(student_ids):
        raise ValueError(
            "Project team sizes do not consume "
            "all students."
        )

    return assignment

def assignment_to_individual(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> List[int]:
    student_index_lookup = {
        student.student_id: index
        for index, student
        in enumerate(data.students)
    }

    individual = []

    for project in data.projects:
        project_id = (
            project.project_id
        )

        if project_id not in assignment:
            raise ValueError(
                f"Assignment is missing "
                f"project '{project_id}'."
            )

        team = assignment[
            project_id
        ]

        if len(team) != project.team_size:
            raise ValueError(
                f"Project '{project_id}' "
                f"requires {project.team_size} "
                f"students, but received "
                f"{len(team)}."
            )

        for student_id in team:
            if (
                student_id
                not in student_index_lookup
            ):
                raise ValueError(
                    f"Unknown student "
                    f"'{student_id}'."
                )

            individual.append(
                student_index_lookup[
                    student_id
                ]
            )

    if sorted(individual) != list(
        range(len(data.students))
    ):
        raise ValueError(
            "Assignment does not contain "
            "every student exactly once."
        )

    canonicalize_individual(
        data=data,
        individual=individual,
    )

    return individual

def canonicalize_assignment(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> CanonicalAssignment:
    return tuple(
        (
            project.project_id,
            tuple(
                sorted(
                    assignment[
                        project.project_id
                    ]
                )
            ),
        )
        for project in data.projects
    )

def canonicalize_assignment_for_output(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> TeamAssignment:
    return {
        project.project_id: sorted(
            assignment[
                project.project_id
            ]
        )
        for project in data.projects
    }

def _build_initial_population(
    data: CohortImportData,
    toolbox: base.Toolbox,
    population_size: int,
    segments: List[Tuple[int, int]],
    seeded_initialization: bool,
    seed_variant_count: int,
):
    population = []
    seen = set()
    seeded_count = 0

    def add_individual(
        values: List[int],
        is_seeded: bool,
    ) -> bool:
        nonlocal seeded_count

        canonicalize_individual(
            data=data,
            individual=values,
        )

        key = tuple(values)

        if key in seen:
            return False

        seen.add(key)

        individual = (
            creator
            .IndividualTeamFormationV1(
                values
            )
        )

        population.append(
            individual
        )

        if is_seeded:
            seeded_count += 1

        return True

    if seeded_initialization:
        technical_assignment = (
            build_technical_greedy_assignment(
                data
            )
        )

        preference_assignment = (
            build_preference_greedy_assignment(
                data
            )
        )

        technical_seed = (
            assignment_to_individual(
                data=data,
                assignment=(
                    technical_assignment
                ),
            )
        )

        preference_seed = (
            assignment_to_individual(
                data=data,
                assignment=(
                    preference_assignment
                ),
            )
        )

        anchors = [
            technical_seed,
            preference_seed,
        ]

        for anchor in anchors:
            add_individual(
                list(anchor),
                is_seeded=True,
            )

        for anchor in anchors:
            created = 0
            attempts = 0
            max_attempts = max(
                100,
                seed_variant_count * 20,
            )

            while (
                created
                < seed_variant_count
                and attempts
                < max_attempts
                and len(population)
                < population_size
            ):
                variant = list(
                    anchor
                )

                swap_count = (
                    1
                    + (
                        created
                        % 3
                    )
                )

                for _ in range(
                    swap_count
                ):
                    mutate_swap_between_teams(
                        variant,
                        segments,
                    )

                canonicalize_individual(
                    data=data,
                    individual=variant,
                )

                if add_individual(
                    variant,
                    is_seeded=True,
                ):
                    created += 1

                attempts += 1

    attempts = 0
    max_attempts = (
        population_size
        * 100
    )

    while (
        len(population)
        < population_size
        and attempts
        < max_attempts
    ):
        random_values = random.sample(
            range(len(data.students)),
            len(data.students),
        )

        add_individual(
            random_values,
            is_seeded=False,
        )

        attempts += 1

    if len(population) != population_size:
        raise RuntimeError(
            "Could not construct the requested "
            "number of unique initial "
            "individuals."
        )

    return (
        population,
        seeded_count,
    )

def optimize_team_formation(
    data: CohortImportData,
    population_size: int = 120,
    generations: int = 150,
    crossover_probability: float = 0.9,
    mutation_probability: float = 0.2,
    mutation_gene_probability: float | None = None,
    seed: int = 42,
    progress_interval: int = 25,
    seeded_initialization: bool = True,
    seed_variant_count: int = 12,
) -> Dict:
    if population_size < 4:
        raise ValueError(
            "Population size must be "
            "at least 4."
        )

    if population_size % 4 != 0:
        raise ValueError(
            "Population size must be "
            "divisible by 4 for "
            "tournament selection."
        )

    if generations < 1:
        raise ValueError(
            "Generations must be "
            "at least 1."
        )

    if seed_variant_count < 0:
        raise ValueError(
            "Seed variant count cannot "
            "be negative."
        )

    if not (
        0.0
        <= crossover_probability
        <= 1.0
    ):
        raise ValueError(
            "Crossover probability must "
            "be between 0 and 1."
        )

    if not (
        0.0
        <= mutation_probability
        <= 1.0
    ):
        raise ValueError(
            "Mutation probability must "
            "be between 0 and 1."
        )

    if sum(
        project.team_size
        for project in data.projects
    ) != len(data.students):
        raise ValueError(
            "Total project team size "
            "must equal the number "
            "of students."
        )

    random.seed(seed)

    _ensure_deap_types()

    student_count = len(
        data.students
    )

    segments = (
        _get_project_segments(
            data
        )
    )

    toolbox = base.Toolbox()

    def create_permutation() -> List[int]:
        individual = random.sample(
            range(student_count),
            student_count,
        )

        canonicalize_individual(
            data=data,
            individual=individual,
        )

        return individual

    toolbox.register(
        "individual",
        tools.initIterate,
        creator.IndividualTeamFormationV1,
        create_permutation,
    )

    toolbox.register(
        "population",
        tools.initRepeat,
        list,
        toolbox.individual,
    )

    def evaluate_individual(
        individual,
    ) -> Tuple[float, float]:
        assignment = (
            individual_to_assignment(
                data=data,
                individual=individual,
            )
        )

        result = (
            evaluate_assignment(
                data=data,
                assignment=assignment,
            )
        )

        return (
            result[
                "technical_requirement_deficit"
            ],
            result[
                "preference_dissatisfaction"
            ],
        )

    toolbox.register(
        "evaluate",
        evaluate_individual,
    )

    toolbox.register(
        "mate",
        tools.cxOrdered,
    )

    toolbox.register(
        "mutate",
        mutate_swap_between_teams,
        segments=segments,
    )

    toolbox.register(
        "select",
        tools.selNSGA2,
    )

    (
        population,
        seeded_individual_count,
    ) = _build_initial_population(
        data=data,
        toolbox=toolbox,
        population_size=population_size,
        segments=segments,
        seeded_initialization=(
            seeded_initialization
        ),
        seed_variant_count=(
            seed_variant_count
        ),
    )

    evaluations = 0

    invalid_individuals = [
        individual
        for individual in population
        if not individual.fitness.valid
    ]

    fitness_values = map(
        toolbox.evaluate,
        invalid_individuals,
    )

    for individual, fitness in zip(
        invalid_individuals,
        fitness_values,
    ):
        individual.fitness.values = (
            fitness
        )
        evaluations += 1

    population = toolbox.select(
        population,
        len(population),
    )

    pareto_archive = (
        tools.ParetoFront()
    )

    pareto_archive.update(
        population
    )

    for generation in range(
        1,
        generations + 1,
    ):
        offspring = (
            tools.selTournamentDCD(
                population,
                len(population),
            )
        )

        offspring = [
            toolbox.clone(
                individual
            )
            for individual
            in offspring
        ]

        for index in range(
            0,
            len(offspring),
            2,
        ):
            child1 = offspring[
                index
            ]

            child2 = offspring[
                index + 1
            ]

            if (
                random.random()
                < crossover_probability
            ):
                toolbox.mate(
                    child1,
                    child2,
                )

                canonicalize_individual(
                    data=data,
                    individual=child1,
                )

                canonicalize_individual(
                    data=data,
                    individual=child2,
                )

                if child1.fitness.valid:
                    del child1.fitness.values

                if child2.fitness.valid:
                    del child2.fitness.values

            if (
                random.random()
                < mutation_probability
            ):
                toolbox.mutate(
                    child1
                )

                canonicalize_individual(
                    data=data,
                    individual=child1,
                )

                if child1.fitness.valid:
                    del child1.fitness.values

            if (
                random.random()
                < mutation_probability
            ):
                toolbox.mutate(
                    child2
                )

                canonicalize_individual(
                    data=data,
                    individual=child2,
                )

                if child2.fitness.valid:
                    del child2.fitness.values

        invalid_individuals = [
            individual
            for individual in offspring
            if not individual.fitness.valid
        ]

        fitness_values = map(
            toolbox.evaluate,
            invalid_individuals,
        )

        for individual, fitness in zip(
            invalid_individuals,
            fitness_values,
        ):
            individual.fitness.values = (
                fitness
            )
            evaluations += 1

        population = toolbox.select(
            population + offspring,
            population_size,
        )

        pareto_archive.update(
            population
        )

        if (
            progress_interval > 0
            and generation
            % progress_interval == 0
        ):
            print(
                f"Generation "
                f"{generation}/"
                f"{generations} "
                f"- evaluations: "
                f"{evaluations:,} "
                f"- archive chromosomes: "
                f"{len(pareto_archive)}"
            )

    objective_points: Dict[
        ObjectivePoint,
        Dict,
    ] = {}

    unique_assignments: Dict[
        ObjectivePoint,
        Set[
            CanonicalAssignment
        ],
    ] = {}

    for individual in (
        pareto_archive
    ):
        technical_deficit = round(
            individual.fitness.values[
                0
            ],
            12,
        )

        preference_dissatisfaction = (
            round(
                individual.fitness.values[
                    1
                ],
                12,
            )
        )

        point = (
            technical_deficit,
            preference_dissatisfaction,
        )

        assignment = (
            individual_to_assignment(
                data=data,
                individual=individual,
            )
        )

        canonical_assignment = (
            canonicalize_assignment(
                data=data,
                assignment=assignment,
            )
        )

        if (
            point
            not in unique_assignments
        ):
            unique_assignments[
                point
            ] = set()

        unique_assignments[
            point
        ].add(
            canonical_assignment
        )

        if (
            point
            not in objective_points
        ):
            objective_points[
                point
            ] = {
                "technical_requirement_deficit": (
                    technical_deficit
                ),
                "preference_dissatisfaction": (
                    preference_dissatisfaction
                ),
                "example_assignment": (
                    canonicalize_assignment_for_output(
                        data=data,
                        assignment=assignment,
                    )
                ),
            }

    sorted_front = []

    for (
        point,
        result,
    ) in objective_points.items():
        result[
            "discovered_unique_allocation_count"
        ] = len(
            unique_assignments[
                point
            ]
        )

        sorted_front.append(
            result
        )

    sorted_front.sort(
        key=lambda item: (
            item[
                "technical_requirement_deficit"
            ],
            item[
                "preference_dissatisfaction"
            ],
        )
    )

    return {
        "algorithm": (
            "Heuristic-Seeded NSGA-II"
            if seeded_initialization
            else "NSGA-II"
        ),
        "optimizer_version": "V3",
        "representation": (
            "Canonical fixed-team-size "
            "student permutation"
        ),
        "initialization": (
            "Technical greedy + "
            "preference greedy + "
            "seed variants + random"
            if seeded_initialization
            else "Random"
        ),
        "crossover_operator": (
            "Ordered crossover"
        ),
        "mutation_operator": (
            "Single cross-team "
            "student swap"
        ),
        "seeded_initialization": (
            seeded_initialization
        ),
        "seed_variant_count": (
            seed_variant_count
        ),
        "seeded_individual_count": (
            seeded_individual_count
        ),
        "seed": seed,
        "population_size": (
            population_size
        ),
        "generations": generations,
        "evaluations": evaluations,
        "archive_chromosome_count": (
            len(pareto_archive)
        ),
        "pareto_point_count": (
            len(sorted_front)
        ),
        "pareto_front": sorted_front,
    }