from typing import Dict, List
from app.models.cohort_import import CohortImportData

TeamAssignment = Dict[str, List[str]]

def validate_assignment(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> None:
    expected_projects = {
        project.project_id: project.team_size
        for project in data.projects
    }

    valid_students = {
        student.student_id
        for student in data.students
    }

    assignment_projects = set(
        assignment.keys()
    )

    expected_project_ids = set(
        expected_projects.keys()
    )

    missing_projects = (
        expected_project_ids
        - assignment_projects
    )

    unknown_projects = (
        assignment_projects
        - expected_project_ids
    )

    if missing_projects:
        raise ValueError(
            "Assignment is missing projects: "
            + ", ".join(
                sorted(missing_projects)
            )
        )

    if unknown_projects:
        raise ValueError(
            "Assignment contains unknown projects: "
            + ", ".join(
                sorted(unknown_projects)
            )
        )

    assigned_students = []

    for project_id, team in assignment.items():
        expected_size = expected_projects[
            project_id
        ]

        if len(team) != expected_size:
            raise ValueError(
                f"Project '{project_id}' requires "
                f"{expected_size} students, "
                f"but received {len(team)}."
            )

        for student_id in team:
            if student_id not in valid_students:
                raise ValueError(
                    f"Unknown student "
                    f"'{student_id}' assigned "
                    f"to project '{project_id}'."
                )

            assigned_students.append(
                student_id
            )

    if (
        len(assigned_students)
        != len(set(assigned_students))
    ):
        raise ValueError(
            "A student appears more than once "
            "in the assignment."
        )

    missing_students = (
        valid_students
        - set(assigned_students)
    )

    if missing_students:
        raise ValueError(
            "The following students are "
            "not assigned: "
            + ", ".join(
                sorted(missing_students)
            )
        )

def calculate_project_technical_coverage(
    data: CohortImportData,
    project_id: str,
    team: List[str],
) -> Dict:
    student_lookup = {
        student.student_id: student
        for student in data.students
    }

    requirements = [
        requirement
        for requirement
        in data.project_requirements
        if requirement.project_id
        == project_id
    ]

    if not requirements:
        raise ValueError(
            f"Project '{project_id}' "
            f"has no technical requirements."
        )

    requirement_results = []
    coverage_values = []

    for requirement in requirements:
        qualified_students = []

        for student_id in team:
            student = student_lookup[
                student_id
            ]

            skill_level = (
                student.skills.get(
                    requirement.technology,
                    0,
                )
            )

            if (
                skill_level
                >= requirement.min_level
            ):
                qualified_students.append(
                    student_id
                )

        qualified_count = len(
            qualified_students
        )

        coverage = min(
            1.0,
            qualified_count
            / requirement.required_members,
        )

        coverage_values.append(
            coverage
        )

        requirement_results.append(
            {
                "technology": (
                    requirement.technology
                ),
                "min_level": (
                    requirement.min_level
                ),
                "required_members": (
                    requirement.required_members
                ),
                "qualified_members": (
                    qualified_count
                ),
                "qualified_students": (
                    qualified_students
                ),
                "coverage": coverage,
            }
        )

    project_coverage = (
        sum(coverage_values)
        / len(coverage_values)
    )

    project_deficit = (
        1.0
        - project_coverage
    )

    return {
        "project_id": project_id,
        "coverage": project_coverage,
        "deficit": project_deficit,
        "requirements": (
            requirement_results
        ),
    }

def calculate_technical_requirement_deficit(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> Dict:
    project_results = []
    project_deficits = []

    for project in data.projects:
        project_id = (
            project.project_id
        )

        team = assignment[
            project_id
        ]

        result = (
            calculate_project_technical_coverage(
                data=data,
                project_id=project_id,
                team=team,
            )
        )

        project_results.append(
            result
        )

        project_deficits.append(
            result["deficit"]
        )

    overall_deficit = (
        sum(project_deficits)
        / len(project_deficits)
    )

    return {
        "technical_requirement_deficit": (
            overall_deficit
        ),
        "technical_requirement_coverage": (
            1.0
            - overall_deficit
        ),
        "projects": project_results,
    }

def calculate_rank_dissatisfaction(
    rank: int,
    ranked_project_count: int,
    total_project_count: int,
) -> float:
    if total_project_count <= 1:
        return 0.0

    if ranked_project_count <= 0:
        return 1.0

    if ranked_project_count >= total_project_count:
        return (
            (rank - 1)
            / (total_project_count - 1)
        )

    return (
        (rank - 1)
        / ranked_project_count
    )

def calculate_preference_dissatisfaction(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> Dict:
    preference_lookup = {
        preference.student_id:
        preference.ranked_projects
        for preference in data.preferences
    }

    project_count = len(
        data.projects
    )

    student_results = []
    dissatisfaction_values = []

    student_project_lookup = {}

    for (
        project_id,
        team,
    ) in assignment.items():
        for student_id in team:
            student_project_lookup[
                student_id
            ] = project_id

    for student in data.students:
        student_id = (
            student.student_id
        )

        assigned_project = (
            student_project_lookup[
                student_id
            ]
        )

        ranked_projects = (
            preference_lookup.get(
                student_id,
                [],
            )
        )

        ranked_project_count = len(
            ranked_projects
        )

        if (
            assigned_project
            in ranked_projects
        ):
            rank = (
                ranked_projects.index(
                    assigned_project
                )
                + 1
            )

            dissatisfaction = (
                calculate_rank_dissatisfaction(
                    rank=rank,
                    ranked_project_count=(
                        ranked_project_count
                    ),
                    total_project_count=(
                        project_count
                    ),
                )
            )
        else:
            rank = None
            dissatisfaction = 1.0

        dissatisfaction_values.append(
            dissatisfaction
        )

        student_results.append(
            {
                "student_id": student_id,
                "assigned_project": (
                    assigned_project
                ),
                "preference_rank": rank,
                "ranked_project_count": (
                    ranked_project_count
                ),
                "dissatisfaction": (
                    dissatisfaction
                ),
            }
        )

    overall_dissatisfaction = (
        sum(dissatisfaction_values)
        / len(dissatisfaction_values)
    )

    return {
        "preference_dissatisfaction": (
            overall_dissatisfaction
        ),
        "preference_satisfaction": (
            1.0
            - overall_dissatisfaction
        ),
        "students": student_results,
    }

def evaluate_assignment(
    data: CohortImportData,
    assignment: TeamAssignment,
) -> Dict:
    validate_assignment(
        data=data,
        assignment=assignment,
    )

    technical_result = (
        calculate_technical_requirement_deficit(
            data=data,
            assignment=assignment,
        )
    )

    preference_result = (
        calculate_preference_dissatisfaction(
            data=data,
            assignment=assignment,
        )
    )

    return {
        "technical_requirement_deficit": (
            technical_result[
                "technical_requirement_deficit"
            ]
        ),
        "technical_requirement_coverage": (
            technical_result[
                "technical_requirement_coverage"
            ]
        ),
        "preference_dissatisfaction": (
            preference_result[
                "preference_dissatisfaction"
            ]
        ),
        "preference_satisfaction": (
            preference_result[
                "preference_satisfaction"
            ]
        ),
        "project_results": (
            technical_result[
                "projects"
            ]
        ),
        "student_preference_results": (
            preference_result[
                "students"
            ]
        ),
    }