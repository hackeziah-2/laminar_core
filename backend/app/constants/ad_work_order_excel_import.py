"""Excel header (lowercase) → WorkOrderADMonitoring / import schema field names."""

AD_WORK_ORDER_EXCEL_COLUMN_MAPPING = {
    "wo number": "work_order_number",
    "last done actt": "last_done_actt",
    "last done tach": "last_done_tach",
    "last done date": "last_done_date",
    "next done actt": "next_done_actt",
    "tach": "tach",
    "atl ref": "atl_ref",
}
