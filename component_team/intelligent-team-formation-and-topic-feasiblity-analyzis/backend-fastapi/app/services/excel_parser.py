from pathlib import Path
from typing import List

from openpyxl import load_workbook

from app.models.cohort_import import ParsedRow


# ============================================================
# STUDENT SHEET CONFIGURATION
# ============================================================

STUDENT_SHEET_NAME = "Students"

STUDENT_HEADERS = [
    "StudentID",
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

def normalize_header(value) -> str:
    """
    Convert an Excel header value into a clean string.
    """

    if value is None:
        return ""

    return str(value).strip()


def is_empty_row(row) -> bool:
    """
    Returns True if an Excel row contains no meaningful values.
    """

    for value in row:
        if value is None:
            continue

        if isinstance(value, str) and value.strip() == "":
            continue

        return False

    return True


# ============================================================
# STUDENTS SHEET PARSER
# ============================================================

def parse_students_sheet(file_path: str | Path) -> List[ParsedRow]:

    workbook = load_workbook(
        filename=file_path,
        read_only=True,
        data_only=True,
    )

    try:

        # ----------------------------------------------------
        # Check whether Students sheet exists
        # ----------------------------------------------------

        if STUDENT_SHEET_NAME not in workbook.sheetnames:
            raise ValueError(
                f"Required sheet '{STUDENT_SHEET_NAME}' was not found."
            )

        worksheet = workbook[STUDENT_SHEET_NAME]

        # ----------------------------------------------------
        # Read first row as headers
        # ----------------------------------------------------

        header_row = next(
            worksheet.iter_rows(
                min_row=1,
                max_row=1,
                values_only=True,
            )
        )

        headers = [
            normalize_header(value)
            for value in header_row
        ]

        # ----------------------------------------------------
        # Check required headers
        # ----------------------------------------------------

        missing_headers = [
            header
            for header in STUDENT_HEADERS
            if header not in headers
        ]

        if missing_headers:
            raise ValueError(
                "Students sheet is missing required columns: "
                + ", ".join(missing_headers)
            )

        # Map each header name to its column position
        header_indexes = {
            header: headers.index(header)
            for header in STUDENT_HEADERS
        }

        parsed_rows: List[ParsedRow] = []

        # ----------------------------------------------------
        # Read student rows
        # ----------------------------------------------------

        for row_number, row in enumerate(
            worksheet.iter_rows(
                min_row=2,
                values_only=True,
            ),
            start=2,
        ):

            # Ignore completely empty rows
            if is_empty_row(row):
                continue

            values = {}

            for header in STUDENT_HEADERS:

                column_index = header_indexes[header]

                if column_index < len(row):
                    values[header] = row[column_index]
                else:
                    values[header] = None

            parsed_rows.append(
                ParsedRow(
                    sheet=STUDENT_SHEET_NAME,
                    row_number=row_number,
                    values=values,
                )
            )

        return parsed_rows

    finally:

        workbook.close()