from time import perf_counter
from typing import Dict, List, Tuple

from app.models.cohort_import import CohortImportData
from app.services.nsga2_optimizer import optimize_team_formation
from app.services.project_pool_selection_service import (
    generate_candidate_project_subsets,
    scope_cohort_to_projects,
)
from app.services.solution_integrity_service import summarize_solution_integrity, verify_solution_integrity
from app.services.team_formation_response_service import build_staff_team_formation_response
from app.services.team_size_configuration_service import apply_team_size_configuration, calculate_team_configuration


def _dominates(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and (a[0] < b[0] or a[1] < b[1])


def _solution_role(index: int, total: int) -> str:
    if total <= 1:
        return "Aligned objectives"
    if index == 0:
        return "Technical-oriented endpoint"
    if index == total - 1:
        return "Preference-oriented endpoint"
    return "Trade-off alternative"


def _allocation_key(solution: Dict) -> Tuple:
    return tuple(
        (team["project_id"], tuple(sorted(student["student_id"] for student in team["students"])))
        for team in sorted(solution["teams"], key=lambda item: item["project_id"])
    )


def _seconds(start: float) -> float:
    return round(perf_counter() - start, 4)


def optimize_with_staff_team_size(
    data: CohortImportData,
    students_per_team: int,
    population_size: int = 120,
    generations: int = 150,
    seed: int = 42,
    seeded_initialization: bool = True,
    seed_variant_count: int = 12,
    max_project_subset_candidates: int = 8,
) -> Dict:
    pipeline_start = perf_counter()
    configuration = calculate_team_configuration(
        student_count=len(data.students),
        project_count=len(data.projects),
        students_per_team=students_per_team,
    )
    required_team_count = configuration["required_team_count"]
    remainder = configuration["remainder_students"]
    all_project_ids = [project.project_id for project in data.projects]

    subset_start = perf_counter()
    project_subsets = generate_candidate_project_subsets(
        data=data,
        required_team_count=required_team_count,
        seed=seed,
        max_candidate_subsets=max_project_subset_candidates,
    )
    project_subset_generation_seconds = _seconds(subset_start)

    all_solutions = []
    total_evaluations = 0
    total_archive_chromosomes = 0
    seeded_individual_count = 0
    optimizer_seconds = 0.0
    response_build_seconds = 0.0
    configuration_seconds = 0.0
    integrity_seconds = 0.0
    candidate_timings = []
    candidate_run_index = 0

    for subset_index, selected_project_ids in enumerate(project_subsets):
        subset_data = scope_cohort_to_projects(data, selected_project_ids)
        unassigned_project_ids = [
            project_id for project_id in all_project_ids if project_id not in set(selected_project_ids)
        ]

        remainder_project_ids: List[str | None]
        if remainder > 0:
            remainder_project_ids = list(selected_project_ids)
        else:
            remainder_project_ids = [None]

        for remainder_project_id in remainder_project_ids:
            candidate_start = perf_counter()
            configuration_start = perf_counter()
            configured_data = apply_team_size_configuration(
                data=subset_data,
                students_per_team=students_per_team,
                remainder_project_id=remainder_project_id,
            )
            candidate_configuration_seconds = _seconds(configuration_start)
            configuration_seconds += candidate_configuration_seconds

            optimizer_start = perf_counter()
            optimization_result = optimize_team_formation(
                data=configured_data,
                population_size=population_size,
                generations=generations,
                seed=seed + candidate_run_index,
                seeded_initialization=seeded_initialization,
                seed_variant_count=seed_variant_count,
            )
            candidate_optimizer_seconds = _seconds(optimizer_start)
            optimizer_seconds += candidate_optimizer_seconds

            response_start = perf_counter()
            response = build_staff_team_formation_response(
                data=configured_data,
                optimization_result=optimization_result,
            )
            candidate_response_seconds = _seconds(response_start)
            response_build_seconds += candidate_response_seconds

            total_evaluations += int(optimization_result.get("evaluations", 0))
            total_archive_chromosomes += int(optimization_result.get("archive_chromosome_count", 0))
            seeded_individual_count += int(optimization_result.get("seeded_individual_count", 0))

            for solution in response["solutions"]:
                enriched = dict(solution)
                enriched["remainder_project_id"] = remainder_project_id
                enriched["selected_project_ids"] = list(selected_project_ids)
                enriched["unassigned_project_ids"] = list(unassigned_project_ids)
                enriched["available_project_count"] = len(all_project_ids)
                enriched["selected_project_count"] = len(selected_project_ids)

                integrity_start = perf_counter()
                enriched["integrity"] = verify_solution_integrity(
                    data=configured_data,
                    solution=enriched,
                )
                integrity_seconds += perf_counter() - integrity_start
                all_solutions.append(enriched)

            candidate_timings.append({
                "subset_index": subset_index + 1,
                "selected_project_ids": list(selected_project_ids),
                "unassigned_project_ids": list(unassigned_project_ids),
                "remainder_project_id": remainder_project_id,
                "configuration_seconds": candidate_configuration_seconds,
                "optimizer_seconds": candidate_optimizer_seconds,
                "response_build_seconds": candidate_response_seconds,
                "total_candidate_seconds": _seconds(candidate_start),
                "optimizer_internal_runtime": optimization_result.get("runtime", {}),
            })
            candidate_run_index += 1

    postprocess_start = perf_counter()
    point_examples: Dict[Tuple[float, float], Dict] = {}
    point_allocations: Dict[Tuple[float, float], set] = {}
    point_discovered_counts: Dict[Tuple[float, float], int] = {}

    for solution in all_solutions:
        if not solution.get("integrity", {}).get("valid", False):
            continue
        point = (
            round(float(solution["technical_requirement_deficit"]), 12),
            round(float(solution["preference_dissatisfaction"]), 12),
        )
        point_allocations.setdefault(point, set()).add(_allocation_key(solution))
        point_discovered_counts[point] = point_discovered_counts.get(point, 0) + int(
            solution.get("discovered_unique_allocation_count", 1)
        )
        if point not in point_examples:
            point_examples[point] = solution

    nondominated_points = []
    points = list(point_examples.keys())
    for point in points:
        if not any(_dominates(other, point) for other in points if other != point):
            nondominated_points.append(point)
    nondominated_points.sort(key=lambda point: (point[0], point[1]))

    solutions = []
    for index, point in enumerate(nondominated_points):
        solution = dict(point_examples[point])
        solution["solution_id"] = index + 1
        solution["role"] = _solution_role(index, len(nondominated_points))
        solution["discovered_unique_allocation_count"] = max(
            len(point_allocations[point]),
            point_discovered_counts[point],
        )
        solutions.append(solution)

    postprocessing_seconds = _seconds(postprocess_start)
    integrity_summary = summarize_solution_integrity(solutions)

    surplus_project_count = configuration["surplus_project_count"]
    project_subset_mode = "fixed_project_set" if surplus_project_count == 0 else "bounded_candidate_subset_search"

    optimizer_metadata = {
        "algorithm": "Heuristic-Seeded NSGA-II" if seeded_initialization else "NSGA-II",
        "optimizer_version": "V3",
        "representation": "Canonical student permutation with staff-configured uniform target team size",
        "initialization": "Technical greedy + preference greedy + seed variants + random" if seeded_initialization else "Random",
        "crossover_operator": "Ordered crossover",
        "mutation_operator": "Single cross-team student swap",
        "seeded_initialization": seeded_initialization,
        "seed_variant_count": seed_variant_count,
        "seeded_individual_count": seeded_individual_count,
        "seed": seed,
        "population_size": population_size,
        "generations": generations,
        "evaluations": total_evaluations,
        "archive_chromosome_count": total_archive_chromosomes,
        "pareto_point_count": len(solutions),
        "dynamic_team_size_wrapper": True,
        "remainder_candidate_runs": candidate_run_index,
        "project_subset_mode": project_subset_mode,
        "approved_project_count": len(all_project_ids),
        "required_team_count": required_team_count,
        "surplus_project_count": surplus_project_count,
        "project_subset_candidate_count": len(project_subsets),
        "max_project_subset_candidates": max_project_subset_candidates,
        "performance_optimization": "Precomputed objective evaluation and optimized technical-greedy seeding are retained. When surplus approved projects exist, a bounded project-subset wrapper evaluates multiple project pools and globally filters their returned objective points for nondominance.",
    }

    runtime = {
        "project_subset_generation_seconds": project_subset_generation_seconds,
        "configuration_seconds": round(configuration_seconds, 4),
        "optimizer_seconds": round(optimizer_seconds, 4),
        "response_build_seconds": round(response_build_seconds, 4),
        "global_postprocessing_seconds": postprocessing_seconds,
        "integrity_check_seconds": round(integrity_seconds, 4),
        "total_pipeline_seconds": _seconds(pipeline_start),
        "candidate_run_count": candidate_run_index,
        "candidate_timings": candidate_timings,
    }

    if surplus_project_count > 0:
        project_selection_note = (
            f"{len(all_project_ids)} approved projects are available for {required_team_count} teams. "
            f"The system evaluates {len(project_subsets)} candidate project subsets, each containing "
            f"{required_team_count} unique projects, then globally filters the discovered solutions for nondominance. "
            "When the number of possible project subsets exceeds the configured candidate limit, this is a bounded heuristic subset search rather than exhaustive enumeration of every possible project subset."
        )
    else:
        project_selection_note = "The number of approved projects equals the number of required teams, so the complete approved project set is used."

    return {
        "optimizer": optimizer_metadata,
        "solution_count": len(solutions),
        "solutions": solutions,
        "integrity_summary": integrity_summary,
        "runtime": runtime,
        "team_configuration": {
            **configuration,
            "project_subset_mode": project_subset_mode,
            "project_subset_candidate_count": len(project_subsets),
            "project_subset_candidates": project_subsets,
            "project_selection_note": project_selection_note,
            "remainder_strategy": (
                "For each candidate project subset, every selected project was evaluated as the possible smaller-team project, then all discovered solutions were globally filtered for nondominance."
                if remainder > 0
                else "No remainder team was required."
            ),
            "remainder_candidate_runs": candidate_run_index,
        },
        "interpretation": {
            "technical_requirement_deficit": "Lower is better. Zero means all modeled technical requirements of the selected projects are fully covered.",
            "preference_dissatisfaction": "Lower is better. Zero means every student is assigned to their first-ranked project.",
            "selection_policy": "No single solution is automatically selected. Academic staff inspect the nondominated alternatives and choose an allocation according to the academic context.",
            "project_pool_policy": project_selection_note,
            "allocation_count_note": "discovered_unique_allocation_count is the number of unique allocations discovered at the same objective point; it is not the exact number of all possible allocations at that point.",
            "team_size_note": (
                f"The target team size is {students_per_team}. One smaller remainder team of {remainder} student(s) is permitted and its project is considered during optimization."
                if remainder > 0
                else f"All teams contain the staff-configured target size of {students_per_team} students."
            ),
            "integrity_note": "Every returned solution is checked for complete student coverage, uniqueness, selected-project uniqueness, and team-size consistency.",
        },
    }
