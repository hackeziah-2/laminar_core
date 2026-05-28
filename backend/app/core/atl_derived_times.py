"""Shared ATL leg / cumulative time computations (airframe, engine, propeller).

Used for API responses (standard fields + auto_*) and aircraft-scoped ATL paged (auto_comp_*).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas.aircraft_technical_log_schema import AircraftTechnicalLogRead

from app.models.aircraft_techinical_log import AircraftTechnicalLog


def _atl_memo_key(item: AircraftTechnicalLog) -> Tuple[int, str, Optional[int]]:
    return (
        int(item.aircraft_fk),
        str(getattr(item, "sequence_no", "")),
        getattr(item, "atl_batch_fk", None),
    )


def _atl_relationships_loaded(entry: AircraftTechnicalLog) -> bool:
    """True when aircraft, atl_batch, and component_parts are already eager-loaded."""
    insp = sa_inspect(entry)
    for rel in ("aircraft", "atl_batch", "component_parts"):
        if rel in insp.unloaded:
            return False
    return True


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
    """Leg airframe run time derived from tachometer delta for ATL computed fields."""
    tach_start = float_or_zero(getattr(atl, "tachometer_start", None))
    tach_end = float_or_zero(getattr(atl, "tachometer_end", None))
    return abs(tach_end - tach_start)


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


# Manual ATL field -> persisted auto_* column used when the manual field is zero.
_PREV_ATTR_TO_AUTO_COL: Dict[str, str] = {
    "engine_tsn": "auto_engine_tsn",
    "engine_tso": "auto_engine_tso",
    "propeller_tsn": "auto_propeller_tsn",
    "propeller_tso": "auto_propeller_tso",
}


def previous_computed_or_aircraft(
    prev_auto_fields: Optional[Dict[str, float]],
    prev_auto_key: str,
    prev_atl,
    prev_attr: str,
    aircraft,
    aircraft_attr: str,
) -> float:
    """Previous cumulative total: persisted auto_* on prev row, else in-memory chain, else aircraft."""
    prev_raw = float_or_zero(getattr(prev_atl, prev_attr, None)) if prev_atl else 0.0
    if prev_raw != 0.0:
        return prev_raw

    # Raw zero: use persisted cumulative on the previous row when backfilled; otherwise aircraft
    # baseline (do not use in-memory prev_auto_fields so a SQL-seeded prior leg does not skew the next).
    auto_col = _PREV_ATTR_TO_AUTO_COL.get(prev_attr)
    if prev_atl and auto_col:
        persisted = float_or_zero(getattr(prev_atl, auto_col, None))
        if persisted != 0.0:
            return persisted

    return float_or_zero(getattr(aircraft, aircraft_attr, None)) if aircraft else 0.0


def compute_auto_fields(
    atl,
    prev_atl,
    aircraft,
    prev_auto_fields: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
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
        if prev_atl is None:
            base_aftt = float_or_zero(
                getattr(aircraft, "airframe_aftt", None)
            ) if aircraft else 0.0
        else:
            # Prefer the previous row's stored cumulative AFTT (manual entry), then aircraft baseline.
            base_aftt = previous_value_or_aircraft(
                prev_atl,
                "airframe_aftt",
                aircraft,
                "airframe_aftt",
            )
        out["auto_airframe_aftt"] = base_aftt + out["auto_airframe_run_time"]
    except Exception:
        pass

    try:
        leg_rt = out["auto_airframe_run_time"]
        out["auto_engine_run_time"] = leg_rt
        out["auto_run_time"] = leg_rt
    except Exception:
        pass

    try:
        if prev_atl is None:
            base_tsn = float_or_zero(
                getattr(aircraft, "engine_tsn", None)
            ) if aircraft else 0.0
            out["auto_engine_tsn"] = base_tsn + out["auto_engine_run_time"]
        else:
            base_tsn = previous_computed_or_aircraft(
                prev_auto_fields,
                "auto_engine_tsn",
                prev_atl,
                "engine_tsn",
                aircraft,
                "engine_tsn",
            )
            out["auto_engine_tsn"] = base_tsn + out["auto_engine_run_time"]
    except Exception:
        pass

    try:
        if prev_atl is None:
            base_tso = float_or_zero(
                getattr(aircraft, "engine_tso", None)
            ) if aircraft else 0.0
            out["auto_engine_tso"] = base_tso + out["auto_engine_run_time"]
        else:
            base_tso = previous_computed_or_aircraft(
                prev_auto_fields,
                "auto_engine_tso",
                prev_atl,
                "engine_tso",
                aircraft,
                "engine_tso",
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
        if prev_atl is None:
            base_ptsn = float_or_zero(
                getattr(aircraft, "propeller_tsn", None)
            ) if aircraft else 0.0
            out["auto_propeller_tsn"] = base_ptsn + out["auto_propeller_run_time"]
        else:
            base_ptsn = previous_computed_or_aircraft(
                prev_auto_fields,
                "auto_propeller_tsn",
                prev_atl,
                "propeller_tsn",
                aircraft,
                "propeller_tsn",
            )
            out["auto_propeller_tsn"] = base_ptsn + out["auto_propeller_run_time"]
    except Exception:
        pass

    try:
        if prev_atl is None:
            base_ptso = float_or_zero(
                getattr(aircraft, "propeller_tso", None)
            ) if aircraft else 0.0
            out["auto_propeller_tso"] = base_ptso + out["auto_propeller_run_time"]
        else:
            base_ptso = previous_computed_or_aircraft(
                prev_auto_fields,
                "auto_propeller_tso",
                prev_atl,
                "propeller_tso",
                aircraft,
                "propeller_tso",
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


# Persisted ORM columns on AircraftTechnicalLog (same keys as compute_auto_fields output).
ATL_AUTO_FIELD_KEYS: tuple[str, ...] = (
    "auto_airframe_run_time",
    "auto_airframe_aftt",
    "auto_engine_run_time",
    "auto_run_time",
    "auto_engine_tsn",
    "auto_engine_tso",
    "auto_engine_tbo",
    "auto_propeller_run_time",
    "auto_propeller_tsn",
    "auto_propeller_tso",
    "auto_propeller_tbo",
)


def _atl_has_persisted_auto_fields(entry: AircraftTechnicalLog) -> bool:
    """True when every persisted auto_* column is set on the row."""
    return all(getattr(entry, key, None) is not None for key in ATL_AUTO_FIELD_KEYS)


def _auto_fields_from_row(entry: AircraftTechnicalLog) -> Dict[str, float]:
    return {key: float_or_zero(getattr(entry, key)) for key in ATL_AUTO_FIELD_KEYS}


def _compute_chain_in_memory(
    chain: List[AircraftTechnicalLog],
    target: AircraftTechnicalLog,
    aircraft_obj: Any,
    memo: Optional[Dict[Tuple[int, str, Optional[int]], Dict[str, float]]],
) -> Dict[str, float]:
    prev_atl = None
    prev_auto_fields: Optional[Dict[str, float]] = None
    result: Optional[Dict[str, float]] = None
    for atl in chain:
        atl_key = _atl_memo_key(atl)
        if memo is not None and atl_key in memo:
            auto_fields = memo[atl_key]
        else:
            auto_fields = compute_auto_fields(
                atl,
                prev_atl,
                aircraft_obj,
                prev_auto_fields=prev_auto_fields,
            )
            if memo is not None:
                memo[atl_key] = auto_fields
        prev_atl = atl
        prev_auto_fields = auto_fields
        if int(atl.id) == int(target.id):
            result = auto_fields
    if result is not None:
        return result
    return compute_auto_fields(target, None, aircraft_obj, prev_auto_fields=None)


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


async def _atl_eager_for_read(
    session: AsyncSession, entry: AircraftTechnicalLog
) -> AircraftTechnicalLog:
    """Reload ATL with relationships; Pydantic from_orm must not trigger async lazy loads."""
    stmt = (
        select(AircraftTechnicalLog)
        .where(AircraftTechnicalLog.id == entry.id)
        .options(
            selectinload(AircraftTechnicalLog.aircraft),
            selectinload(AircraftTechnicalLog.atl_batch),
            selectinload(AircraftTechnicalLog.component_parts),
        )
    )
    return (await session.execute(stmt)).scalar_one()


async def aircraft_technical_log_read_with_computed(
    session: AsyncSession,
    entry: AircraftTechnicalLog,
    *,
    recompute: bool = False,
) -> AircraftTechnicalLogRead:
    """Build AircraftTechnicalLogRead with standard time fields replaced by computed values."""
    if not _atl_relationships_loaded(entry):
        entry = await _atl_eager_for_read(session, entry)
    aircraft_obj = entry.aircraft
    memo: Dict[Tuple[int, str, Optional[int]], Dict[str, float]] = {}
    auto_fields = await resolve_auto_fields(
        session, entry, aircraft_obj, memo, force_recompute=recompute
    )
    auto_fields = {k: round(v, 2) for k, v in auto_fields.items()}
    base = AircraftTechnicalLogRead.from_orm(entry)
    auto_only = {k: auto_fields[k] for k in ATL_AUTO_FIELD_KEYS}
    merged = {**base.dict(), **canonical_time_fields_from_auto(auto_fields), **auto_only}
    return AircraftTechnicalLogRead.parse_obj(merged)


async def resolve_auto_fields(
    session: AsyncSession,
    item: AircraftTechnicalLog,
    aircraft_obj: Any,
    memo: Optional[Dict[Tuple[int, str, Optional[int]], Dict[str, float]]] = None,
    *,
    force_recompute: bool = False,
) -> Dict[str, float]:
    """Resolve cumulative auto_* values through the previous ATL chain (no recursion)."""
    from app.repository.aircraft_technical_log import (
        fetch_predecessors_for_atl,
        get_previous_atl,
    )

    key = _atl_memo_key(item)
    if memo is not None and key in memo:
        return memo[key]

    if not force_recompute and _atl_has_persisted_auto_fields(item):
        return _auto_fields_from_row(item)

    batch_fk = getattr(item, "atl_batch_fk", None)
    aircraft_fk = int(item.aircraft_fk)

    if not force_recompute:
        prev_atl = await get_previous_atl(
            session,
            aircraft_fk,
            item.sequence_no,
            atl_batch_fk=batch_fk,
        )
        if prev_atl is None:
            return compute_auto_fields(item, None, aircraft_obj, prev_auto_fields=None)
        if _atl_has_persisted_auto_fields(prev_atl):
            return compute_auto_fields(item, prev_atl, aircraft_obj, prev_auto_fields=None)

    predecessors = await fetch_predecessors_for_atl(
        session,
        aircraft_fk,
        item.sequence_no,
        atl_batch_fk=batch_fk,
    )
    chain = predecessors + [item]
    return _compute_chain_in_memory(chain, item, aircraft_obj, memo)


async def backfill_atl_auto_fields_for_scope(
    session: AsyncSession,
    aircraft_fk: int,
    *,
    atl_batch_fk: Optional[int] = None,
    aircraft_obj: Optional[Any] = None,
) -> int:
    """Persist auto_* for all ATLs in one aircraft/batch stream (ascending sequence). Returns rows updated."""
    from app.models.aircraft import Aircraft
    from app.repository.aircraft_technical_log import list_atls_for_scope_ordered

    if aircraft_obj is None:
        aircraft_obj = await session.get(Aircraft, aircraft_fk)
    rows = await list_atls_for_scope_ordered(
        session, aircraft_fk, atl_batch_fk=atl_batch_fk
    )
    prev_atl = None
    prev_auto_fields: Optional[Dict[str, float]] = None
    for row in rows:
        auto_fields = compute_auto_fields(
            row,
            prev_atl,
            aircraft_obj,
            prev_auto_fields=prev_auto_fields,
        )
        for k in ATL_AUTO_FIELD_KEYS:
            setattr(row, k, round(auto_fields[k], 2))
        prev_atl = row
        prev_auto_fields = auto_fields
    if rows:
        await session.flush()
    return len(rows)


async def persist_atl_auto_fields_to_row(
    session: AsyncSession,
    entry: "AircraftTechnicalLog",
    aircraft_obj: Optional[Any] = None,
) -> None:
    """Run compute_auto_fields / chain and set rounded auto_* columns on entry (create/update persist)."""
    from app.models.aircraft import Aircraft
    from app.repository.aircraft_technical_log import get_previous_atl

    # Never access entry.aircraft (async lazy load); only explicit session.get.
    if aircraft_obj is None and getattr(entry, "aircraft_fk", None) is not None:
        aircraft_obj = await session.get(Aircraft, entry.aircraft_fk)
    prev_atl = await get_previous_atl(
        session,
        entry.aircraft_fk,
        entry.sequence_no,
        atl_batch_fk=getattr(entry, "atl_batch_fk", None),
    )
    prev_auto_fields = None
    if prev_atl is not None and _atl_has_persisted_auto_fields(prev_atl):
        prev_auto_fields = _auto_fields_from_row(prev_atl)
    elif prev_atl is not None:
        prev_auto_fields = await resolve_auto_fields(session, prev_atl, aircraft_obj, {})
    auto_fields = compute_auto_fields(
        entry, prev_atl, aircraft_obj, prev_auto_fields=prev_auto_fields
    )
    for k in ATL_AUTO_FIELD_KEYS:
        setattr(entry, k, round(auto_fields[k], 2))
