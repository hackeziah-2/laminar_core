"""Aircraft Fuel Report — monthly ATL Logbook rollup for dashboard charts."""

from __future__ import annotations

import logging
import statistics
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
    AircraftMonthBreakdown,
    AircraftMonthBreakdownRow,
    DataQualityFlag,
    FuelReportMeta,
    FuelReportRange,
    FuelReportSummary,
    MonthlyFuelRow,
    YoyFlyingHours,
    YoyFlyingHoursMonth,
    parse_year_month,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_CHAIN_TOLERANCE = Decimal("0.5")  # gallons — "roughly match" prior AFTER+uplift
# YoY month flagged when max(hours)/min(hours) among years with data exceeds this.
# July 152→796 (~5.2x) is the reference case; owners can tune this constant.
_YOY_VARIANCE_RATIO_THRESHOLD = Decimal("3")
# Per-aircraft burn flagged when ratio vs peer median exceeds this (e.g. 5 vs ~20).
_FLEET_BURN_OUTLIER_RATIO = Decimal("4")

_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
_MONTH_FULL = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# Cache key: (start, end, aircraft_ids, years, month_year)
_CacheKey = Tuple[str, str, Tuple[int, ...], Tuple[int, ...], Optional[str]]

# ---------------------------------------------------------------------------
# Simple process-local cache
# ---------------------------------------------------------------------------
_cache_lock = threading.Lock()
_report_cache: Dict[_CacheKey, AircraftFuelReportResponse] = {}


def invalidate_fuel_report_cache(*, origin_date: Optional[date] = None) -> None:
    """
    Drop cached rollups.

    When ``origin_date`` is set, drop entries whose monthly range, YoY years,
    or ``month_year`` slicer covers that date; otherwise clear the entire cache.
    """
    with _cache_lock:
        if origin_date is None:
            _report_cache.clear()
            return
        ym = f"{origin_date.year:04d}-{origin_date.month:02d}"
        year = origin_date.year
        to_drop = [
            key
            for key in _report_cache
            if key[0] <= ym <= key[1]
            or year in key[3]
            or key[4] == ym
        ]
        for key in to_drop:
            _report_cache.pop(key, None)


def _cache_get(
    start_month: str,
    end_month: str,
    aircraft_ids: Sequence[int],
    years: Sequence[int],
    month_year: Optional[str],
) -> Optional[AircraftFuelReportResponse]:
    key: _CacheKey = (
        start_month,
        end_month,
        tuple(sorted(aircraft_ids)),
        tuple(sorted(years)),
        month_year,
    )
    with _cache_lock:
        return _report_cache.get(key)


def _cache_set(
    start_month: str,
    end_month: str,
    aircraft_ids: Sequence[int],
    years: Sequence[int],
    month_year: Optional[str],
    response: AircraftFuelReportResponse,
) -> None:
    key: _CacheKey = (
        start_month,
        end_month,
        tuple(sorted(aircraft_ids)),
        tuple(sorted(years)),
        month_year,
    )
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
    """Round to 2 decimal places for legacy monthly/summary fields."""
    return float(value.quantize(Decimal("0.01")))


def _raw_float(value: Decimal) -> float:
    """Convert Decimal → float without display rounding (new YoY / slicer fields)."""
    return float(value)


def month_label(year: int, month: int) -> str:
    """e.g. 2026-01 → Jan-26"""
    return f"{_MONTH_ABBR[month - 1]}-{year % 100:02d}"


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def ym_to_date_bounds(year: int, month: int) -> Tuple[date, date]:
    """Inclusive first/last calendar day of YYYY-MM."""
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def exclusive_month_end(year: int, month: int) -> date:
    """First day of the month after ``year-month`` (exclusive upper bound)."""
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def ym_to_exclusive_range(start_month: str, end_month: str) -> Tuple[date, date]:
    """
    Convert YYYY-MM..YYYY-MM to ``[start, end_exclusive)``.

    Example: 2023-01..2026-12 → 2023-01-01 .. 2027-01-01
    """
    sy, sm = parse_year_month(start_month)
    ey, em = parse_year_month(end_month)
    return date(sy, sm, 1), exclusive_month_end(ey, em)


