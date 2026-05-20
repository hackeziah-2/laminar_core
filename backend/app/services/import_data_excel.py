"""
Generic Excel/CSV import (legacy module path).

Prefer:
  - app.services.excel_import_service.ExcelImportService
  - app.services.excel_import.config.ExcelImportConfig
"""
from app.services.excel_import.parsers import (
    make_hashable as _make_hashable,
    normalize_import_nature_of_flight as _normalize_import_nature_of_flight,
    parse_import_origin_date as _parse_import_origin_date,
)
from app.repository.excel_import import (
    model_column_names as _model_column_names,
    normalize_unique_fields as _normalize_unique_fields,
)
from app.services.excel_import.row_builder import schema_field_names as _schema_field_names
from app.services.excel_import_service import import_excel_generic

__all__ = [
    "import_excel_generic",
    "_make_hashable",
    "_model_column_names",
    "_normalize_import_nature_of_flight",
    "_normalize_unique_fields",
    "_parse_import_origin_date",
    "_schema_field_names",
]
