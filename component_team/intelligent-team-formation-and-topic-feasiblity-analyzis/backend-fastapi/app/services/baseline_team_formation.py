import heapq
from typing import Dict, List
from app.models.cohort_import import CohortImportData
from app.services.team_formation_objectives import TeamAssignment, evaluate_assignment

def build_preference_greedy_assignment(data: CohortImportData) -> TeamAssignment:
    capacities = {project.project_id: project.team_size for project in data.projects}
    assignment: TeamAssignment = {project.project_id: [] for project in data.projects}
    preference_lookup = {
        preference.student_id: preference.ranked_projects
        for preference in data.preferences
    }
    unassigned = {student.student_id for student in data.students}
    max_rank_count = max(
        (len(preference.ranked_projects) for preference in data.preferences),
        default=0,
    )
    for rank_index in range(max_rank_count):
        candidates = []
        for student_id in sorted(unassigned):
            ranked_projects = preference_lookup.get(student_id, [])
            if rank_index >= len(ranked_projects):
                continue
            project_id = ranked_projects[rank_index]
            if project_id not in capacities:
                continue
            if len(assignment[project_id]) >= capacities[project_id]:
                continue
            candidates.append((student_id, project_id))
        for student_id, project_id in candidates:
            if student_id not in unassigned:
                continue
            if len(assignment[project_id]) >= capacities[project_id]:
                continue
            assignment[project_id].append(student_id)
            unassigned.remove(student_id)
    for student_id in sorted(unassigned):
        available_projects = [
            project_id
            for project_id in capacities
            if len(assignment[project_id]) < capacities[project_id]
        ]
        if not available_projects:
            raise ValueError(f"No project capacity remains for student '{student_id}'.")
        ranked_projects = preference_lookup.get(student_id, [])
        def fallback_key(project_id: str):
            if project_id in ranked_projects:
                return 0, ranked_projects.index(project_id), project_id
            return 1, len(ranked_projects), project_id
        chosen_project = min(available_projects, key=fallback_key)
        assignment[chosen_project].append(student_id)
    return assignment

def build_technical_greedy_assignment(data: CohortImportData) -> TeamAssignment:
    capacities = {project.project_id: project.team_size for project in data.projects}
    assignment: TeamAssignment = {project.project_id: [] for project in data.projects}
    student_lookup = {student.student_id: student for student in data.students}
    requirements_lookup: Dict[str, List] = {project.project_id: [] for project in data.projects}
    for requirement in data.project_requirements:
        requirements_lookup[requirement.project_id].append(requirement)
    qualified_counts: Dict[str, Dict[str, int]] = {
        project.project_id: {
            requirement.technology: 0
            for requirement in requirements_lookup[project.project_id]
        }
        for project in data.projects
    }
    unassigned = {student.student_id for student in data.students}

    def calculate_gain(student_id: str, project_id: str) -> float:
        student = student_lookup[student_id]
        requirements = requirements_lookup[project_id]
        if not requirements:
            return 0.0
        gain = 0.0
        for requirement in requirements:
            current_count = qualified_counts[project_id][requirement.technology]
            before = min(1.0, current_count / requirement.required_members)
            after_count = current_count + int(
                student.skills.get(requirement.technology, 0) >= requirement.min_level
            )
            after = min(1.0, after_count / requirement.required_members)
            gain += after - before
        return gain / len(requirements)

    project_heaps = {}
    def rebuild_project_heap(project_id: str) -> None:
        if len(assignment[project_id]) >= capacities[project_id]:
            project_heaps[project_id] = []
            return
        heap = [
            (-calculate_gain(student_id, project_id), student_id)
            for student_id in unassigned
        ]
        heapq.heapify(heap)
        project_heaps[project_id] = heap

    for project in data.projects:
        rebuild_project_heap(project.project_id)

    while unassigned:
        best_choice = None
        best_gain = -1.0
        for project in data.projects:
            project_id = project.project_id
            if len(assignment[project_id]) >= capacities[project_id]:
                continue
            heap = project_heaps[project_id]
            while heap and heap[0][1] not in unassigned:
                heapq.heappop(heap)
            if not heap:
                continue
            negative_gain, student_id = heap[0]
            gain = -negative_gain
            tie_key = (gain, student_id, project_id)
            if (
                best_choice is None
                or gain > best_gain
                or (gain == best_gain and tie_key < best_choice["tie_key"])
            ):
                best_gain = gain
                best_choice = {
                    "student_id": student_id,
                    "project_id": project_id,
                    "tie_key": tie_key,
                }
        if best_choice is None:
            raise RuntimeError("Technical greedy assignment could not complete the cohort.")
        student_id = best_choice["student_id"]
        project_id = best_choice["project_id"]
        assignment[project_id].append(student_id)
        student = student_lookup[student_id]
        for requirement in requirements_lookup[project_id]:
            if student.skills.get(requirement.technology, 0) >= requirement.min_level:
                qualified_counts[project_id][requirement.technology] += 1
        unassigned.remove(student_id)
        rebuild_project_heap(project_id)
    return assignment

def evaluate_baselines(data: CohortImportData) -> Dict:
    technical_assignment = build_technical_greedy_assignment(data)
    preference_assignment = build_preference_greedy_assignment(data)
    technical_result = evaluate_assignment(data=data, assignment=technical_assignment)
    preference_result = evaluate_assignment(data=data, assignment=preference_assignment)
    return {
        "technical_greedy": {
            "assignment": technical_assignment,
            "technical_requirement_deficit": technical_result["technical_requirement_deficit"],
            "preference_dissatisfaction": technical_result["preference_dissatisfaction"],
        },
        "preference_greedy": {
            "assignment": preference_assignment,
            "technical_requirement_deficit": preference_result["technical_requirement_deficit"],
            "preference_dissatisfaction": preference_result["preference_dissatisfaction"],
        },
    }
