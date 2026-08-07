"""Aircraft Fuel Report — monthly ATL Logbook rollup for dashboard charts."""

from __future__ import annotations

import logging
import threading
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, DefaultDict, Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import ph_now
from app.repository.aircraft_fuel_report import (
    fetch_fuel_report_atl_rows,
    fetch_fuel_report_available_month_bounds,
    resolve_aircraft_filter_ids,
)
from app.schemas.aircraft_fuel_report_schema import (
    AircraftFuelBreakdown,
    AircraftFuelReportQuery,
    AircraftFuelReportResponse,
    DataQualityFlag,
    FuelReportMeta,
    FuelReportRange,
    FuelReportSummary,
    MonthlyFuelRow,
    parse_year_month,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_CHAIN_TOLERANCE = Decimal("0.5")  # gallons — "roughly match" prior AFTER+uplift

_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# ---------------------------------------------------------------------------
# Simple process-local cache keyed on (start_month, end_month, aircraft_ids)
# ---------------------------------------------------------------------------
_cache_lock = threading.Lock()
_report_cache: Dict[Tuple[str, str, Tuple[int, ...]], AircraftFuelReportResponse] = {}


def invalidate_fuel_report_cache(*, origin_date: Optional[date] = None) -> None:
    """
    Drop cached rollups.

    When ``origin_date`` is set, drop entries whose [start, end] covers that month;
    otherwise clear the entire cache (safe default on ATL writes).
    """
    with _cache_lock:
        if origin_date is None:
            _report_cache.clear()
            return
        ym = f"{origin_date.year:04d}-{origin_date.month:02d}"
        to_drop = [
            key
            for key in _report_cache
            if key[0] <= ym <= key[1]
        ]
        for key in to_drop:
            _report_cache.pop(key, None)


def _cache_get(
    start_month: str,
    end_month: str,
    aircraft_ids: Sequence[int],
) -> Optional[AircraftFuelReportResponse]:
    key = (start_month, end_month, tuple(sorted(aircraft_ids)))
    with _cache_lock:
        return _report_cache.get(key)


def _cache_set(
    start_month: str,
    end_month: str,
    aircraft_ids: Sequence[int],
    response: AircraftFuelReportResponse,
) -> None:
    key = (start_month, end_month, tuple(sorted(aircraft_ids)))
    with _cache_lock:
        _report_cache[key] = response


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _nz(value: Any) -> Decimal:
    """Treat null / unparseable numeric fields as 0."""
    parsed = _to_decimal(value)
    return _ZERO if parsed is None else parsed


def _to_float(value: Decimal) -> float:
    """Round to 2 decimal places for API response values."""
    return float(value.quantize(Decimal("0.01")))


def month_label(year: int, month: int) -> str:
    """e.g. 2026-01 → Jan-26"""
    return f"{_MONTH_ABBR[month - 1]}-{year % 100:02d}"


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def ym_to_date_bounds(year: int, month: int) -> Tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def fuel_consumed(
    left_prior: Optional[Decimal],
    right_prior: Optional[Decimal],
    left_after: Optional[Decimal],
    right_after: Optional[Decimal],
) -> Decimal:
    """
    (PRIOR DEP. LEFT + PRIOR DEP. RIGHT) − (AFTER ON-BLKS LEFT + AFTER ON-BLKS RIGHT).

    Null sides are treated as 0.
    """
    return (
        (_nz(left_prior) + _nz(right_prior))
        - (_nz(left_after) + _nz(right_after))
    )


def oil_consumed(
    oil_prior: Optional[Decimal],
    oil_after: Optional[Decimal],
) -> Decimal:
    """OIL PRIOR DEP − OIL AFTER ON-BLKS; nulls treated as 0."""
    return _nz(oil_prior) - _nz(oil_after)


def fuel_burn_per_hour(
    total_fuel: Decimal,
    total_hours: Decimal,
) -> Optional[float]:
    """SUM(fuel) / SUM(hours), rounded to 2 dp; null when hours are zero."""
    if total_hours == _ZERO:
        return None
    return _to_float(total_fuel / total_hours)


@dataclass
class _Acc:
    hours: Decimal = _ZERO
    fuel: Decimal = _ZERO
    oil: Decimal = _ZERO
    landings: int = 0

    def add_hours(self, hours: Decimal) -> None:
        self.hours += hours

    def add_fuel(self, fuel: Decimal) -> None:
        self.fuel += fuel

    def add_oil(self, oil: Decimal) -> None:
        self.oil += oil

    def add_landings(self, n: int) -> None:
        self.landings += n


@dataclass
class _BuildState:
    by_month_aircraft: DefaultDict[str, DefaultDict[str, _Acc]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(_Acc))
    )
    by_month: DefaultDict[str, _Acc] = field(default_factory=lambda: defaultdict(_Acc))
    grand: _Acc = field(default_factory=_Acc)
    flags: List[DataQualityFlag] = field(default_factory=list)
    # last complete fuel snapshot per tail for chain checks
    last_after_plus_uplift: Dict[str, Decimal] = field(default_factory=dict)


