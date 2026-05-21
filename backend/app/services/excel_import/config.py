"""Configuration for a generic Excel import run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel


@dataclass(frozen=True)
class ExcelImportConfig:
    model: type
    schema: Type[BaseModel]
    unique_fields: Union[str, List[str]]
    hook_key: str
    dry_run: bool = False
    column_mapping: Optional[Dict[str, str]] = None
    integrity_error_messages: Optional[Dict[str, str]] = None
    inject_fields: Dict[str, Any] = field(default_factory=dict)
    audit_account_id: Optional[int] = None
