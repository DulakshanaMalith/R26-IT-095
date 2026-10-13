from typing import Dict, List

from app.models.cohort_import import (
    CohortImportData,
)
from app.services.team_formation_objectives import (
    evaluate_assignment,
)


def _round_metric(
    value: float,
) -> float:
    return round(
        float(value),
        12,
    )


def _build_student_lookup(
    data: CohortImportData,
) -> Dict:
    return {
        student.student_id: student
        for student in data.students
    }


def _build_preference_lookup(
    data: CohortImportData,
) -> Dict[str, List[str]]:
    return {
        preference.student_id:
        preference.ranked_projects
        for preference in data.preferences
    }


def _solution_role(
    index: int,
    total: int,
) -> str:
    if total <= 1:
        return "Aligned objectives"

    if index == 0:
        return (
            "Technical-oriented endpoint"
        )

    if index == total - 1:
        return (
            "Preference-oriented endpoint"
        )

    return "Trade-off alternative"


def build_staff_team_formation_response(
    data: CohortImportData,
    optimization_result: Dict,
) -> Dict:
    student_lookup = (
        _build_student_lookup(
            data
        )
    )

    preference_lookup = (
        _build_preference_lookup(
            data
        )
    )

    raw_front = (
        optimization_result.get(
            "pareto_front",
            [],
        )
    )

    solutions = []

    for (
        index,
        raw_point,
    ) in enumerate(
        raw_front
    ):
        assignment = raw_point[
            "example_assignment"
        ]

        evaluation = (
            evaluate_assignment(
                data=data,
                assignment=assignment,
            )
        )

        project_evaluation_lookup = {
            item["project_id"]: item
            for item
            in evaluation[
                "project_results"
            ]
        }

        student_preference_lookup = {
            item["student_id"]: item
            for item
            in evaluation[
                "student_preference_results"
            ]
        }

        teams = []

        for project in data.projects:
            project_id = (
                project.project_id
            )

            team_student_ids = (
                assignment[
                    project_id
                ]
            )

            project_result = (
                project_evaluation_lookup[
                    project_id
                ]
            )

            requirements = []

            required_technologies = []

            for requirement in (
                project_result[
                    "requirements"
                ]
            ):
                technology = (
                    requirement[
                        "technology"
                    ]
                )

                required_technologies.append(
                    technology
                )

                requirements.append(
                    {
                        "technology": (
                            technology
                        ),
                        "min_level": (
                            requirement[
                                "min_level"
                            ]
                        ),
                        "required_members": (
                            requirement[
                                "required_members"
                            ]
                        ),
                        "qualified_members": (
                            requirement[
                                "qualified_members"
                            ]
                        ),
                        "qualified_students": (
                            requirement[
                                "qualified_students"
                            ]
                        ),
                        "coverage": (
                            _round_metric(
                                requirement[
                                    "coverage"
                                ]
                            )
                        ),
                        "status": (
                            "Covered"
                            if requirement[
                                "coverage"
                            ] >= 1.0
                            else "Gap"
                        ),
                    }
                )

            team_students = []

            team_dissatisfaction = []

            first_choice_count = 0
            ranked_choice_count = 0
            unranked_count = 0

            for student_id in (
                team_student_ids
            ):
                student = (
                    student_lookup[
                        student_id
                    ]
                )

                preference_result = (
                    student_preference_lookup[
                        student_id
                    ]
                )

                preference_rank = (
                    preference_result[
                        "preference_rank"
                    ]
                )

                dissatisfaction = (
                    preference_result[
                        "dissatisfaction"
                    ]
                )

                team_dissatisfaction.append(
                    dissatisfaction
                )

                if preference_rank == 1:
                    first_choice_count += 1

                if preference_rank is None:
                    unranked_count += 1
                else:
                    ranked_choice_count += 1

                relevant_skills = {
                    technology: (
                        student.skills.get(
                            technology,
                            0,
                        )
                    )
                    for technology
                    in required_technologies
                }

                team_students.append(
                    {
                        "student_id": (
                            student_id
                        ),
                        "preference_rank": (
                            preference_rank
                        ),
                        "dissatisfaction": (
                            _round_metric(
                                dissatisfaction
                            )
                        ),
                        "ranked_projects": (
                            preference_lookup.get(
                                student_id,
                                [],
                            )
                        ),
                        "relevant_skills": (
                            relevant_skills
                        ),
                    }
                )

            if team_dissatisfaction:
                team_preference_dissatisfaction = (
                    sum(
                        team_dissatisfaction
                    )
                    / len(
                        team_dissatisfaction
                    )
                )
            else:
                team_preference_dissatisfaction = (
                    0.0
                )

            teams.append(
                {
                    "project_id": (
                        project_id
                    ),
                    "project_title": (
                        project.project_title
                    ),
                    "team_size": (
                        project.team_size
                    ),
                    "technical_coverage": (
                        _round_metric(
                            project_result[
                                "coverage"
                            ]
                        )
                    ),
                    "technical_deficit": (
                        _round_metric(
                            project_result[
                                "deficit"
                            ]
                        )
                    ),
                    "technical_status": (
                        "Fully covered"
                        if project_result[
                            "deficit"
                        ] <= 0.0
                        else (
                            "Has technical gaps"
                        )
                    ),
                    "preference_summary": {
                        "average_dissatisfaction": (
                            _round_metric(
                                team_preference_dissatisfaction
                            )
                        ),
                        "first_choice_count": (
                            first_choice_count
                        ),
                        "ranked_choice_count": (
                            ranked_choice_count
                        ),
                        "unranked_count": (
                            unranked_count
                        ),
                    },
                    "requirements": (
                        requirements
                    ),
                    "students": (
                        team_students
                    ),
                }
            )

        solutions.append(
            {
                "solution_id": (
                    index + 1
                ),
                "role": (
                    _solution_role(
                        index,
                        len(raw_front),
                    )
                ),
                "technical_requirement_deficit": (
                    _round_metric(
                        evaluation[
                            "technical_requirement_deficit"
                        ]
                    )
                ),
                "technical_requirement_coverage": (
                    _round_metric(
                        evaluation[
                            "technical_requirement_coverage"
                        ]
                    )
                ),
                "preference_dissatisfaction": (
                    _round_metric(
                        evaluation[
                            "preference_dissatisfaction"
                        ]
                    )
                ),
                "preference_satisfaction": (
                    _round_metric(
                        evaluation[
                            "preference_satisfaction"
                        ]
                    )
                ),
                "discovered_unique_allocation_count": (
                    raw_point.get(
                        "discovered_unique_allocation_count",
                        1,
                    )
                ),
                "teams": teams,
            }
        )

    optimizer_metadata = {
        key: value
        for key, value
        in optimization_result.items()
        if key != "pareto_front"
    }

    return {
        "optimizer": (
            optimizer_metadata
        ),
        "solution_count": (
            len(solutions)
        ),
        "solutions": solutions,
        "interpretation": {
            "technical_requirement_deficit": (
                "Lower is better. Zero means "
                "all modeled project technical "
                "requirements are fully covered."
            ),
            "preference_dissatisfaction": (
                "Lower is better. Zero means "
                "every student is assigned to "
                "their first-ranked project."
            ),
            "selection_policy": (
                "No single solution is "
                "automatically selected. "
                "Academic staff inspect the "
                "Pareto alternatives and choose "
                "an allocation according to the "
                "academic context."
            ),
            "allocation_count_note": (
                "discovered_unique_allocation_count "
                "is the number of unique "
                "allocations discovered by this "
                "optimizer run at the same "
                "objective point; it is not the "
                "exact number of all possible "
                "allocations at that point."
            ),
        },
    }