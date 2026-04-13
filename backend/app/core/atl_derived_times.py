"""Shared ATL leg / cumulative time computations (airframe, engine, propeller).

Used for API responses (standard fields + auto_*) and aircraft-scoped ATL paged (auto_comp_*).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.aircraft_technical_log_schema import (
    AircraftTechnicalLogRead,
    ATLPagedItemWithAuto,
)

if TYPE_CHECKING:
    from app.models.aircraft_techinical_log import AircraftTechnicalLog


def float_or_zero(value: Any) -> float:
    """Parse value to float; return 0.0 on error or None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) if (value == value) else 0.0  # NaN check
    if isinstance(value, str):
        try:
            return float(value.strip()) if value.strip() else 0.0
        except ValueError:
            return 0.0
    return 0.0


def current_airframe_run_time(atl) -> float:
    """Leg airframe run time: stored airframe_run_time when non-zero; else tach_end - tach_start (non-negative)."""
    stored = float_or_zero(getattr(atl, "airframe_run_time", None))
    if stored != 0.0:
        return stored
    tach_start = float_or_zero(getattr(atl, "tachometer_start", None))
    tach_end = float_or_zero(getattr(atl, "tachometer_end", None))
    return max(0.0, tach_end - tach_start)


def previous_value_or_aircraft(
    prev_atl,
    prev_attr: str,
    aircraft,
    aircraft_attr: str,
) -> float:
    """Previous ATL field if present and non-zero; otherwise aircraft baseline."""
    prev_val = float_or_zero(getattr(prev_atl, prev_attr, None)) if prev_atl else 0.0
    if prev_val != 0.0:
        return prev_val
    return float_or_zero(getattr(aircraft, aircraft_attr, None)) if aircraft else 0.0


def compute_auto_fields(atl, prev_atl, aircraft) -> Dict[str, float]:
    """Compute auto_* field values (floats, not rounded)."""
    out = {
        "auto_airframe_run_time": 0.0,
        "auto_airframe_aftt": 0.0,
        "auto_engine_run_time": 0.0,
        "auto_run_time": 0.0,
        "auto_engine_tsn": 0.0,
        "auto_engine_tso": 0.0,
        "auto_engine_tbo": 0.0,
        "auto_propeller_run_time": 0.0,
        "auto_propeller_tsn": 0.0,
        "auto_propeller_tso": 0.0,
        "auto_propeller_tbo": 0.0,
    }
    try:
        out["auto_airframe_run_time"] = current_airframe_run_time(atl)
    except Exception:
        pass

    try:
        prev_aftt = float_or_zero(getattr(prev_atl, "airframe_aftt", None)) if prev_atl else 0.0
        out["auto_airframe_aftt"] = prev_aftt + out["auto_airframe_run_time"]
    except Exception:
        pass

    try:
        leg_rt = out["auto_airframe_run_time"]
        out["auto_engine_run_time"] = leg_rt
        out["auto_run_time"] = leg_rt
    except Exception:
        pass

    try:
        base_tsn = previous_value_or_aircraft(
            prev_atl, "engine_tsn", aircraft, "engine_tsn"
        )
        out["auto_engine_tsn"] = base_tsn + out["auto_engine_run_time"]
    except Exception:
        pass

    try:
        base_tso = previous_value_or_aircraft(
            prev_atl, "engine_tso", aircraft, "engine_tso"
        )
        out["auto_engine_tso"] = base_tso + out["auto_engine_run_time"]
    except Exception:
        pass

    try:
        life_engine = float_or_zero(getattr(aircraft, "engine_life_time_limit", None)) if aircraft else float_or_zero(getattr(atl, "life_time_limit_engine", None))
        curr_tso = out["auto_engine_tso"]
        out["auto_engine_tbo"] = life_engine - curr_tso if life_engine else 0.0
    except Exception:
        pass

    try:
        out["auto_propeller_run_time"] = out["auto_airframe_run_time"]
    except Exception:
        pass

    try:
        base_ptsn = previous_value_or_aircraft(
            prev_atl, "propeller_tsn", aircraft, "propeller_tsn"
        )
        out["auto_propeller_tsn"] = base_ptsn + out["auto_propeller_run_time"]
    except Exception:
        pass

    try:
        base_ptso = previous_value_or_aircraft(
            prev_atl, "propeller_tso", aircraft, "propeller_tso"
        )
        out["auto_propeller_tso"] = base_ptso + out["auto_propeller_run_time"]
    except Exception:
        pass

    try:
        life_prop = float_or_zero(getattr(aircraft, "propeller_life_time_limit", None)) if aircraft else float_or_zero(getattr(atl, "life_time_limit_propeller", None))
        curr_tso = out["auto_propeller_tso"]
        out["auto_propeller_tbo"] = life_prop - curr_tso if life_prop else 0.0
    except Exception:
        pass

    return out


