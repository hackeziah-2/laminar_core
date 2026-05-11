"""ATL Excel/CSV row cleanup: semantic column aliases, JSON component lists, wide/duplicate columns, continuation rows."""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.schemas.aircraft_technical_log_schema import normalize_component_part_dict_for_import

_ATL_SEMANTIC_ALIASES: Tuple[Tuple[str, str], ...] = (
    ("airframe_afft_start", "tachometer_start"),
    ("airframe_afft_end", "tachometer_end"),
    ("maintenance_action", "remarks"),
    ("maintenance_description", "actions_taken"),
    ("engine_life_limit", "life_time_limit_engine"),
    ("propeller_life_limit", "life_time_limit_propeller"),
)

_COMPONENT_JSON_KEYS = frozenset(
    {"component_parts_record", "component_parts_records", "component_parts_json"}
)

_PART_BASE_KEYS = frozenset(
    {
        "removed_part_no",
        "removed_serial_no",
        "part_removed_remaining_time",
        "part_installed_remaining_time",
        "installed_part_no",
        "installed_serial_no",
        "part_description",
        "part_remark",
        "ata_chapter",
        "part_qty",
        "part_unit",
        "part_nomenclature",
    }
)


def _atl_cell_nonempty(v: Any) -> bool:
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and (math.isnan(v) or not math.isfinite(v)):
        return False
    if isinstance(v, str) and not str(v).strip():
        return False
    return True


def _atl_sequence_nonempty(v: Any) -> bool:
    if not _atl_cell_nonempty(v):
        return False
    if isinstance(v, float) and math.isfinite(v) and v == int(v):
        return True
    if isinstance(v, int) and not isinstance(v, bool):
        return True
    s = str(v).strip()
    return bool(s) and s.lower() not in ("nan", "none")


def normalize_sequence_no(value: Any) -> Optional[str]:
    if value is None:
        return None

    # Handle pandas float
    if isinstance(value, float):
        if math.isnan(value) or not math.isfinite(value):
            return None
        return str(int(value))

    value = str(value).strip()

    # Remove trailing .0
    if value.endswith(".0"):
        value = value[:-2]

    return value


def split_part_column(key: str) -> Tuple[Optional[str], int]:
    """Return (base_field, block_index) for part import columns; (None, 0) if not a part column."""
    if key in _PART_BASE_KEYS:
        return key, 0
    m = re.match(r"^(.+)\.(\d+)$", key)
    if m and m.group(1) in _PART_BASE_KEYS:
        return m.group(1), int(m.group(2))
    m = re.match(r"^(.+)_(\d+)$", key)
    if m and m.group(1) in _PART_BASE_KEYS:
        n = int(m.group(2))
        if n >= 2:
            return m.group(1), n - 1
    return None, 0


def _max_part_block_index(merged: Dict[str, Any]) -> int:
    mx = -1
    for k in merged:
        base, idx = split_part_column(k)
        if base is not None:
            mx = max(mx, idx)
    return mx


def absorb_continuation_parts_into(prev: Dict[str, Any], cont: Dict[str, Any]) -> None:
    """Append part columns from a continuation row onto prev using .{n} suffixes."""
    mx = _max_part_block_index(prev)
    start = 0 if mx < 0 else mx + 1
    for k, v in cont.items():
        base, idx = split_part_column(k)
        if base is None:
            continue
        if not _atl_cell_nonempty(v):
            continue
        blk = start + idx
        new_k = base if blk == 0 else f"{base}.{blk}"
        prev[new_k] = v


def merge_atl_continuation_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge rows with blank sequence_no into the previous row (extra component part lines)."""
    out: List[Dict[str, Any]] = []
    acc: Optional[Dict[str, Any]] = None
    for row in records:
        r = dict(row)
        sequence_no = normalize_sequence_no(r.get("sequence_no"))
        r["sequence_no"] = sequence_no
        if _atl_sequence_nonempty(sequence_no):
            if acc is not None:
                out.append(acc)
            acc = r
        elif acc is not None:
            absorb_continuation_parts_into(acc, r)
    if acc is not None:
        out.append(acc)
    return out


def _apply_semantic_aliases(merged: Dict[str, Any]) -> None:
    for alias, target in _ATL_SEMANTIC_ALIASES:
        if alias not in merged:
            continue
        val = merged.pop(alias)
        if not _atl_cell_nonempty(val):
            continue
        if target not in merged or not _atl_cell_nonempty(merged.get(target)):
            merged[target] = val


def _parse_component_parts_json_cell(raw: Any) -> List[Dict[str, Any]]:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    try:
        if pd.isna(raw):
            return []
    except (TypeError, ValueError):
        pass
    s = str(raw).strip()
    if not s:
        return []
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        inner = data.get("component_parts_record") or data.get("component_parts") or data.get("records")
        if isinstance(inner, list):
            data = inner
        elif all(isinstance(v, dict) for v in data.values()):
            data = list(data.values())
        else:
            data = [data]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _gather_wide_part_blocks(merged: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks: Dict[int, Dict[str, Any]] = {}
    for k, v in list(merged.items()):
        base, idx = split_part_column(k)
        if base is None:
            continue
        blocks.setdefault(idx, {})[base] = v
    ordered = sorted(blocks.keys())
    out: List[Dict[str, Any]] = []
    for i in ordered:
        d = blocks[i]
        if any(_atl_cell_nonempty(d.get(x)) for x in _PART_BASE_KEYS):
            out.append(dict(d))
    return out


def _pop_all_part_columns(merged: Dict[str, Any]) -> None:
    for k in list(merged.keys()):
        base, _ = split_part_column(k)
        if base is not None:
            merged.pop(k, None)


def normalize_atl_import_row(merged: Dict[str, Any]) -> None:
    """Mutate merged: aliases, JSON parts, wide/flat part columns -> component_parts; strip import-only keys."""
    _apply_semantic_aliases(merged)

    json_parts: List[Dict[str, Any]] = []
    for jk in _COMPONENT_JSON_KEYS:
        if jk in merged:
            json_parts.extend(_parse_component_parts_json_cell(merged.pop(jk)))

    wide_blocks = _gather_wide_part_blocks(merged)
    _pop_all_part_columns(merged)

    combined: List[Dict[str, Any]] = []
    combined.extend(json_parts)
    combined.extend(wide_blocks)

    if combined:
        merged["component_parts"] = [
            normalize_component_part_dict_for_import(p) for p in combined
        ]
    else:
        merged.pop("component_parts", None)
