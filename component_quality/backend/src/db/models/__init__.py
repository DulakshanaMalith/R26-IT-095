"""Import all PostgreSQL models so Alembic can see complete metadata."""

from src.db.models.history import AnalysisHistoryRecord, GradingRecord, KnowledgeGraphRecord
from src.db.models.workflow import (
    AiSupervisorReviewDraft,
    Analysis,
    NotificationLog,
    Proposal,
    ProposalVersion,
    Student,
    SupervisorProfile,
    SupervisorReview,
    SupervisorReviewDraft,
    SupervisorStudentAssignment,
    User,
)

__all__ = [
    "AiSupervisorReviewDraft",
    "Analysis",
    "AnalysisHistoryRecord",
    "GradingRecord",
    "KnowledgeGraphRecord",
    "NotificationLog",
    "Proposal",
    "ProposalVersion",
    "Student",
    "SupervisorProfile",
    "SupervisorReview",
    "SupervisorReviewDraft",
    "SupervisorStudentAssignment",
    "User",
]

