from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, root_validator


# ---------- Component Record Schemas (one-to-many with Engine/Airframe/Avionics logbooks) ----------
class ComponentRecordBase(BaseModel):
    """Shared fields for engine/airframe/avionics component records."""
    qty: float
    unit: str = Field(..., max_length=20)
    nomenclature: str = Field(..., max_length=255)
    removed_part_no: Optional[str] = Field(None, max_length=100, alias="removedPartNo")
    removed_serial_no: Optional[str] = Field(None, max_length=100, alias="removedSerialNo")
    installed_part_no: Optional[str] = Field(None, max_length=100, alias="installedPartNo")
    installed_serial_no: Optional[str] = Field(None, max_length=100, alias="installedSerialNo")
    ata_chapter: Optional[str] = Field(None, max_length=50, alias="ataChapter")

    class Config:
        allow_population_by_field_name = True


class ComponentRecordCreate(ComponentRecordBase):
    """Payload for creating a component record (nested in logbook create/update)."""
    id: Optional[int] = None


# ---------- Mechanic Detail Schema (for nested mechanic info) ----------
class MechanicDetail(BaseModel):
    """Mechanic details for logbook entries."""
    id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    license_no: Optional[str] = None

    class Config:
        orm_mode = True


# ---------- Engine Logbook Schemas ----------
class EngineLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    engine_tsn: Optional[float] = None
    sequence_no: str = Field(..., max_length=50)
    tach_time: Optional[float] = None
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)


class EngineLogbookCreate(EngineLogbookBase):
    component_parts: Optional[List[ComponentRecordCreate]] = Field(None, alias="componentParts")

    class Config:
        allow_population_by_field_name = True


class EngineLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    engine_tsn: Optional[float] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    tach_time: Optional[float] = None
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)
    component_parts: Optional[List[ComponentRecordCreate]] = Field(None, alias="componentParts")

    class Config:
        allow_population_by_field_name = True


class EngineComponentRecordRead(ComponentRecordBase):
    id: int
    engine_log_fk: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class EngineLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    engine_tsn: Optional[float] = None
    sequence_no: str
    tach_time: Optional[float] = None
    engine_tso: Optional[float] = None
    engine_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    web_link: Optional[str] = None
    component_parts: Optional[List[EngineComponentRecordRead]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @root_validator(pre=True)
    def orm_to_component_parts(cls, v: Any) -> Any:
        if isinstance(v, dict):
            if "component_parts" not in v and "engine_component_parts" in v:
                v = dict(v)
                v["component_parts"] = v.get("engine_component_parts") or []
            return v

        orm_state = getattr(v, "__dict__", None)
        if orm_state is not None and (
            "engine_component_parts" in orm_state or "mechanic" in orm_state
        ):
            return {
                "id": orm_state.get("id"),
                "aircraft_fk": orm_state.get("aircraft_fk"),
                "date": orm_state.get("date"),
                "engine_tsn": orm_state.get("engine_tsn"),
                "sequence_no": orm_state.get("sequence_no"),
                "tach_time": orm_state.get("tach_time"),
                "engine_tso": orm_state.get("engine_tso"),
                "engine_tbo": orm_state.get("engine_tbo"),
                "description": orm_state.get("description"),
                "mechanic_fk": orm_state.get("mechanic_fk"),
                "mechanic": orm_state.get("mechanic"),
                "signature": orm_state.get("signature"),
                "upload_file": orm_state.get("upload_file"),
                "web_link": orm_state.get("web_link"),
                "created_at": orm_state.get("created_at"),
                "updated_at": orm_state.get("updated_at"),
                "component_parts": orm_state.get("engine_component_parts") or [],
            }
        return v

    class Config:
        orm_mode = True


# ---------- Airframe Logbook Schemas ----------
class AirframeLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    sequence_no: str = Field(..., max_length=50)
    tach_time: Optional[float] = None
    airframe_time: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)


class AirframeLogbookCreate(AirframeLogbookBase):
    component_parts: Optional[List[ComponentRecordCreate]] = Field(None, alias="componentParts")

    class Config:
        allow_population_by_field_name = True


class AirframeLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    tach_time: Optional[float] = None
    airframe_time: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)
    component_parts: Optional[List[ComponentRecordCreate]] = Field(None, alias="componentParts")

    class Config:
        allow_population_by_field_name = True