def years_from_month_range(start_month: str, end_month: str) -> List[int]:
    """Inclusive calendar years spanned by start_month..end_month (YYYY-MM)."""
    start_year, _ = parse_year_month(start_month)
    end_year, _ = parse_year_month(end_month)
    if start_year > end_year:
        start_year, end_year = end_year, start_year
    return list(range(start_year, end_year + 1))


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
    row: Any = None,
    tail: str = "",
    origin_date: Optional[str] = None,
) -> None:
    origin = _row_month_date(row) if row is not None else None
    origin_iso = origin.isoformat() if origin else origin_date
    state.flags.append(
        DataQualityFlag(
            code=code,
            message=message,
            sequence_no=getattr(row, "sequence_no", None) if row is not None else None,
            aircraft_tail=tail or None,
            origin_date=origin_iso,
        )
    )
    logger.warning(
        "fuel_report data_quality code=%s seq=%s tail=%s origin=%s msg=%s",
        code,
        getattr(row, "sequence_no", None) if row is not None else None,
        tail,
        origin_iso,
        message,
    )


def _normalize_tail(registration: Optional[str]) -> str:
    if registration is None:
        return ""
    return registration.strip().upper()


def _row_month_date(row: Any) -> Optional[date]:
    """ATL off-blocks date (origin_date); nulls are skipped by callers."""
    for attr in ("off_blocks_date", "origin_date"):
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


def _yoy_ratio(values: Sequence[Decimal]) -> Optional[Decimal]:
    """max/min among positive values; None if fewer than two positive datapoints."""
    positive = [v for v in values if v > _ZERO]
    if len(positive) < 2:
        return None
    lo = min(positive)
    hi = max(positive)
    if lo == _ZERO:
        return None
    return hi / lo


def build_yoy_flying_hours(
    state: _BuildState,
    years: Sequence[int],
) -> YoyFlyingHours:
    """
    Jan–Dec flying hours per requested year.

    grand_total / average_fh only include months that have data for that year
    (hours > 0) — missing months are not zero-padded into the totals.
    """
    sorted_years = sorted(years)
    months_out: List[YoyFlyingHoursMonth] = []
    # Track months-with-data per year for average/grand_total
    year_month_hours: Dict[int, List[Decimal]] = {y: [] for y in sorted_years}

    for month_idx in range(1, 13):
        values_dec: Dict[str, Decimal] = {}
        values_out: Dict[str, float] = {}
        for y in sorted_years:
            mk = month_key(y, month_idx)
            hours = state.by_month.get(mk, _Acc()).hours
            values_dec[str(y)] = hours
            values_out[str(y)] = _raw_float(hours)
            if hours > _ZERO:
                year_month_hours[y].append(hours)

        flag: Optional[str] = None
        ratio = _yoy_ratio(list(values_dec.values()))
        if ratio is not None and ratio >= _YOY_VARIANCE_RATIO_THRESHOLD:
            flag = "large_yoy_variance"
            _flag(
                state,
                code="large_yoy_variance",
                message=(
                    f"{_MONTH_FULL[month_idx - 1]} YoY flying hours ratio "
                    f"{_raw_float(ratio):.2f}x exceeds threshold "
                    f"{_raw_float(_YOY_VARIANCE_RATIO_THRESHOLD)}x "
                    f"(values={ {k: _raw_float(v) for k, v in values_dec.items()} })"
                ),
                origin_date=f"{sorted_years[0]:04d}-{month_idx:02d}-01",
            )

        months_out.append(
            YoyFlyingHoursMonth(
                month=_MONTH_FULL[month_idx - 1],
                values=values_out,
                flag=flag,
            )
        )

    grand_total: Dict[str, float] = {}
    average_fh: Dict[str, float] = {}
    for y in sorted_years:
        samples = year_month_hours[y]
        if samples:
            total = sum(samples, _ZERO)
            grand_total[str(y)] = _raw_float(total)
            average_fh[str(y)] = _raw_float(total / Decimal(len(samples)))
        else:
            grand_total[str(y)] = 0.0
            average_fh[str(y)] = 0.0

    return YoyFlyingHours(
        years=sorted_years,
        months=months_out,
        average_fh=average_fh,
        grand_total=grand_total,
    )


