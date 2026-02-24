from datetime import date, time, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, validator
from app.models.aircraft_techinical_log import TypeEnum


def parse_zulu_time_to_time(value: Any) -> Optional[time]:
    """Parse Zulu time string (HH:MM or HH:MM:SS, 24-hour) to Python time object."""
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if len(s) == 5:  # HH:MM
            return datetime.strptime(s, "%H:%M").time()
        if len(s) == 8:  # HH:MM:SS
            return datetime.strptime(s, "%H:%M:%S").time()
        raise ValueError(f"Invalid time format: '{value}'. Use HH:MM or HH:MM:SS (24-hour).")
    return value


# ---------- Component Parts Record Schemas ----------
class ComponentPartsRecordBase(BaseModel):
    qty: float
    unit: str = Field(..., max_length=20)
    nomenclature: str = Field(..., max_length=255)
    removed_part_no: Optional[str] = Field(None, max_length=100)
    removed_serial_no: Optional[str] = Field(None, max_length=100)
    installed_part_no: Optional[str] = Field(None, max_length=100)
    installed_serial_no: Optional[str] = Field(None, max_length=100)
    part_description: Optional[str] = None
    ata_chapter: Optional[str] = Field(None, max_length=50)


class ComponentPartsRecordCreate(ComponentPartsRecordBase):
    pass


class ComponentPartsRecordUpdate(BaseModel):
    qty: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=20)
    nomenclature: Optional[str] = Field(None, max_length=255)
    removed_part_no: Optional[str] = Field(None, max_length=100)
    removed_serial_no: Optional[str] = Field(None, max_length=100)
    installed_part_no: Optional[str] = Field(None, max_length=100)
    installed_serial_no: Optional[str] = Field(None, max_length=100)
    part_description: Optional[str] = None
    ata_chapter: Optional[str] = Field(None, max_length=50)


class ComponentPartsRecordRead(ComponentPartsRecordBase):
    id: int

    class Config:
        orm_mode = True


# ---------- Aircraft Technical Log Base Schema ----------
# Only sequence_no and aircraft_fk are required; all other fields are optional.
class AircraftTechnicalLogBase(BaseModel):
    aircraft_fk: int = Field(..., description="Aircraft ID (required).")
    sequence_no: str = Field(..., max_length=50, description="ATL sequence number (required).")
    nature_of_flight: Optional[TypeEnum] = None
    next_inspection_due: Optional[str] = Field(None, max_length=100)
    tach_time_due: Optional[float] = None

    origin_station: Optional[str] = Field(None, max_length=50)
    origin_date: Optional[date] = None
    origin_time: Optional[time] = None

    destination_station: Optional[str] = Field(None, max_length=50)
    destination_date: Optional[date] = None
    destination_time: Optional[time] = None

    number_of_landings: Optional[int] = None

    hobbs_meter_start: Optional[float] = Field(None, description="Auto-populated from previous ATL entry if not provided")
    hobbs_meter_end: Optional[float] = None
    hobbs_meter_total: Optional[float] = None

    tachometer_start: Optional[float] = Field(None, description="Auto-populated from previous ATL entry if not provided")
    tachometer_end: Optional[float] = None
    tachometer_total: Optional[float] = None

    # Airframe time fields
    airframe_prev_time: Optional[float] = None
    airframe_flight_time: Optional[float] = None
    airframe_total_time: Optional[float] = None
    airframe_run_time: Optional[float] = None
    airframe_aftt: Optional[float] = None

    # Engine time fields
    engine_prev_time: Optional[float] = None
    engine_flight_time: Optional[float] = None
    engine_total_time: Optional[float] = None
    engine_run_time: Optional[float] = None
    engine_tsn: Optional[str] = Field(None, max_length=100)
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None

    # Propeller time fields
    propeller_prev_time: Optional[float] = None
    propeller_flight_time: Optional[float] = None
    propeller_total_time: Optional[float] = None
    propeller_run_time: Optional[float] = None
    propeller_tsn: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None

    # Life time limits
    life_time_limit_engine: Optional[float] = None
    life_time_limit_propeller: Optional[float] = None

    fuel_qty_left_uplift_qty: Optional[float] = None
    fuel_qty_right_uplift_qty: Optional[float] = None
    fuel_qty_left_prior_departure: Optional[float] = None
    fuel_qty_right_prior_departure: Optional[float] = None
    fuel_qty_left_after_on_blks: Optional[float] = None
    fuel_qty_right_after_on_blks: Optional[float] = None

    oil_qty_uplift_qty: Optional[float] = None
    oil_qty_prior_departure: Optional[float] = None
    oil_qty_after_on_blks: Optional[float] = None

    remarks: Optional[str] = None
    actions_taken: Optional[str] = None

    remark_person: Optional[int] = None
    actiontaken_person: Optional[int] = None

    pilot_fk: Optional[int] = None
    maintenance_fk: Optional[int] = None

    pilot_accepted_by: Optional[int] = None
    pilot_accept_date: Optional[date] = None
    pilot_accept_time: Optional[time] = None

    rts_signed_by: Optional[int] = None
    rts_date: Optional[date] = None
    rts_time: Optional[time] = None

    white_atl: Optional[str] = None
    dfp: Optional[str] = None

    component_parts: Optional[List[ComponentPartsRecordCreate]] = []

    @validator("nature_of_flight", pre=True)
    def empty_str_to_none_nature_of_flight(cls, v: Any) -> Any:
        """Treat empty string or "-" as None for optional nature_of_flight."""
        if v is None or (isinstance(v, str) and (not str(v).strip() or str(v).strip() == "-")):
            return None
        return v

    @validator("origin_station", "origin_date", "destination_station", "destination_date", pre=True)
    def empty_str_to_none_origin_dest(cls, v: Any) -> Any:
        """Treat empty string as None for origin/destination fields."""
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        return v

    @validator("origin_time", "destination_time", "pilot_accept_time", "rts_time", pre=True)
    def parse_time_fields(cls, v: Any) -> Any:
        """Accept Zulu time strings (HH:MM or HH:MM:SS, 24-hour) and convert to time."""
        return parse_zulu_time_to_time(v)


