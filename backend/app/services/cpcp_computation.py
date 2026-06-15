"""CPCP monitoring: next-due fields (persisted on create/update) and remaining metrics (read-time)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional, Set, Tuple, Union

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.atl_derived_times import map_auto_fields_to_comp, resolve_auto_fields
from app.database import ph_now
from app.models.cpcp_monitoring import CPCPMonitoring
from app.repository.aircraft import get_aircraft_raw
from app.repository.aircraft_technical_log import get_latest_aircraft_technical_log
from app.schemas.cpcp_monitoring_schema import CPCPMonitoringRead


def _round2(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def compute_cpcp_next_due_tuple(
    last_done_tach: Optional[float],
    last_done_aftt: Optional[float],
    last_done_date: Optional[date],
    interval_hours: Optional[float],
    interval_months: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[date]]:
    """Pure next_due_* from inputs (same as Excel: +interval_hours, EDATE +interval_months)."""
    ih = interval_hours
    lt = last_done_tach
    la = last_done_aftt
    ld = last_done_date
    im = interval_months

    next_tach = float(lt) + float(ih) if lt is not None and ih is not None else None
    next_aftt = float(la) + float(ih) if la is not None and ih is not None else None

    next_date: Optional[date] = None
    if ld is not None and im is not None:
        try:
            m = float(im)
        except (TypeError, ValueError):
            next_date = None
        else:
            whole = int(m // 1)
            frac = m - whole
            delta = relativedelta(months=whole)
            if abs(frac) > 1e-9:
                delta += relativedelta(days=int(round(frac * 30.436875)))
            next_date = ld + delta

    return next_tach, next_aftt, next_date


def apply_cpcp_next_due_fields(obj: CPCPMonitoring) -> None:
    """Set next_due_tach, next_due_aftt, next_due_date from last_done_* and intervals (Excel-style)."""
    t, a, d = compute_cpcp_next_due_tuple(
        obj.last_done_tach,
        obj.last_done_aftt,
        obj.last_done_date,
        obj.interval_hours,
        obj.interval_months,
    )
    obj.next_due_tach = t
    obj.next_due_aftt = a
    obj.next_due_date = d


def _effective_next_dues(obj: CPCPMonitoring) -> Tuple[Optional[float], Optional[float], Optional[date]]:
    """Prefer persisted columns; fall back to in-memory computation for legacy rows."""
    c_tach, c_aftt, c_date = compute_cpcp_next_due_tuple(
        obj.last_done_tach,
        obj.last_done_aftt,
        obj.last_done_date,
        obj.interval_hours,
        obj.interval_months,
    )
    eff_tach = obj.next_due_tach if obj.next_due_tach is not None else c_tach
    eff_aftt = obj.next_due_aftt if obj.next_due_aftt is not None else c_aftt
    eff_date = obj.next_due_date if obj.next_due_date is not None else c_date
    return eff_tach, eff_aftt, eff_date


def _manila_today() -> date:
    """Calendar 'today' for CPCP remaining_* (Asia/Manila)."""
    return ph_now().date()


def _yearfrac_times_12(today: date, end: date) -> float:
    """Approximate YEARFRAC(today, end) * 12 using actual/365-style year length (basis 3 style)."""
    delta_days = (end - today).days
    return round((delta_days / 365.0) * 12.0, 2)


def compute_cpcp_remaining(
    *,
    next_due_date: Optional[Union[date, datetime]],
    next_due_tach: Optional[float],
    next_due_aftt: Optional[float],
    tachometer_end: Optional[float],
    airframe_aftt: Optional[float],
) -> dict:
    """Remaining calendar and hours vs latest ATL (same tach / airframe_aftt as aircraft details)."""
    today_date = _manila_today()
    out = {
        "remaining_months": None,
        "remaining_days": None,
        "remaining_tach": None,
        "remaining_aftt": None,
    }
    if next_due_date is not None:
        end_date: date = (
            next_due_date.date()
            if isinstance(next_due_date, datetime)
            else next_due_date
        )
        days = (end_date - today_date).days
        out["remaining_days"] = days
        out["remaining_months"] = _yearfrac_times_12(today_date, end_date)
    if next_due_tach is not None and tachometer_end is not None:
        out["remaining_tach"] = _round2(float(next_due_tach) - float(tachometer_end))
    if next_due_aftt is not None and airframe_aftt is not None:
        out["remaining_aftt"] = _round2(float(next_due_aftt) - float(airframe_aftt))
    return out


async def _latest_atl_tach_and_airframe_aftt(
    session: AsyncSession,
    aircraft_id: int,
) -> Tuple[Optional[float], Optional[float]]:
    aircraft = await get_aircraft_raw(session, aircraft_id)
    latest = await get_latest_aircraft_technical_log(session, aircraft_fk=aircraft_id)
    if not latest or not aircraft:
        return None, None
    tach = _round2(latest.tachometer_end)
    auto_base = await resolve_auto_fields(session, latest, aircraft)
    auto_rounded = {k: round(v, 2) for k, v in auto_base.items()}
    auto_comp = {k: round(v, 2) for k, v in map_auto_fields_to_comp(auto_rounded).items()}
    aftt = _round2(auto_comp.get("auto_comp_airframe_aftt"))
    return tach, aftt


async def fetch_latest_atl_metrics_by_aircraft_ids(
    session: AsyncSession,
    aircraft_ids: Set[int],
) -> Dict[int, Tuple[Optional[float], Optional[float]]]:
    """Per aircraft_id: (tachometer_end, airframe_aftt) from latest ATL, matching aircraft details."""
    out: Dict[int, Tuple[Optional[float], Optional[float]]] = {
        aid: (None, None) for aid in aircraft_ids
    }
    for aid in aircraft_ids:
        tach, aftt = await _latest_atl_tach_and_airframe_aftt(session, aid)
        out[aid] = (tach, aftt)
    return out


async def to_cpcp_monitoring_read(
    session: AsyncSession,
    obj: CPCPMonitoring,
) -> CPCPMonitoringRead:
    """ORM row → read schema including remaining_* from latest ATL for the aircraft."""
    tach, aftt = await _latest_atl_tach_and_airframe_aftt(session, obj.aircraft_id)
    eff_tach, eff_aftt, eff_date = _effective_next_dues(obj)
    base = CPCPMonitoringRead.from_orm(obj)
    data = base.dict()
    data["next_due_tach"] = eff_tach
    data["next_due_aftt"] = eff_aftt
    data["next_due_date"] = eff_date
    data.update(
        compute_cpcp_remaining(
            next_due_date=eff_date,
            next_due_tach=eff_tach,
            next_due_aftt=eff_aftt,
            tachometer_end=tach,
            airframe_aftt=aftt,
        )
    )
    return CPCPMonitoringRead(**data)


def to_cpcp_monitoring_read_sync(
    obj: CPCPMonitoring,
    *,
    tachometer_end: Optional[float],
    airframe_aftt: Optional[float],
) -> CPCPMonitoringRead:
    """Build read model when ATL metrics are already resolved (e.g. batched paged list)."""
    eff_tach, eff_aftt, eff_date = _effective_next_dues(obj)
    base = CPCPMonitoringRead.from_orm(obj)
    data = base.dict()
    data["next_due_tach"] = eff_tach
    data["next_due_aftt"] = eff_aftt
    data["next_due_date"] = eff_date
    data.update(
        compute_cpcp_remaining(
            next_due_date=eff_date,
            next_due_tach=eff_tach,
            next_due_aftt=eff_aftt,
            tachometer_end=tachometer_end,
            airframe_aftt=airframe_aftt,
        )
    )
    return CPCPMonitoringRead(**data)