class AirframeComponentRecordRead(ComponentRecordBase):
    id: int
    airframe_log_fk: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AirframeLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    sequence_no: str
    tach_time: Optional[float] = None
    airframe_time: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    web_link: Optional[str] = None
    component_parts: Optional[List[AirframeComponentRecordRead]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @root_validator(pre=True)
    def orm_to_component_parts(cls, v: Any) -> Any:
        if isinstance(v, dict):
            if "component_parts" not in v and "airframe_component_parts" in v:
                v = dict(v)
                v["component_parts"] = v.get("airframe_component_parts") or []
            return v

        orm_state = getattr(v, "__dict__", None)
        if orm_state is not None and (
            "airframe_component_parts" in orm_state or "mechanic" in orm_state
        ):
            return {
                "id": orm_state.get("id"),
                "aircraft_fk": orm_state.get("aircraft_fk"),
                "date": orm_state.get("date"),
                "sequence_no": orm_state.get("sequence_no"),
                "tach_time": orm_state.get("tach_time"),
                "airframe_time": orm_state.get("airframe_time"),
                "description": orm_state.get("description"),
                "mechanic_fk": orm_state.get("mechanic_fk"),
                "mechanic": orm_state.get("mechanic"),
                "signature": orm_state.get("signature"),
                "upload_file": orm_state.get("upload_file"),
                "web_link": orm_state.get("web_link"),
                "created_at": orm_state.get("created_at"),
                "updated_at": orm_state.get("updated_at"),
                "component_parts": orm_state.get("airframe_component_parts") or [],
            }
        return v

    class Config:
        orm_mode = True


# ---------- Avionics Logbook Schemas ----------
class AvionicsLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    airframe_tsn: Optional[float] = None
    sequence_no: str = Field(..., max_length=50)
    component: Optional[str] = Field(None, max_length=255)
    part_no: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)


class AvionicsLogbookCreate(AvionicsLogbookBase):
    component_parts: Optional[List[ComponentRecordCreate]] = Field(None, alias="componentParts")

    class Config:
        allow_population_by_field_name = True


class AvionicsLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    airframe_tsn: Optional[float] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    component: Optional[str] = Field(None, max_length=255)
    part_no: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)
    component_parts: Optional[List[ComponentRecordCreate]] = Field(None, alias="componentParts")

    class Config:
        allow_population_by_field_name = True


class AvionicsComponentRecordRead(ComponentRecordBase):
    id: int
    avionics_log_fk: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AvionicsLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    airframe_tsn: Optional[float] = None
    sequence_no: str
    component: Optional[str] = None
    part_no: Optional[str] = None
    serial_no: Optional[str] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    web_link: Optional[str] = None
    component_parts: Optional[List[AvionicsComponentRecordRead]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @root_validator(pre=True)
    def orm_to_component_parts(cls, v: Any) -> Any:
        if isinstance(v, dict):
            if "component_parts" not in v and "avionics_component_parts" in v:
                v = dict(v)
                v["component_parts"] = v.get("avionics_component_parts") or []
            return v

        orm_state = getattr(v, "__dict__", None)
        if orm_state is not None and (
            "avionics_component_parts" in orm_state or "mechanic" in orm_state
        ):
            data = {
                "id": orm_state.get("id"),
                "aircraft_fk": orm_state.get("aircraft_fk"),
                "date": orm_state.get("date"),
                "airframe_tsn": orm_state.get("airframe_tsn"),
                "sequence_no": orm_state.get("sequence_no"),
                "component": orm_state.get("component"),
                "part_no": orm_state.get("part_no"),
                "serial_no": orm_state.get("serial_no"),
                "description": orm_state.get("description"),
                "mechanic_fk": orm_state.get("mechanic_fk"),
                "mechanic": orm_state.get("mechanic"),
                "signature": orm_state.get("signature"),
                "upload_file": orm_state.get("upload_file"),
                "web_link": orm_state.get("web_link"),
                "created_at": orm_state.get("created_at"),
                "updated_at": orm_state.get("updated_at"),
                "component_parts": orm_state.get("avionics_component_parts") or [],
            }
            return data
        return v

    class Config:
        orm_mode = True


# ---------- Propeller Logbook Schemas ----------
class PropellerLogbookBase(BaseModel):
    aircraft_fk: int
    date: date
    propeller_tsn: Optional[float] = None
    sequence_no: str = Field(..., max_length=50)
    tach_time: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)


class PropellerLogbookCreate(PropellerLogbookBase):
    pass


class PropellerLogbookUpdate(BaseModel):
    aircraft_fk: Optional[int] = None
    date: Optional[date] = None
    propeller_tsn: Optional[float] = None
    sequence_no: Optional[str] = Field(None, max_length=50)
    tach_time: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    signature: Optional[str] = Field(None, max_length=255)
    upload_file: Optional[str] = Field(None, max_length=500)
    web_link: Optional[str] = Field(None, max_length=2048)


class PropellerLogbookRead(BaseModel):
    id: int
    aircraft_fk: int
    date: date
    propeller_tsn: Optional[float] = None
    sequence_no: str
    tach_time: Optional[float] = None
    propeller_tso: Optional[float] = None
    propeller_tbo: Optional[float] = None
    description: Optional[str] = None
    mechanic_fk: Optional[int] = None
    mechanic: Optional[MechanicDetail] = None
    signature: Optional[str] = None
    upload_file: Optional[str] = None
    web_link: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
