from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class AircraftDetail(BaseModel):
    """Aircraft summary for document-on-board responses (registration, model, status)."""

    registration: str
    model: str
    status: str

    @validator("status", pre=True)
    def status_to_str(cls, v):
        if hasattr(v, "value"):
            return v.value
        return str(v) if v is not None else None

    class Config:
        orm_mode = True


class DocumentOnBoardBase(BaseModel):
    aircraft_id: int
    document_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    issue_date: date
    expiry_date: Optional[date] = None
    warning_days: Optional[int] = Field(default=30, ge=0)
    status: Optional[str] = "Active"
    file_path: Optional[str] = Field(None, max_length=500)

    @validator("status", pre=True)
    def validate_status(cls, v):
        """Validate status value (case-insensitive)."""
        if v is None:
            return "Active"
        valid_statuses = ["active", "expired", "expiring soon", "inactive"]
        if str(v).lower().strip() not in valid_statuses:
            raise ValueError(
                f"Invalid status: {v}. Must be one of: Active, Expired, Expiring Soon, Inactive"
            )
        return v

    class Config:
        orm_mode = True


class DocumentOnBoardCreate(DocumentOnBoardBase):
    pass


class DocumentOnBoardUpdate(BaseModel):
    aircraft_id: Optional[int] = None
    document_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    warning_days: Optional[int] = Field(None, ge=0)
    status: Optional[str] = None
    file_path: Optional[str] = Field(None, max_length=500)

    @validator("status", pre=True)
    def validate_status(cls, v):
        """Validate status value (case-insensitive)."""
        if v is None:
            return None
        valid_statuses = ["active", "expired", "expiring soon", "inactive"]
        if str(v).lower().strip() not in valid_statuses:
            raise ValueError(
                f"Invalid status: {v}. Must be one of: Active, Expired, Expiring Soon, Inactive"
            )
        return v

    class Config:
        orm_mode = True


class DocumentOnBoardRead(DocumentOnBoardBase):
    document_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    aircraft: Optional[AircraftDetail] = None

    class Config:
        orm_mode = True