def _flag(
    state: _BuildState,
    *,
    code: str,
    message: str,
    row: Any,
    tail: str,
) -> None:
    origin = _row_month_date(row)
    state.flags.append(
        DataQualityFlag(
            code=code,
            message=message,
            sequence_no=getattr(row, "sequence_no", None),
            aircraft_tail=tail or None,
            origin_date=origin.isoformat() if origin else None,
        )
    )
    logger.warning(
        "fuel_report data_quality code=%s seq=%s tail=%s origin=%s msg=%s",
        code,
        getattr(row, "sequence_no", None),
        tail,
        origin,
        message,
    )


def _normalize_tail(registration: Optional[str]) -> str:
    if registration is None:
        return ""
    return registration.strip().upper()


def _row_month_date(row: Any) -> Optional[date]:
    """Prefer SQL month_date; fall back to origin_date."""
    for attr in ("month_date", "origin_date"):
        value = getattr(row, attr, None)
        if value is None:
            continue
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
    return None


def _row_run_time(row: Any) -> Decimal:
    """Prefer SQL run_time coalesce; then airframe / auto / tach fields; else 0."""
    for attr in (
        "run_time",
        "airframe_run_time",
        "auto_airframe_run_time",
        "tachometer_total",
    ):
        hours = _to_decimal(getattr(row, attr, None))
        if hours is not None:
            return hours
    return _ZERO


def process_atl_rows(rows: Sequence[Any]) -> _BuildState:
    """Aggregate ATL rows; null numerics treated as 0. Attach data-quality flags."""
    state = _BuildState()

    for row in rows:
        origin = _row_month_date(row)
        if origin is None:
            continue

        mk = month_key(origin.year, origin.month)
        tail = _normalize_tail(row.registration)
        hours = _row_run_time(row)
        landings = int(_nz(getattr(row, "number_of_landings", None)))

        left_prior = _nz(row.fuel_qty_left_prior_departure)
        right_prior = _nz(row.fuel_qty_right_prior_departure)
        left_after = _nz(row.fuel_qty_left_after_on_blks)
        right_after = _nz(row.fuel_qty_right_after_on_blks)
        left_uplift = _nz(row.fuel_qty_left_uplift_qty)
        right_uplift = _nz(row.fuel_qty_right_uplift_qty)

        fuel = fuel_consumed(left_prior, right_prior, left_after, right_after)
        oil = oil_consumed(
            row.oil_qty_prior_departure,
            row.oil_qty_after_on_blks,
        )

        # Chain check: PRIOR ≈ previous row's (AFTER ON-BLKS + uplift) for same aircraft
        if tail:
            prior_total = left_prior + right_prior
            expected = state.last_after_plus_uplift.get(tail)
            if expected is not None and abs(prior_total - expected) > _CHAIN_TOLERANCE:
                _flag(
                    state,
                    code="fuel_chain_break",
                    message=(
                        f"PRIOR DEP. ({prior_total}) does not roughly match prior "
                        f"AFTER ON-BLKS + uplift ({expected})"
                    ),
                    row=row,
                    tail=tail,
                )

        if fuel < _ZERO:
            _flag(
                state,
                code="negative_fuel_consumed",
                message=(
                    f"fuel_consumed={fuel} (AFTER ON-BLKS exceeds PRIOR DEP.) "
                    "— logbook entry error"
                ),
                row=row,
                tail=tail,
            )

        # Always count hours / landings / fuel / oil (nulls already 0)
        state.by_month[mk].add_hours(hours)
        state.by_month[mk].add_landings(landings)
        state.by_month[mk].add_fuel(fuel)
        state.by_month[mk].add_oil(oil)
        state.grand.add_hours(hours)
        state.grand.add_landings(landings)
        state.grand.add_fuel(fuel)
        state.grand.add_oil(oil)
        if tail:
            state.by_month_aircraft[mk][tail].add_hours(hours)
            state.by_month_aircraft[mk][tail].add_landings(landings)
            state.by_month_aircraft[mk][tail].add_fuel(fuel)
            state.by_month_aircraft[mk][tail].add_oil(oil)
            state.last_after_plus_uplift[tail] = (
                left_after + right_after + left_uplift + right_uplift
            )

    return state


