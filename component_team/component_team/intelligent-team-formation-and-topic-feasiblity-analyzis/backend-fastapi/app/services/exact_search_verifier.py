from itertools import combinations
from math import factorial
from typing import Dict, Generator, List, Tuple
from app.models.cohort_import import CohortImportData
from app.services.team_formation_objectives import (
    TeamAssignment,
    evaluate_assignment,
)

ObjectivePoint = Tuple[float, float]

def calculate_number_of_allocations(
    data: CohortImportData,
) -> int:
    student_count = len(data.students)
    team_sizes = [
        project.team_size
        for project in data.projects
    ]

    if sum(team_sizes) != student_count:
        raise ValueError(
            "The total project team size does not equal "
            "the number of students."
        )

    result = factorial(student_count)

    for team_size in team_sizes:
        result //= factorial(team_size)

    return result

def generate_all_assignments(
    data: CohortImportData,
) -> Generator[TeamAssignment, None, None]:
    project_ids = [
        project.project_id
        for project in data.projects
    ]

    team_sizes = {
        project.project_id: project.team_size
        for project in data.projects
    }

    student_ids = tuple(
        student.student_id
        for student in data.students
    )

    if sum(team_sizes.values()) != len(student_ids):
        raise ValueError(
            "The total project team size does not equal "
            "the number of students."
        )

    def assign_project(
        project_index: int,
        remaining_students: Tuple[str, ...],
        current_assignment: TeamAssignment,
    ) -> Generator[TeamAssignment, None, None]:
        project_id = project_ids[project_index]

        if project_index == len(project_ids) - 1:
            expected_size = team_sizes[project_id]

            if len(remaining_students) != expected_size:
                return

            final_assignment = {
                key: list(value)
                for key, value in current_assignment.items()
            }

            final_assignment[project_id] = list(
                remaining_students
            )

            yield final_assignment
            return

        team_size = team_sizes[project_id]

        for selected_team in combinations(
            remaining_students,
            team_size,
        ):
            selected_set = set(selected_team)

            new_remaining = tuple(
                student_id
                for student_id in remaining_students
                if student_id not in selected_set
            )

            current_assignment[project_id] = list(
                selected_team
            )

            yield from assign_project(
                project_index + 1,
                new_remaining,
                current_assignment,
            )

            del current_assignment[project_id]

    if not project_ids:
        return

    yield from assign_project(
        project_index=0,
        remaining_students=student_ids,
        current_assignment={},
    )

def dominates(
    point_a: ObjectivePoint,
    point_b: ObjectivePoint,
) -> bool:
    a_f1, a_f2 = point_a
    b_f1, b_f2 = point_b

    no_worse = (
        a_f1 <= b_f1
        and a_f2 <= b_f2
    )

    strictly_better = (
        a_f1 < b_f1
        or a_f2 < b_f2
    )

    return no_worse and strictly_better

def update_pareto_front(
    pareto_front: Dict[
        ObjectivePoint,
        Dict,
    ],
    point: ObjectivePoint,
    assignment: TeamAssignment,
) -> None:
    for existing_point in list(
        pareto_front.keys()
    ):
        if dominates(
            existing_point,
            point,
        ):
            return

    dominated_points = [
        existing_point
        for existing_point in pareto_front
        if dominates(
            point,
            existing_point,
        )
    ]

    for dominated_point in dominated_points:
        del pareto_front[dominated_point]

    if point in pareto_front:
        pareto_front[point][
            "allocation_count"
        ] += 1
        return

    pareto_front[point] = {
        "technical_requirement_deficit": point[0],
        "preference_dissatisfaction": point[1],
        "allocation_count": 1,
        "example_assignment": {
            project_id: list(team)
            for project_id, team in assignment.items()
        },
    }

def find_exact_pareto_front(
    data: CohortImportData,
    progress_interval: int = 5000,
) -> Dict:
    expected_allocations = (
        calculate_number_of_allocations(data)
    )

    pareto_front: Dict[
        ObjectivePoint,
        Dict,
    ] = {}

    evaluated = 0

    best_technical_deficit = 1.0
    best_preference_dissatisfaction = 1.0

    for assignment in generate_all_assignments(
        data
    ):
        result = evaluate_assignment(
            data=data,
            assignment=assignment,
        )

        technical_deficit = round(
            result[
                "technical_requirement_deficit"
            ],
            12,
        )

        preference_dissatisfaction = round(
            result[
                "preference_dissatisfaction"
            ],
            12,
        )

        point = (
            technical_deficit,
            preference_dissatisfaction,
        )

        update_pareto_front(
            pareto_front=pareto_front,
            point=point,
            assignment=assignment,
        )

        best_technical_deficit = min(
            best_technical_deficit,
            technical_deficit,
        )

        best_preference_dissatisfaction = min(
            best_preference_dissatisfaction,
            preference_dissatisfaction,
        )

        evaluated += 1

        if (
            progress_interval > 0
            and evaluated % progress_interval == 0
        ):
            print(
                f"Evaluated {evaluated:,} / "
                f"{expected_allocations:,} allocations..."
            )

    sorted_front = sorted(
        pareto_front.values(),
        key=lambda item: (
            item[
                "technical_requirement_deficit"
            ],
            item[
                "preference_dissatisfaction"
            ],
        ),
    )

    return {
        "expected_allocations": (
            expected_allocations
        ),
        "evaluated_allocations": evaluated,
        "pareto_point_count": len(
            sorted_front
        ),
        "best_technical_deficit": (
            best_technical_deficit
        ),
        "best_preference_dissatisfaction": (
            best_preference_dissatisfaction
        ),
        "pareto_front": sorted_front,
    }