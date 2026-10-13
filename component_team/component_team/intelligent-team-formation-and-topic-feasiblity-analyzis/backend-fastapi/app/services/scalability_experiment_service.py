import time
from typing import Dict, List
from app.services.nsga2_optimizer import (
    optimize_team_formation,
)
from app.services.synthetic_cohort_generator import (
    generate_synthetic_cohort,
)

def run_scalability_smoke_test(
    student_sizes: List[int] | None = None,
    conflict_level: str = "medium",
    dataset_seed: int = 2026,
    optimizer_seed: int = 42,
    population_size: int = 120,
    generations: int = 150,
) -> Dict:
    if student_sizes is None:
        student_sizes = [
            20,
            40,
            60,
            100,
        ]

    results = []

    print(
        "Starting NSGA-II scalability "
        "smoke test..."
    )

    print(
        f"Conflict level: "
        f"{conflict_level}"
    )

    print(
        f"Population: "
        f"{population_size}"
    )

    print(
        f"Generations: "
        f"{generations}"
    )

    print()

    for student_count in student_sizes:
        print(
            f"Running {student_count} "
            f"students..."
        )

        data = generate_synthetic_cohort(
            student_count=student_count,
            conflict_level=conflict_level,
            team_size=4,
            seed=dataset_seed,
        )

        start_time = (
            time.perf_counter()
        )

        optimization_result = (
            optimize_team_formation(
                data=data,
                population_size=(
                    population_size
                ),
                generations=generations,
                seed=optimizer_seed,
                progress_interval=0,
            )
        )

        runtime = (
            time.perf_counter()
            - start_time
        )

        pareto_front = (
            optimization_result[
                "pareto_front"
            ]
        )

        if not pareto_front:
            raise RuntimeError(
                "NSGA-II returned an empty "
                "Pareto front."
            )

        best_technical_point = min(
            pareto_front,
            key=lambda item: (
                item[
                    "technical_requirement_deficit"
                ],
                item[
                    "preference_dissatisfaction"
                ],
            ),
        )

        best_preference_point = min(
            pareto_front,
            key=lambda item: (
                item[
                    "preference_dissatisfaction"
                ],
                item[
                    "technical_requirement_deficit"
                ],
            ),
        )

        result = {
            "students": (
                student_count
            ),
            "projects": (
                len(data.projects)
            ),
            "team_size": 4,
            "conflict_level": (
                conflict_level
            ),
            "dataset_seed": (
                dataset_seed
            ),
            "optimizer_seed": (
                optimizer_seed
            ),
            "population_size": (
                population_size
            ),
            "generations": (
                generations
            ),
            "evaluations": (
                optimization_result[
                    "evaluations"
                ]
            ),
            "runtime_seconds": (
                runtime
            ),
            "pareto_point_count": (
                optimization_result[
                    "pareto_point_count"
                ]
            ),
            "archive_chromosome_count": (
                optimization_result[
                    "archive_chromosome_count"
                ]
            ),
            "best_technical_deficit": (
                best_technical_point[
                    "technical_requirement_deficit"
                ]
            ),
            "technical_endpoint_preference_dissatisfaction": (
                best_technical_point[
                    "preference_dissatisfaction"
                ]
            ),
            "best_preference_dissatisfaction": (
                best_preference_point[
                    "preference_dissatisfaction"
                ]
            ),
            "preference_endpoint_technical_deficit": (
                best_preference_point[
                    "technical_requirement_deficit"
                ]
            ),
        }

        results.append(
            result
        )

        print(
            f"  Projects: "
            f"{result['projects']}"
        )

        print(
            f"  Runtime: "
            f"{runtime:.3f}s"
        )

        print(
            f"  Evaluations: "
            f"{result['evaluations']:,}"
        )

        print(
            f"  Pareto points: "
            f"{result['pareto_point_count']}"
        )

        print(
            f"  Best technical deficit: "
            f"{result['best_technical_deficit']:.4f}"
        )

        print(
            f"  Best preference "
            f"dissatisfaction: "
            f"{result['best_preference_dissatisfaction']:.4f}"
        )

        print()

    total_runtime = sum(
        result["runtime_seconds"]
        for result in results
    )

    return {
        "experiment": (
            "NSGA-II Scalability "
            "Smoke Test"
        ),
        "purpose": (
            "Preliminary runtime and "
            "solution-size check before "
            "the full repeated scalability "
            "experiment."
        ),
        "configuration": {
            "student_sizes": (
                student_sizes
            ),
            "conflict_level": (
                conflict_level
            ),
            "dataset_seed": (
                dataset_seed
            ),
            "optimizer_seed": (
                optimizer_seed
            ),
            "population_size": (
                population_size
            ),
            "generations": (
                generations
            ),
        },
        "total_runtime_seconds": (
            total_runtime
        ),
        "results": results,
    }