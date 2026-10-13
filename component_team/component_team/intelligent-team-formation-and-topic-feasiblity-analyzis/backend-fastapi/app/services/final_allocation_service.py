from datetime import datetime
from math import ceil
from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload
from app.db_models.final_allocation import FinalAllocation, FinalTeam, FinalTeamMember, FinalTeamRequirement, FinalTeamSupervisor
from app.models.final_allocation import FinalAllocationCreateRequest

def _allocation_id() -> str:
    return f"TF-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6].upper()}"

def _validate_payload(request: FinalAllocationCreateRequest) -> tuple[list[dict], dict[str, dict]]:
    solution = request.selected_solution
    teams = solution.get("teams") or []
    if not teams:
        raise ValueError("The selected solution does not contain any teams.")
    if solution.get("integrity") and not solution["integrity"].get("valid", False):
        raise ValueError("The selected solution failed its allocation-integrity check and cannot be saved as final.")
    project_ids = [team.get("project_id") for team in teams]
    if None in project_ids or len(project_ids) != len(set(project_ids)):
        raise ValueError("The selected solution contains a missing or duplicate project assignment.")
    student_ids = []
    for team in teams:
        members = team.get("students") or []
        expected_size = int(team.get("team_size", 0))
        if len(members) != expected_size:
            raise ValueError(f"Project {team.get('project_id')} has {len(members)} students but team_size is {expected_size}.")
        student_ids.extend(member.get("student_id") for member in members)
    if None in student_ids or len(student_ids) != len(set(student_ids)):
        raise ValueError("The selected solution contains a missing or duplicate student assignment.")

    students_per_team = request.students_per_team
    if isinstance(students_per_team, bool) or not isinstance(students_per_team, int) or students_per_team < 2:
        raise ValueError("Students per team must be an integer of at least 2.")
    required_team_count = ceil(len(student_ids) / students_per_team)
    if len(teams) != required_team_count:
        raise ValueError(
            f"The selected solution must contain exactly {required_team_count} teams for "
            f"{len(student_ids)} students at a target team size of {students_per_team}."
        )
    quotient, remainder = divmod(len(student_ids), students_per_team)
    expected_sizes = sorted(([students_per_team] * quotient) + ([remainder] if remainder else []))
    actual_sizes = sorted(len(team.get("students") or []) for team in teams)
    if actual_sizes != expected_sizes:
        raise ValueError(
            f"The selected solution has invalid team sizes. Expected {expected_sizes}, "
            f"received {actual_sizes}."
        )

    assignments = request.supervisor_allocation.get("assignments") or []
    supervisor_by_project = {assignment.get("project_id"): assignment for assignment in assignments}
    if len(supervisor_by_project) != len(assignments):
        raise ValueError("Supervisor allocation contains duplicate project assignments.")
    if set(supervisor_by_project) != set(project_ids):
        missing = sorted(set(project_ids) - set(supervisor_by_project))
        extra = sorted(set(supervisor_by_project) - set(project_ids))
        raise ValueError(f"Supervisor allocation must cover exactly the selected projects. Missing={missing}, unexpected={extra}.")
    return teams, supervisor_by_project

def _validate_reference_matches_solution(
    reference_data: dict | None,
    teams: list[dict],
    students_per_team: int | None = None,
) -> None:
    if not reference_data:
        return
    reference_students = {str(item.get("student_id") or "").strip().upper() for item in reference_data.get("students") or []}
    reference_projects = {str(item.get("project_id") or "").strip().upper() for item in reference_data.get("projects") or []}
    solution_students = {str(member.get("student_id") or "").strip().upper() for team in teams for member in team.get("students") or []}
    solution_projects = {str(team.get("project_id") or "").strip().upper() for team in teams}
    if reference_students != solution_students:
        raise ValueError("The uploaded source workbook student set does not match the selected final allocation.")
    if not solution_projects:
        raise ValueError("The selected final allocation does not contain any projects.")
    if not solution_projects.issubset(reference_projects):
        unexpected = sorted(solution_projects - reference_projects)
        raise ValueError(
            "The selected final allocation contains project(s) that are not present in the "
            f"uploaded source workbook: {unexpected}."
        )

    if students_per_team is not None:
        if isinstance(students_per_team, bool) or not isinstance(students_per_team, int) or students_per_team < 2:
            raise ValueError("Students per team must be an integer of at least 2.")
        student_count = len(reference_students)
        required_team_count = ceil(student_count / students_per_team)
        if len(teams) != required_team_count:
            raise ValueError(
                f"The selected final allocation must contain exactly {required_team_count} teams "
                f"for {student_count} students at a target team size of {students_per_team}."
            )
        quotient, remainder = divmod(student_count, students_per_team)
        expected_sizes = sorted(([students_per_team] * quotient) + ([remainder] if remainder else []))
        actual_sizes = sorted(len(team.get("students") or []) for team in teams)
        if actual_sizes != expected_sizes:
            raise ValueError(
                f"The selected final allocation has invalid team sizes. Expected {expected_sizes}, "
                f"received {actual_sizes}."
            )

