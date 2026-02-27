import math
from datetime import date, time, datetime
from typing import Optional, List, Any

import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator

from app.models.aircraft_techinical_log import TypeEnum, WorkStatus


def normalize_datetime(value: Any) -> Any:
    """Coerce pandas NA/NaN to None; extract date() from datetime/timestamp."""
    if pd.isna(value):
        return None
    if hasattr(value, "date"):
        return value.date()
    return value


def _excel_empty_to_none(value: Any) -> Any:
    """Coerce Excel empty/NaN/NA to None for optional fields."""
    if value in (None, "", "NA", "N/A"):
        return None
    if isinstance(value, str) and value.strip().upper() in ("NA", "N/A"):
        return None
    if isinstance(value, float) and (math.isnan(value) or not math.isfinite(value)):
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s or s == "-":
            return None
    return value


def parse_zulu_time_to_time(value: Any) -> Optional[time]:
    """Parse origin_time Zulu/HHMM/HH:MM/HHMMSS into Python time object."""
    value = _excel_empty_to_none(value)
    if value is None:
        return None

    # Already a time object
    if isinstance(value, time):
        return value

    # Numeric input: int or float
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if math.isnan(value) or not math.isfinite(value):
                return None
            value = int(value)  # 0239.0 -> 239
        if not (0 <= value <= 235959):
            return None
        s = str(value).zfill(4)  # 239 -> "0239"
        if len(s) == 4:
            return datetime.strptime(s, "%H%M").time()
        elif len(s) == 6:
            return datetime.strptime(s, "%H%M%S").time()
        return None

    # String input
    if isinstance(value, str):
        s = value.strip().upper()
        # Remove Zulu/UTC suffixes
        if s.endswith((" ZULU", " Z", " UTC")):
            s = s.rsplit(" ", 1)[0]
        elif s.endswith("Z"):
            s = s[:-1]
        s = s.strip()

        # Remove colon
        s_clean = s.replace(":", "")

        # Remove trailing decimal like ".0" from Excel export
        if "." in s_clean:
            s_clean = s_clean.split(".")[0]

        if not s_clean.isdigit():
            raise ValueError(
                f"Invalid time format: '{value}'. Use HH:MM, HHMM (e.g., 2317), or Zulu (e.g., 0440 Zulu)."
            )

        # 3-digit HHMM -> 4-digit
        if len(s_clean) == 3:
            s_clean = "0" + s_clean
        elif len(s_clean) not in (4, 6):
            raise ValueError(f"Invalid time format: '{value}'.")

        if len(s_clean) == 4:
            return datetime.strptime(s_clean, "%H%M").time()
        elif len(s_clean) == 6:
            return datetime.strptime(s_clean, "%H%M%S").time()

    return None


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

    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    work_status: Optional[WorkStatus] = None

    component_parts: Optional[List[ComponentPartsRecordCreate]] = []

    @validator("nature_of_flight", pre=True)
    def empty_str_to_none_nature_of_flight(cls, v: Any) -> Any:
        """Treat empty string, whitespace-only, or "-" as None so DB stores NULL."""
        if v is None or (isinstance(v, str) and (not str(v).strip() or str(v).strip() == "-")):
            return None
        return v

    @validator("nature_of_flight", pre=True)
    def normalize_enum(cls, v: Any) -> Any:
        """Normalize string: strip, upper, replace spaces with underscores (e.g. ATL REPL -> ATL_REPL)."""
        if isinstance(v, str):
            return v.strip().upper().replace(" ", "_")
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
        v = _excel_empty_to_none(v)
        if v is None:
            return None
        return parse_zulu_time_to_time(v)


# ---------- Aircraft Technical Log Create Schema ----------
class AircraftTechnicalLogCreate(AircraftTechnicalLogBase):
    pass


