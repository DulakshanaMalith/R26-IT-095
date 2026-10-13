from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class FinalAllocationCreateRequest(BaseModel):
    source_file_name: Optional[str] = None
    students_per_team: int = Field(ge=2)
    optimizer: Dict[str, Any] = Field(default_factory=dict)
    selected_solution: Dict[str, Any]
    supervisor_allocation: Dict[str, Any]
