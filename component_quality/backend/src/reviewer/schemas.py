from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Issue(BaseModel):
    issue_id: str = Field(..., description="A unique identifier for this issue (e.g., 'issue_001').")
    type: Literal["Weakness", "Strength"] = Field(..., description="Whether this is a weakness or strength.")
    severity: Literal["low", "medium", "high"] = Field(..., description="Severity of the issue. Use 'low' for strengths.")
    section: str = Field(..., description="The section of the proposal this issue relates to (e.g., 'Methodology', 'Motivation').")
    criterion: str = Field(..., description="The evaluation criterion this relates to, if applicable.")
    evidence_span: str = Field(..., description="The EXACT text span from the proposal that serves as evidence. MUST be a direct quote.")
    reason: str = Field(..., description="A detailed explanation of why this is a weakness or strength.")
    recommendation: str = Field(..., description="Actionable recommendation for the author to address the weakness.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model-generated confidence score (0.0 to 1.0). Not calibrated.")
    retrieved_example_ids: List[str] = Field(default_factory=list, description="IDs of any historical RAG examples that influenced this issue.")

class ReviewResult(BaseModel):
    proposal_summary: str = Field(..., description="A brief, 2-3 sentence summary of the entire proposal.")
    overall_assessment: str = Field(..., description="High-level assessment of the proposal's quality.")
    issues: List[Issue] = Field(..., description="List of weaknesses identified in the proposal.")
    strengths: List[Issue] = Field(..., description="List of strengths identified in the proposal.")
    criterion_results: List[dict] = Field(default_factory=list, description="Scores or structured feedback per criterion, if applicable.")
