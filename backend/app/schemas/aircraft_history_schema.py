from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.aircraft_schema import AircraftOut


class AircraftHistoryRead(BaseModel):
    id: int
    aircraft_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[int] = None
    changed_by_name: Optional[str] = None
    changed_at: datetime
    action_type: str

    class Config:
        orm_mode = True


class AircraftUpdateWithHistoryResponse(BaseModel):
    aircraft: AircraftOut
    history_records: list[AircraftHistoryRead]

    class Config:
        orm_mode = True
