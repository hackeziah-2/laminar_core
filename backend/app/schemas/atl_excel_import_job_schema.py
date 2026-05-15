from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AtlExcelImportStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class AtlExcelImportProgressResponse(BaseModel):
    job_id: str
    progress: float = Field(..., description="processed_rows / total_rows * 100 (0 if total_rows is 0)")
    status: str
    message: Optional[str] = None
    total_rows: int = 0
    processed_rows: int = 0
    failed_rows: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
