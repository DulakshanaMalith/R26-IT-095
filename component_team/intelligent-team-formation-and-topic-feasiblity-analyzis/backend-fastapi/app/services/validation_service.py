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

def normalize_supervisor_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()

def normalize_domain(value) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()

def normalize_domain_type(value) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()

def validate_students(rows: List[ParsedRow]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_student_ids = {}

    for row in rows:
        values = row.values
        student_id = normalize_student_id(values.get("StudentID"))

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
                        message=f"Competency rating for {skill} is required.",
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
    students_per_team: int | None = None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_project_ids = {}
    for row in rows:
        values = row.values
        project_id = normalize_project_id(values.get("ProjectID"))
        title = values.get("ProjectTitle")
        team_size = values.get("TeamSize")
        if not project_id:
            issues.append(ValidationIssue(severity="ERROR", code="PROJECT_ID_REQUIRED", sheet=row.sheet, row=row.row_number, field="ProjectID", message="ProjectID must not be blank."))
        elif project_id in seen_project_ids:
            first_row = seen_project_ids[project_id]
            issues.append(ValidationIssue(severity="ERROR", code="PROJECT_DUPLICATE_ID", sheet=row.sheet, row=row.row_number, field="ProjectID", message=f"ProjectID '{project_id}' is duplicated. It already appears in row {first_row}."))
        else:
            seen_project_ids[project_id] = row.row_number
        if title is None or str(title).strip() == "":
            issues.append(ValidationIssue(severity="ERROR", code="PROJECT_TITLE_REQUIRED", sheet=row.sheet, row=row.row_number, field="ProjectTitle", message="ProjectTitle must not be blank."))
        if students_per_team is None and (isinstance(team_size, bool) or not isinstance(team_size, int) or team_size <= 0):
            issues.append(ValidationIssue(severity="ERROR", code="PROJECT_TEAM_SIZE_INVALID", sheet=row.sheet, row=row.row_number, field="TeamSize", message="TeamSize must be a positive integer."))
    return issues

def validate_project_requirements(
    requirement_rows: List[ParsedRow],
    project_rows: List[ParsedRow],
    students_per_team: int | None = None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    project_team_sizes = {}
    for row in project_rows:
        project_id = normalize_project_id(row.values.get("ProjectID"))
        team_size = students_per_team if students_per_team is not None else row.values.get("TeamSize")
        if project_id:
            project_team_sizes[project_id] = team_size

    seen_requirements = set()

    for row in requirement_rows:
        values = row.values
        project_id = normalize_project_id(values.get("ProjectID"))
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
                    message=f"Project '{project_id}' does not exist.",
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

        requirement_key = (project_id, technology_name)

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
                    message="MinLevel must be an integer between 2 and 5.",
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
                    message="RequiredMembers must be a positive integer.",
                )
            )
        elif project_id in project_team_sizes:
            team_size = project_team_sizes[project_id]

            if (
                isinstance(team_size, int)
                and not isinstance(team_size, bool)
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

def validate_preferences(
    preference_rows: List[ParsedRow],
    student_rows: List[ParsedRow],
    project_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    valid_student_ids = {
        normalize_student_id(row.values.get("StudentID"))
        for row in student_rows
        if normalize_student_id(row.values.get("StudentID"))
    }

    valid_project_ids = {
        normalize_project_id(row.values.get("ProjectID"))
        for row in project_rows
        if normalize_project_id(row.values.get("ProjectID"))
    }

    seen_student_rows = {}
    project_count = len(valid_project_ids)
    required_preference_count = min(3, project_count)

    for row in preference_rows:
        values = row.values
        student_id = normalize_student_id(values.get("StudentID"))

        if not student_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PREFERENCE_STUDENT_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="StudentID",
                    message="StudentID must not be blank.",
                )
            )
        elif student_id not in valid_student_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PREFERENCE_STUDENT_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="StudentID",
                    message=(
                        f"Student '{student_id}' does not exist "
                        "in the Students sheet."
                    ),
                )
            )

        if student_id:
            if student_id in seen_student_rows:
                first_row = seen_student_rows[student_id]
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="PREFERENCE_ROW_DUPLICATE",
                        sheet=row.sheet,
                        row=row.row_number,
                        field="StudentID",
                        message=(
                            f"Student '{student_id}' already has "
                            f"a preference row at row {first_row}."
                        ),
                    )
                )
            else:
                seen_student_rows[student_id] = row.row_number

        ranked_projects = []

        for rank in range(1, 4):
            field_name = f"Preference{rank}"
            project_id = normalize_project_id(values.get(field_name))

            if (
                rank <= required_preference_count
                and not project_id
            ):
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="PREFERENCE_REQUIRED",
                        sheet=row.sheet,
                        row=row.row_number,
                        field=field_name,
                        message=f"{field_name} is required.",
                    )
                )
                continue

            if not project_id:
                continue

            if project_id not in valid_project_ids:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="PREFERENCE_PROJECT_UNKNOWN",
                        sheet=row.sheet,
                        row=row.row_number,
                        field=field_name,
                        message=f"Project '{project_id}' does not exist.",
                    )
                )

            if project_id in ranked_projects:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="PREFERENCE_DUPLICATE_PROJECT",
                        sheet=row.sheet,
                        row=row.row_number,
                        field=field_name,
                        message=(
                            f"Project '{project_id}' appears more "
                            "than once in this student's preferences."
                        ),
                    )
                )
            else:
                ranked_projects.append(project_id)

    preference_student_ids = set(seen_student_rows.keys())

    for student_id in valid_student_ids:
        if student_id not in preference_student_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PREFERENCE_ROW_MISSING",
                    sheet="Preferences",
                    row=None,
                    field="StudentID",
                    message=(
                        f"Student '{student_id}' does not have "
                        "a preference row."
                    ),
                )
            )

    return issues

