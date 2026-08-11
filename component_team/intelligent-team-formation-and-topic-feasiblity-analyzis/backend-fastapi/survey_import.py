import os
import re
import sys
import pandas as pd

from skill_catalog import (
    SKILL_KEYS,
    SKILL_DISPLAY_NAMES,
    get_skill_column,
    MIN_SKILL_LEVEL,
    MAX_SKILL_LEVEL,
)


# ---------------------------------------------------------
# Output configuration
# ---------------------------------------------------------

REAL_DATA_DIR = os.path.join(
    "data",
    "real"
)

OUTPUT_FILE = os.path.join(
    REAL_DATA_DIR,
    "student_skill_profiles.csv"
)


# ---------------------------------------------------------
# Google Form header aliases
# ---------------------------------------------------------
#
# Google Forms may export grid columns using headings such as:
#
#   Rate your skills [React]
#   Technical Skills [Node.js]
#
# We therefore search for the technology name inside each
# column rather than depending on one exact form title.
# ---------------------------------------------------------

SKILL_ALIASES = {
    "React": [
        "react",
    ],

    "HTML/CSS": [
        "html/css",
        "html css",
        "htmlcss",
        "html and css",
    ],

    "Angular": [
        "angular",
    ],

    "Vue": [
        "vue",
        "vue.js",
        "vuejs",
    ],

    "NodeJS": [
        "node.js",
        "nodejs",
        "node js",
        "node",
    ],

    "Express": [
        "express",
        "express.js",
        "expressjs",
    ],

    "Java": [
        "java",
    ],

    "PHP": [
        "php",
    ],

    "FastAPI": [
        "fastapi",
        "fast api",
    ],

    "MongoDB": [
        "mongodb",
        "mongo db",
        "mongo",
    ],

    "MySQL": [
        "mysql",
        "my sql",
    ],

    "PostgreSQL": [
        "postgresql",
        "postgres",
        "postgre sql",
    ],

    "Firebase": [
        "firebase",
    ],

    "Python": [
        "python",
    ],

    "TensorFlow": [
        "tensorflow",
        "tensor flow",
    ],

    "Pandas": [
        "pandas",
    ],
}


# ---------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------

def normalize_text(value):
    """
    Normalize text for reliable comparison.
    """
    return re.sub(
        r"\s+",
        " ",
        str(value).strip().lower()
    )