# ---------- Aircraft Technical Log Create Schema ----------
class AircraftTechnicalLogCreate(AircraftTechnicalLogBase):
    pass


# ---------- Aircraft Technical Log Update Schema ----------
class AircraftTechnicalLogUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    nature_of_flight: Optional[TypeEnum] = None
    next_inspection_due: Optional[str] = Field(None, max_length=100)
    tach_time_due: Optional[float] = None

    origin_station: Optional[str] = Field(None, max_length=50)
    origin_date: Optional[date] = None
    origin_time: Optional[time] = None

    destination_station: Optional[str] = Field(None, max_length=50)
    destination_date: Optional[date] = None
    destination_time: Optional[time] = None

    number_of_landings: Optional[int] = None

    hobbs_meter_start: Optional[float] = None
    hobbs_meter_end: Optional[float] = None
    hobbs_meter_total: Optional[float] = None

    tachometer_start: Optional[float] = None
    tachometer_end: Optional[float] = None
    tachometer_total: Optional[float] = None

    # Airframe time fields
    airframe_prev_time: Optional[float] = None
    airframe_flight_time: Optional[float] = None
    airframe_total_time: Optional[float] = None
    airframe_run_time: Optional[float] = None
    airframe_aftt: Optional[float] = None

    # Engine time fields
    engine_prev_time: Optional[float] = None
    engine_flight_time: Optional[float] = None
    engine_total_time: Optional[float] = None
    engine_run_time: Optional[float] = None
    engine_tsn: Optional[str] = Field(None, max_length=100)
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None

    # Propeller time fields
    propeller_prev_time: Optional[float] = None
    propeller_flight_time: Optional[float] = None
    propeller_total_time: Optional[float] = None
    propeller_run_time: Optional[float] = None
    propeller_tsn: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None

    # Life time limits
    life_time_limit_engine: Optional[float] = None
    life_time_limit_propeller: Optional[float] = None

    fuel_qty_left_uplift_qty: Optional[float] = None
    fuel_qty_right_uplift_qty: Optional[float] = None
    fuel_qty_left_prior_departure: Optional[float] = None
    fuel_qty_right_prior_departure: Optional[float] = None
    fuel_qty_left_after_on_blks: Optional[float] = None
    fuel_qty_right_after_on_blks: Optional[float] = None

    oil_qty_uplift_qty: Optional[float] = None
    oil_qty_prior_departure: Optional[float] = None
    oil_qty_after_on_blks: Optional[float] = None

    remarks: Optional[str] = None
    actions_taken: Optional[str] = None

    remark_person: Optional[int] = None
    actiontaken_person: Optional[int] = None

    pilot_fk: Optional[int] = None
    maintenance_fk: Optional[int] = None

    pilot_accepted_by: Optional[int] = None
    pilot_accept_date: Optional[date] = None
    pilot_accept_time: Optional[time] = None

    rts_signed_by: Optional[int] = None
    rts_date: Optional[date] = None
    rts_time: Optional[time] = None

    white_atl: Optional[str] = None
    dfp: Optional[str] = None

    component_parts: Optional[List[ComponentPartsRecordCreate]] = None

    @validator("nature_of_flight", pre=True)
    def empty_str_to_none_nature_of_flight_update(cls, v: Any) -> Any:
        """Treat empty string or "-" as None for optional nature_of_flight."""
        if v is None or (isinstance(v, str) and (not str(v).strip() or str(v).strip() == "-")):
            return None
        return v

    @validator("origin_station", "origin_date", "destination_station", "destination_date", pre=True)
    def empty_str_to_none_origin_dest_update(cls, v: Any) -> Any:
        """Treat empty string as None for origin/destination fields."""
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        return v

    @validator("origin_time", "destination_time", "pilot_accept_time", "rts_time", pre=True)
    def parse_time_fields(cls, v: Any) -> Any:
        """Accept Zulu time strings (HH:MM or HH:MM:SS) and convert to time."""
        return parse_zulu_time_to_time(v)


# ---------- Aircraft Read Schema (for nested display) ----------
class AircraftRead(BaseModel):
    id: int
    registration: str
    model: str

    class Config:
        orm_mode = True


# ---------- ATL Search response (id for atl_ref, sequence_no + aircraft summary) ----------
class ATLSearchItem(BaseModel):
    """Minimal ATL search result for TCC ATL Reference dropdown. id is aircraft_technical_log.id (use as atl_ref)."""
    id: int
    sequence_no: str
    aircraft: AircraftRead

    class Config:
        orm_mode = True


# ---------- Aircraft Technical Log Read Schema ----------
class AircraftTechnicalLogRead(AircraftTechnicalLogBase):
    id: int
    aircraft: Optional[AircraftRead] = None
    component_parts: List[ComponentPartsRecordRead] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Display value: "-" when nature_of_flight is None/empty
    nature_of_flight_display: Optional[str] = None

    @validator("nature_of_flight_display", always=True)
    def set_nature_of_flight_display(cls, v: Any, values: dict) -> str:
        nof = values.get("nature_of_flight")
        return nof.value if nof is not None else "-"

    class Config:
        orm_mode = True
