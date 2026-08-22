from time import perf_counter
from typing import Dict, List, Tuple
from app.models.cohort_import import CohortImportData
from app.services.nsga2_optimizer import optimize_team_formation
from app.services.solution_integrity_service import (
    summarize_solution_integrity,
    verify_solution_integrity,
)
from app.services.team_formation_response_service import build_staff_team_formation_response
from app.services.team_size_configuration_service import (
    apply_team_size_configuration,
    calculate_team_configuration,
)

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
) -> Dict:
    pipeline_start = perf_counter()
    configuration = calculate_team_configuration(
        student_count=len(data.students),
        project_count=len(data.projects),
        students_per_team=students_per_team,
    )
    remainder = configuration["remainder_students"]
    candidate_project_ids: List[str | None]
    if remainder > 0:
        candidate_project_ids = [project.project_id for project in data.projects]
    else:
        candidate_project_ids = [None]
    all_solutions = []
    total_evaluations = 0
    total_archive_chromosomes = 0
    seeded_individual_count = 0
    optimizer_seconds = 0.0
    response_build_seconds = 0.0
    configuration_seconds = 0.0
    candidate_timings = []
    for candidate_index, remainder_project_id in enumerate(candidate_project_ids):
        candidate_start = perf_counter()
        configuration_start = perf_counter()
        configured_data = apply_team_size_configuration(
            data=data,
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
            seed=seed + candidate_index,
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
            all_solutions.append(enriched)
        candidate_timings.append({
            "remainder_project_id": remainder_project_id,
            "configuration_seconds": candidate_configuration_seconds,
            "optimizer_seconds": candidate_optimizer_seconds,
            "response_build_seconds": candidate_response_seconds,
            "total_candidate_seconds": _seconds(candidate_start),
        })
    postprocess_start = perf_counter()
    point_examples: Dict[Tuple[float, float], Dict] = {}
    point_allocations: Dict[Tuple[float, float], set] = {}
    point_discovered_counts: Dict[Tuple[float, float], int] = {}
    for solution in all_solutions:
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
    integrity_start = perf_counter()
    for solution in solutions:
        solution["integrity"] = verify_solution_integrity(data=data, solution=solution)
    integrity_summary = summarize_solution_integrity(solutions)
    integrity_seconds = _seconds(integrity_start)
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
        "remainder_candidate_runs": len(candidate_project_ids),
    }
    runtime = {
        "configuration_seconds": round(configuration_seconds, 4),
        "optimizer_seconds": round(optimizer_seconds, 4),
        "response_build_seconds": round(response_build_seconds, 4),
        "global_postprocessing_seconds": postprocessing_seconds,
        "integrity_check_seconds": integrity_seconds,
        "total_pipeline_seconds": _seconds(pipeline_start),
        "candidate_run_count": len(candidate_project_ids),
        "candidate_timings": candidate_timings,
    }
    return {
        "optimizer": optimizer_metadata,
        "solution_count": len(solutions),
        "solutions": solutions,
        "integrity_summary": integrity_summary,
        "runtime": runtime,
        "team_configuration": {
            **configuration,
            "remainder_strategy": (
                "Every approved project was evaluated as the possible smaller-team project, then the discovered solutions were globally filtered for nondominance."
                if remainder > 0
                else "No remainder team was required."
            ),
            "remainder_candidate_runs": len(candidate_project_ids),
        },
        "interpretation": {
            "technical_requirement_deficit": "Lower is better. Zero means all modeled project technical requirements are fully covered.",
            "preference_dissatisfaction": "Lower is better. Zero means every student is assigned to their first-ranked project.",
            "selection_policy": "No single solution is automatically selected. Academic staff inspect the Pareto alternatives and choose an allocation according to the academic context.",
            "allocation_count_note": "discovered_unique_allocation_count is the number of unique allocations discovered at the same objective point; it is not the exact number of all possible allocations at that point.",
            "team_size_note": (
                f"The target team size is {students_per_team}. One smaller remainder team of {remainder} student(s) is permitted and its project is considered during optimization."
                if remainder > 0
                else f"All teams contain the staff-configured target size of {students_per_team} students."
            ),
            "integrity_note": "Every returned solution is automatically checked for complete student coverage, uniqueness, project coverage, and team-size consistency.",
        },
    }
