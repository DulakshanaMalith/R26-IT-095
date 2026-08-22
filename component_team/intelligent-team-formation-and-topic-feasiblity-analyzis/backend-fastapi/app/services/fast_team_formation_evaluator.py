from typing import List, Tuple
from app.models.cohort_import import CohortImportData
from app.services.team_formation_objectives import calculate_rank_dissatisfaction

class FastTeamFormationEvaluator:
    def __init__(self, data: CohortImportData):
        self.student_count = len(data.students)
        self.project_count = len(data.projects)
        self.student_index = {
            student.student_id: index
            for index, student in enumerate(data.students)
        }
        self.project_index = {
            project.project_id: index
            for index, project in enumerate(data.projects)
        }
        self.segments: List[Tuple[int, int]] = []
        offset = 0
        for project in data.projects:
            end = offset + project.team_size
            self.segments.append((offset, end))
            offset = end
        if offset != self.student_count:
            raise ValueError("Project team sizes do not consume all students.")
        requirements_by_project = {
            project.project_id: []
            for project in data.projects
        }
        for requirement in data.project_requirements:
            requirements_by_project[requirement.project_id].append(requirement)
        self.project_requirements = []
        for project in data.projects:
            requirements = requirements_by_project[project.project_id]
            if not requirements:
                raise ValueError(f"Project '{project.project_id}' has no technical requirements.")
            prepared = []
            for requirement in requirements:
                qualification = bytearray(
                    1 if student.skills.get(requirement.technology, 0) >= requirement.min_level else 0
                    for student in data.students
                )
                prepared.append((requirement.required_members, qualification))
            self.project_requirements.append(prepared)
        self.preference_matrix = [
            [1.0] * self.project_count
            for _ in range(self.student_count)
        ]
        for preference in data.preferences:
            student_idx = self.student_index.get(preference.student_id)
            if student_idx is None:
                continue
            ranked_projects = preference.ranked_projects
            ranked_project_count = len(ranked_projects)
            for rank, project_id in enumerate(ranked_projects, start=1):
                project_idx = self.project_index.get(project_id)
                if project_idx is None:
                    continue
                self.preference_matrix[student_idx][project_idx] = calculate_rank_dissatisfaction(
                    rank=rank,
                    ranked_project_count=ranked_project_count,
                    total_project_count=self.project_count,
                )

    def evaluate(self, individual: List[int]) -> Tuple[float, float]:
        if len(individual) != self.student_count:
            raise ValueError("Individual length does not match the number of students.")
        project_deficits = []
        assigned_project_indexes = [0] * self.student_count
        for project_idx, ((start, end), requirements) in enumerate(
            zip(self.segments, self.project_requirements)
        ):
            team_indexes = individual[start:end]
            coverage_values = []
            for required_members, qualification in requirements:
                qualified_count = sum(qualification[student_idx] for student_idx in team_indexes)
                coverage_values.append(min(1.0, qualified_count / required_members))
            project_coverage = sum(coverage_values) / len(coverage_values)
            project_deficits.append(1.0 - project_coverage)
            for student_idx in team_indexes:
                assigned_project_indexes[student_idx] = project_idx
        technical_deficit = sum(project_deficits) / len(project_deficits)
        dissatisfaction_values = [
            self.preference_matrix[student_idx][assigned_project_indexes[student_idx]]
            for student_idx in range(self.student_count)
        ]
        preference_dissatisfaction = sum(dissatisfaction_values) / self.student_count
        return technical_deficit, preference_dissatisfaction
