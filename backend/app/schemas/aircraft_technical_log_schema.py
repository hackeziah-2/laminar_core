import math
import re
from datetime import date, time, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator

from app.models.aircraft_techinical_log import TypeEnum, WorkStatus
from app.schemas.atl_batch_schema import AtlBatchBrief


def normalize_datetime(value: Any) -> Any:
    """Coerce pandas NA/NaN to None; extract date() from datetime/timestamp."""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or not math.isfinite(value)):
            return None
        if 1 <= float(value) < 100000:
            # Excel serial date (1900 system)
            return (datetime(1899, 12, 30) + timedelta(days=int(float(value)))).date()
        return value
    if isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r"\d+(?:\.0+)?", s):
            try:
                fv = float(s)
                if 1 <= fv < 100000:
                    return (datetime(1899, 12, 30) + timedelta(days=int(fv))).date()
            except ValueError:
                return value
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


def _import_scalar_clean(value: Any) -> Any:
    """Like _excel_empty_to_none but also treats pandas NA as None (nested part cells)."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return _excel_empty_to_none(value)


def normalize_component_part_dict_for_import(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one ComponentPartsRecord row from Excel/CSV before ComponentPartsRecordCreate validation."""
    d = dict(raw)

    q = _import_scalar_clean(d.get("qty"))
    if q is None:
        d["qty"] = 1.0
    elif isinstance(q, str):
        s = q.strip().replace(",", "")
        try:
            d["qty"] = float(s)
        except ValueError:
            d["qty"] = 1.0
    elif isinstance(q, (int, float)):
        if isinstance(q, float) and (math.isnan(q) or not math.isfinite(q)):
            d["qty"] = 1.0
        else:
            d["qty"] = float(q)
    else:
        d["qty"] = 1.0

    unit = _import_scalar_clean(d.get("unit"))
    d["unit"] = (str(unit).strip()[:20] if unit is not None and str(unit).strip() else "EA")

    nom = _import_scalar_clean(d.get("nomenclature"))
    if nom is not None:
        nom = str(nom).strip()[:255]
    if not nom:
        pd_ = _import_scalar_clean(d.get("part_description"))
        if pd_ is not None:
            nom = str(pd_).strip()[:255]
    if not nom:
        for alt in ("installed_part_no", "removed_part_no"):
            pn = _import_scalar_clean(d.get(alt))
            if pn is not None:
                nom = str(pn).strip()[:255]
                break
    d["nomenclature"] = nom or ""

    for key in (
        "removed_part_no",
        "removed_serial_no",
        "installed_part_no",
        "installed_serial_no",
        "ata_chapter",
    ):
        v = _import_scalar_clean(d.get(key))
        if v is None:
            d[key] = None
        elif isinstance(v, float) and math.isfinite(v) and v == int(v):
            d[key] = str(int(v))[:100]
        else:
            s = str(v).strip()
            d[key] = s[:100] if s else None

    for key in (
        "part_description",
        "part_remark",
        "part_installed_remaining_time",
        "part_removed_remaining_time",
    ):
        v = _import_scalar_clean(d.get(key))
        if v is None:
            d[key] = None
        elif isinstance(v, float) and math.isfinite(v) and v == int(v):
            d[key] = str(int(v))
        else:
            s = str(v).strip()
            d[key] = s if s else None

    return d


def normalize_sequence_no_digits_only(value: str) -> str:
    """Normalize to number-only: strip optional leading 'ATL-', then whitespace. '001' or 'ATL-001' -> '001'. Stored value is digits only."""
    if not value or not str(value).strip():
        return value
    s = str(value).strip()
    if s.upper().startswith("ATL-"):
        s = s[4:].lstrip()
    return s


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