def build_aircraft_month_breakdown(
    state: _BuildState,
    *,
    month_year: Optional[str],
) -> AircraftMonthBreakdown:
    """
    Per-aircraft hours/fuel for a single month slicer.

    Uses shared ``fuel_burn_per_hour`` (null when hours == 0).
    Flags fleet burn outliers via the same data_quality_flags list.
    """
    if not month_year:
        return AircraftMonthBreakdown(month_year=None, aircraft=[])

    y, m = parse_year_month(month_year)
    mk = month_key(y, m)
    label = month_label(y, m)
    by_tail = state.by_month_aircraft.get(mk, {})

    rows: List[AircraftMonthBreakdownRow] = []
    burns: Dict[str, float] = {}
    for tail in sorted(by_tail.keys()):
        acc = by_tail[tail]
        burn = fuel_burn_per_hour(acc.fuel, acc.hours)
        if burn is not None:
            burns[tail] = burn
        rows.append(
            AircraftMonthBreakdownRow(
                tail_number=tail,
                hours=_raw_float(acc.hours),
                fuel=_raw_float(acc.fuel),
                fuel_burn_per_hour=burn,
            )
        )

    # Outlier check vs leave-one-out peer median (need ≥2 aircraft with burn rates)
    if len(burns) >= 2:
        for row in rows:
            if row.fuel_burn_per_hour is None:
                continue
            peer_values = [v for t, v in burns.items() if t != row.tail_number]
            if not peer_values:
                continue
            peer_median = Decimal(str(statistics.median(peer_values)))
            if peer_median <= _ZERO:
                continue
            burn_dec = Decimal(str(row.fuel_burn_per_hour))
            ratio = max(burn_dec, peer_median) / min(burn_dec, peer_median)
            if ratio >= _FLEET_BURN_OUTLIER_RATIO:
                row.flag = "fuel_burn_outlier"
                _flag(
                    state,
                    code="fuel_burn_outlier",
                    message=(
                        f"{row.tail_number} fuel_burn_per_hour="
                        f"{row.fuel_burn_per_hour} is "
                        f"{_raw_float(ratio):.2f}x vs peer median "
                        f"{_raw_float(peer_median)} for {label}"
                    ),
                    tail=row.tail_number,
                    origin_date=f"{y:04d}-{m:02d}-01",
                )

    return AircraftMonthBreakdown(month_year=label, aircraft=rows)


