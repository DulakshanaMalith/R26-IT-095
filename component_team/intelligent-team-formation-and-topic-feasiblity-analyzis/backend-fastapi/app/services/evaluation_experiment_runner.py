import csv
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.services.baseline_team_formation import (
    build_preference_greedy_assignment,
    build_technical_greedy_assignment,
)
from app.services.evaluation_metrics import (
    calculate_front_metrics,
)
from app.services.nsga2_optimizer import (
    optimize_team_formation,
)
from app.services.stochastic_baselines import (
    run_random_search,
    run_weighted_single_objective_search,
)
from app.services.synthetic_cohort_generator import (
    generate_synthetic_cohort,
)
from app.services.team_formation_objectives import (
    evaluate_assignment,
)

METHOD_TECHNICAL_GREEDY = "Technical Greedy"
METHOD_PREFERENCE_GREEDY = "Preference Greedy"
METHOD_RANDOM = "Random Search"
METHOD_WEIGHTED = "Weighted Single-Objective GA"
METHOD_NSGA2_UNSEEDED = "Unseeded NSGA-II"
METHOD_NSGA2_SEEDED = "Heuristic-Seeded NSGA-II"

STOCHASTIC_METHODS = [
    METHOD_RANDOM,
    METHOD_WEIGHTED,
    METHOD_NSGA2_UNSEEDED,
    METHOD_NSGA2_SEEDED,
]


def _single_point_metrics(
    technical_deficit: float,
    preference_dissatisfaction: float,
) -> Dict:
    front = [
        {
            "technical_requirement_deficit": technical_deficit,
            "preference_dissatisfaction": preference_dissatisfaction,
        }
    ]

    return calculate_front_metrics(
        front
    )


def _compact_front(
    metrics: Dict,
) -> List[Dict]:
    return metrics.get(
        "nondominated_points",
        [],
    )


def _build_record(
    method: str,
    student_count: int,
    conflict_level: str,
    dataset_seed: int,
    optimizer_seed: Optional[int],
    runtime_seconds: float,
    metrics: Dict,
    evaluations: Optional[int],
    project_count: int,
    population_size: Optional[int] = None,
    generations: Optional[int] = None,
    evaluation_budget: Optional[int] = None,
) -> Dict:
    return {
        "method": method,
        "students": student_count,
        "projects": project_count,
        "conflict_level": conflict_level,
        "dataset_seed": dataset_seed,
        "optimizer_seed": optimizer_seed,
        "population_size": population_size,
        "generations": generations,
        "evaluation_budget": evaluation_budget,
        "evaluations": evaluations,
        "runtime_seconds": runtime_seconds,
        "pareto_point_count": metrics[
            "nondominated_point_count"
        ],
        "best_technical_deficit": metrics[
            "best_technical_deficit"
        ],
        "best_preference_dissatisfaction": metrics[
            "best_preference_dissatisfaction"
        ],
        "hypervolume": metrics[
            "hypervolume"
        ],
        "front_points": _compact_front(
            metrics
        ),
    }


def _record_key(
    record: Dict,
) -> str:
    optimizer_seed = record.get(
        "optimizer_seed"
    )

    return "|".join(
        [
            str(record["method"]),
            str(record["students"]),
            str(record["conflict_level"]),
            str(record["dataset_seed"]),
            (
                "NONE"
                if optimizer_seed is None
                else str(optimizer_seed)
            ),
        ]
    )


def _load_existing_records(
    jsonl_path: Path,
) -> List[Dict]:
    if not jsonl_path.exists():
        return []

    records = []

    with jsonl_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(
                    json.loads(line)
                )
            except json.JSONDecodeError:
                print(
                    "Warning: skipped one invalid JSONL line."
                )

    return records


def _append_jsonl_record(
    jsonl_path: Path,
    record: Dict,
) -> None:
    with jsonl_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
        )
        file.write("\n")


def _write_csv(
    csv_path: Path,
    records: List[Dict],
) -> None:
    fieldnames = [
        "method",
        "students",
        "projects",
        "conflict_level",
        "dataset_seed",
        "optimizer_seed",
        "population_size",
        "generations",
        "evaluation_budget",
        "evaluations",
        "runtime_seconds",
        "pareto_point_count",
        "best_technical_deficit",
        "best_preference_dissatisfaction",
        "hypervolume",
        "front_points",
    ]

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for record in records:
            csv_record = dict(
                record
            )

            csv_record[
                "front_points"
            ] = json.dumps(
                record.get(
                    "front_points",
                    [],
                ),
                ensure_ascii=False,
            )

            writer.writerow(
                {
                    field: csv_record.get(
                        field
                    )
                    for field in fieldnames
                }
            )


