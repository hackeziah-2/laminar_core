"""Nature-of-flight required fields for ATL create/update/import."""

from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError
from pydantic.error_wrappers import ErrorWrapper

ATL_REQUIRED_FIELD_MESSAGE = "This field is required."

_TACH_HOBBS_NATURES = frozenset({"TR", "TR_WITH_PIREM", "EGR"})
_PRF_NATURES = frozenset({"PRF"})

_FIELD_ALIASES: Dict[str, Tuple[str, ...]] = {
    "tachometer_end": ("tachometer_end", "tachometerEnd", "tach_end", "tachEnd"),
    "hobbs_meter_end": ("hobbs_meter_end", "hobbsMeterEnd", "hobbs_end", "hobbsEnd"),
    "origin_date": ("origin_date", "originDate", "off_blocks_date", "offBlocksDate"),
    "origin_time": ("origin_time", "originTime", "off_blocks_time", "offBlocksTime"),
    "rts_signed_by": ("rts_signed_by", "rtsSignedBy"),
    "rts_date": ("rts_date", "rtsDate"),
    "rts_time": ("rts_time", "rtsTime"),
    "pilot_accepted_by": (
        "pilot_accepted_by",
        "pilotAcceptedBy",
        "pilot_fk",
        "pilotFk",
    ),
    "pilot_accept_date": ("pilot_accept_date", "pilotAcceptDate"),
    "pilot_accept_time": ("pilot_accept_time", "pilotAcceptTime"),
}


def _normalize_nature(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    value = getattr(raw, "value", raw)
    text = str(value).strip()
    if not text or text == "-":
        return None
    compact = " ".join(
        text.upper().replace("_", " ").replace("-", " ").replace("/", " ").split()
    )
    aliases = {
        "TR": "TR",
        "EGR": "EGR",
        "PRF": "PRF",
        "TR WITH PIREM": "TR_WITH_PIREM",
        "TR W PIREM": "TR_WITH_PIREM",
        "TR_WITH_PIREM": "TR_WITH_PIREM",
    }
    return aliases.get(compact) or aliases.get(compact.replace(" ", "_"))


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _is_blank_assignee(value: Any) -> bool:
    if _is_blank(value):
        return True
    if isinstance(value, str) and value.strip().lower() in (
        "none",
        "null",
        "undefined",
        "-",
        "na",
        "n/a",
        "no selected name",
    ):
        return True
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return False
    return number <= 0


def _lookup(values: Dict[str, Any], canonical: str) -> Tuple[bool, Any]:
    for alias in _FIELD_ALIASES[canonical]:
        if alias in values:
            return True, values[alias]
    return False, None


def collect_atl_nature_required_field_errors(
    values: Dict[str, Any],
    *,
    skip_if_nature_omitted: bool,
) -> List[Tuple[str, str]]:
    nature_present = "nature_of_flight" in values or "natureOfFlight" in values
    if skip_if_nature_omitted and not nature_present:
        return []

    raw_nature = values.get("nature_of_flight", values.get("natureOfFlight"))
    nature = _normalize_nature(raw_nature)
    if nature is None:
        return []

    errors: List[Tuple[str, str]] = []

    def require(canonical: str, blank_fn=_is_blank) -> None:
        found, value = _lookup(values, canonical)
        if not found or blank_fn(value):
            errors.append((canonical, ATL_REQUIRED_FIELD_MESSAGE))

    if nature in _TACH_HOBBS_NATURES:
        require("tachometer_end")
        require("hobbs_meter_end")

    if nature in _PRF_NATURES:
        require("origin_date")
        require("origin_time")
        require("rts_signed_by", _is_blank_assignee)
        require("rts_date")
        require("rts_time")
        require("pilot_accepted_by", _is_blank_assignee)
        require("pilot_accept_date")
        require("pilot_accept_time")

    return errors


def enforce_atl_nature_required_fields(
    values: Any,
    model: Type[BaseModel],
    *,
    skip_if_nature_omitted: bool,
) -> Any:
    if not isinstance(values, dict):
        return values
    errors = collect_atl_nature_required_field_errors(
        values, skip_if_nature_omitted=skip_if_nature_omitted
    )
    if errors:
        raise ValidationError(
            [ErrorWrapper(ValueError(msg), loc=(field,)) for field, msg in errors],
            model,
        )
    return values