def parse_import_reported_released_datetime(value: Any) -> Any:
    """Parse import strings for date_time_reported / date_time_released.

    Accepts: ``01-Mar-24 0738Z``, ``01-Mar-24 0738``, ``01-Mar-24`` (midnight),
    plus Excel timestamps and existing datetime/date objects.
    """
    v = _excel_empty_to_none(value)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, datetime):
        return v
    if isinstance(v, date) and not isinstance(v, datetime):
        return datetime.combine(v, time.min)
    if hasattr(v, "to_pydatetime"):
        try:
            return v.to_pydatetime()
        except Exception:
            pass
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return None

    m = re.fullmatch(
        r"(\d{2})-([A-Za-z]{3})-(\d{2})(?:\s+(\d{3,6})(Z)?)?",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        day_s, mon_s, yr_s, hhmm_s, _z = m.groups()
        date_s = f"{day_s}-{mon_s.capitalize()}-{yr_s}"
        try:
            d = datetime.strptime(date_s, "%d-%b-%y").date()
        except ValueError:
            return v
        if not hhmm_s:
            return datetime.combine(d, time.min)
        t_digits = hhmm_s
        if len(t_digits) == 3:
            t_digits = "0" + t_digits
        try:
            if len(t_digits) == 4:
                tm = datetime.strptime(t_digits, "%H%M").time()
            elif len(t_digits) == 6:
                tm = datetime.strptime(t_digits, "%H%M%S").time()
            else:
                return v
        except ValueError:
            return v
        return datetime.combine(d, tm)

    return v


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
    part_installed_remaining_time: Optional[str] = None
    part_removed_remaining_time: Optional[str] = None
    part_remark: Optional[str] = None


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
    part_installed_remaining_time: Optional[str] = None
    part_removed_remaining_time: Optional[str] = None
    part_remark: Optional[str] = None


class ComponentPartsRecordRead(ComponentPartsRecordBase):
    id: int

    class Config:
        orm_mode = True


# ---------- Aircraft Technical Log Base Schema ----------
# Only sequence_no and aircraft_fk are required; all other fields are optional.
class AircraftTechnicalLogBase(BaseModel):
    aircraft_fk: int = Field(..., description="Aircraft ID (required).")
    atl_batch_fk: Optional[int] = Field(None, description="Optional ATL batch grouping.")
    sequence_no: str = Field(..., max_length=50, description="ATL sequence number (required). Stored as number only (e.g. 001).")

    @validator("sequence_no", pre=True)
    def normalize_sequence_no(cls, v: Any) -> str:
        """Normalize sequence_no to number only for create/import (strip optional ATL- prefix)."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        return normalize_sequence_no_digits_only(str(v).strip())

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
    engine_tsn: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="engineTsn",
        description="Optional; omit or leave blank when unknown.",
    )
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None

    # Propeller time fields
    propeller_prev_time: Optional[float] = None
    propeller_flight_time: Optional[float] = None
    propeller_total_time: Optional[float] = None
    propeller_run_time: Optional[float] = None
    propeller_tsn: Optional[float] = Field(
        default=None,
        alias="propellerTsn",
        description="Optional; omit or leave blank when unknown.",
    )
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

    date_time_reported: Optional[datetime] = None
    date_time_released: Optional[datetime] = None

    white_atl: Optional[str] = None
    dfp: Optional[str] = None
    white_atl_web_link: Optional[str] = None
    dfp_web_link: Optional[str] = None

    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    work_status: Optional[WorkStatus] = None

    auto_airframe_run_time: Optional[float] = None
    auto_airframe_aftt: Optional[float] = None
    auto_engine_run_time: Optional[float] = None
    auto_run_time: Optional[float] = None
    auto_engine_tsn: Optional[float] = None
    auto_engine_tso: Optional[float] = None
    auto_engine_tbo: Optional[float] = None
    auto_propeller_run_time: Optional[float] = None
    auto_propeller_tsn: Optional[float] = None
    auto_propeller_tso: Optional[float] = None
    auto_propeller_tbo: Optional[float] = None

    component_parts: Optional[List[ComponentPartsRecordCreate]] = []

    @validator("engine_tsn", "propeller_tsn", pre=True)
    def empty_str_optional_tsn_fields(cls, v: Any) -> Any:
        """TSN fields are optional; treat blank strings like omitted (no validation error)."""
        if v is None:
            return None
        if isinstance(v, str) and not str(v).strip():
            return None
        return v

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

    class Config:
        allow_population_by_field_name = True


# ---------- Aircraft Technical Log Create Schema ----------
class AircraftTechnicalLogCreate(AircraftTechnicalLogBase):
    pass


# ---------- Aircraft Technical Log Import Schema (Excel/CSV) ----------
class AircraftTechnicalLogImportSchema(AircraftTechnicalLogBase):
    """Schema for validating Aircraft Technical Log rows during Excel/CSV import.
    Coerces Excel NaN, empty, '-' and float-integer values to None so empty cells validate.
    """

    # None = row did not specify parts (import keeps existing DB children); list = replace parts for that ATL.
    component_parts: Optional[List[ComponentPartsRecordCreate]] = Field(default=None)

    @root_validator(pre=True)
    def excel_empty_and_dash_to_none(cls, values: Any) -> Any:
        """Coerce empty string and '-' to None for every field in import row."""
        if not isinstance(values, dict):
            return values
        return {
            k: v if k == "component_parts" else _excel_empty_to_none(v)
            for k, v in values.items()
        }

    @validator("component_parts", pre=True)
    def normalize_nested_component_parts(cls, v: Any) -> Any:
        """Clean NaN/Excel sentinels in each part dict; required fields get safe defaults."""
        if v is None:
            return None
        if not isinstance(v, list):
            return v
        out: List[Dict[str, Any]] = []
        for item in v:
            if item is None:
                continue
            if hasattr(item, "dict") and callable(getattr(item, "dict")):
                item = item.dict()
            if not isinstance(item, dict):
                continue
            out.append(normalize_component_part_dict_for_import(item))
        return out if out else None

    @validator("work_status", pre=True, always=True)
    def default_work_status_on_import(cls, v: Any) -> Any:
        """Default empty/null/dash import values to FOR_REVIEW."""
        if v is None:
            return WorkStatus.FOR_REVIEW
        if isinstance(v, str):
            s = v.strip()
            if not s or s == "-":
                return WorkStatus.FOR_REVIEW
            return s.upper().replace(" ", "_")
        return v

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

    @validator("date_time_reported", "date_time_released", pre=True)
    def excel_reported_released_datetime(cls, v: Any) -> Any:
        return parse_import_reported_released_datetime(v)

    @validator("sequence_no", pre=True)
    def sequence_no_numeric_excel(cls, v: Any) -> Any:
        """Coerce SEQ NO. exported as Excel float (e.g. 10001.0) before base normalizer."""
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return v
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if isinstance(v, float):
                if math.isnan(v) or not math.isfinite(v):
                    return None
                if v == int(v):
                    v = int(v)
            return str(v)
        return v

    @validator("engine_tsn", pre=True)
    def engine_tsn_numeric_excel_to_str(cls, v: Any) -> Any:
        """Fleet exports store Engine TSN as numbers; model column is string."""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(v, str) and str(v).strip().upper() == "UNK":
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if isinstance(v, float) and (math.isnan(v) or not math.isfinite(v)):
                return None
            if isinstance(v, float) and v == int(v):
                return str(int(v))
            return str(v)
        return v

    @validator("propeller_tsn", pre=True)
    def propeller_tsn_excel_unk_to_none(cls, v: Any) -> Any:
        """Treat Excel sentinel UNK as unknown (NULL); column is float."""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(v, str) and str(v).strip().upper() == "UNK":
            return None
        return v

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
        allow_population_by_field_name = True


# ---------- Aircraft Technical Log Update Schema ----------
class AircraftTechnicalLogUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    atl_batch_fk: Optional[int] = None
    sequence_no: Optional[str] = Field(None, max_length=50, description="ATL sequence number; stored as number only when set.")

    @validator("sequence_no", pre=True)
    def normalize_sequence_no_update(cls, v: Any) -> Any:
        """Normalize sequence_no to number only when provided (strip optional ATL- prefix)."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        return normalize_sequence_no_digits_only(str(v).strip())

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
    engine_tsn: Optional[str] = Field(
        default=None,
        max_length=100,
        alias="engineTsn",
        description="Optional; omit or leave blank when unknown.",
    )
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None

    # Propeller time fields
    propeller_prev_time: Optional[float] = None
    propeller_flight_time: Optional[float] = None
    propeller_total_time: Optional[float] = None
    propeller_run_time: Optional[float] = None
    propeller_tsn: Optional[float] = Field(
        default=None,
        alias="propellerTsn",
        description="Optional; omit or leave blank when unknown.",
    )
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

    date_time_reported: Optional[datetime] = None
    date_time_released: Optional[datetime] = None

    white_atl: Optional[str] = None
    dfp: Optional[str] = None
    white_atl_web_link: Optional[str] = None
    dfp_web_link: Optional[str] = None

    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    work_status: Optional[WorkStatus] = None

    auto_airframe_run_time: Optional[float] = None
    auto_airframe_aftt: Optional[float] = None
    auto_engine_run_time: Optional[float] = None
    auto_run_time: Optional[float] = None
    auto_engine_tsn: Optional[float] = None
    auto_engine_tso: Optional[float] = None
    auto_engine_tbo: Optional[float] = None
    auto_propeller_run_time: Optional[float] = None
    auto_propeller_tsn: Optional[float] = None
    auto_propeller_tso: Optional[float] = None
    auto_propeller_tbo: Optional[float] = None

    component_parts: Optional[List[ComponentPartsRecordCreate]] = None

    @validator("engine_tsn", "propeller_tsn", pre=True)
    def empty_str_optional_tsn_fields_update(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str) and not str(v).strip():
            return None
        return v

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

    class Config:
        allow_population_by_field_name = True


class AircraftTechnicalLogBulkWorkStatusUpdateRequest(BaseModel):
    ids: List[int] = Field(..., min_items=1, description="ATL record IDs to update.")
    work_status: WorkStatus
    atomic: bool = Field(
        False,
        description="When true, fail and rollback the whole batch on first error.",
    )


class AircraftTechnicalLogBulkWorkStatusUpdateItem(BaseModel):
    id: int
    success: bool
    message: str


class AircraftTechnicalLogBulkWorkStatusUpdateResponse(BaseModel):
    updated_count: int
    failed_count: int
    results: List[AircraftTechnicalLogBulkWorkStatusUpdateItem]


class AircraftTechnicalLogBulkDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_items=1, description="ATL record IDs to soft delete.")
    atomic: bool = Field(
        False,
        description="When true, fail and rollback the whole batch on first error.",
    )


