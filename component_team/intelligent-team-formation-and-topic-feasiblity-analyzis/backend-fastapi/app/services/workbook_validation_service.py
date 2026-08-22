from pathlib import Path
from typing import List
from app.models.cohort_import import (
    ParsedRow,
    ValidationIssue,
    ValidationReport,
    ValidationSummary,
)
from app.services.excel_parser import (
    parse_students_sheet,
    parse_preferences_sheet,
    parse_projects_sheet,
    parse_project_requirements_sheet,
    parse_domains_sheet,
    parse_project_domains_sheet,
    parse_supervisors_sheet,
    parse_supervisor_domains_sheet,
)
from app.services.validation_service import (
    validate_students,
    validate_preferences,
    validate_projects,
    validate_project_requirements,
    validate_domains,
    validate_project_domains,
    validate_supervisors,
    validate_supervisor_domains,
    validate_cohort_slots,
    validate_technical_feasibility,
    validate_supervisor_capacity,
    validate_supervisor_expertise_coverage,
)

def _schema_error(message: str) -> ValidationIssue:
    return ValidationIssue(
        severity="ERROR",
        code="WORKBOOK_SCHEMA_ERROR",
        sheet=None,
        row=None,
        field=None,
        message=message,
    )

def validate_workbook(
    file_path: str | Path,
    students_per_team: int | None = None,
) -> ValidationReport:
    issues: List[ValidationIssue] = []

    try:
        students = parse_students_sheet(file_path)
        preferences = parse_preferences_sheet(file_path)
        projects = parse_projects_sheet(file_path)
        requirements = parse_project_requirements_sheet(file_path)
        domains = parse_domains_sheet(file_path)
        project_domains = parse_project_domains_sheet(file_path)
        supervisors = parse_supervisors_sheet(file_path)
        supervisor_domains = parse_supervisor_domains_sheet(file_path)
    except (ValueError, KeyError) as exc:
        issues.append(
            _schema_error(str(exc))
        )

        return ValidationReport(
            valid=False,
            summary=ValidationSummary(
                students=0,
                projects=0,
                supervisors=0,
                errors=1,
                warnings=0,
            ),
            issues=issues,
        )

    issues.extend(
        validate_students(students)
    )

    issues.extend(
        validate_projects(
            projects,
            students_per_team=students_per_team,
        )
    )

    issues.extend(
        validate_project_requirements(
            requirements,
            projects,
            students_per_team=students_per_team,
        )
    )

    issues.extend(
        validate_preferences(
            preferences,
            students,
            projects,
        )
    )

    issues.extend(
        validate_domains(domains)
    )

    issues.extend(
        validate_project_domains(
            project_domains,
            projects,
            domains,
        )
    )

    issues.extend(
        validate_supervisors(
            supervisors
        )
    )

    issues.extend(
        validate_supervisor_domains(
            supervisor_domains,
            supervisors,
            domains,
        )
    )

    issues.extend(
        validate_cohort_slots(
            students,
            projects,
            students_per_team=students_per_team,
        )
    )

    issues.extend(
        validate_technical_feasibility(
            students,
            requirements,
        )
    )

    issues.extend(
        validate_supervisor_capacity(
            supervisors,
            projects,
        )
    )

    issues.extend(
        validate_supervisor_expertise_coverage(
            projects,
            project_domains,
            supervisors,
            supervisor_domains,
        )
    )

    error_count = sum(
        1
        for issue in issues
        if issue.severity == "ERROR"
    )

    warning_count = sum(
        1
        for issue in issues
        if issue.severity == "WARNING"
    )

    return ValidationReport(
        valid=error_count == 0,
        summary=ValidationSummary(
            students=len(students),
            projects=len(projects),
            supervisors=len(supervisors),
            errors=error_count,
            warnings=warning_count,
        ),
        issues=issues,
    )