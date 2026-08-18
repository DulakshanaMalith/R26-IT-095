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

ConflictLevel = Literal[
    "low",
    "medium",
    "high",
]

TEAM_SIZE = 4

def _project_id(
    index: int,
) -> str:
    return f"P{index + 1:03d}"

def _student_id(
    index: int,
) -> str:
    return f"SYN-{index + 1:04d}"

def _generate_background_skill(
    rng: random.Random,
) -> int:
    """
    Generate general competency before project-specific
    guarantees are applied.

    Most ratings are 1-2, but some students obtain
    incidental competency at levels 3-5. Therefore,
    different dataset seeds produce genuinely different
    cross-project qualification patterns.
    """

    roll = rng.random()

    if roll < 0.32:
        return 1

    if roll < 0.75:
        return 2

    if roll < 0.92:
        return 3

    if roll < 0.98:
        return 4

    return 5

def _build_project_structure(
    project_count: int,
    rng: random.Random,
):
    projects = []
    requirements = []

    for project_index in range(
        project_count
    ):
        project_id = _project_id(
            project_index
        )

        projects.append(
            ProjectInput(
                project_id=project_id,
                project_title=(
                    f"Synthetic Project "
                    f"{project_index + 1}"
                ),
                team_size=TEAM_SIZE,
                status="Approved",
            )
        )

        requirement_count = (
            rng.randint(3, 4)
        )

        technologies = rng.sample(
            list(REQUIRED_SKILLS),
            requirement_count,
        )

        for technology in technologies:
            min_level = rng.choice(
                [3, 3, 4]
            )

            required_members = (
                rng.choice(
                    [1, 2, 2]
                )
            )

            requirements.append(
                ProjectRequirementInput(
                    project_id=project_id,
                    technology=technology,
                    min_level=min_level,
                    required_members=(
                        required_members
                    ),
                )
            )

    return (
        projects,
        requirements,
    )

def _build_student_skills(
    student_count: int,
    project_requirements: List[
        ProjectRequirementInput
    ],
    rng: random.Random,
) -> List[Dict[str, int]]:
    skill_maps = []

    for _ in range(
        student_count
    ):
        skills = {
            skill: (
                _generate_background_skill(
                    rng
                )
            )
            for skill in REQUIRED_SKILLS
        }

        skill_maps.append(
            skills
        )

    requirements_by_project = {}

    for requirement in (
        project_requirements
    ):
        requirements_by_project.setdefault(
            requirement.project_id,
            [],
        ).append(
            requirement
        )

    project_count = (
        student_count
        // TEAM_SIZE
    )

    for project_index in range(
        project_count
    ):
        project_id = _project_id(
            project_index
        )

        home_student_indexes = [
            (
                project_index
                * TEAM_SIZE
                + position
            )
            for position in range(
                TEAM_SIZE
            )
        ]

        requirements = (
            requirements_by_project[
                project_id
            ]
        )

        for requirement in requirements:
            qualified_indexes = (
                rng.sample(
                    home_student_indexes,
                    requirement.required_members,
                )
            )

            for student_index in (
                qualified_indexes
            ):
                guaranteed_level = (
                    requirement.min_level
                    + rng.choice(
                        [0, 0, 1]
                    )
                )

                guaranteed_level = min(
                    5,
                    guaranteed_level,
                )

                current_level = (
                    skill_maps[
                        student_index
                    ][
                        requirement.technology
                    ]
                )

                skill_maps[
                    student_index
                ][
                    requirement.technology
                ] = max(
                    current_level,
                    guaranteed_level,
                )

    return skill_maps

def _cyclic_project(
    project_index: int,
    shift: int,
    project_count: int,
) -> str:
    target_index = (
        project_index
        + shift
    ) % project_count

    return _project_id(
        target_index
    )