# ---------- Aircraft Technical Log Import Schema (Excel/CSV) ----------
class AircraftTechnicalLogImportSchema(AircraftTechnicalLogBase):
    """Schema for validating Aircraft Technical Log rows during Excel/CSV import.
    Coerces Excel NaN, empty, '-' and float-integer values to None so empty cells validate.
    """

    @root_validator(pre=True)
    def excel_empty_and_dash_to_none(cls, values: Any) -> Any:
        """Coerce empty string and '-' to None for every field in import row."""
        if not isinstance(values, dict):
            return values
        return {k: _excel_empty_to_none(v) for k, v in values.items()}

    @validator(
        "destination_date",
        "origin_date",
        "pilot_accept_date",
        "rts_date",
        pre=True,
    )
    def excel_date_to_none(cls, v: Any) -> Any:
        """Coerce Excel NaN to None; normalize datetime/timestamp to date."""
        v = _excel_empty_to_none(v)
        v = normalize_datetime(v)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return v

    @validator(
        "destination_time",
        "origin_time",
        "pilot_accept_time",
        "rts_time",
        pre=True,
    )
    def excel_time_to_none(cls, v: Any) -> Any:
        """Coerce Excel NaN to None before time parsing."""
        v = _excel_empty_to_none(v)
        if v is None:
            return None
        return parse_zulu_time_to_time(v)

    @validator(
        "number_of_landings",
        "remark_person",
        "actiontaken_person",
        "pilot_fk",
        "maintenance_fk",
        "pilot_accepted_by",
        "rts_signed_by",
        pre=True,
    )
    def excel_int_to_none_or_int(cls, v: Any) -> Any:
        """Coerce Excel NaN to None; allow float that is whole number (e.g. 1.0) as int."""
        v = _excel_empty_to_none(v)
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            if math.isnan(v) or not math.isfinite(v):
                return None
            if v == int(v):
                return int(v)
            return None
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return None

    class Config:
        orm_mode = True


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

    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    work_status: Optional[WorkStatus] = None

    component_parts: Optional[List[ComponentPartsRecordCreate]] = None

    @validator("nature_of_flight", pre=True)
    def empty_str_to_none_nature_of_flight_update(cls, v: Any) -> Any:
        """Treat empty string, whitespace-only, or "-" as None so DB stores NULL."""
        if v is None or (isinstance(v, str) and (not str(v).strip() or str(v).strip() == "-")):
            return None
        return v

    @validator("nature_of_flight", pre=True)
    def normalize_enum_update(cls, v: Any) -> Any:
        """Normalize string: strip, upper, replace spaces with underscores."""
        if isinstance(v, str):
            return v.strip().upper().replace(" ", "_")
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
    """Minimal ATL search result for TCC ATL Reference dropdown / Sequence No. type-to-search. id is aircraft_technical_log.id (use as atl_ref). sequence_no_display is for UI (e.g. ATL-24451)."""
    id: int
    sequence_no: str
    sequence_no_display: Optional[str] = None  # "ATL-{sequence_no}" for dropdown label
    aircraft: AircraftRead

    @validator("sequence_no_display", always=True)
    def set_sequence_no_display(cls, v: Any, values: dict) -> str:
        seq = values.get("sequence_no")
        if not seq:
            return ""
        s = str(seq).strip()
        if s.upper().startswith("ATL"):
            return s
        return f"ATL-{s}"

    class Config:
        orm_mode = True


# ---------- Aircraft Technical Log Read Schema ----------
class AircraftTechnicalLogRead(AircraftTechnicalLogBase):
    id: int
    aircraft: Optional[AircraftRead] = None
    component_parts: List[ComponentPartsRecordRead] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    work_status: Optional[WorkStatus] = None
    # Display value: "-" when nature_of_flight is None/empty
    nature_of_flight_display: Optional[str] = None

    @validator("nature_of_flight_display", always=True)
    def set_nature_of_flight_display(cls, v: Any, values: dict) -> str:
        nof = values.get("nature_of_flight")
        return nof.value if nof is not None else "-"

    class Config:
        orm_mode = True


# ---------- ATL Paged response (Read + auto_comp_* computed fields) ----------
class ATLPagedItem(AircraftTechnicalLogRead):
    """ATL read with computed fields: auto_comp_airframe_run_time, auto_comp_airframe_aftt, etc."""

    auto_comp_airframe_run_time: Optional[float] = 0.0
    auto_comp_airframe_aftt: Optional[float] = 0.0
    auto_comp_engine_run_time: Optional[float] = 0.0
    auto_comp_engine_tsn: Optional[float] = 0.0
    auto_comp_engine_tso: Optional[float] = 0.0
    auto_comp_engine_tbo: Optional[float] = 0.0
    auto_comp_propeller_run_time: Optional[float] = 0.0
    auto_comp_propeller_tsn: Optional[float] = 0.0
    auto_comp_propeller_tso: Optional[float] = 0.0
    auto_comp_propeller_tbo: Optional[float] = 0.0

    class Config:
        orm_mode = True
