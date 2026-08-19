from typing import Dict, List

from app.models.cohort_import import CohortImportData
from app.services.team_formation_objectives import (
    calculate_project_technical_coverage,
)


def _round_metric(value: float) -> float:
    return round(float(value), 12)


def analyze_topic_technical_feasibility(
    data: CohortImportData,
    project_id: str,
    team_student_ids: List[str],
) -> Dict:
    normalized_project_id = project_id.strip()

    project_lookup = {
        project.project_id: project
        for project in data.projects
    }

    if normalized_project_id not in project_lookup:
        raise ValueError(
            f"Unknown project ID '{normalized_project_id}'."
        )

    cleaned_team = [
        student_id.strip()
        for student_id in team_student_ids
        if student_id and student_id.strip()
    ]

    if not cleaned_team:
        raise ValueError(
            "At least one student ID is required "
            "for topic feasibility analysis."
        )

    if len(cleaned_team) != len(set(cleaned_team)):
        raise ValueError(
            "The team contains duplicate student IDs."
        )

    student_lookup = {
        student.student_id: student
        for student in data.students
    }

    unknown_students = sorted(
        student_id
        for student_id in cleaned_team
        if student_id not in student_lookup
    )

    if unknown_students:
        raise ValueError(
            "Unknown student ID(s): "
            + ", ".join(unknown_students)
        )

    project = project_lookup[
        normalized_project_id
    ]

    technical_result = (
        calculate_project_technical_coverage(
            data=data,
            project_id=normalized_project_id,
            team=cleaned_team,
        )
    )

    requirement_results = []
    covered_requirement_count = 0

    for requirement in (
        technical_result["requirements"]
    ):
        technology = (
            requirement["technology"]
        )

        min_level = (
            requirement["min_level"]
        )

        required_members = (
            requirement["required_members"]
        )

        qualified_members = (
            requirement["qualified_members"]
        )

        coverage = float(
            requirement["coverage"]
        )

        gap_members = max(
            0,
            required_members
            - qualified_members,
        )

        if coverage >= 1.0:
            status = "Covered"
            covered_requirement_count += 1
        else:
            status = "Gap"

        student_evidence = []

        for student_id in cleaned_team:
            student = student_lookup[
                student_id
            ]

            skill_level = int(
                student.skills.get(
                    technology,
                    0,
                )
            )

            student_evidence.append(
                {
                    "student_id": (
                        student_id
                    ),
                    "skill_level": (
                        skill_level
                    ),
                    "qualifies": (
                        skill_level
                        >= min_level
                    ),
                }
            )

        requirement_results.append(
            {
                "technology": (
                    technology
                ),
                "min_level": (
                    min_level
                ),
                "required_members": (
                    required_members
                ),
                "qualified_members": (
                    qualified_members
                ),
                "qualified_students": (
                    requirement[
                        "qualified_students"
                    ]
                ),
                "gap_members": (
                    gap_members
                ),
                "coverage": (
                    _round_metric(
                        coverage
                    )
                ),
                "status": (
                    status
                ),
                "student_evidence": (
                    student_evidence
                ),
            }
        )

    requirement_count = len(
        requirement_results
    )

    gap_requirement_count = (
        requirement_count
        - covered_requirement_count
    )

    technical_coverage = (
        _round_metric(
            technical_result[
                "coverage"
            ]
        )
    )

    technical_deficit = (
        _round_metric(
            technical_result[
                "deficit"
            ]
        )
    )

    if technical_deficit <= 0.0:
        overall_status = (
            "Technically Covered"
        )
    else:
        overall_status = (
            "Technical Gaps Identified"
        )

    return {
        "project": {
            "project_id": (
                project.project_id
            ),
            "project_title": (
                project.project_title
            ),
            "expected_team_size": (
                project.team_size
            ),
            "status": (
                project.status
            ),
        },
        "team": {
            "student_ids": (
                cleaned_team
            ),
            "actual_team_size": (
                len(cleaned_team)
            ),
            "expected_team_size": (
                project.team_size
            ),
            "team_size_matches_project": (
                len(cleaned_team)
                == project.team_size
            ),
        },
        "technical_coverage": (
            technical_coverage
        ),
        "technical_deficit": (
            technical_deficit
        ),
        "status": (
            overall_status
        ),
        "requirement_summary": {
            "total_requirements": (
                requirement_count
            ),
            "covered_requirements": (
                covered_requirement_count
            ),
            "gap_requirements": (
                gap_requirement_count
            ),
        },
        "requirements": (
            requirement_results
        ),
        "interpretation": {
            "technical_coverage": (
                "The mean requirement coverage "
                "across the selected project's "
                "modeled technology requirements."
            ),
            "technical_deficit": (
                "One minus technical coverage. "
                "Lower is better; zero means all "
                "modeled technical requirements "
                "are covered."
            ),
            "scope_note": (
                "This analysis evaluates technical "
                "requirement coverage only. "
                "It does not predict grades, "
                "teamwork quality, completion, "
                "or overall project success."
            ),
        },
    }