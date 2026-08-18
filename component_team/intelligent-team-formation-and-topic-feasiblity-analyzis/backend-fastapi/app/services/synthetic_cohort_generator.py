import random
from typing import Dict, List, Literal
from app.models.cohort_import import (
    CohortImportData,
    PreferenceInput,
    ProjectInput,
    ProjectRequirementInput,
    StudentInput,
)
from app.services.team_formation_objectives import TeamAssignment
from app.services.validation_service import REQUIRED_SKILLS

ConflictLevel = Literal["low", "medium", "high"]

PROJECT_TECH_PROFILES = [
    ["React", "HTML_CSS", "NodeJS", "PostgreSQL"],
    ["Python", "TensorFlow", "Pandas", "FastAPI"],
    ["Java", "Angular", "MySQL", "PostgreSQL"],
    ["Vue", "PHP", "Firebase", "MongoDB"],
    ["Express", "NodeJS", "MongoDB", "MySQL"],
]

STRONG_SKILL_PATTERN = {
    0: [0, 1],
    1: [0, 2],
    2: [1, 3],
    3: [2, 3],
}

def _project_id(index: int) -> str:
    return f"P{index + 1:03d}"

def _student_id(index: int) -> str:
    return f"SYN-{index + 1:04d}"

def _cyclic_project(
    home_project_index: int,
    offset: int,
    project_count: int,
) -> str:
    target_index = (
        home_project_index + offset
    ) % project_count

    return _project_id(target_index)

def _build_preferences(
    home_project_index: int,
    team_position: int,
    project_count: int,
    conflict_level: ConflictLevel,
) -> List[str]:
    home = _cyclic_project(
        home_project_index,
        0,
        project_count,
    )

    next_project = _cyclic_project(
        home_project_index,
        1,
        project_count,
    )

    second_next = _cyclic_project(
        home_project_index,
        2,
        project_count,
    )

    if conflict_level == "low":
        return [
            home,
            next_project,
            second_next,
        ]

    if conflict_level == "medium":
        if team_position < 2:
            return [
                home,
                next_project,
                second_next,
            ]

        return [
            next_project,
            home,
            second_next,
        ]

    if conflict_level == "high":
        return [
            next_project,
            second_next,
            home,
        ]

    raise ValueError(
        f"Unknown conflict level: "
        f"{conflict_level}"
    )

def generate_synthetic_cohort(
    student_count: int,
    conflict_level: ConflictLevel,
    team_size: int = 4,
    seed: int = 2026,
) -> CohortImportData:
    if student_count < 20:
        raise ValueError(
            "Scalability datasets should contain "
            "at least 20 students."
        )

    if student_count % team_size != 0:
        raise ValueError(
            "Student count must be divisible by "
            "the project team size."
        )

    if team_size != 4:
        raise ValueError(
            "Synthetic generator V1 currently "
            "supports team_size=4 only."
        )

    project_count = (
        student_count // team_size
    )

    if project_count < 3:
        raise ValueError(
            "At least three projects are required."
        )

    rng = random.Random(seed)

    students = []
    preferences = []
    projects = []
    project_requirements = []

    for project_index in range(
        project_count
    ):
        project_id = _project_id(
            project_index
        )

        profile = PROJECT_TECH_PROFILES[
            project_index
            % len(PROJECT_TECH_PROFILES)
        ]

        projects.append(
            ProjectInput(
                project_id=project_id,
                project_title=(
                    f"Synthetic Project "
                    f"{project_index + 1}"
                ),
                team_size=team_size,
                status="Approved",
            )
        )

        for technology in profile:
            project_requirements.append(
                ProjectRequirementInput(
                    project_id=project_id,
                    technology=technology,
                    min_level=3,
                    required_members=2,
                )
            )

        for team_position in range(
            team_size
        ):
            student_index = (
                project_index
                * team_size
                + team_position
            )

            student_id = _student_id(
                student_index
            )

            skills = {
                skill: rng.randint(1, 2)
                for skill in REQUIRED_SKILLS
            }

            strong_indexes = (
                STRONG_SKILL_PATTERN[
                    team_position
                ]
            )

            for profile_index in (
                strong_indexes
            ):
                technology = profile[
                    profile_index
                ]

                skills[technology] = (
                    rng.randint(4, 5)
                )

            students.append(
                StudentInput(
                    student_id=student_id,
                    skills=skills,
                )
            )

            ranked_projects = (
                _build_preferences(
                    home_project_index=(
                        project_index
                    ),
                    team_position=(
                        team_position
                    ),
                    project_count=(
                        project_count
                    ),
                    conflict_level=(
                        conflict_level
                    ),
                )
            )

            preferences.append(
                PreferenceInput(
                    student_id=student_id,
                    ranked_projects=(
                        ranked_projects
                    ),
                )
            )

    return CohortImportData(
        students=students,
        preferences=preferences,
        projects=projects,
        project_requirements=(
            project_requirements
        ),
        project_domains=[],
        supervisors=[],
        supervisor_domains=[],
        domains=[],
    )

def build_home_assignment(
    data: CohortImportData,
) -> TeamAssignment:
    assignment: TeamAssignment = {}

    offset = 0

    for project in data.projects:
        end = (
            offset
            + project.team_size
        )

        assignment[
            project.project_id
        ] = [
            student.student_id
            for student
            in data.students[
                offset:end
            ]
        ]

        offset = end

    return assignment

def build_first_choice_assignment(
    data: CohortImportData,
) -> TeamAssignment:
    assignment: TeamAssignment = {
        project.project_id: []
        for project in data.projects
    }

    for preference in data.preferences:
        if not preference.ranked_projects:
            raise ValueError(
                f"Student "
                f"'{preference.student_id}' "
                f"has no project preferences."
            )

        first_choice = (
            preference.ranked_projects[0]
        )

        if first_choice not in assignment:
            raise ValueError(
                f"Unknown first-choice project "
                f"'{first_choice}'."
            )

        assignment[
            first_choice
        ].append(
            preference.student_id
        )

    for project in data.projects:
        actual_size = len(
            assignment[
                project.project_id
            ]
        )

        if (
            actual_size
            != project.team_size
        ):
            raise ValueError(
                f"First-choice assignment for "
                f"'{project.project_id}' has "
                f"{actual_size} students instead "
                f"of {project.team_size}."
            )

    return assignment