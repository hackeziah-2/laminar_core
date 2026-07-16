"""Excel header (lowercase) → ADMonitoring / import schema field names.

Canonical labels: ``AD NUMBER``, ``SUBJECT``, ``INSPECTION INTERVAL``,
``DATE OF EFFECTIVITY`` (any case; snake_case aliases included).
"""

AD_EXCEL_COLUMN_MAPPING = {
    "ad number": "ad_number",
    "ad_number": "ad_number",
    "subject": "subject",
    "inspection interval": "inspection_interval",
    "inspection_interval": "inspection_interval",
    "date of effectivity": "compli_date",
    "date of effectivity or compliance date": "compli_date",
    "compli_date": "compli_date",
    "web link": "web_link",
    "web_link": "web_link",
}