class AircraftTechnicalLogBulkDeleteItem(BaseModel):
    id: int
    success: bool
    message: str


class AircraftTechnicalLogBulkDeleteResponse(BaseModel):
    deleted_count: int
    failed_count: int
    results: List[AircraftTechnicalLogBulkDeleteItem]


# ---------- Aircraft Read Schema (for nested display) ----------
class AircraftRead(BaseModel):
    id: int
    registration: str
    model: str

    class Config:
        orm_mode = True


# ---------- ATL Search response (id for atl_ref, sequence_no + aircraft summary) ----------
class ATLSearchItem(BaseModel):
    """ATL sequence search (CPCP/TCC ATL Reference, etc.). id = atl_ref. search_display is CPCP label: sequence_no: TACH: … AFTT: … DATE: …"""

    id: int
    sequence_no: str
    tachometer_end: Optional[float] = None
    auto_airframe_aftt: Optional[float] = None
    origin_date: Optional[date] = None
    search_display: Optional[str] = None
    sequence_no_display: Optional[str] = None  # Same as sequence_no for legacy dropdown label (number only)
    aircraft: AircraftRead

    @validator("sequence_no_display", always=True)
    def set_sequence_no_display(cls, v: Any, values: dict) -> str:
        seq = values.get("sequence_no")
        if not seq:
            return ""
        return str(seq).strip()

    @root_validator
    def set_search_display(cls, values: Any) -> Any:
        """One-line label for Add/Edit forms (e.g. CPCP ATL Reference)."""
        if not isinstance(values, dict):
            return values
        seq = str(values.get("sequence_no") or "").strip()

        def fmt_num(v: Any) -> str:
            if v is None:
                return "—"
            try:
                return f"{float(v):.2f}"
            except (TypeError, ValueError):
                return "—"

        od = values.get("origin_date")
        date_s = od.isoformat() if isinstance(od, date) else "—"
        tach = values.get("tachometer_end")
        aftt = values.get("auto_airframe_aftt")
        values["search_display"] = f"{seq}: TACH: {fmt_num(tach)} AFTT: {fmt_num(aftt)} DATE: {date_s}"
        return values

    class Config:
        orm_mode = True


class ATLAircraftScopedSearchItem(BaseModel):
    """GET /api/v1/aircraft/{aircraft_id}/atl/?sequence_number= — sequence row with tach end, computed AFTT (same chain as auto_airframe_aftt / atl/paged), and origin date."""

    id: int
    sequence_no: str
    tachometer_end: Optional[float] = None
    auto_airframe_aftt: Optional[float] = None
    origin_date: Optional[date] = None


# ---------- Aircraft Technical Log Read Schema ----------
class AircraftTechnicalLogRead(AircraftTechnicalLogBase):
    id: int
    aircraft: Optional[AircraftRead] = None
    atl_batch: Optional[AtlBatchBrief] = None
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


# ---------- ATL Paged response for /aircraft-technical-log/paged (Read + persisted auto_* columns) ----------
class ATLPagedItemWithAuto(AircraftTechnicalLogRead):
    """ATL read including auto_* from AircraftTechnicalLog persisted columns (same shape as list paged API)."""

    class Config:
        orm_mode = True
