from collections import Counter
from typing import Dict
from app.models.cohort_import import CohortImportData

def verify_solution_integrity(data: CohortImportData, solution: Dict) -> Dict:
    expected_student_ids = {student.student_id for student in data.students}
    expected_project_ids = {project.project_id for project in data.projects}
    teams = solution.get("teams", [])
    assigned_student_ids = []
    returned_project_ids = []
    team_size_violations = []
    for team in teams:
        project_id = team.get("project_id")
        returned_project_ids.append(project_id)
        students = team.get("students", [])
        student_ids = [student.get("student_id") for student in students]
        assigned_student_ids.extend(student_ids)
        expected_size = int(team.get("team_size", 0))
        actual_size = len(student_ids)
        if actual_size != expected_size:
            team_size_violations.append({
                "project_id": project_id,
                "expected_size": expected_size,
                "actual_size": actual_size,
            })
    student_counts = Counter(assigned_student_ids)
    project_counts = Counter(returned_project_ids)
    duplicate_student_ids = sorted(
        student_id for student_id, count in student_counts.items()
        if student_id is not None and count > 1
    )
    duplicate_project_ids = sorted(
        project_id for project_id, count in project_counts.items()
        if project_id is not None and count > 1
    )
    assigned_student_set = {student_id for student_id in assigned_student_ids if student_id is not None}
    returned_project_set = {project_id for project_id in returned_project_ids if project_id is not None}
    missing_student_ids = sorted(expected_student_ids - assigned_student_set)
    unexpected_student_ids = sorted(assigned_student_set - expected_student_ids)
    missing_project_ids = sorted(expected_project_ids - returned_project_set)
    unexpected_project_ids = sorted(returned_project_set - expected_project_ids)
    valid = (
        len(teams) == len(expected_project_ids)
        and len(assigned_student_ids) == len(expected_student_ids)
        and len(assigned_student_set) == len(expected_student_ids)
        and not duplicate_student_ids
        and not missing_student_ids
        and not unexpected_student_ids
        and not duplicate_project_ids
        and not missing_project_ids
        and not unexpected_project_ids
        and not team_size_violations
    )
    return {
        "valid": valid,
        "expected_students": len(expected_student_ids),
        "assigned_student_entries": len(assigned_student_ids),
        "unique_assigned_students": len(assigned_student_set),
        "duplicate_student_count": len(duplicate_student_ids),
        "missing_student_count": len(missing_student_ids),
        "unexpected_student_count": len(unexpected_student_ids),
        "expected_teams": len(expected_project_ids),
        "returned_teams": len(teams),
        "duplicate_project_count": len(duplicate_project_ids),
        "missing_project_count": len(missing_project_ids),
        "unexpected_project_count": len(unexpected_project_ids),
        "team_size_violation_count": len(team_size_violations),
        "duplicate_student_ids": duplicate_student_ids[:20],
        "missing_student_ids": missing_student_ids[:20],
        "unexpected_student_ids": unexpected_student_ids[:20],
        "duplicate_project_ids": duplicate_project_ids[:20],
        "missing_project_ids": missing_project_ids[:20],
        "unexpected_project_ids": unexpected_project_ids[:20],
        "team_size_violations": team_size_violations[:20],
        "detail_lists_truncated_at": 20,
    }

def summarize_solution_integrity(solutions: list[Dict]) -> Dict:
    invalid_solution_ids = [
        solution.get("solution_id")
        for solution in solutions
        if not solution.get("integrity", {}).get("valid", False)
    ]
    return {
        "solutions_checked": len(solutions),
        "all_solutions_valid": len(invalid_solution_ids) == 0,
        "invalid_solution_count": len(invalid_solution_ids),
        "invalid_solution_ids": invalid_solution_ids,
    }
