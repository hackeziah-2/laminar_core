from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


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
