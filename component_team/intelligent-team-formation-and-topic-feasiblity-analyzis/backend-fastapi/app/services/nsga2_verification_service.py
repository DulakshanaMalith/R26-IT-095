import time
from statistics import mean
from typing import Dict, List, Set, Tuple
from app.models.cohort_import import CohortImportData
from app.services.exact_search_verifier import (
    find_exact_pareto_front,
)
from app.services.nsga2_optimizer import (
    optimize_team_formation,
)

ObjectivePoint = Tuple[float, float]

def _extract_front_points(
    pareto_front: List[Dict],
) -> Set[ObjectivePoint]:
    return {
        (
            round(
                item[
                    "technical_requirement_deficit"
                ],
                12,
            ),
            round(
                item[
                    "preference_dissatisfaction"
                ],
                12,
            ),
        )
        for item in pareto_front
    }

def _points_for_output(
    points: Set[ObjectivePoint],
) -> List[Dict]:
    return [
        {
            "technical_requirement_deficit": point[0],
            "preference_dissatisfaction": point[1],
        }
        for point in sorted(points)
    ]

def verify_nsga2_against_exact_front(
    data: CohortImportData,
    seeds: List[int] | None = None,
    population_size: int = 120,
    generations: int = 150,
    crossover_probability: float = 0.9,
    mutation_probability: float = 0.2,
    mutation_gene_probability: float = 0.1,
) -> Dict:
    if seeds is None:
        seeds = list(range(1, 31))

    if not seeds:
        raise ValueError(
            "At least one random seed is required."
        )

    print(
        "Calculating exact Pareto front..."
    )

    exact_start = time.perf_counter()

    exact_result = find_exact_pareto_front(
        data=data,
        progress_interval=0,
    )

    exact_runtime = (
        time.perf_counter()
        - exact_start
    )

    exact_points = _extract_front_points(
        exact_result["pareto_front"]
    )

    print(
        f"Exact front contains "
        f"{len(exact_points)} objective point(s)."
    )

    run_results = []

    for run_number, seed in enumerate(
        seeds,
        start=1,
    ):
        start_time = time.perf_counter()

        nsga2_result = optimize_team_formation(
            data=data,
            population_size=population_size,
            generations=generations,
            crossover_probability=(
                crossover_probability
            ),
            mutation_probability=(
                mutation_probability
            ),
            mutation_gene_probability=(
                mutation_gene_probability
            ),
            seed=seed,
            progress_interval=0,
        )

        runtime = (
            time.perf_counter()
            - start_time
        )

        discovered_points = (
            _extract_front_points(
                nsga2_result[
                    "pareto_front"
                ]
            )
        )

        recovered_points = (
            exact_points
            & discovered_points
        )

        missing_points = (
            exact_points
            - discovered_points
        )

        extra_points = (
            discovered_points
            - exact_points
        )

        recall = (
            len(recovered_points)
            / len(exact_points)
            if exact_points
            else 1.0
        )

        precision = (
            len(recovered_points)
            / len(discovered_points)
            if discovered_points
            else 0.0
        )

        exact_match = (
            discovered_points
            == exact_points
        )

        run_result = {
            "run": run_number,
            "seed": seed,
            "exact_front_match": (
                exact_match
            ),
            "discovered_point_count": (
                len(discovered_points)
            ),
            "recovered_exact_point_count": (
                len(recovered_points)
            ),
            "missing_exact_point_count": (
                len(missing_points)
            ),
            "extra_point_count": (
                len(extra_points)
            ),
            "front_recall": recall,
            "front_precision": precision,
            "evaluations": nsga2_result[
                "evaluations"
            ],
            "runtime_seconds": runtime,
            "missing_points": (
                _points_for_output(
                    missing_points
                )
            ),
            "extra_points": (
                _points_for_output(
                    extra_points
                )
            ),
        }

        run_results.append(
            run_result
        )

        status = (
            "EXACT"
            if exact_match
            else "PARTIAL"
        )

        print(
            f"Run {run_number:02d}/"
            f"{len(seeds):02d} "
            f"- seed {seed:02d} "
            f"- {status} "
            f"- recall {recall:.3f} "
            f"- points "
            f"{len(discovered_points)} "
            f"- {runtime:.3f}s"
        )

    exact_match_runs = sum(
        1
        for result in run_results
        if result[
            "exact_front_match"
        ]
    )

    failed_seeds = [
        result["seed"]
        for result in run_results
        if not result[
            "exact_front_match"
        ]
    ]

    summary = {
        "runs": len(run_results),
        "exact_front_point_count": (
            len(exact_points)
        ),
        "exact_match_runs": (
            exact_match_runs
        ),
        "exact_match_rate": (
            exact_match_runs
            / len(run_results)
        ),
        "mean_front_recall": mean(
            result["front_recall"]
            for result in run_results
        ),
        "minimum_front_recall": min(
            result["front_recall"]
            for result in run_results
        ),
        "mean_front_precision": mean(
            result["front_precision"]
            for result in run_results
        ),
        "mean_evaluations": mean(
            result["evaluations"]
            for result in run_results
        ),
        "mean_runtime_seconds": mean(
            result["runtime_seconds"]
            for result in run_results
        ),
        "minimum_runtime_seconds": min(
            result["runtime_seconds"]
            for result in run_results
        ),
        "maximum_runtime_seconds": max(
            result["runtime_seconds"]
            for result in run_results
        ),
        "exact_search_runtime_seconds": (
            exact_runtime
        ),
        "failed_seeds": failed_seeds,
    }

    return {
        "experiment": (
            "NSGA-II Exact Pareto Front Verification"
        ),
        "parameters": {
            "population_size": (
                population_size
            ),
            "generations": generations,
            "crossover_probability": (
                crossover_probability
            ),
            "mutation_probability": (
                mutation_probability
            ),
            "mutation_gene_probability": (
                mutation_gene_probability
            ),
            "seeds": seeds,
        },
        "exact_front": (
            _points_for_output(
                exact_points
            )
        ),
        "summary": summary,
        "runs": run_results,
    }