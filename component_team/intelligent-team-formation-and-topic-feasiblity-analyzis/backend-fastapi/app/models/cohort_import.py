from typing import Dict, List, Literal, Optional, Any

from pydantic import BaseModel, Field


# ============================================================
# STUDENT
# ============================================================

class StudentInput(BaseModel):
    student_id: str

    # Example:
    # {
    #     "React": 5,
    #     "NodeJS": 4,
    #     "Python": 2
    # }
    skills: Dict[str, int]


# ============================================================
# STUDENT PROJECT PREFERENCES
# ============================================================

class PreferenceInput(BaseModel):
    student_id: str

    # Example:
    # ["P03", "P01", "P02"]
    ranked_projects: List[str]


# ============================================================
# PROJECT
# ============================================================

class ProjectInput(BaseModel):
    project_id: str

    project_title: str

    team_size: int = Field(gt=0)

    status: str = "Approved"


# ============================================================
# PROJECT TECHNICAL REQUIREMENT
# ============================================================

class ProjectRequirementInput(BaseModel):
    project_id: str

    technology: str

    min_level: int

    required_members: int


# ============================================================
# PROJECT DOMAIN
# ============================================================

class ProjectDomainInput(BaseModel):
    project_id: str

    domain: str


# ============================================================
# SUPERVISOR
# ============================================================

class SupervisorInput(BaseModel):
    supervisor_id: str

    supervisor_name: str

    maximum_teams: int

    current_load: int


# ============================================================
# SUPERVISOR DOMAIN
# ============================================================

class SupervisorDomainInput(BaseModel):
    supervisor_id: str

    type: Literal["Expertise", "Interest"]

    domain: str


# ============================================================
# COMPLETE WORKBOOK DATA
# ============================================================

class CohortImportData(BaseModel):
    students: List[StudentInput]

    preferences: List[PreferenceInput]

    projects: List[ProjectInput]

    project_requirements: List[ProjectRequirementInput]

    project_domains: List[ProjectDomainInput]

    supervisors: List[SupervisorInput]

    supervisor_domains: List[SupervisorDomainInput]

    domains: List[str]


# ============================================================
# VALIDATION RESULT MODELS
# ============================================================

class ValidationIssue(BaseModel):
    severity: Literal["ERROR", "WARNING"]

    code: str

    sheet: Optional[str] = None

    row: Optional[int] = None

    field: Optional[str] = None

    message: str


class ValidationSummary(BaseModel):
    students: int = 0

    projects: int = 0

    supervisors: int = 0

    errors: int = 0

    warnings: int = 0


class ValidationReport(BaseModel):
    valid: bool

    summary: ValidationSummary

    issues: List[ValidationIssue]

class ParsedRow(BaseModel):
    sheet: str
    row_number: int
    values: Dict[str, Any]