def persist_final_allocation(
    db: Session,
    *,
    source_file_name: str | None,
    students_per_team: int,
    algorithm: str,
    optimizer_version: str,
    solution: dict,
    supervisor_assignments: list[dict],
    reference_data: dict | None,
    allocation_source: str,
    revision_number: int,
    parent_allocation_id: str | None = None,
    change_reason: str | None = None,
) -> dict:
    teams = solution.get("teams") or []
    supervisor_by_project = {str(item.get("project_id")): item for item in supervisor_assignments}
    if not teams:
        raise ValueError("No teams were supplied for persistence.")
    student_count = sum(len(team.get("students") or []) for team in teams)
    allocation = FinalAllocation(
        id=_allocation_id(),
        source_file_name=source_file_name,
        algorithm=algorithm,
        optimizer_version=optimizer_version,
        solution_id=int(solution.get("solution_id", 0)),
        solution_role=str(solution.get("role") or "Selected allocation"),
        students_per_team=students_per_team,
        student_count=student_count,
        project_count=len(teams),
        technical_requirement_deficit=float(solution.get("technical_requirement_deficit", 0.0)),
        technical_requirement_coverage=float(solution.get("technical_requirement_coverage", 0.0)),
        preference_dissatisfaction=float(solution.get("preference_dissatisfaction", 0.0)),
        preference_satisfaction=float(solution.get("preference_satisfaction", 0.0)),
        integrity_valid=bool(solution.get("integrity", {}).get("valid", True)),
        status="ACTIVE",
        revision_number=revision_number,
        parent_allocation_id=parent_allocation_id,
        allocation_source=allocation_source,
        change_reason=change_reason,
        reference_data=reference_data,
    )
    try:
        db.execute(update(FinalAllocation).where(FinalAllocation.status == "ACTIVE").values(status="ARCHIVED"))
        db.flush()
        db.add(allocation)
        db.flush()
        for default_number, team_data in enumerate(teams, start=1):
            project_id = str(team_data.get("project_id") or "")
            if project_id not in supervisor_by_project:
                raise ValueError(f"No supervisor assignment was supplied for project {project_id}.")
            preference = team_data.get("preference_summary") or {}
            team = FinalTeam(
                allocation_id=allocation.id,
                team_number=int(team_data.get("team_number") or default_number),
                project_id=project_id,
                project_title=str(team_data.get("project_title") or ""),
                team_size=int(team_data.get("team_size", len(team_data.get("students") or []))),
                technical_coverage=float(team_data.get("technical_coverage", 0.0)),
                technical_deficit=float(team_data.get("technical_deficit", 0.0)),
                technical_status=str(team_data.get("technical_status") or ""),
                preference_average_dissatisfaction=float(preference.get("average_dissatisfaction", 0.0)),
                first_choice_count=int(preference.get("first_choice_count", 0)),
                ranked_choice_count=int(preference.get("ranked_choice_count", 0)),
                unranked_count=int(preference.get("unranked_count", 0)),
            )
            db.add(team)
            db.flush()
            for member in team_data.get("students") or []:
                db.add(FinalTeamMember(
                    team_id=team.id,
                    student_id=str(member.get("student_id")),
                    preference_rank=member.get("preference_rank"),
                    dissatisfaction=float(member.get("dissatisfaction", 0.0)),
                    ranked_projects=list(member.get("ranked_projects") or []),
                    relevant_skills=dict(member.get("relevant_skills") or {}),
                ))
            for requirement in team_data.get("requirements") or []:
                db.add(FinalTeamRequirement(
                    team_id=team.id,
                    technology=str(requirement.get("technology") or ""),
                    min_level=int(requirement.get("min_level", 0)),
                    required_members=int(requirement.get("required_members", 0)),
                    qualified_members=int(requirement.get("qualified_members", 0)),
                    qualified_students=list(requirement.get("qualified_students") or []),
                    coverage=float(requirement.get("coverage", 0.0)),
                    status=str(requirement.get("status") or ""),
                ))
            assignment = supervisor_by_project[project_id]
            db.add(FinalTeamSupervisor(
                team_id=team.id,
                supervisor_id=str(assignment.get("supervisor_id") or ""),
                supervisor_name=str(assignment.get("supervisor_name") or ""),
                match_status=str(assignment.get("match_status") or ""),
                current_load=int(assignment.get("current_load", 0)),
                maximum_teams=int(assignment.get("maximum_teams", 0)),
                projected_load=int(assignment.get("projected_load", 0)),
                remaining_capacity=int(assignment.get("remaining_capacity", 0)),
                project_domains=list(assignment.get("project_domains") or []),
                expertise_matches=list(assignment.get("expertise_matches") or []),
                interest_matches=list(assignment.get("interest_matches") or []),
                explanation=str(assignment.get("explanation") or ""),
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_final_allocation(db, allocation.id)

def create_final_allocation(db: Session, request: FinalAllocationCreateRequest, reference_data: dict | None = None) -> dict:
    teams, supervisor_by_project = _validate_payload(request)
    _validate_reference_matches_solution(reference_data, teams, request.students_per_team)
    solution = request.selected_solution
    optimizer = request.optimizer
    return persist_final_allocation(
        db,
        source_file_name=request.source_file_name,
        students_per_team=request.students_per_team,
        algorithm=str(optimizer.get("algorithm") or "Heuristic-Seeded NSGA-II"),
        optimizer_version=str(optimizer.get("optimizer_version") or "V3"),
        solution=solution,
        supervisor_assignments=list(supervisor_by_project.values()),
        reference_data=reference_data,
        allocation_source="OPTIMIZER",
        revision_number=1,
    )

def attach_reference_data(db: Session, allocation_id: str, reference_data: dict) -> dict:
    allocation = db.get(FinalAllocation, allocation_id)
    if allocation is None:
        raise ValueError("Final allocation was not found.")
    existing = get_final_allocation(db, allocation_id)
    _validate_reference_matches_solution(
        reference_data,
        existing.get("teams") or [],
        int(existing.get("students_per_team") or 0),
    )
    allocation.reference_data = reference_data
    db.commit()
    return get_final_allocation(db, allocation_id)

def get_final_allocation(db: Session, allocation_id: str) -> dict | None:
    statement = select(FinalAllocation).where(FinalAllocation.id == allocation_id).options(
        selectinload(FinalAllocation.teams).selectinload(FinalTeam.members),
        selectinload(FinalAllocation.teams).selectinload(FinalTeam.requirements),
        selectinload(FinalAllocation.teams).selectinload(FinalTeam.supervisor),
    )
    allocation = db.scalar(statement)
    return None if allocation is None else _serialize_allocation(allocation)

def _serialize_allocation(allocation: FinalAllocation) -> dict:
    teams = []
    for team in sorted(allocation.teams, key=lambda item: item.team_number):
        supervisor = team.supervisor
        teams.append({
            "team_number": team.team_number,
            "project_id": team.project_id,
            "project_title": team.project_title,
            "team_size": team.team_size,
            "technical_coverage": team.technical_coverage,
            "technical_deficit": team.technical_deficit,
            "technical_status": team.technical_status,
            "preference_summary": {
                "average_dissatisfaction": team.preference_average_dissatisfaction,
                "first_choice_count": team.first_choice_count,
                "ranked_choice_count": team.ranked_choice_count,
                "unranked_count": team.unranked_count,
            },
            "students": [{
                "student_id": member.student_id,
                "preference_rank": member.preference_rank,
                "dissatisfaction": member.dissatisfaction,
                "ranked_projects": member.ranked_projects,
                "relevant_skills": member.relevant_skills,
            } for member in team.members],
            "requirements": [{
                "technology": requirement.technology,
                "min_level": requirement.min_level,
                "required_members": requirement.required_members,
                "qualified_members": requirement.qualified_members,
                "qualified_students": requirement.qualified_students,
                "coverage": requirement.coverage,
                "status": requirement.status,
            } for requirement in team.requirements],
            "supervisor": None if supervisor is None else {
                "supervisor_id": supervisor.supervisor_id,
                "supervisor_name": supervisor.supervisor_name,
                "match_status": supervisor.match_status,
                "current_load": supervisor.current_load,
                "maximum_teams": supervisor.maximum_teams,
                "projected_load": supervisor.projected_load,
                "remaining_capacity": supervisor.remaining_capacity,
                "project_domains": supervisor.project_domains,
                "expertise_matches": supervisor.expertise_matches,
                "interest_matches": supervisor.interest_matches,
                "explanation": supervisor.explanation,
            },
        })
    return {
        "allocation_id": allocation.id,
        "created_at": allocation.created_at.isoformat(),
        "source_file_name": allocation.source_file_name,
        "algorithm": allocation.algorithm,
        "optimizer_version": allocation.optimizer_version,
        "solution_id": allocation.solution_id,
        "solution_role": allocation.solution_role,
        "students_per_team": allocation.students_per_team,
        "student_count": allocation.student_count,
        "project_count": allocation.project_count,
        "technical_requirement_deficit": allocation.technical_requirement_deficit,
        "technical_requirement_coverage": allocation.technical_requirement_coverage,
        "preference_dissatisfaction": allocation.preference_dissatisfaction,
        "preference_satisfaction": allocation.preference_satisfaction,
        "integrity_valid": allocation.integrity_valid,
        "status": allocation.status,
        "revision_number": allocation.revision_number,
        "parent_allocation_id": allocation.parent_allocation_id,
        "allocation_source": allocation.allocation_source,
        "change_reason": allocation.change_reason,
        "revision_enabled": allocation.reference_data is not None,
        "teams": teams,
    }

def get_supervisor_groups(db: Session, allocation_id: str, supervisor_id: str) -> dict | None:
    allocation = db.scalar(select(FinalAllocation).where(FinalAllocation.id == allocation_id))
    if allocation is None:
        return None
    statement = select(FinalTeam).join(FinalTeamSupervisor, FinalTeamSupervisor.team_id == FinalTeam.id).where(
        FinalTeam.allocation_id == allocation_id,
        FinalTeamSupervisor.supervisor_id == supervisor_id,
    ).options(selectinload(FinalTeam.members), selectinload(FinalTeam.supervisor)).order_by(FinalTeam.team_number)
    teams = list(db.scalars(statement).all())
    if not teams:
        return {
            "allocation_id": allocation_id,
            "revision_number": allocation.revision_number,
            "allocation_source": allocation.allocation_source,
            "supervisor": {"supervisor_id": supervisor_id, "supervisor_name": None},
            "group_count": 0,
            "groups": [],
        }
    supervisor = teams[0].supervisor
    return {
        "allocation_id": allocation_id,
        "revision_number": allocation.revision_number,
        "allocation_source": allocation.allocation_source,
        "supervisor": {"supervisor_id": supervisor.supervisor_id, "supervisor_name": supervisor.supervisor_name},
        "group_count": len(teams),
        "groups": [{
            "group_key": f"{allocation_id}-T{team.team_number:03d}",
            "team_number": team.team_number,
            "project_id": team.project_id,
            "project_title": team.project_title,
            "members": [member.student_id for member in team.members],
        } for team in teams],
    }

def get_active_final_allocation(db: Session) -> dict | None:
    statement = select(FinalAllocation).where(FinalAllocation.status == "ACTIVE").options(
        selectinload(FinalAllocation.teams).selectinload(FinalTeam.members),
        selectinload(FinalAllocation.teams).selectinload(FinalTeam.requirements),
        selectinload(FinalAllocation.teams).selectinload(FinalTeam.supervisor),
    )
    allocation = db.scalar(statement)
    return None if allocation is None else _serialize_allocation(allocation)

def get_active_supervisor_groups(db: Session, supervisor_id: str) -> dict | None:
    allocation_id = db.scalar(select(FinalAllocation.id).where(FinalAllocation.status == "ACTIVE"))
    return None if allocation_id is None else get_supervisor_groups(db, allocation_id, supervisor_id)

def get_active_team_data(db: Session) -> dict | None:
    allocation = get_active_final_allocation(db)
    if allocation is None:
        return None
    return {
        "allocation_id": allocation["allocation_id"],
        "allocation_status": allocation["status"],
        "revision_number": allocation["revision_number"],
        "allocation_source": allocation["allocation_source"],
        "student_count": allocation["student_count"],
        "team_count": allocation["project_count"],
        "teams": [{
            "group_key": f"{allocation['allocation_id']}-T{team['team_number']:03d}",
            "team_number": team["team_number"],
            "project_id": team["project_id"],
            "project_title": team["project_title"],
            "members": [student["student_id"] for student in team["students"]],
            "supervisor": None if not team.get("supervisor") else {
                "supervisor_id": team["supervisor"]["supervisor_id"],
                "supervisor_name": team["supervisor"]["supervisor_name"],
            },
        } for team in allocation["teams"]],
    }