def _iter_months(start: date, end: date) -> List[Tuple[int, int]]:
    """Inclusive list of (year, month) from start's month through end's month."""
    y, m = start.year, start.month
    ey, em = end.year, end.month
    out: List[Tuple[int, int]] = []
    while (y, m) <= (ey, em):
        out.append((y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return out


def build_fuel_report(
    rows: Sequence[Any],
    *,
    start_month: str,
    end_month: str,
) -> AircraftFuelReportResponse:
    """Build monthly series + summary + data_quality_flags from ATL rows."""
    sy, sm = parse_year_month(start_month)
    ey, em = parse_year_month(end_month)
    range_start, _ = ym_to_date_bounds(sy, sm)
    _, range_end = ym_to_date_bounds(ey, em)

    state = process_atl_rows(rows)
    monthly: List[MonthlyFuelRow] = []

    if rows:
        for y, m in _iter_months(range_start, range_end):
            mk = month_key(y, m)
            acc = state.by_month.get(mk, _Acc())
            breakdown: List[AircraftFuelBreakdown] = []
            for tail in sorted(state.by_month_aircraft.get(mk, {}).keys()):
                a = state.by_month_aircraft[mk][tail]
                breakdown.append(
                    AircraftFuelBreakdown(
                        tail_number=tail,
                        hours=_to_float(a.hours),
                        fuel_gal=_to_float(a.fuel),
                        fuel_burn_per_hour=fuel_burn_per_hour(a.fuel, a.hours),
                        oil_usage_qrts=_to_float(a.oil),
                    )
                )
            monthly.append(
                MonthlyFuelRow(
                    month=mk,
                    month_label=month_label(y, m),
                    hours=_to_float(acc.hours),
                    fuel_gal=_to_float(acc.fuel),
                    fuel_burn_per_hour=fuel_burn_per_hour(acc.fuel, acc.hours),
                    oil_usage_qrts=_to_float(acc.oil),
                    landings=acc.landings,
                    aircraft_breakdown=breakdown,
                )
            )
    # else: empty range → monthly: [] (not 404)

    g = state.grand
    return AircraftFuelReportResponse(
        meta=FuelReportMeta(
            source="ATL Logbook",
            range=FuelReportRange(start=start_month, end=end_month),
            generated_at=ph_now(),
        ),
        summary=FuelReportSummary(
            total_hours=_to_float(g.hours),
            total_fuel_gal=_to_float(g.fuel),
            avg_fuel_burn_per_hour=fuel_burn_per_hour(g.fuel, g.hours),
            total_oil_usage_qrts=_to_float(g.oil),
            total_landings=g.landings,
        ),
        monthly=monthly,
        data_quality_flags=state.flags,
    )


def parse_aircraft_filter(raw: Optional[str]) -> List[str]:
    """Split comma-separated tails and normalize; empty → []."""
    if not raw or not raw.strip():
        return []
    return [p.strip().upper() for p in raw.split(",") if p.strip()]


def parse_aircraft_id_filter(raw: Optional[str]) -> List[int]:
    """Split comma-separated aircraft PKs; empty → []. Raises ValueError on bad ints."""
    if not raw or not raw.strip():
        return []
    out: List[int] = []
    for part in raw.split(","):
        text = part.strip()
        if not text:
            continue
        out.append(int(text))
    return out


async def resolve_query_month_bounds(
    session: AsyncSession,
    query: AircraftFuelReportQuery,
    *,
    aircraft_ids: Optional[Sequence[int]] = None,
) -> Tuple[str, str, date, date]:
    """
    Resolve start/end YYYY-MM and inclusive date bounds.

    Defaults to earliest/latest month date when params omitted (optionally
    scoped to the resolved aircraft filter).
    Empty data + omitted params → synthetic current-month empty window.
    """
    min_d, max_d = await fetch_fuel_report_available_month_bounds(
        session,
        aircraft_ids=aircraft_ids,
    )

    if query.start_month:
        sy, sm = parse_year_month(query.start_month)
        start_d, _ = ym_to_date_bounds(sy, sm)
        start_ym = query.start_month
    elif min_d is not None:
        start_d = date(min_d.year, min_d.month, 1)
        start_ym = month_key(min_d.year, min_d.month)
    else:
        today = ph_now().date()
        start_d = date(today.year, today.month, 1)
        start_ym = month_key(today.year, today.month)

    if query.end_month:
        ey, em = parse_year_month(query.end_month)
        _, end_d = ym_to_date_bounds(ey, em)
        end_ym = query.end_month
    elif max_d is not None:
        _, end_d = ym_to_date_bounds(max_d.year, max_d.month)
        end_ym = month_key(max_d.year, max_d.month)
    else:
        today = ph_now().date()
        _, end_d = ym_to_date_bounds(today.year, today.month)
        end_ym = month_key(today.year, today.month)

    if start_d > end_d:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_month must be <= end_month",
        )
    return start_ym, end_ym, start_d, end_d


async def get_aircraft_fuel_report(
    session: AsyncSession,
    query: AircraftFuelReportQuery,
) -> AircraftFuelReportResponse:
    """Fetch ATLs, validate aircraft filter, build (or cache-hit) monthly report."""
    resolved_ids, unknown_regs, unknown_ids = await resolve_aircraft_filter_ids(
        session,
        registrations=query.aircraft,
        aircraft_ids=query.aircraft_ids,
    )
    if unknown_regs or unknown_ids:
        parts: List[str] = []
        if unknown_regs:
            parts.append(f"Unknown aircraft tail number(s): {', '.join(unknown_regs)}")
        if unknown_ids:
            parts.append(
                "Unknown aircraft id(s): "
                + ", ".join(str(i) for i in unknown_ids)
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(parts),
        )

    # When caller passed a filter, scope to those ids; otherwise all aircraft.
    filter_ids: Optional[List[int]] = (
        resolved_ids if (query.aircraft or query.aircraft_ids) else None
    )

    start_ym, end_ym, start_d, end_d = await resolve_query_month_bounds(
        session,
        query,
        aircraft_ids=filter_ids,
    )

    cache_ids = tuple(sorted(filter_ids or []))
    cached = _cache_get(start_ym, end_ym, cache_ids)
    if cached is not None:
        return cached

    rows = await fetch_fuel_report_atl_rows(
        session,
        start_date=start_d,
        end_date=end_d,
        aircraft_ids=filter_ids,
    )
    response = build_fuel_report(rows, start_month=start_ym, end_month=end_ym)
    _cache_set(start_ym, end_ym, cache_ids, response)
    return response
