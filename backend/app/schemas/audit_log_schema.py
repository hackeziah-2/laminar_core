from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuditLogRead(BaseModel):
    id: int
    module_name: str
    table_name: str
    record_id: int
    action: str
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None
    performed_by_user_id: Optional[int] = None
    performed_by_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class AuditLogPagedResponse(BaseModel):
    page: int
    limit: int
    total: int
    items: List[AuditLogRead] = Field(default_factory=list)