def validate_domains(
    domain_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_domains = {}

    for row in domain_rows:
        raw_domain = row.values.get("Domain")
        domain = normalize_domain(raw_domain)

        if not domain:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="DOMAIN_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Domain",
                    message="Domain must not be blank.",
                )
            )
            continue

        if domain in seen_domains:
            first_row = seen_domains[domain]
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="DOMAIN_DUPLICATE",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Domain",
                    message=(
                        f"Domain '{raw_domain}' is duplicated. "
                        f"It already appears in row {first_row}."
                    ),
                )
            )
        else:
            seen_domains[domain] = row.row_number

    return issues

def validate_project_domains(
    project_domain_rows: List[ParsedRow],
    project_rows: List[ParsedRow],
    domain_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    valid_project_ids = {
        normalize_project_id(row.values.get("ProjectID"))
        for row in project_rows
        if normalize_project_id(row.values.get("ProjectID"))
    }

    valid_domains = {
        normalize_domain(row.values.get("Domain"))
        for row in domain_rows
        if normalize_domain(row.values.get("Domain"))
    }

    seen_project_domains = set()
    projects_with_domains = set()

    for row in project_domain_rows:
        project_id = normalize_project_id(
            row.values.get("ProjectID")
        )
        raw_domain = row.values.get("Domain")
        domain = normalize_domain(raw_domain)

        if project_id not in valid_project_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_DOMAIN_PROJECT_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="ProjectID",
                    message=f"Project '{project_id}' does not exist.",
                )
            )

        if not domain:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_DOMAIN_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Domain",
                    message="Domain must not be blank.",
                )
            )
        elif domain not in valid_domains:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_DOMAIN_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Domain",
                    message=(
                        f"Domain '{raw_domain}' does not exist "
                        "in the controlled Domains sheet."
                    ),
                )
            )

        key = (project_id, domain)

        if project_id and domain:
            if key in seen_project_domains:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="PROJECT_DOMAIN_DUPLICATE",
                        sheet=row.sheet,
                        row=row.row_number,
                        field="Domain",
                        message=(
                            f"Project '{project_id}' already has "
                            f"domain '{raw_domain}'."
                        ),
                    )
                )
            else:
                seen_project_domains.add(key)

            if (
                project_id in valid_project_ids
                and domain in valid_domains
            ):
                projects_with_domains.add(project_id)

    for project_id in valid_project_ids:
        if project_id not in projects_with_domains:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="PROJECT_DOMAIN_MISSING",
                    sheet="ProjectDomains",
                    row=None,
                    field="ProjectID",
                    message=(
                        f"Project '{project_id}' does not have "
                        "any valid assigned domain."
                    ),
                )
            )

    return issues

