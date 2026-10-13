from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.database import Base

class FinalAllocation(Base):
    __tablename__ = "final_allocations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(120), nullable=False)
    optimizer_version: Mapped[str] = mapped_column(String(30), nullable=False)
    solution_id: Mapped[int] = mapped_column(Integer, nullable=False)
    solution_role: Mapped[str] = mapped_column(String(160), nullable=False)
    students_per_team: Mapped[int] = mapped_column(Integer, nullable=False)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False)
    project_count: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_requirement_deficit: Mapped[float] = mapped_column(Float, nullable=False)
    technical_requirement_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    preference_dissatisfaction: Mapped[float] = mapped_column(Float, nullable=False)
    preference_satisfaction: Mapped[float] = mapped_column(Float, nullable=False)
    integrity_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_allocation_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    allocation_source: Mapped[str] = mapped_column(String(40), nullable=False, default="OPTIMIZER")
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    teams: Mapped[list["FinalTeam"]] = relationship(back_populates="allocation", cascade="all, delete-orphan", order_by="FinalTeam.team_number")

class FinalTeam(Base):
    __tablename__ = "final_teams"
    __table_args__ = (UniqueConstraint("allocation_id", "project_id", name="uq_final_team_allocation_project"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    allocation_id: Mapped[str] = mapped_column(ForeignKey("final_allocations.id", ondelete="CASCADE"), nullable=False, index=True)
    team_number: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False)
    project_title: Mapped[str] = mapped_column(String(500), nullable=False)
    team_size: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    technical_deficit: Mapped[float] = mapped_column(Float, nullable=False)
    technical_status: Mapped[str] = mapped_column(String(120), nullable=False)
    preference_average_dissatisfaction: Mapped[float] = mapped_column(Float, nullable=False)
    first_choice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ranked_choice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unranked_count: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation: Mapped[FinalAllocation] = relationship(back_populates="teams")
    members: Mapped[list["FinalTeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan", order_by="FinalTeamMember.student_id")
    requirements: Mapped[list["FinalTeamRequirement"]] = relationship(back_populates="team", cascade="all, delete-orphan", order_by="FinalTeamRequirement.technology")
    supervisor: Mapped[Optional["FinalTeamSupervisor"]] = relationship(back_populates="team", cascade="all, delete-orphan", uselist=False)

class FinalTeamMember(Base):
    __tablename__ = "final_team_members"
    __table_args__ = (UniqueConstraint("team_id", "student_id", name="uq_final_team_member"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("final_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(100), nullable=False)
    preference_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dissatisfaction: Mapped[float] = mapped_column(Float, nullable=False)
    ranked_projects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    relevant_skills: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    team: Mapped[FinalTeam] = relationship(back_populates="members")

class FinalTeamRequirement(Base):
    __tablename__ = "final_team_requirements"
    __table_args__ = (UniqueConstraint("team_id", "technology", name="uq_final_team_requirement"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("final_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    technology: Mapped[str] = mapped_column(String(120), nullable=False)
    min_level: Mapped[int] = mapped_column(Integer, nullable=False)
    required_members: Mapped[int] = mapped_column(Integer, nullable=False)
    qualified_members: Mapped[int] = mapped_column(Integer, nullable=False)
    qualified_students: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    coverage: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    team: Mapped[FinalTeam] = relationship(back_populates="requirements")

class FinalTeamSupervisor(Base):
    __tablename__ = "final_team_supervisors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("final_teams.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    supervisor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    supervisor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_status: Mapped[str] = mapped_column(String(120), nullable=False)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_teams: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_load: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    project_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expertise_matches: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    interest_matches: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    team: Mapped[FinalTeam] = relationship(back_populates="supervisor")
