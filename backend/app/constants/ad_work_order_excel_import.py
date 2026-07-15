"""Excel header (lowercase) → WorkOrderADMonitoring / import schema field names.

Canonical spreadsheet labels:
``WO NUMBER``, ``LAST DONE AFTT``, ``LAST DONE TACH``, ``LAST DONE DATE``,
``NEXT DUE AFTT``, ``NEXT DUE TACH``, ``ATL REF`` (any case; snake_case aliases included).
"""

AD_WORK_ORDER_EXCEL_COLUMN_MAPPING = {
    "wo number": "work_order_number",
    "wo_number": "work_order_number",
    "last done aftt": "last_done_aftt",
    "last_done_aftt": "last_done_aftt",
    "last done actt": "last_done_aftt",
    "last_done_actt": "last_done_aftt",
    "last done tach": "last_done_tach",
    "last_done_tach": "last_done_tach",
    "last done date": "last_done_date",
    "last_done_date": "last_done_date",
    "next due aftt": "next_due_aftt",
    "next_due_aftt": "next_due_aftt",
    "next done aftt": "next_due_aftt",
    "next_done_aftt": "next_due_aftt",
    "next done actt": "next_due_aftt",
    "next_done_actt": "next_due_aftt",
    "next due tach": "next_due_tach",
    "next_due_tach": "next_due_tach",
    "next done tach": "next_due_tach",
    "next_done_tach": "next_due_tach",
    "tach": "next_due_tach",
    "atl ref": "atl_ref",
    "atl_ref": "atl_ref",
}
