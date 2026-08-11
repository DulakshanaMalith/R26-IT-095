"""
Central skill taxonomy for the Intelligent Team Formation
and Topic Feasibility Analysis component.

IMPORTANT:
- The current research experiment uses 16 technical skills.
- All backend modules should use this catalogue instead of
  defining separate skill lists.
- Additional skills can be added later without changing the
  overall team-formation architecture.
"""

# ------------------------------------------------------------------
# Experimental Skill Taxonomy - Version 1
# ------------------------------------------------------------------

SKILL_CATALOG = [
    {
        "key": "React",
        "display_name": "React",
        "category": "Frontend",
    },
    {
        "key": "HTML/CSS",
        "display_name": "HTML/CSS",
        "category": "Frontend",
    },
    {
        "key": "Angular",
        "display_name": "Angular",
        "category": "Frontend",
    },
    {
        "key": "Vue",
        "display_name": "Vue.js",
        "category": "Frontend",
    },

    {
        "key": "NodeJS",
        "display_name": "Node.js",
        "category": "Backend",
    },
    {
        "key": "Express",
        "display_name": "Express.js",
        "category": "Backend",
    },
    {
        "key": "Java",
        "display_name": "Java",
        "category": "Backend",
    },
    {
        "key": "PHP",
        "display_name": "PHP",
        "category": "Backend",
    },
    {
        "key": "FastAPI",
        "display_name": "FastAPI",
        "category": "Backend",
    },

    {
        "key": "MongoDB",
        "display_name": "MongoDB",
        "category": "Database",
    },
    {
        "key": "MySQL",
        "display_name": "MySQL",
        "category": "Database",
    },
    {
        "key": "PostgreSQL",
        "display_name": "PostgreSQL",
        "category": "Database",
    },
    {
        "key": "Firebase",
        "display_name": "Firebase",
        "category": "Database",
    },

    {
        "key": "Python",
        "display_name": "Python",
        "category": "Data/ML",
    },
    {
        "key": "TensorFlow",
        "display_name": "TensorFlow",
        "category": "Data/ML",
    },
    {
        "key": "Pandas",
        "display_name": "Pandas",
        "category": "Data/ML",
    },
]


# ------------------------------------------------------------------
# Convenience values used by other backend modules
# ------------------------------------------------------------------

SKILL_KEYS = [skill["key"] for skill in SKILL_CATALOG]

SKILL_COLUMNS = [f"Skill_{skill}" for skill in SKILL_KEYS]

SKILL_DISPLAY_NAMES = {
    skill["key"]: skill["display_name"]
    for skill in SKILL_CATALOG
}

SKILL_CATEGORIES = {
    skill["key"]: skill["category"]
    for skill in SKILL_CATALOG
}


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------

MIN_SKILL_LEVEL = 1
MAX_SKILL_LEVEL = 5


def get_skill_column(skill_key: str) -> str:
    """
    Convert a skill key into the corresponding student-data column.

    Example:
        React -> Skill_React
        NodeJS -> Skill_NodeJS
    """
    return f"Skill_{skill_key}"


def is_valid_skill(skill_key: str) -> bool:
    """Check whether a skill exists in the current taxonomy."""
    return skill_key in SKILL_KEYS


def is_valid_skill_level(value) -> bool:
    """Check whether a skill rating is between 1 and 5."""
    try:
        value = int(value)
        return MIN_SKILL_LEVEL <= value <= MAX_SKILL_LEVEL
    except (TypeError, ValueError):
        return False