# Map shared computation to auto_comp_* names (GET /api/v1/aircraft/{id}/atl/paged).
_AUTO_TO_COMP_KEYS: tuple[tuple[str, str], ...] = (
    ("auto_airframe_run_time", "auto_comp_airframe_run_time"),
    ("auto_airframe_aftt", "auto_comp_airframe_aftt"),
    ("auto_engine_run_time", "auto_comp_engine_run_time"),
    ("auto_engine_tsn", "auto_comp_engine_tsn"),
    ("auto_engine_tso", "auto_comp_engine_tso"),
    ("auto_engine_tbo", "auto_comp_engine_tbo"),
    ("auto_propeller_run_time", "auto_comp_propeller_run_time"),
    ("auto_propeller_tsn", "auto_comp_propeller_tsn"),
    ("auto_propeller_tso", "auto_comp_propeller_tso"),
    ("auto_propeller_tbo", "auto_comp_propeller_tbo"),
)


def compute_auto_comp_fields(atl, prev_atl, aircraft) -> Dict[str, float]:
    """Same rules as compute_auto_fields but with auto_comp_* keys for aircraft-scoped ATL paged API."""
    raw = compute_auto_fields(atl, prev_atl, aircraft)
    return map_auto_fields_to_comp(raw)


def map_auto_fields_to_comp(auto_fields: Dict[str, float]) -> Dict[str, float]:
    """Rename auto_* keys to auto_comp_* (same numeric values)."""
    return {comp: auto_fields[auto] for auto, comp in _AUTO_TO_COMP_KEYS}


def canonical_time_fields_from_auto(auto_fields: Dict[str, float]) -> Dict[str, Any]:
    """Map auto_* (already rounded) onto AircraftTechnicalLog persisted/read field names."""
    def r(key: str) -> float:
        return round(auto_fields[key], 2)

    return {
        "airframe_run_time": r("auto_airframe_run_time"),
        "engine_run_time": r("auto_engine_run_time"),
        "propeller_run_time": r("auto_propeller_run_time"),
        "airframe_aftt": r("auto_airframe_aftt"),
        "engine_tsn": f"{r('auto_engine_tsn'):.2f}",
        "engine_tso": r("auto_engine_tso"),
        "engine_tbo": r("auto_engine_tbo"),
        "propeller_tsn": r("auto_propeller_tsn"),
        "propeller_tso": r("auto_propeller_tso"),
        "propeller_tbo": r("auto_propeller_tbo"),
    }


async def aircraft_technical_log_read_with_computed(
    session: AsyncSession,
    entry: AircraftTechnicalLog,
) -> AircraftTechnicalLogRead:
    """Build AircraftTechnicalLogRead with standard time fields replaced by computed values."""
    from app.repository.aircraft_technical_log import get_previous_atl

    prev_atl = await get_previous_atl(session, entry.aircraft_fk, entry.sequence_no)
    aircraft_obj = getattr(entry, "aircraft", None)
    auto_fields = compute_auto_fields(entry, prev_atl, aircraft_obj)
    auto_fields = {k: round(v, 2) for k, v in auto_fields.items()}
    base = AircraftTechnicalLogRead.from_orm(entry)
    merged = {**base.dict(), **canonical_time_fields_from_auto(auto_fields)}
    return AircraftTechnicalLogRead.parse_obj(merged)


def atl_paged_item_with_computed(
    item: AircraftTechnicalLog,
    prev_atl: Optional[AircraftTechnicalLog],
    aircraft_obj: Any,
) -> ATLPagedItemWithAuto:
    """Single list row: standard fields + auto_* both reflect the same computation."""
    auto_fields = compute_auto_fields(item, prev_atl, aircraft_obj)
    auto_fields = {k: round(v, 2) for k, v in auto_fields.items()}
    base = AircraftTechnicalLogRead.from_orm(item)
    merged = {
        **base.dict(),
        **canonical_time_fields_from_auto(auto_fields),
        **auto_fields,
    }
    return ATLPagedItemWithAuto.parse_obj(merged)
