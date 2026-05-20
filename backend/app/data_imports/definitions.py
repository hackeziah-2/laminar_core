"""Declarative Excel import target definitions (one per importable table)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Type, Union

from pydantic import BaseModel

ImportContextResolver = Callable[
    [Any, Mapping[str, Any]],
    Awaitable[Dict[str, Any]],
]


@dataclass(frozen=True)
class ExcelImportTarget:
    """Metadata and defaults for importing rows into one SQLAlchemy model."""

    key: str
    label: str
    model: type
    schema: Type[BaseModel]
    unique_fields: Union[str, List[str]]
    hook_key: str
    rbac_module: str
    rbac_action: str = "can_create"
    summary: str = ""
    column_mapping: Optional[Dict[str, str]] = None
    integrity_error_messages: Optional[Dict[str, str]] = None
    required_form_fields: tuple[str, ...] = ()
    optional_form_fields: tuple[str, ...] = ()
    resolve_context: Optional[ImportContextResolver] = None
    legacy_paths: tuple[str, ...] = field(default_factory=tuple)
