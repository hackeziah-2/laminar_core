"""Build CSV/Excel upload bytes for import tests."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional


def aircraft_csv_bytes(rows: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """Minimal valid aircraft import CSV (headers lowercased as in production)."""
    default_row = {
        "registration": "IMP-001",
        "model": "172",
        "msn": "MSN-IMP-001",
        "base": "Test Base",
        "ownership": "Test Owner",
        "status": "Active",
    }
    data = rows if rows is not None else [default_row]
    fieldnames = list(data[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def invalid_extension_bytes() -> bytes:
    return b"not a spreadsheet"


def ad_csv_bytes(rows: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """Minimal valid AD monitoring import CSV (friendly headers as in production mapping)."""
    default_row = {
        "AD Number": "32232",
        "Subject": "CONNECTING ROD ASSEMBLY",
        "Inspection Interval": "Every 100 hours or Annual, WCF",
        "Date of Effectivity or Compliance Date": "6/5/2023",
    }
    data = rows if rows is not None else [default_row]
    fieldnames: List[str] = []
    for row in data:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def ad_work_order_csv_bytes(rows: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """Minimal valid AD work-order import CSV (friendly headers as in production mapping)."""
    default_row = {
        "WO Number": "17212-A-000343",
        "Last Done Actt": "6080.1",
        "Last Done Tach": "6079.5",
        "Last Done Date": "6/5/2023",
        "Next Done Actt": "6180.1",
        "Tach": "6179.5",
        "Atl Ref": "ATL-0002225",
    }
    data = rows if rows is not None else [default_row]
    fieldnames: List[str] = []
    for row in data:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def tcc_csv_bytes(rows: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """Minimal valid TCC maintenance import CSV (friendly headers as in production mapping)."""
    default_row = {
        "Category": "POWERPLANT",
        "Part Number": "O-320-E2D",
        "Serial Number": "L-20134-27A",
        "Description": "Engine",
        "Component Method of Compliance": "Overhaul",
        "Last Done Date": "6/5/2023",
        "Last Done Tach": "6345.6",
        "Last Done AFTT": "6346.2",
        "Last Done Method of Compliance": "Overhaul",
        "Component Limit Years": "12",
        "Component Limit Hours": "2000",
        "Atl Ref": "10001",
    }
    data = rows if rows is not None else [default_row]
    fieldnames: List[str] = []
    for row in data:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def ldnd_csv_bytes(rows: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """Minimal valid LDND import CSV (friendly headers as in production mapping)."""
    default_row = {
        "Inspection Type": "100",
        "Unit": "HRS",
        "Last Done Tach Due": "5878.4",
        "Last Done Tach Done": "5879.2",
        "Next Due Tach Hours": "5928.4",
        "Performed Date Start": "17-Aug-23",
        "Performed Date End": "8/17/2023",
    }
    data = rows if rows is not None else [default_row]
    fieldnames = list(data[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def cpcp_csv_bytes(rows: Optional[List[Dict[str, Any]]] = None) -> bytes:
    """Minimal valid CPCP monitoring import CSV (friendly headers as in production mapping)."""
    default_row = {
        "Inspection Operation": "Fuselage skin check",
        "Description": "CPCP visual inspection",
        "Interval Hours": "250",
        "Interval Months": "12",
        "Last Done Tach": "6345.6",
        "Last Done AFTT": "6346.2",
        "Last Done Date": "6/5/2023",
        "Sequence No.": "10001",
    }
    data = rows if rows is not None else [default_row]
    fieldnames: List[str] = []
    for row in data:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")