def _run_deterministic_baselines(
    data,
    student_count: int,
    conflict_level: str,
    dataset_seed: int,
) -> List[Dict]:
    technical_start = (
        time.perf_counter()
    )

    technical_assignment = (
        build_technical_greedy_assignment(
            data
        )
    )

    technical_result = (
        evaluate_assignment(
            data=data,
            assignment=technical_assignment,
        )
    )

    technical_runtime = (
        time.perf_counter()
        - technical_start
    )

    preference_start = (
        time.perf_counter()
    )

    preference_assignment = (
        build_preference_greedy_assignment(
            data
        )
    )

    preference_result = (
        evaluate_assignment(
            data=data,
            assignment=preference_assignment,
        )
    )

    preference_runtime = (
        time.perf_counter()
        - preference_start
    )

    technical_metrics = (
        _single_point_metrics(
            technical_result[
                "technical_requirement_deficit"
            ],
            technical_result[
                "preference_dissatisfaction"
            ],
        )
    )

    preference_metrics = (
        _single_point_metrics(
            preference_result[
                "technical_requirement_deficit"
            ],
            preference_result[
                "preference_dissatisfaction"
            ],
        )
    )

    project_count = len(
        data.projects
    )

    return [
        _build_record(
            method=METHOD_TECHNICAL_GREEDY,
            student_count=student_count,
            conflict_level=conflict_level,
            dataset_seed=dataset_seed,
            optimizer_seed=None,
            runtime_seconds=technical_runtime,
            metrics=technical_metrics,
            evaluations=None,
            project_count=project_count,
        ),
        _build_record(
            method=METHOD_PREFERENCE_GREEDY,
            student_count=student_count,
            conflict_level=conflict_level,
            dataset_seed=dataset_seed,
            optimizer_seed=None,
            runtime_seconds=preference_runtime,
            metrics=preference_metrics,
            evaluations=None,
            project_count=project_count,
        ),
    ]


def _run_stochastic_method(
    method: str,
    data,
    student_count: int,
    conflict_level: str,
    dataset_seed: int,
    optimizer_seed: int,
    population_size: int,
    generations: int,
    evaluation_budget: int,
) -> Dict:
    start = (
        time.perf_counter()
    )

    if method == METHOD_RANDOM:
        result = run_random_search(
            data=data,
            evaluation_budget=evaluation_budget,
            seed=optimizer_seed,
        )

        metrics = result[
            "metrics"
        ]

        evaluations = result[
            "evaluations"
        ]

    elif method == METHOD_WEIGHTED:
        result = (
            run_weighted_single_objective_search(
                data=data,
                evaluation_budget=evaluation_budget,
                population_size=population_size,
                seed=optimizer_seed,
            )
        )

        metrics = result[
            "metrics"
        ]

        evaluations = result[
            "evaluations"
        ]

    elif method in {
        METHOD_NSGA2_UNSEEDED,
        METHOD_NSGA2_SEEDED,
    }:
        seeded = (
            method
            == METHOD_NSGA2_SEEDED
        )

        result = optimize_team_formation(
            data=data,
            population_size=population_size,
            generations=generations,
            seed=optimizer_seed,
            progress_interval=0,
            seeded_initialization=seeded,
        )

        metrics = (
            calculate_front_metrics(
                result[
                    "pareto_front"
                ]
            )
        )

        evaluations = result[
            "evaluations"
        ]

    else:
        raise ValueError(
            f"Unknown method: {method}"
        )

    runtime = (
        time.perf_counter()
        - start
    )

    return _build_record(
        method=method,
        student_count=student_count,
        conflict_level=conflict_level,
        dataset_seed=dataset_seed,
        optimizer_seed=optimizer_seed,
        runtime_seconds=runtime,
        metrics=metrics,
        evaluations=evaluations,
        project_count=len(
            data.projects
        ),
        population_size=(
            population_size
            if method != METHOD_RANDOM
            else None
        ),
        generations=(
            generations
            if method
            in {
                METHOD_NSGA2_UNSEEDED,
                METHOD_NSGA2_SEEDED,
            }
            else None
        ),
        evaluation_budget=(
            evaluation_budget
            if method
            in {
                METHOD_RANDOM,
                METHOD_WEIGHTED,
            }
            else None
        ),
    )


