"""Blank LDND unit is stored as null, including Annual inspections."""

from app.schemas.ldnd_monitoring_schema import (
    LDNDMonitoringCreate,
    LDNDMonitoringImportSchema,
    LDNDMonitoringUpdate,
    is_annual_inspection,
)


def test_annual_inspection_detection():
    assert is_annual_inspection("Annual Inspection") is True
    assert is_annual_inspection("ANNUAL") is True
    assert is_annual_inspection("100-Hour Inspection") is False
    assert is_annual_inspection("Semi-annual Inspection") is False


def test_create_keeps_a_blank_unit():
    annual = LDNDMonitoringCreate(
        aircraft_fk=1,
        inspection_type="Annual Inspection",
        unit=None,
    )
    assert annual.unit is None

    blank = LDNDMonitoringCreate(
        aircraft_fk=1,
        inspection_type="Annual Inspection",
        unit="",
    )
    assert blank.unit is None

    none_label = LDNDMonitoringCreate(
        aircraft_fk=1,
        inspection_type="100-Hour Inspection",
        unit="None",
    )
    assert none_label.unit is None


def test_create_keeps_hrs_and_cycles():
    hours = LDNDMonitoringCreate(
        aircraft_fk=1,
        inspection_type="100-Hour Inspection",
        unit="hrs",
    )
    cycles = LDNDMonitoringCreate(
        aircraft_fk=1,
        inspection_type="100-Hour Inspection",
        unit="CYCLES",
    )
    assert hours.unit == "HRS"
    assert cycles.unit == "CYCLES"


def test_update_can_clear_unit():
    updated = LDNDMonitoringUpdate(unit="")
    assert updated.unit is None
    assert "unit" in updated.dict(exclude_unset=True)


def test_import_omitted_unit_stays_blank_only_for_annual():
    annual = LDNDMonitoringImportSchema(
        aircraft_fk=1,
        inspection_type="Annual Inspection",
        last_done_tach_done=10,
    )
    other = LDNDMonitoringImportSchema(
        aircraft_fk=1,
        inspection_type="100-Hour Inspection",
        last_done_tach_done=10,
    )
    assert annual.unit is None
    assert other.unit == "HRS"


def test_import_does_not_default_annual_unit_to_hrs():
    annual = LDNDMonitoringImportSchema(
        aircraft_fk=1,
        inspection_type="Annual Inspection",
        unit="",
        last_done_tach_done=10,
    )
    other = LDNDMonitoringImportSchema(
        aircraft_fk=1,
        inspection_type="100-Hour Inspection",
        unit="",
        last_done_tach_done=10,
    )
    assert annual.unit is None
    assert other.unit == "HRS"
