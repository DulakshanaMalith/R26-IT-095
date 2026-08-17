from typing import List

from app.models.cohort_import import ParsedRow, ValidationIssue


# ============================================================
# STUDENT VALIDATION CONFIGURATION
# ============================================================

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


# ============================================================
# HELPERS
# ============================================================

def normalize_student_id(value) -> str:
    """
    Normalize a StudentID before duplicate/reference checking.
    """

    if value is None:
        return ""

    return str(value).strip().upper()


# ============================================================
# STUDENT VALIDATOR
# ============================================================

def validate_students(
    rows: List[ParsedRow],
) -> List[ValidationIssue]:

    issues: List[ValidationIssue] = []

    seen_student_ids = {}

    for row in rows:

        values = row.values

        # ----------------------------------------------------
        # Student ID validation
        # ----------------------------------------------------

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

        else:

            if student_id in seen_student_ids:

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

        # ----------------------------------------------------
        # Skill validation
        # ----------------------------------------------------

        for skill in REQUIRED_SKILLS:

            value = values.get(skill)

            # Missing value
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

            # Must be an integer
            # bool is excluded because Python treats True/False as int
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

            # Must be in 1-5 range
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