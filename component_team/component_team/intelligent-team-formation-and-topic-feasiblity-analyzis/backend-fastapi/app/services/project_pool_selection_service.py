from itertools import combinations
from math import comb
import random
from typing import List

from app.models.cohort_import import CohortImportData


def _technical_potential_by_project(data: CohortImportData) -> dict[str, float]:
    requirements_by_project: dict[str, list] = {
        project.project_id: [] for project in data.projects
    }
    for requirement in data.project_requirements:
        if requirement.project_id in requirements_by_project:
            requirements_by_project[requirement.project_id].append(requirement)

    scores: dict[str, float] = {}
    for project in data.projects:
        requirements = requirements_by_project.get(project.project_id, [])
        if not requirements:
            scores[project.project_id] = 0.0
            continue
        coverages = []
        for requirement in requirements:
            qualified = sum(
                1
                for student in data.students
                if student.skills.get(requirement.technology, 0) >= requirement.min_level
            )
            if requirement.required_members <= 0:
                coverage = 1.0
            else:
                coverage = min(1.0, qualified / requirement.required_members)
            coverages.append(coverage)
        scores[project.project_id] = sum(coverages) / len(coverages)
    return scores


def _preference_counts_by_project(data: CohortImportData) -> dict[str, tuple[int, int, int, int]]:
    project_ids = {project.project_id for project in data.projects}
    counts = {project_id: [0, 0, 0, 0] for project_id in project_ids}
    for preference in data.preferences:
        for rank_index, project_id in enumerate(preference.ranked_projects[:3]):
            if project_id not in counts:
                continue
            counts[project_id][rank_index] += 1
            counts[project_id][3] += 1
    return {project_id: tuple(values) for project_id, values in counts.items()}


def generate_candidate_project_subsets(
    data: CohortImportData,
    required_team_count: int,
    *,
    seed: int = 42,
    max_candidate_subsets: int = 8,
) -> List[List[str]]:
    project_ids = [project.project_id for project in data.projects]
    project_count = len(project_ids)

    if required_team_count < 1:
        raise ValueError("At least one project team is required.")
    if project_count < required_team_count:
        raise ValueError(
            f"{required_team_count} project teams are required, but only "
            f"{project_count} approved projects are available."
        )
    if project_count == required_team_count:
        return [project_ids]
    if max_candidate_subsets < 2:
        raise ValueError("max_candidate_subsets must be at least 2 when surplus projects exist.")

    total_combinations = comb(project_count, required_team_count)
    if total_combinations <= max_candidate_subsets:
        return [list(item) for item in combinations(project_ids, required_team_count)]

    project_order = {project_id: index for index, project_id in enumerate(project_ids)}
    technical = _technical_potential_by_project(data)
    preference = _preference_counts_by_project(data)

    preference_ranked = sorted(
        project_ids,
        key=lambda project_id: (
            -preference[project_id][0],
            -preference[project_id][1],
            -preference[project_id][2],
            -preference[project_id][3],
            -technical[project_id],
            project_order[project_id],
        ),
    )
    technical_ranked = sorted(
        project_ids,
        key=lambda project_id: (
            -technical[project_id],
            -preference[project_id][0],
            -preference[project_id][3],
            project_order[project_id],
        ),
    )

    candidates: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()

    def canonical(values) -> tuple[str, ...]:
        chosen = set(values)
        return tuple(project_id for project_id in project_ids if project_id in chosen)

    def add(values) -> bool:
        key = canonical(values)
        if len(key) != required_team_count or key in seen:
            return False
        seen.add(key)
        candidates.append(key)
        return True

    preference_anchor = preference_ranked[:required_team_count]
    technical_anchor = technical_ranked[:required_team_count]
    add(preference_anchor)
    add(technical_anchor)

    # Explore one-project neighborhoods around the two objective-specific anchors.
    # This keeps project-pool exploration multi-view without introducing a hidden weighted score.
    random_reserve = 2
    deterministic_limit = max(2, max_candidate_subsets - random_reserve)
    for anchor in (preference_anchor, technical_anchor):
        selected = list(anchor)
        unselected = [project_id for project_id in project_ids if project_id not in selected]
        for selected_project in reversed(selected):
            for replacement in unselected:
                variant = [project_id for project_id in selected if project_id != selected_project]
                variant.append(replacement)
                add(variant)
                if len(candidates) >= deterministic_limit:
                    break
            if len(candidates) >= deterministic_limit:
                break
        if len(candidates) >= deterministic_limit:
            break

    rng = random.Random(seed)
    attempts = 0
    max_attempts = max_candidate_subsets * 100
    while len(candidates) < max_candidate_subsets and attempts < max_attempts:
        add(rng.sample(project_ids, required_team_count))
        attempts += 1

    if not candidates:
        raise RuntimeError("Could not construct any candidate project subsets.")

    return [list(item) for item in candidates]


def scope_cohort_to_projects(
    data: CohortImportData,
    selected_project_ids: List[str],
) -> CohortImportData:
    selected = set(selected_project_ids)
    scoped = data.model_copy(deep=True)
    scoped.projects = [
        project for project in scoped.projects if project.project_id in selected
    ]
    scoped.project_requirements = [
        requirement
        for requirement in scoped.project_requirements
        if requirement.project_id in selected
    ]

    # Project-domain data is not required by NSGA-II, but filtering it keeps the
    # scoped cohort internally consistent if the model contains this field.
    if hasattr(scoped, "project_domains"):
        scoped.project_domains = [
            item
            for item in scoped.project_domains
            if getattr(item, "project_id", None) in selected
        ]

    if len(scoped.projects) != len(selected):
        available = {project.project_id for project in data.projects}
        missing = sorted(selected - available)
        raise ValueError(f"Unknown selected project(s): {missing}.")

    return scoped
