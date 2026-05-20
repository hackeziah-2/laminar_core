from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, validator

from app.services.excel_import.parsers import parse_import_date


class AircraftSummary(BaseModel):
    id: int
    registration: str

    class Config:
        orm_mode = True


# ---------- ADMonitoring ----------
class ADMonitoringBase(BaseModel):
    aircraft_fk: int
    ad_number: str = Field(..., max_length=100)
    subject: str = Field(..., max_length=100)
    inspection_interval: str = Field(..., max_length=100)
    compli_date: Optional[date] = None
    file_path: Optional[str] = Field(None, max_length=500)

    class Config:
        orm_mode = True


class ADMonitoringCreate(ADMonitoringBase):
    pass


class ADMonitoringImportSchema(BaseModel):
    """One spreadsheet row for AD monitoring import (aircraft_fk from form context)."""

    aircraft_fk: int
    ad_number: str = Field(..., max_length=100)
    subject: str = Field(..., max_length=100)
    inspection_interval: str = Field(..., max_length=100)
    compli_date: Optional[date] = None

    @staticmethod
    def _coerce_required_str(v: Any, field_name: str) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError(f"{field_name} is required")
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        if isinstance(v, int) and not isinstance(v, bool):
            return str(v)
        return str(v).strip()

    @validator("ad_number", pre=True)
    def coerce_ad_number(cls, v: Any) -> str:
        return cls._coerce_required_str(v, "ad_number")

    @validator("subject", pre=True)
    def coerce_subject(cls, v: Any) -> str:
        return cls._coerce_required_str(v, "subject")

    @validator("inspection_interval", pre=True)
    def coerce_inspection_interval(cls, v: Any) -> str:
        return cls._coerce_required_str(v, "inspection_interval")

    @validator("compli_date", pre=True)
    def coerce_import_date(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        parsed = parse_import_date(v)
        if isinstance(parsed, date):
            return parsed
        if isinstance(parsed, str):
            raise ValueError(f"invalid date format: {parsed!r}")
        return parsed


class ADMonitoringUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    ad_number: Optional[str] = Field(None, max_length=100)
    subject: Optional[str] = Field(None, max_length=100)
    inspection_interval: Optional[str] = Field(None, max_length=100)
    compli_date: Optional[date] = None
    file_path: Optional[str] = Field(None, max_length=500)

    class Config:
        orm_mode = True


class ADMonitoringRead(ADMonitoringBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    aircraft: Optional[AircraftSummary] = None
    ad_works: Optional[List["WorkOrderADMonitoringSummary"]] = None

    class Config:
        orm_mode = True


# ---------- WorkOrderADMonitoring ----------
class ADMonitoringSummary(BaseModel):
    """Embedded in WorkOrderADMonitoringRead."""

    id: int
    ad_number: str
    subject: Optional[str] = None

    class Config:
        orm_mode = True


class WorkOrderADMonitoringSummary(BaseModel):
    """Embedded in ADMonitoringRead.ad_works."""

    id: int
    ad_monitoring_fk: int
    work_order_number: str
    atl_ref: str
    last_done_date: Optional[date] = None
    last_done_tach: Optional[float] = None
    next_done_actt: Optional[float] = None

    class Config:
        orm_mode = True


class WorkOrderADMonitoringBase(BaseModel):
    ad_monitoring_fk: int
    work_order_number: str = Field(..., max_length=50)
    last_done_actt: Optional[float] = None
    last_done_tach: Optional[float] = None
    last_done_date: Optional[date] = None
    next_done_actt: Optional[float] = None
    tach: Optional[float] = None
    atl_ref: str = Field(..., max_length=50)

    class Config:
        orm_mode = True


class WorkOrderADMonitoringCreate(WorkOrderADMonitoringBase):
    pass


def _coerce_optional_float(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s or s in ("-", "NA", "N/A"):
            return None
        try:
            return float(s)
        except ValueError:
            return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return v


class WorkOrderADMonitoringImportSchema(BaseModel):
    """One spreadsheet row for AD work-order import (ad_monitoring_fk from form context)."""

    ad_monitoring_fk: int
    work_order_number: str = Field(..., max_length=50)
    last_done_actt: Optional[float] = None
    last_done_tach: Optional[float] = None
    last_done_date: Optional[date] = None
    next_done_actt: Optional[float] = None
    tach: Optional[float] = None
    atl_ref: str = Field(..., max_length=50)

    @staticmethod
    def _coerce_required_str(v: Any, field_name: str) -> str:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError(f"{field_name} is required")
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        if isinstance(v, int) and not isinstance(v, bool):
            return str(v)
        return str(v).strip()

    @validator("work_order_number", pre=True)
    def coerce_work_order_number(cls, v: Any) -> str:
        return cls._coerce_required_str(v, "work_order_number")

    @validator("atl_ref", pre=True)
    def coerce_atl_ref(cls, v: Any) -> str:
        return cls._coerce_required_str(v, "atl_ref")

    @validator(
        "last_done_actt",
        "last_done_tach",
        "next_done_actt",
        "tach",
        pre=True,
    )
    def coerce_optional_floats(cls, v: Any) -> Any:
        return _coerce_optional_float(v)

    @validator("last_done_date", pre=True)
    def coerce_import_date(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        parsed = parse_import_date(v)
        if isinstance(parsed, date):
            return parsed
        if isinstance(parsed, str):
            raise ValueError(f"invalid date format: {parsed!r}")
        return parsed


class WorkOrderADMonitoringUpdate(BaseModel):
    """Partial update; all fields optional."""

    ad_monitoring_fk: Optional[int] = None
    work_order_number: Optional[str] = Field(None, max_length=50)
    last_done_actt: Optional[float] = None
    last_done_tach: Optional[float] = None
    last_done_date: Optional[date] = None
    next_done_actt: Optional[float] = None
    tach: Optional[float] = None
    atl_ref: Optional[str] = Field(None, max_length=50)

    class Config:
        orm_mode = True


class WorkOrderADMonitoringRead(WorkOrderADMonitoringBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ad_monitoring: Optional[ADMonitoringSummary] = None

    class Config:
        orm_mode = True


ADMonitoringRead.update_forward_refs()