def _build_preferences(
    student_count: int,
    project_count: int,
    conflict_level: ConflictLevel,
    seed: int,
) -> List[PreferenceInput]:
    """
    Preferences are generated independently from skills.

    For the same dataset seed:
    - Low, Medium and High use exactly the same
      students and technical requirements.
    - Only preference conflict changes.

    A cyclic target mapping keeps first-choice project
    capacities balanced.
    """

    structure_rng = random.Random(
        seed + 100_003
    )

    medium_rng = random.Random(
        seed + 200_003
    )

    target_shift = (
        structure_rng.randint(
            1,
            project_count - 1,
        )
    )

    secondary_options = [
        shift
        for shift in range(
            1,
            project_count
        )
        if shift != target_shift
    ]

    secondary_shift = (
        structure_rng.choice(
            secondary_options
        )
    )

    medium_movers = {}

    for project_index in range(
        project_count
    ):
        medium_movers[
            project_index
        ] = set(
            medium_rng.sample(
                range(TEAM_SIZE),
                TEAM_SIZE // 2,
            )
        )

    preferences = []

    for student_index in range(
        student_count
    ):
        project_index = (
            student_index
            // TEAM_SIZE
        )

        team_position = (
            student_index
            % TEAM_SIZE
        )

        home_project = (
            _cyclic_project(
                project_index,
                0,
                project_count,
            )
        )

        conflict_project = (
            _cyclic_project(
                project_index,
                target_shift,
                project_count,
            )
        )

        secondary_project = (
            _cyclic_project(
                project_index,
                secondary_shift,
                project_count,
            )
        )

        if conflict_level == "low":
            ranked_projects = [
                home_project,
                conflict_project,
                secondary_project,
            ]

        elif conflict_level == "medium":
            if (
                team_position
                in medium_movers[
                    project_index
                ]
            ):
                ranked_projects = [
                    conflict_project,
                    home_project,
                    secondary_project,
                ]
            else:
                ranked_projects = [
                    home_project,
                    conflict_project,
                    secondary_project,
                ]

        elif conflict_level == "high":
            ranked_projects = [
                conflict_project,
                secondary_project,
                home_project,
            ]

        else:
            raise ValueError(
                "Conflict level must be "
                "'low', 'medium', or 'high'."
            )

        preferences.append(
            PreferenceInput(
                student_id=(
                    _student_id(
                        student_index
                    )
                ),
                ranked_projects=(
                    ranked_projects
                ),
            )
        )

    return preferences

def generate_synthetic_cohort(
    student_count: int,
    conflict_level: ConflictLevel,
    team_size: int = TEAM_SIZE,
    seed: int = 2026,
) -> CohortImportData:
    if student_count < 20:
        raise ValueError(
            "Scalability datasets should "
            "contain at least 20 students."
        )

    if team_size != TEAM_SIZE:
        raise ValueError(
            "Synthetic Generator V2 "
            "currently supports team_size=4 only."
        )

    if (
        student_count
        % team_size
        != 0
    ):
        raise ValueError(
            "Student count must be divisible "
            "by the project team size."
        )

    project_count = (
        student_count
        // team_size
    )

    if project_count < 3:
        raise ValueError(
            "At least three projects "
            "are required."
        )

    technical_rng = (
        random.Random(
            seed
        )
    )

    (
        projects,
        project_requirements,
    ) = _build_project_structure(
        project_count=project_count,
        rng=technical_rng,
    )

    skill_maps = (
        _build_student_skills(
            student_count=student_count,
            project_requirements=(
                project_requirements
            ),
            rng=technical_rng,
        )
    )

    students = [
        StudentInput(
            student_id=(
                _student_id(
                    index
                )
            ),
            skills=skill_maps[
                index
            ],
        )
        for index in range(
            student_count
        )
    ]

    preferences = (
        _build_preferences(
            student_count=student_count,
            project_count=project_count,
            conflict_level=(
                conflict_level
            ),
            seed=seed,
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
            preference.ranked_projects[
                0
            ]
        )

        if (
            first_choice
            not in assignment
        ):
            raise ValueError(
                f"Unknown first-choice "
                f"project '{first_choice}'."
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
                f"First-choice assignment "
                f"for '{project.project_id}' "
                f"has {actual_size} students "
                f"instead of "
                f"{project.team_size}."
            )

    return assignment