def build_fuel_report(
    rows: Sequence[Any],
    *,
    start_month: str,
    end_month: str,
    years: Optional[Sequence[int]] = None,
    month_year: Optional[str] = None,
) -> AircraftFuelReportResponse:
    """
    Build monthly series + YoY + month breakdown + data_quality_flags.

    ``rows`` may span a widened fetch (YoY years / slicer). Monthly series and
    summary are scoped to ``[start_month, end_month]`` via half-open
    off_blocks_date bounds; YoY and the aircraft month breakdown read from the
    full aggregated state.
    """
    range_start, range_end_exclusive = ym_to_exclusive_range(start_month, end_month)
    resolved_years = (
        list(years) if years else years_from_month_range(start_month, end_month)
    )

    state_all = process_atl_rows(rows)

    window_rows = [
        row
        for row in rows
        if (origin := _row_month_date(row)) is not None
        and range_start <= origin < range_end_exclusive
    ]
    state_window = process_atl_rows(window_rows) if window_rows else _BuildState()

    # Inclusive last day only for iterating month buckets in the response
    _, range_end_inclusive = ym_to_date_bounds(*parse_year_month(end_month))

    monthly: List[MonthlyFuelRow] = []
    if window_rows:
        for y, m in _iter_months(range_start, range_end_inclusive):
            mk = month_key(y, m)
            acc = state_window.by_month.get(mk, _Acc())
            breakdown: List[AircraftFuelBreakdown] = []
            for tail in sorted(state_window.by_month_aircraft.get(mk, {}).keys()):
                a = state_window.by_month_aircraft[mk][tail]
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

    # Carry row-level flags from the monthly window; YoY / outlier flags append next
    state_all.flags = list(state_window.flags)
    yoy = build_yoy_flying_hours(state_all, resolved_years)
    aircraft_month = build_aircraft_month_breakdown(state_all, month_year=month_year)

    g = state_window.grand
    return AircraftFuelReportResponse(
        meta=FuelReportMeta(
            source="ATL Logbook",
            range=FuelReportRange(start=start_month, end=end_month),
            generated_at=ph_now(),
            fuel_unit="gallons",
        ),
        summary=FuelReportSummary(
            total_hours=_to_float(g.hours),
            total_fuel_gal=_to_float(g.fuel),
            avg_fuel_burn_per_hour=fuel_burn_per_hour(g.fuel, g.hours),
            total_oil_usage_qrts=_to_float(g.oil),
            total_landings=g.landings,
        ),
        monthly=monthly,
        data_quality_flags=state_all.flags,
        yoy_flying_hours=yoy,
        aircraft_month_breakdown=aircraft_month,
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


def parse_years_filter(raw: Optional[str]) -> List[int]:
    """Split comma-separated years; empty → [] (caller applies default)."""
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


def _union_fetch_bounds(
    *,
    start_d: date,
    end_d_exclusive: date,
    years: Sequence[int],
    month_year: Optional[str],
) -> Tuple[date, date]:
    """
    Widen the ATL fetch window to cover monthly range + YoY years + slicer month.

    Returns ``(fetch_start, fetch_end_exclusive)`` half-open bounds.
    """
    fetch_start, fetch_end_excl = start_d, end_d_exclusive
    if years:
        y_min, y_max = min(years), max(years)
        fetch_start = min(fetch_start, date(y_min, 1, 1))
        fetch_end_excl = max(fetch_end_excl, date(y_max + 1, 1, 1))
    if month_year:
        my, mm = parse_year_month(month_year)
        m_start = date(my, mm, 1)
        m_end_excl = exclusive_month_end(my, mm)
        fetch_start = min(fetch_start, m_start)
        fetch_end_excl = max(fetch_end_excl, m_end_excl)
    return fetch_start, fetch_end_excl


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
    # resolve_query_month_bounds returns inclusive last day; convert to exclusive
    end_d_exclusive = exclusive_month_end(end_d.year, end_d.month)

    years = (
        list(query.years)
        if query.years
        else years_from_month_range(start_ym, end_ym)
    )
    month_year = query.month_year

    cache_ids = tuple(sorted(filter_ids or []))
    cached = _cache_get(start_ym, end_ym, cache_ids, years, month_year)
    if cached is not None:
        return cached

    fetch_start, fetch_end_exclusive = _union_fetch_bounds(
        start_d=start_d,
        end_d_exclusive=end_d_exclusive,
        years=years,
        month_year=month_year,
    )

    rows = await fetch_fuel_report_atl_rows(
        session,
        start_date=fetch_start,
        end_date_exclusive=fetch_end_exclusive,
        aircraft_ids=filter_ids,
    )
    response = build_fuel_report(
        rows,
        start_month=start_ym,
        end_month=end_ym,
        years=years,
        month_year=month_year,
    )
    _cache_set(start_ym, end_ym, cache_ids, years, month_year, response)
    return response