def validate_supervisors(
    supervisor_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_supervisor_ids = {}

    for row in supervisor_rows:
        values = row.values
        supervisor_id = normalize_supervisor_id(
            values.get("SupervisorID")
        )
        supervisor_name = values.get("SupervisorName")
        maximum_teams = values.get("MaximumTeams")
        current_load = values.get("CurrentLoad")

        if not supervisor_id:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_ID_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="SupervisorID",
                    message="SupervisorID must not be blank.",
                )
            )
        elif supervisor_id in seen_supervisor_ids:
            first_row = seen_supervisor_ids[supervisor_id]
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_DUPLICATE_ID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="SupervisorID",
                    message=(
                        f"SupervisorID '{supervisor_id}' "
                        f"is duplicated. It already appears "
                        f"in row {first_row}."
                    ),
                )
            )
        else:
            seen_supervisor_ids[supervisor_id] = row.row_number

        if (
            supervisor_name is None
            or str(supervisor_name).strip() == ""
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_NAME_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="SupervisorName",
                    message="SupervisorName must not be blank.",
                )
            )

        if (
            isinstance(maximum_teams, bool)
            or not isinstance(maximum_teams, int)
            or maximum_teams <= 0
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_MAXIMUM_TEAMS_INVALID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="MaximumTeams",
                    message="MaximumTeams must be a positive integer.",
                )
            )

        if (
            isinstance(current_load, bool)
            or not isinstance(current_load, int)
            or current_load < 0
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_LOAD_INVALID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="CurrentLoad",
                    message=(
                        "CurrentLoad must be an integer "
                        "greater than or equal to 0."
                    ),
                )
            )
        elif (
            isinstance(maximum_teams, int)
            and not isinstance(maximum_teams, bool)
            and maximum_teams > 0
            and current_load > maximum_teams
        ):
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_LOAD_INVALID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="CurrentLoad",
                    message=(
                        f"CurrentLoad ({current_load}) cannot "
                        f"exceed MaximumTeams ({maximum_teams})."
                    ),
                )
            )

    return issues

def validate_supervisor_domains(
    supervisor_domain_rows: List[ParsedRow],
    supervisor_rows: List[ParsedRow],
    domain_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    valid_supervisor_ids = {
        normalize_supervisor_id(row.values.get("SupervisorID"))
        for row in supervisor_rows
        if normalize_supervisor_id(row.values.get("SupervisorID"))
    }

    valid_domains = {
        normalize_domain(row.values.get("Domain"))
        for row in domain_rows
        if normalize_domain(row.values.get("Domain"))
    }

    valid_types = {"expertise", "interest"}
    seen_supervisor_domains = set()
    supervisors_with_expertise = set()

    for row in supervisor_domain_rows:
        values = row.values
        supervisor_id = normalize_supervisor_id(
            values.get("SupervisorID")
        )
        raw_type = values.get("Type")
        domain_type = normalize_domain_type(raw_type)
        raw_domain = values.get("Domain")
        domain = normalize_domain(raw_domain)

        if supervisor_id not in valid_supervisor_ids:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_ID_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="SupervisorID",
                    message=(
                        f"Supervisor '{supervisor_id}' "
                        "does not exist in the Supervisors sheet."
                    ),
                )
            )

        if domain_type not in valid_types:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_DOMAIN_TYPE_INVALID",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Type",
                    message=(
                        "Type must be either "
                        "'Expertise' or 'Interest'."
                    ),
                )
            )

        if not domain:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_DOMAIN_REQUIRED",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Domain",
                    message="Domain must not be blank.",
                )
            )
        elif domain not in valid_domains:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_DOMAIN_UNKNOWN",
                    sheet=row.sheet,
                    row=row.row_number,
                    field="Domain",
                    message=(
                        f"Domain '{raw_domain}' does not exist "
                        "in the controlled Domains sheet."
                    ),
                )
            )

        key = (
            supervisor_id,
            domain_type,
            domain,
        )

        if supervisor_id and domain_type and domain:
            if key in seen_supervisor_domains:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        code="SUPERVISOR_DOMAIN_DUPLICATE",
                        sheet=row.sheet,
                        row=row.row_number,
                        field="Domain",
                        message=(
                            f"Supervisor '{supervisor_id}' "
                            f"already has '{raw_domain}' "
                            f"registered as '{raw_type}'."
                        ),
                    )
                )
            else:
                seen_supervisor_domains.add(key)

        if (
            supervisor_id in valid_supervisor_ids
            and domain_type == "expertise"
            and domain in valid_domains
        ):
            supervisors_with_expertise.add(supervisor_id)

    for supervisor_id in valid_supervisor_ids:
        if supervisor_id not in supervisors_with_expertise:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SUPERVISOR_EXPERTISE_MISSING",
                    sheet="SupervisorDomains",
                    row=None,
                    field="SupervisorID",
                    message=(
                        f"Supervisor '{supervisor_id}' "
                        "does not have any valid Expertise domain."
                    ),
                )
            )

    return issues

