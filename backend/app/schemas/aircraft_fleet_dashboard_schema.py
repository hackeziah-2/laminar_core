"""Schemas for GET /api/v1/reports/aircraft-fleet-dashboard."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AircraftFleetDashboardComponent(BaseModel):
    """One magneto TCC row. Tach fields are one-decimal strings."""

    magneto: Optional[str] = None
    due_for_replacement_tach: Optional[str] = Field(
        None,
        description="TCC last_done_tach. Null when last done tach is missing.",
    )
    remaining_hours: Optional[str] = Field(
        None,
        description="TCC remaining_tach. Null when remaining tach is missing. Read-only.",
    )
    part_number: Optional[str] = None
    serial_number: Optional[str] = None


class AircraftFleetDashboardItem(BaseModel):
    """One registered aircraft, with Daily Fleet Update and magneto components attached."""

    aircraft_ident: str
    status: Optional[str] = Field(
        None,
        description="Daily Fleet Update status. Null when the aircraft has no update.",
    )
    eod_tach: Optional[str] = Field(
        None,
        description="Daily Fleet Update tach_time_eod. Null when the aircraft has no update.",
    )
    components: List[AircraftFleetDashboardComponent] = Field(default_factory=list)


class AircraftFleetDashboardResponse(BaseModel):
    items: List[AircraftFleetDashboardItem]
    total: int
    page: int
    page_size: int
    pages: int
