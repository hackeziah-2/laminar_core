"""Unit tests for SQLAlchemy models."""
import pytest
from datetime import date, time
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aircraft import Aircraft
from app.models.aircraft_techinical_log import AircraftTechnicalLog, TypeEnum
from app.models.atl_monitoring import LDNDMonitoring


@pytest.mark.asyncio
async def test_create_aircraft_model(db_session: AsyncSession):
    """Test creating an Aircraft model instance."""
    aircraft = Aircraft(
        registration="TEST-REG-001",
        manufacturer="Boeing",
        type="Commercial",
        model="737-800",
        msn="MSN-001",
        base="Test Base",
        ownership="Test Owner",
        status="Active",
    )
    db_session.add(aircraft)
    await db_session.commit()
    await db_session.refresh(aircraft)

    assert aircraft.id is not None
    assert aircraft.registration == "TEST-REG-001"
    assert aircraft.status == "Active"


@pytest.mark.asyncio
async def test_create_aircraft_technical_log_model(
    db_session: AsyncSession,
    test_aircraft_data: dict
):
    """Test creating an AircraftTechnicalLog model instance."""
    # Create aircraft first
    aircraft = Aircraft(**test_aircraft_data)
    db_session.add(aircraft)
    await db_session.flush()

    # Create ATL log
    atl = AircraftTechnicalLog(
        aircraft_fk=aircraft.id,
        sequence_no="ATL-001",
        nature_of_flight=TypeEnum.TR,
        origin_station="ORG",
        origin_date=date.today(),
        origin_time=time(10, 0, 0),
        destination_station="DEST",
        destination_date=date.today(),
        destination_time=time(12, 0, 0),
        number_of_landings=1,
        hobbs_meter_start=100.0,
        hobbs_meter_end=102.5,
        hobbs_meter_total=2.5,
        tachometer_start=100.0,
        tachometer_end=102.5,
        tachometer_total=2.5,
    )
    db_session.add(atl)
    await db_session.commit()
    await db_session.refresh(atl)

    assert atl.id is not None
    assert atl.sequence_no == "ATL-001"
    assert atl.nature_of_flight == TypeEnum.TR
    assert atl.aircraft_fk == aircraft.id


@pytest.mark.asyncio
async def test_aircraft_soft_delete(db_session: AsyncSession):
    """Test soft delete functionality on Aircraft model."""
    aircraft = Aircraft(
        registration="TEST-SOFT-DELETE",
        manufacturer="Boeing",
        type="Commercial",
        model="737-800",
        msn="MSN-SOFT-DELETE",
        base="Test Base",
        ownership="Test Owner",
        status="Active",
    )
    db_session.add(aircraft)
    await db_session.commit()
    await db_session.refresh(aircraft)

    assert aircraft.is_deleted is False

    # Soft delete
    aircraft.soft_delete()
    await db_session.commit()
    await db_session.refresh(aircraft)

    assert aircraft.is_deleted is True