def validate_cohort_slots(
    student_rows: List[ParsedRow],
    project_rows: List[ParsedRow],
    students_per_team: int | None = None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    valid_student_ids = {normalize_student_id(row.values.get("StudentID")) for row in student_rows if normalize_student_id(row.values.get("StudentID"))}
    total_students = len(valid_student_ids)
    if students_per_team is not None:
        if isinstance(students_per_team, bool) or not isinstance(students_per_team, int) or students_per_team < 2:
            issues.append(ValidationIssue(severity="ERROR", code="TEAM_SIZE_CONFIGURATION_INVALID", sheet=None, row=None, field="students_per_team", message="Students per team must be an integer of at least 2."))
            return issues
        full_team_count = total_students // students_per_team
        remainder_students = total_students % students_per_team
        required_team_count = full_team_count + (1 if remainder_students else 0)
        project_count = len({normalize_project_id(row.values.get("ProjectID")) for row in project_rows if normalize_project_id(row.values.get("ProjectID"))})
        if project_count != required_team_count:
            issues.append(ValidationIssue(severity="ERROR", code="PROJECT_TEAM_COUNT_MISMATCH", sheet="Projects", row=None, field="ProjectID", message=f"The cohort contains {total_students} students and the target team size is {students_per_team}, so {required_team_count} project teams are required. The workbook contains {project_count} approved projects."))
        if remainder_students:
            message = f"The cohort is not exactly divisible by the target team size. {full_team_count} full team(s) of {students_per_team} and one remainder team of {remainder_students} student(s) will be formed."
            if remainder_students == 1:
                message += " The final team will contain only one student, so staff should confirm that this exception is acceptable."
            issues.append(ValidationIssue(severity="WARNING", code="COHORT_REMAINDER_TEAM", sheet=None, row=None, field="students_per_team", message=message))
        return issues
    total_team_slots = 0
    for row in project_rows:
        team_size = row.values.get("TeamSize")
        if isinstance(team_size, int) and not isinstance(team_size, bool) and team_size > 0:
            total_team_slots += team_size
    if total_team_slots != total_students:
        issues.append(ValidationIssue(severity="ERROR", code="COHORT_SLOT_MISMATCH", sheet="Projects", row=None, field="TeamSize", message=f"The cohort contains {total_students} unique students, but the projects provide {total_team_slots} team slots. The total number of team slots must equal the number of students being allocated."))
    return issues

def validate_technical_feasibility(
    student_rows: List[ParsedRow],
    requirement_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    for requirement in requirement_rows:
        values = requirement.values

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

        if technology_name not in REQUIRED_SKILLS:
            continue

        if (
            isinstance(min_level, bool)
            or not isinstance(min_level, int)
            or min_level < 2
            or min_level > 5
        ):
            continue

        if (
            isinstance(required_members, bool)
            or not isinstance(required_members, int)
            or required_members < 1
        ):
            continue

        qualified_students = 0

        for student in student_rows:
            skill_value = student.values.get(
                technology_name
            )

            if (
                isinstance(skill_value, int)
                and not isinstance(skill_value, bool)
                and 1 <= skill_value <= 5
                and skill_value >= min_level
            ):
                qualified_students += 1

        if qualified_students < required_members:
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    code="TECHNICALLY_IMPOSSIBLE_REQUIREMENT",
                    sheet=requirement.sheet,
                    row=requirement.row_number,
                    field="RequiredMembers",
                    message=(
                        f"Project '{project_id}' requires "
                        f"{required_members} students with "
                        f"{technology_name} competency Level "
                        f"{min_level} or above, but the entire "
                        f"cohort contains only {qualified_students} "
                        "qualified students."
                    ),
                )
            )

    return issues

