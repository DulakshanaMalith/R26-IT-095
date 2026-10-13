from pathlib import Path
from app.models.cohort_import import (
    CohortImportData,
    PreferenceInput,
    ProjectDomainInput,
    ProjectInput,
    ProjectRequirementInput,
    StudentInput,
    SupervisorDomainInput,
    SupervisorInput,
)
from app.services.excel_parser import (
    parse_domains_sheet,
    parse_preferences_sheet,
    parse_project_domains_sheet,
    parse_project_requirements_sheet,
    parse_projects_sheet,
    parse_students_sheet,
    parse_supervisor_domains_sheet,
    parse_supervisors_sheet,
)
from app.services.validation_service import (
    REQUIRED_SKILLS,
    normalize_domain_type,
    normalize_project_id,
    normalize_student_id,
    normalize_supervisor_id,
)
from app.services.workbook_validation_service import validate_workbook

def build_cohort_import_data(
    file_path: str | Path,
    students_per_team: int | None = None,
    remainder_project_id: str | None = None,
) -> CohortImportData:
    report = validate_workbook(
        file_path,
        students_per_team=students_per_team,
    )

    if not report.valid:
        raise ValueError(
            f"Workbook validation failed with "
            f"{report.summary.errors} error(s)."
        )

    student_rows = parse_students_sheet(file_path)
    preference_rows = parse_preferences_sheet(file_path)
    project_rows = parse_projects_sheet(file_path)
    requirement_rows = parse_project_requirements_sheet(file_path)
    domain_rows = parse_domains_sheet(file_path)
    project_domain_rows = parse_project_domains_sheet(file_path)
    supervisor_rows = parse_supervisors_sheet(file_path)
    supervisor_domain_rows = parse_supervisor_domains_sheet(file_path)

    students = []

    for row in student_rows:
        student_id = normalize_student_id(
            row.values.get("StudentID")
        )

        skills = {
            skill: int(row.values.get(skill))
            for skill in REQUIRED_SKILLS
        }

        students.append(
            StudentInput(
                student_id=student_id,
                skills=skills,
            )
        )

    preferences = []

    for row in preference_rows:
        student_id = normalize_student_id(
            row.values.get("StudentID")
        )

        ranked_projects = []

        for rank in range(1, 4):
            project_id = normalize_project_id(
                row.values.get(
                    f"Preference{rank}"
                )
            )

            if project_id:
                ranked_projects.append(
                    project_id
                )

        preferences.append(
            PreferenceInput(
                student_id=student_id,
                ranked_projects=ranked_projects,
            )
        )

    projects = []

    for row in project_rows:
        projects.append(
            ProjectInput(
                project_id=normalize_project_id(
                    row.values.get("ProjectID")
                ),
                project_title=str(
                    row.values.get("ProjectTitle")
                ).strip(),
                team_size=(
                    students_per_team
                    if students_per_team is not None
                    else int(row.values.get("TeamSize"))
                ),
                status=str(
                    row.values.get("Status")
                    or "Approved"
                ).strip(),
            )
        )

    project_requirements = []

    for row in requirement_rows:
        project_requirements.append(
            ProjectRequirementInput(
                project_id=normalize_project_id(
                    row.values.get("ProjectID")
                ),
                technology=str(
                    row.values.get("Technology")
                ).strip(),
                min_level=int(
                    row.values.get("MinLevel")
                ),
                required_members=int(
                    row.values.get(
                        "RequiredMembers"
                    )
                ),
            )
        )

    project_domains = []

    for row in project_domain_rows:
        project_domains.append(
            ProjectDomainInput(
                project_id=normalize_project_id(
                    row.values.get("ProjectID")
                ),
                domain=str(
                    row.values.get("Domain")
                ).strip(),
            )
        )

    supervisors = []

    for row in supervisor_rows:
        supervisors.append(
            SupervisorInput(
                supervisor_id=normalize_supervisor_id(
                    row.values.get(
                        "SupervisorID"
                    )
                ),
                supervisor_name=str(
                    row.values.get(
                        "SupervisorName"
                    )
                ).strip(),
                maximum_teams=int(
                    row.values.get(
                        "MaximumTeams"
                    )
                ),
                current_load=int(
                    row.values.get(
                        "CurrentLoad"
                    )
                ),
            )
        )

    supervisor_domains = []

    for row in supervisor_domain_rows:
        normalized_type = normalize_domain_type(
            row.values.get("Type")
        )

        domain_type = (
            "Expertise"
            if normalized_type == "expertise"
            else "Interest"
        )

        supervisor_domains.append(
            SupervisorDomainInput(
                supervisor_id=normalize_supervisor_id(
                    row.values.get(
                        "SupervisorID"
                    )
                ),
                type=domain_type,
                domain=str(
                    row.values.get("Domain")
                ).strip(),
            )
        )

    domains = [
        str(row.values.get("Domain")).strip()
        for row in domain_rows
    ]

    data = CohortImportData(
        students=students,
        preferences=preferences,
        projects=projects,
        project_requirements=project_requirements,
        project_domains=project_domains,
        supervisors=supervisors,
        supervisor_domains=supervisor_domains,
        domains=domains,
    )
    if students_per_team is not None:
        from app.services.team_size_configuration_service import apply_team_size_configuration
        data = apply_team_size_configuration(
            data=data,
            students_per_team=students_per_team,
            remainder_project_id=remainder_project_id,
        )
    return data