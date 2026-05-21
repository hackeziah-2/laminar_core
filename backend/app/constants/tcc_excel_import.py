"""Excel header (lowercase) → TCCMaintenanceImportSchema field names."""

TCC_EXCEL_COLUMN_MAPPING = {
    "category": "category",
    "part number": "part_number",
    "serial number": "serial_number",
    "description": "description",
    "component method of compliance": "component_method_of_compliance",
    "last done date": "last_done_date",
    "last done tach": "last_done_tach",
    "last done aftt": "last_done_aftt",
    "last done method of compliance": "last_done_method_of_compliance",
    "method of compliance": "last_done_method_of_compliance",
    "component limit years": "component_limit_years",
    "component limit hours": "component_limit_hours",
    # Spreadsheet value is ATL sequence_no; resolved to aircraft_technical_log.id → atl_ref
    "atl ref": "atl_sequence",
    "atl ref.": "atl_sequence",
    "sequence no": "atl_sequence",
    "sequence no.": "atl_sequence",
    "sequence_no": "atl_sequence",
    "sequence number": "atl_sequence",
    "atl sequence": "atl_sequence",
    "atl sequence no": "atl_sequence",
}