def validate_supervisor_capacity(
    supervisor_rows: List[ParsedRow],
    project_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    project_ids = {
        normalize_project_id(row.values.get("ProjectID"))
        for row in project_rows
        if normalize_project_id(row.values.get("ProjectID"))
    }

    project_count = len(project_ids)
    total_available_slots = 0

    for row in supervisor_rows:
        maximum_teams = row.values.get("MaximumTeams")
        current_load = row.values.get("CurrentLoad")

        if (
            isinstance(maximum_teams, int)
            and not isinstance(maximum_teams, bool)
            and maximum_teams > 0
            and isinstance(current_load, int)
            and not isinstance(current_load, bool)
            and current_load >= 0
            and current_load <= maximum_teams
        ):
            total_available_slots += (
                maximum_teams - current_load
            )

    if total_available_slots < project_count:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                code="SUPERVISOR_CAPACITY_INSUFFICIENT",
                sheet="Supervisors",
                row=None,
                field="MaximumTeams",
                message=(
                    f"There are {project_count} project teams, "
                    f"but only {total_available_slots} valid "
                    "supervisor slots are currently available."
                ),
            )
        )

    return issues

def validate_supervisor_expertise_coverage(
    project_rows: List[ParsedRow],
    project_domain_rows: List[ParsedRow],
    supervisor_rows: List[ParsedRow],
    supervisor_domain_rows: List[ParsedRow],
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    project_domains = {}

    for row in project_domain_rows:
        project_id = normalize_project_id(
            row.values.get("ProjectID")
        )
        domain = normalize_domain(
            row.values.get("Domain")
        )

        if project_id and domain:
            project_domains.setdefault(
                project_id,
                set(),
            ).add(domain)

    available_supervisors = set()

    for row in supervisor_rows:
        supervisor_id = normalize_supervisor_id(
            row.values.get("SupervisorID")
        )
        maximum_teams = row.values.get("MaximumTeams")
        current_load = row.values.get("CurrentLoad")

        if (
            supervisor_id
            and isinstance(maximum_teams, int)
            and not isinstance(maximum_teams, bool)
            and isinstance(current_load, int)
            and not isinstance(current_load, bool)
            and maximum_teams > current_load >= 0
        ):
            available_supervisors.add(
                supervisor_id
            )

    supervisor_expertise = {}

    for row in supervisor_domain_rows:
        supervisor_id = normalize_supervisor_id(
            row.values.get("SupervisorID")
        )
        domain_type = normalize_domain_type(
            row.values.get("Type")
        )
        domain = normalize_domain(
            row.values.get("Domain")
        )

        if (
            supervisor_id in available_supervisors
            and domain_type == "expertise"
            and domain
        ):
            supervisor_expertise.setdefault(
                supervisor_id,
                set(),
            ).add(domain)

    valid_project_ids = {
        normalize_project_id(row.values.get("ProjectID"))
        for row in project_rows
        if normalize_project_id(row.values.get("ProjectID"))
    }

    for project_id in valid_project_ids:
        required_domains = project_domains.get(
            project_id,
            set(),
        )

        if not required_domains:
            continue

        has_match = False

        for expertise_domains in supervisor_expertise.values():
            if required_domains.intersection(
                expertise_domains
            ):
                has_match = True
                break

        if not has_match:
            issues.append(
                ValidationIssue(
                    severity="WARNING",
                    code="NO_EXPERTISE_MATCH",
                    sheet="ProjectDomains",
                    row=None,
                    field="Domain",
                    message=(
                        f"Project '{project_id}' currently has no "
                        "available supervisor whose Expertise domains "
                        "match any of its project domains."
                    ),
                )
            )

    return issues