def extract_rating(value):
    """
    Convert Google Form answers into an integer 1-5.

    Supported examples:

        4
        "4"
        "4 - Proficient"
        "4 — Proficient"
        "Level 4"
        "Rating: 4"
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    match = re.search(
        r"\b([1-5])\b",
        text
    )

    if not match:
        return None

    rating = int(
        match.group(1)
    )

    if (
        MIN_SKILL_LEVEL
        <= rating
        <= MAX_SKILL_LEVEL
    ):
        return rating

    return None


def find_skill_column(
    dataframe_columns,
    skill_key
):
    """
    Find the Google Form column corresponding
    to a particular skill.
    """

    aliases = SKILL_ALIASES[
        skill_key
    ]

    for column in dataframe_columns:

        normalized_column = normalize_text(
            column
        )

        # Prefer the text inside Google Forms'
        # grid brackets if available.
        bracket_matches = re.findall(
            r"\[([^\]]+)\]",
            normalized_column
        )

        for bracket_text in bracket_matches:

            normalized_bracket = normalize_text(
                bracket_text
            )

            for alias in aliases:

                if (
                    normalized_bracket
                    == normalize_text(alias)
                ):
                    return column

    # Fallback:
    # search the entire column header.
    for column in dataframe_columns:

        normalized_column = normalize_text(
            column
        )

        for alias in aliases:

            normalized_alias = normalize_text(
                alias
            )

            if normalized_alias in normalized_column:
                return column

    return None


# ---------------------------------------------------------
# Main Import Function
# ---------------------------------------------------------

def import_google_form_csv(
    input_csv_path
):

    print(
        "\n========================================"
    )
    print(
        " Google Forms Skill Data Importer"
    )
    print(
        "========================================\n"
    )

    # -----------------------------------------------------
    # Read exported Google Form CSV
    # -----------------------------------------------------

    try:
        source_df = pd.read_csv(
            input_csv_path
        )

    except Exception as e:
        print(
            f"❌ Could not read CSV file: {e}"
        )
        return False

    print(
        f"✅ Loaded {len(source_df)} "
        f"Google Form responses."
    )

    if len(source_df) == 0:
        print(
            "❌ The CSV contains no responses."
        )
        return False

    # -----------------------------------------------------
    # Match all 16 skill columns
    # -----------------------------------------------------

    matched_columns = {}
    missing_skills = []

    for skill in SKILL_KEYS:

        column = find_skill_column(
            source_df.columns,
            skill
        )

        if column is None:

            missing_skills.append(
                skill
            )

        else:

            matched_columns[
                skill
            ] = column

    if missing_skills:

        print(
            "\n❌ The following skill columns "
            "could not be found:"
        )

        for skill in missing_skills:

            print(
                f"   - "
                f"{SKILL_DISPLAY_NAMES[skill]}"
            )

        print(
            "\nAvailable CSV columns:"
        )

        for column in source_df.columns:

            print(
                f"   • {column}"
            )

        print(
            "\nNo output file was created."
        )

        return False

    print(
        "\n✅ All 16 skill columns detected."
    )

    # -----------------------------------------------------
    # Convert survey responses
    # -----------------------------------------------------

    clean_rows = []

    skipped_rows = []

    for row_index, row in (
        source_df.iterrows()
    ):

        student_number = (
            len(clean_rows) + 1
        )

        student_id = (
            f"P{student_number:03d}"
        )

        clean_student = {
            "student_id": student_id,
            "profile_source":
                "survey_self_report"
        }

        row_is_valid = True

        for skill in SKILL_KEYS:

            source_column = (
                matched_columns[skill]
            )

            rating = extract_rating(
                row[source_column]
            )

            if rating is None:

                row_is_valid = False
                break

            clean_student[
                get_skill_column(skill)
            ] = rating

        if row_is_valid:

            clean_rows.append(
                clean_student
            )

        else:

            skipped_rows.append(
                row_index + 2
            )

    # -----------------------------------------------------
    # Check usable responses
    # -----------------------------------------------------

    if not clean_rows:

        print(
            "\n❌ No complete skill profiles "
            "could be imported."
        )

        return False

    # -----------------------------------------------------
    # Create clean DataFrame
    # -----------------------------------------------------

    output_df = pd.DataFrame(
        clean_rows
    )

    desired_columns = [
        "student_id",
        "profile_source"
    ] + [
        get_skill_column(skill)
        for skill in SKILL_KEYS
    ]

    output_df = output_df[
        desired_columns
    ]

    # -----------------------------------------------------
    # Save standardized real dataset
    # -----------------------------------------------------

    os.makedirs(
        REAL_DATA_DIR,
        exist_ok=True
    )

    output_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # -----------------------------------------------------
    # Report
    # -----------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        " Import Complete"
    )

    print(
        "========================================"
    )

    print(
        f"✅ Valid profiles: "
        f"{len(output_df)}"
    )

    if skipped_rows:

        print(
            f"⚠️ Incomplete responses skipped: "
            f"{len(skipped_rows)}"
        )

        print(
            "   CSV rows:",
            skipped_rows
        )

    print(
        f"\n📁 Saved to:\n"
        f"   {OUTPUT_FILE}"
    )

    print(
        "\nAssigned IDs:"
    )

    print(
        f"   P001 → "
        f"P{len(output_df):03d}"
    )

    print(
        "\nThese IDs are generated by the "
        "research system and are not "
        "participant-provided identifiers."
    )

    return True


# ---------------------------------------------------------
# Command Line Entry Point
# ---------------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "\nUsage:"
        )

        print(
            'python survey_import.py '
            '"path_to_google_form_export.csv"'
        )

        print(
            "\nExample:"
        )

        print(
            'python survey_import.py '
            '"responses.csv"'
        )

        sys.exit(1)

    csv_path = sys.argv[1]

    if not os.path.exists(
        csv_path
    ):

        print(
            f"❌ File not found: "
            f"{csv_path}"
        )

        sys.exit(1)

    success = import_google_form_csv(
        csv_path
    )

    if not success:
        sys.exit(1)