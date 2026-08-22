from math import ceil
from typing import Dict
from app.models.cohort_import import CohortImportData

def calculate_team_configuration(student_count: int, project_count: int, students_per_team: int) -> Dict:
    if isinstance(students_per_team, bool) or not isinstance(students_per_team, int):
        raise ValueError("Students per team must be an integer.")
    if students_per_team < 2:
        raise ValueError("Students per team must be at least 2.")
    if student_count < 1:
        raise ValueError("At least one student is required for team formation.")
    full_team_count = student_count // students_per_team
    remainder_students = student_count % students_per_team
    required_team_count = ceil(student_count / students_per_team)
    if project_count != required_team_count:
        raise ValueError(
            f"The cohort contains {student_count} students and the target team size is "
            f"{students_per_team}, so {required_team_count} project teams are required. "
            f"The workbook currently contains {project_count} approved projects."
        )
    return {
        "student_count": student_count,
        "target_team_size": students_per_team,
        "full_team_count": full_team_count,
        "remainder_students": remainder_students,
        "required_team_count": required_team_count,
        "has_remainder_team": remainder_students > 0,
        "small_remainder_warning": remainder_students == 1,
    }

def apply_team_size_configuration(
    data: CohortImportData,
    students_per_team: int,
    remainder_project_id: str | None = None,
) -> CohortImportData:
    configured = data.model_copy(deep=True)
    configuration = calculate_team_configuration(
        student_count=len(configured.students),
        project_count=len(configured.projects),
        students_per_team=students_per_team,
    )
    remainder = configuration["remainder_students"]
    valid_project_ids = {project.project_id for project in configured.projects}
    if remainder > 0:
        if remainder_project_id is None:
            remainder_project_id = configured.projects[-1].project_id
        if remainder_project_id not in valid_project_ids:
            raise ValueError(f"Unknown remainder-team project '{remainder_project_id}'.")
    for project in configured.projects:
        project.team_size = (
            remainder
            if remainder > 0 and project.project_id == remainder_project_id
            else students_per_team
        )
    return configured
