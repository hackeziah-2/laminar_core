"""Excel header (lowercase) -> CPCPMonitoringImportSchema field names."""

CPCP_EXCEL_COLUMN_MAPPING = {
    "inspection operation": "inspection_operation",
    "description": "description",
    "interval hours": "interval_hours",
    "interval months": "interval_months",
    "last done tach": "last_done_tach",
    "last done aftt": "last_done_aftt",
    "last done date": "last_done_date",
    # Spreadsheet value is ATL sequence_no; resolved to aircraft_technical_log.id -> atl_ref
    "sequence no.": "atl_sequence",
    "sequence no": "atl_sequence",
    "sequence_no": "atl_sequence",
    "sequence number": "atl_sequence",
    "atl ref": "atl_sequence",
    "atl ref.": "atl_sequence",
}