def run_evaluation_experiment(
    student_sizes: List[int],
    conflict_levels: List[str],
    dataset_seeds: List[int],
    optimizer_seeds: List[int],
    output_prefix: str,
    population_size: int = 120,
    generations: int = 150,
    evaluation_budget: int = 16650,
    output_directory: str = "test_results",
    methods: Optional[List[str]] = None,
) -> Dict:
    if not student_sizes:
        raise ValueError(
            "At least one student size is required."
        )

    if not conflict_levels:
        raise ValueError(
            "At least one conflict level is required."
        )

    if not dataset_seeds:
        raise ValueError(
            "At least one dataset seed is required."
        )

    if not optimizer_seeds:
        raise ValueError(
            "At least one optimizer seed is required."
        )

    if population_size < 4:
        raise ValueError(
            "Population size must be at least 4."
        )

    if population_size % 4 != 0:
        raise ValueError(
            "Population size must be divisible by 4."
        )

    if generations < 1:
        raise ValueError(
            "Generations must be at least 1."
        )

    if evaluation_budget < 1:
        raise ValueError(
            "Evaluation budget must be at least 1."
        )

    valid_conflict_levels = {
        "low",
        "medium",
        "high",
    }

    for conflict_level in (
        conflict_levels
    ):
        if (
            conflict_level
            not in valid_conflict_levels
        ):
            raise ValueError(
                "Conflict level must be "
                "'low', 'medium', or 'high'."
            )

    all_methods = [
        METHOD_TECHNICAL_GREEDY,
        METHOD_PREFERENCE_GREEDY,
        METHOD_RANDOM,
        METHOD_WEIGHTED,
        METHOD_NSGA2_UNSEEDED,
        METHOD_NSGA2_SEEDED,
    ]

    if methods is None:
        methods = list(
            all_methods
        )

    unknown_methods = [
        method
        for method in methods
        if method not in all_methods
    ]

    if unknown_methods:
        raise ValueError(
            "Unknown evaluation method(s): "
            + ", ".join(
                unknown_methods
            )
        )

    output_dir = Path(
        output_directory
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    jsonl_path = (
        output_dir
        / f"{output_prefix}_runs.jsonl"
    )

    csv_path = (
        output_dir
        / f"{output_prefix}_runs.csv"
    )

    summary_path = (
        output_dir
        / f"{output_prefix}_summary.json"
    )

    records = (
        _load_existing_records(
            jsonl_path
        )
    )

    completed_keys = {
        _record_key(
            record
        )
        for record in records
    }

    experiment_start = (
        time.perf_counter()
    )

    total_datasets = (
        len(student_sizes)
        * len(conflict_levels)
        * len(dataset_seeds)
    )

    dataset_number = 0

    for student_count in (
        student_sizes
    ):
        for conflict_level in (
            conflict_levels
        ):
            for dataset_seed in (
                dataset_seeds
            ):
                dataset_number += 1

                print()
                print(
                    f"Dataset "
                    f"{dataset_number}/"
                    f"{total_datasets}"
                )

                print(
                    f"Students: "
                    f"{student_count}"
                )

                print(
                    f"Conflict: "
                    f"{conflict_level}"
                )

                print(
                    f"Dataset seed: "
                    f"{dataset_seed}"
                )

                data = (
                    generate_synthetic_cohort(
                        student_count=student_count,
                        conflict_level=conflict_level,
                        seed=dataset_seed,
                    )
                )

                deterministic_needed = any(
                    method in {
                        METHOD_TECHNICAL_GREEDY,
                        METHOD_PREFERENCE_GREEDY,
                    }
                    for method in methods
                )

                if deterministic_needed:
                    baseline_records = (
                        _run_deterministic_baselines(
                            data=data,
                            student_count=student_count,
                            conflict_level=conflict_level,
                            dataset_seed=dataset_seed,
                        )
                    )

                    for record in (
                        baseline_records
                    ):
                        if (
                            record["method"]
                            not in methods
                        ):
                            continue

                        key = (
                            _record_key(
                                record
                            )
                        )

                        if (
                            key
                            in completed_keys
                        ):
                            print(
                                f"  "
                                f"{record['method']}"
                                f" → already completed"
                            )
                            continue

                        _append_jsonl_record(
                            jsonl_path,
                            record,
                        )

                        records.append(
                            record
                        )

                        completed_keys.add(
                            key
                        )

                        print(
                            f"  "
                            f"{record['method']}"
                            f" → HV "
                            f"{record['hypervolume']:.4f}"
                            f" | "
                            f"{record['runtime_seconds']:.4f}s"
                        )

                for optimizer_seed in (
                    optimizer_seeds
                ):
                    for method in (
                        STOCHASTIC_METHODS
                    ):
                        if (
                            method
                            not in methods
                        ):
                            continue

                        placeholder = {
                            "method": method,
                            "students": student_count,
                            "conflict_level": conflict_level,
                            "dataset_seed": dataset_seed,
                            "optimizer_seed": optimizer_seed,
                        }

                        key = (
                            _record_key(
                                placeholder
                            )
                        )

                        if (
                            key
                            in completed_keys
                        ):
                            print(
                                f"  "
                                f"{method} "
                                f"seed "
                                f"{optimizer_seed}"
                                f" → already completed"
                            )
                            continue

                        print(
                            f"  {method} "
                            f"seed "
                            f"{optimizer_seed}..."
                        )

                        record = (
                            _run_stochastic_method(
                                method=method,
                                data=data,
                                student_count=student_count,
                                conflict_level=conflict_level,
                                dataset_seed=dataset_seed,
                                optimizer_seed=optimizer_seed,
                                population_size=population_size,
                                generations=generations,
                                evaluation_budget=evaluation_budget,
                            )
                        )

                        _append_jsonl_record(
                            jsonl_path,
                            record,
                        )

                        records.append(
                            record
                        )

                        completed_keys.add(
                            key
                        )

                        print(
                            f"    HV "
                            f"{record['hypervolume']:.4f}"
                            f" | points "
                            f"{record['pareto_point_count']}"
                            f" | "
                            f"{record['runtime_seconds']:.2f}s"
                        )

                _write_csv(
                    csv_path,
                    records,
                )

    total_runtime = (
        time.perf_counter()
        - experiment_start
    )

    _write_csv(
        csv_path,
        records,
    )

    expected_deterministic_records = (
        total_datasets
        * sum(
            1
            for method in methods
            if method
            in {
                METHOD_TECHNICAL_GREEDY,
                METHOD_PREFERENCE_GREEDY,
            }
        )
    )

    stochastic_method_count = sum(
        1
        for method in methods
        if method
        in STOCHASTIC_METHODS
    )

    expected_stochastic_records = (
        total_datasets
        * len(optimizer_seeds)
        * stochastic_method_count
    )

    expected_record_count = (
        expected_deterministic_records
        + expected_stochastic_records
    )

    experiment_records = [
        record
        for record in records
        if (
            record.get("students")
            in student_sizes
            and record.get(
                "conflict_level"
            )
            in conflict_levels
            and record.get(
                "dataset_seed"
            )
            in dataset_seeds
            and record.get(
                "method"
            )
            in methods
            and (
                record.get(
                    "optimizer_seed"
                )
                is None
                or record.get(
                    "optimizer_seed"
                )
                in optimizer_seeds
            )
        )
    ]

    summary = {
        "experiment": (
            "Multi-Objective Team Formation "
            "Evaluation"
        ),
        "output_prefix": output_prefix,
        "student_sizes": student_sizes,
        "conflict_levels": conflict_levels,
        "dataset_seeds": dataset_seeds,
        "optimizer_seeds": optimizer_seeds,
        "population_size": population_size,
        "generations": generations,
        "evaluation_budget": evaluation_budget,
        "methods": methods,
        "dataset_count": total_datasets,
        "stochastic_method_count": (
            stochastic_method_count
        ),
        "expected_record_count": (
            expected_record_count
        ),
        "experiment_record_count": len(
            experiment_records
        ),
        "all_loaded_record_count": len(
            records
        ),
        "complete": (
            len(experiment_records)
            == expected_record_count
        ),
        "total_runtime_seconds": (
            total_runtime
        ),
        "jsonl_file": str(
            jsonl_path
        ),
        "csv_file": str(
            csv_path
        ),
        "summary_file": str(
            summary_path
        ),
    }

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    return summary