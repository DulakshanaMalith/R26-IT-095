from typing import List
from app.models.cohort_import import ParsedRow, ValidationIssue

REQUIRED_SKILLS = [
    "React",
    "HTML_CSS",
    "Angular",
    "Vue",
    "NodeJS",
    "Express",
    "Java",
    "PHP",
    "FastAPI",
    "MongoDB",
    "MySQL",
    "PostgreSQL",
    "Firebase",
    "Python",
    "TensorFlow",
    "Pandas",
]

def normalize_student_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()

def normalize_project_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()

def validate_students(
    rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_student_ids = {}

    for row in rows:
        values = row.values
        raw_student_id = values.get("StudentID")
        student_id = normalize_student_id(raw_student_id)

        if not student_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="STUDENT_ID_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="StudentID",
                    message="StudentID must not be blank.",
                )
            )
        elif student_id in seen_student_ids:
            first_row = seen_student_ids[student_id]
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="STUDENT_DUPLICATE_ID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="StudentID",
                    message=(
                        f"StudentID '{student_id}' is duplicated. "
                        f"It already appears in row {first_row}."
                    ),
                )
            )
        else:
            seen_student_ids[student_id] = row.row_number

        for skill in REQUIRED_SKILLS:
            value = values.get(skill)

            if value is None or (
                isinstance(value, str)
                and value.strip() == ""
            ):
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="SKILL_MISSING",
                        sheet=row.sheet,
                        row=row.row_number,
                        field=skill,
                        message=(
                            f"Competency rating for {skill} is required."
                        ),
                    )
                )
                continue

            if isinstance(value, bool) or not isinstance(value, int):
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="SKILL_NOT_INTEGER",
                        sheet=row.sheet,
                        row=row.row_number,
                        field=skill,
                        message=(
                            f"Expected an integer between 1 and 5 "
                            f"for {skill}, but received '{value}'."
                        ),
                    )
                )
                continue

            if value < 1 or value > 5:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="SKILL_OUT_OF_RANGE",
                        sheet=row.sheet,
                        row=row.row_number,
                        field=skill,
                        message=(
                            f"Expected a competency level between "
                            f"1 and 5 for {skill}, but received {value}."
                        ),
                    )
                )

    return issues

def validate_projects(
    rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_project_ids = {}

    for row in rows:
        values = row.values
        project_id = normalize_project_id(
            values.get("ProjectID")
        )
        title = values.get("ProjectTitle")
        team_size = values.get("TeamSize")

        if not project_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_ID_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="ProjectID",
                    message="ProjectID must not be blank.",
                )
            )
        elif project_id in seen_project_ids:
            first_row = seen_project_ids[project_id]
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_DUPLICATE_ID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="ProjectID",
                    message=(
                        f"ProjectID '{project_id}' is duplicated. "
                        f"It already appears in row {first_row}."
                    ),
                )
            )
        else:
            seen_project_ids[project_id] = row.row_number

        if title is None or str(title).strip() == "":
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_TITLE_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="ProjectTitle",
                    message="ProjectTitle must not be blank.",
                )
            )

        if (
            isinstance(team_size, bool)
            or not isinstance(team_size, int)
            or team_size <= 0
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_TEAM_SIZE_INVALID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="TeamSize",
                    message="TeamSize must be a positive integer.",
                )
            )

    return issues

def validate_project_requirements(
    requirement_rows: List[ParsedRow],
    project_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    project_team_sizes = {}

    for row in project_rows:
        project_id = normalize_project_id(
            row.values.get("ProjectID")
        )
        team_size = row.values.get("TeamSize")

        if project_id:
            project_team_sizes[project_id] = team_size

    seen_requirements = set()

    for row in requirement_rows:
        values = row.values

        project_id = normalize_project_id(
            values.get("ProjectID")
        )

        technology = values.get("Technology")

        technology_name = (
            str(technology).strip()
            if technology is not None
            else ""
        )

        min_level = values.get("MinLevel")
        required_members = values.get("RequiredMembers")

        if project_id not in project_team_sizes:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="REQUIREMENT_PROJECT_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="ProjectID",
                    message=(
                        f"Project '{project_id}' does not exist."
                    ),
                )
            )

        if technology_name not in REQUIRED_SKILLS:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="REQUIREMENT_TECH_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Technology",
                    message=(
                        f"Technology '{technology_name}' "
                        "is not part of the defined skill catalog."
                    ),
                )
            )

        requirement_key = (
            project_id,
            technology_name,
        )

        if requirement_key in seen_requirements:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="REQUIREMENT_DUPLICATE",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Technology",
                    message=(
                        f"Requirement '{project_id} + "
                        f"{technology_name}' is duplicated."
                    ),
                )
            )
        else:
            seen_requirements.add(requirement_key)

        if (
            isinstance(min_level, bool)
            or not isinstance(min_level, int)
            or min_level < 2
            or min_level > 5
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="REQUIREMENT_MINLEVEL_RANGE",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="MinLevel",
                    message=(
                        "MinLevel must be an integer between 2 and 5."
                    ),
                )
            )

        if (
            isinstance(required_members, bool)
            or not isinstance(required_members, int)
            or required_members < 1
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="REQUIREMENT_MEMBERS_INVALID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="RequiredMembers",
                    message=(
                        "RequiredMembers must be a positive integer."
                    ),
                )
            )
        elif project_id in project_team_sizes:
            team_size = project_team_sizes[project_id]

            if (
                isinstance(team_size, int)
                and required_members > team_size
            ):
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="REQUIREMENT_MEMBERS_INVALID",
                        sheet=row.sheet,
                        row=row.row_number,
                        field="RequiredMembers",
                        message=(
                            f"Project {project_id} has a team size "
                            f"of {team_size}, but requires "
                            f"{required_members} members for "
                            f"{technology_name}."
                        ),
                    )
                )

    return issues