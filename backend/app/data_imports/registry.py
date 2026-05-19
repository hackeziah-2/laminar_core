"""Registry of Excel import targets (register once, use from API and jobs)."""
from __future__ import annotations

from typing import Dict, List, Optional

from app.data_imports.definitions import ExcelImportTarget

_TARGETS: Dict[str, ExcelImportTarget] = {}
_LEGACY_PATH_INDEX: Dict[str, str] = {}


def register_import_target(target: ExcelImportTarget) -> None:
    if target.key in _TARGETS:
        raise ValueError(f"Duplicate Excel import target key: {target.key!r}")
    _TARGETS[target.key] = target
    for path in target.legacy_paths:
        if path in _LEGACY_PATH_INDEX:
            raise ValueError(f"Duplicate legacy import path: {path!r}")
        _LEGACY_PATH_INDEX[path] = target.key


def get_import_target(key: str) -> Optional[ExcelImportTarget]:
    return _TARGETS.get(key)


def resolve_import_target_key(key_or_path: str) -> Optional[str]:
    """Resolve target key from registry key or legacy URL segment."""
    if key_or_path in _TARGETS:
        return key_or_path
    return _LEGACY_PATH_INDEX.get(key_or_path)


def list_import_targets() -> List[ExcelImportTarget]:
    return sorted(_TARGETS.values(), key=lambda t: t.key)


def ensure_import_targets_loaded() -> None:
    """Import target modules so they self-register (idempotent)."""
    import app.data_imports.targets  # noqa: F401
