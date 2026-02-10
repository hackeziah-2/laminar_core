import json
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status, Form, File, UploadFile, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import ad_monitoring_schema
from app.repository.ad_monitoring import (
    get_ad_monitoring,
    get_ad_monitoring_by_aircraft,
    list_ad_monitoring,
    create_ad_monitoring,
    update_ad_monitoring,
    soft_delete_ad_monitoring,
    soft_delete_ad_monitoring_by_aircraft,
    get_work_order_ad_monitoring,
    get_work_order_ad_monitoring_by_ad,
    list_work_order_ad_monitoring,
    create_work_order_ad_monitoring,
    update_work_order_ad_monitoring,
    soft_delete_work_order_ad_monitoring,
    soft_delete_work_order_ad_monitoring_by_ad,
)
from app.repository.aircraft import get_aircraft
from app.database import get_session

# ---------- Dependencies ----------
async def get_ad_monitoring_scoped_to_aircraft(
    aircraft_fk: int,
    ad_monitoring_fk: int,
    session: AsyncSession = Depends(get_session),
):
    """Resolve AD monitoring by ID scoped to aircraft; raise 404 if not found."""
    ad = await get_ad_monitoring_by_aircraft(session, ad_monitoring_fk, aircraft_fk)
    if not ad:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return ad

# ---------- ADMonitoring routers ----------
router = APIRouter(
    prefix="/api/v1/ad-monitoring",
    tags=["ad-monitoring"],
)
router_aircraft_scoped = APIRouter(
    prefix="/api/v1/aircraft",
    tags=["ad-monitoring"],
)

# ---------- WorkOrderADMonitoring routers ----------
router_work_order = APIRouter(
    prefix="/api/v1/work-order-ad-monitoring",
    tags=["work-order-ad-monitoring"],
)


# ========== ADMonitoring: global endpoints ==========
@router.get("/paged")
async def api_list_ad_monitoring_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    aircraft_fk: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_ad_monitoring(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_fk,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [ad_monitoring_schema.ADMonitoringRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/{ad_id}", response_model=ad_monitoring_schema.ADMonitoringRead)
async def api_get_ad_monitoring(
    ad_id: int,
    session: AsyncSession = Depends(get_session),
):
    obj = await get_ad_monitoring(session, ad_id)
    if not obj:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return obj


@router.post(
    "/",
    response_model=ad_monitoring_schema.ADMonitoringRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_ad_monitoring(
    request: Request,
    json_data: Optional[str] = Form(None),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    try:
        if json_data is not None:
            parsed = json.loads(json_data)
        else:
            parsed = await request.json()
        data = ad_monitoring_schema.ADMonitoringCreate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    return await create_ad_monitoring(session, data, upload_file)


@router.put("/{ad_id}", response_model=ad_monitoring_schema.ADMonitoringRead)
async def api_update_ad_monitoring(
    ad_id: int,
    request: Request,
    json_data: Optional[str] = Form(None),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    try:
        if json_data is not None:
            parsed = json.loads(json_data)
        else:
            parsed = await request.json()
        data = ad_monitoring_schema.ADMonitoringUpdate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    updated = await update_ad_monitoring(session, ad_id, data, upload_file)
    if not updated:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return updated


@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_ad_monitoring(
    ad_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await soft_delete_ad_monitoring(session, ad_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return None


# ========== ADMonitoring: aircraft-scoped CRUD (api/v1/aircraft/{aircraft_fk}/ad_monitoring/) ==========
@router_aircraft_scoped.get("/{aircraft_fk}/ad_monitoring/paged")
async def api_list_ad_monitoring_by_aircraft_paged(
    aircraft_fk: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    aircraft = await get_aircraft(session, aircraft_fk)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    offset = (page - 1) * limit
    items, total = await list_ad_monitoring(
        session=session,
        limit=limit,
        offset=offset,
        aircraft_fk=aircraft_fk,
        search=search,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [ad_monitoring_schema.ADMonitoringRead.from_orm(i) for i in items],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_aircraft_scoped.get(
    "/{aircraft_fk}/ad_monitoring/{ad_id}",
    response_model=ad_monitoring_schema.ADMonitoringRead,
)
async def api_get_ad_monitoring_by_aircraft(
    aircraft_fk: int,
    ad_id: int,
    session: AsyncSession = Depends(get_session),
):
    obj = await get_ad_monitoring_by_aircraft(session, ad_id, aircraft_fk)
    if not obj:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return obj


@router_aircraft_scoped.post(
    "/{aircraft_fk}/ad_monitoring/",
    response_model=ad_monitoring_schema.ADMonitoringRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_ad_monitoring_by_aircraft(
    aircraft_fk: int,
    request: Request,
    json_data: Optional[str] = Form(None),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    aircraft = await get_aircraft(session, aircraft_fk)
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    try:
        if json_data is not None:
            parsed = json.loads(json_data)
        else:
            parsed = await request.json()
        parsed["aircraft_fk"] = aircraft_fk
        create_data = ad_monitoring_schema.ADMonitoringCreate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    return await create_ad_monitoring(session, create_data, upload_file)


@router_aircraft_scoped.put(
    "/{aircraft_fk}/ad_monitoring/{ad_id}",
    response_model=ad_monitoring_schema.ADMonitoringRead,
)
async def api_update_ad_monitoring_by_aircraft(
    aircraft_fk: int,
    ad_id: int,
    request: Request,
    json_data: Optional[str] = Form(None),
    upload_file: UploadFile = File(None),
    session: AsyncSession = Depends(get_session),
):
    existing = await get_ad_monitoring_by_aircraft(session, ad_id, aircraft_fk)
    if not existing:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    try:
        if json_data is not None:
            parsed = json.loads(json_data)
        else:
            parsed = await request.json()
        data = ad_monitoring_schema.ADMonitoringUpdate(**parsed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    updated = await update_ad_monitoring(session, ad_id, data, upload_file)
    if not updated:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return updated


@router_aircraft_scoped.delete(
    "/{aircraft_fk}/ad_monitoring/{ad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def api_delete_ad_monitoring_by_aircraft(
    aircraft_fk: int,
    ad_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await soft_delete_ad_monitoring_by_aircraft(
        session, ad_id, aircraft_fk
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="ADMonitoring not found")
    return None


# ========== WorkOrderADMonitoring: aircraft-scoped CRUD ==========
@router_aircraft_scoped.get(
    "/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/paged",
    tags=["work-order-ad-monitoring"],
)
async def api_list_work_orders_by_aircraft_ad_paged(
    aircraft_fk: int,
    ad_monitoring_fk: int,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_ad_monitoring_scoped_to_aircraft),
):
    offset = (page - 1) * limit
    items, total = await list_work_order_ad_monitoring(
        session=session,
        limit=limit,
        offset=offset,
        ad_monitoring_fk=ad_monitoring_fk,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [
            ad_monitoring_schema.WorkOrderADMonitoringRead.from_orm(i)
            for i in items
        ],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_aircraft_scoped.get(
    "/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/{work_order_id}",
    response_model=ad_monitoring_schema.WorkOrderADMonitoringRead,
    tags=["work-order-ad-monitoring"],
)
async def api_get_work_order_by_aircraft_ad(
    aircraft_fk: int,
    ad_monitoring_fk: int,
    work_order_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_ad_monitoring_scoped_to_aircraft),
):
    obj = await get_work_order_ad_monitoring_by_ad(
        session, work_order_id, ad_monitoring_fk
    )
    if not obj:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    return obj


@router_aircraft_scoped.post(
    "/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/",
    response_model=ad_monitoring_schema.WorkOrderADMonitoringRead,
    status_code=status.HTTP_201_CREATED,
    tags=["work-order-ad-monitoring"],
)
async def api_create_work_order_by_aircraft_ad(
    aircraft_fk: int,
    ad_monitoring_fk: int,
    data: ad_monitoring_schema.WorkOrderADMonitoringCreate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_ad_monitoring_scoped_to_aircraft),
):
    create_data = ad_monitoring_schema.WorkOrderADMonitoringCreate(
        **{**data.dict(), "ad_monitoring_fk": ad_monitoring_fk}
    )
    return await create_work_order_ad_monitoring(session, create_data)


@router_aircraft_scoped.put(
    "/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/{work_order_id}",
    response_model=ad_monitoring_schema.WorkOrderADMonitoringRead,
    tags=["work-order-ad-monitoring"],
)
async def api_update_work_order_by_aircraft_ad(
    aircraft_fk: int,
    ad_monitoring_fk: int,
    work_order_id: int,
    data: ad_monitoring_schema.WorkOrderADMonitoringUpdate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_ad_monitoring_scoped_to_aircraft),
):
    existing = await get_work_order_ad_monitoring_by_ad(
        session, work_order_id, ad_monitoring_fk
    )
    if not existing:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    updated = await update_work_order_ad_monitoring(
        session, work_order_id, data
    )
    if not updated:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    return updated


@router_aircraft_scoped.delete(
    "/{aircraft_fk}/ad_monitoring/{ad_monitoring_fk}/work-order-ad-monitoring/{work_order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["work-order-ad-monitoring"],
)
async def api_delete_work_order_by_aircraft_ad(
    aircraft_fk: int,
    ad_monitoring_fk: int,
    work_order_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(get_ad_monitoring_scoped_to_aircraft),
):
    deleted = await soft_delete_work_order_ad_monitoring_by_ad(
        session, work_order_id, ad_monitoring_fk
    )
    if not deleted:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    return None


# ========== WorkOrderADMonitoring: global endpoints ==========
@router_work_order.get("/paged")
async def api_list_work_order_ad_monitoring_paged(
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    ad_monitoring_fk: Optional[int] = Query(None),
    sort: Optional[str] = Query(""),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * limit
    items, total = await list_work_order_ad_monitoring(
        session=session,
        limit=limit,
        offset=offset,
        ad_monitoring_fk=ad_monitoring_fk,
        sort=sort,
    )
    pages = ceil(total / limit) if total else 0
    return {
        "items": [
            ad_monitoring_schema.WorkOrderADMonitoringRead.from_orm(i)
            for i in items
        ],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router_work_order.get(
    "/{work_order_id}",
    response_model=ad_monitoring_schema.WorkOrderADMonitoringRead,
)
async def api_get_work_order_ad_monitoring(
    work_order_id: int,
    session: AsyncSession = Depends(get_session),
):
    obj = await get_work_order_ad_monitoring(session, work_order_id)
    if not obj:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    return obj


@router_work_order.post(
    "/",
    response_model=ad_monitoring_schema.WorkOrderADMonitoringRead,
    status_code=status.HTTP_201_CREATED,
)
async def api_create_work_order_ad_monitoring(
    data: ad_monitoring_schema.WorkOrderADMonitoringCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_work_order_ad_monitoring(session, data)


@router_work_order.put(
    "/{work_order_id}",
    response_model=ad_monitoring_schema.WorkOrderADMonitoringRead,
)
async def api_update_work_order_ad_monitoring(
    work_order_id: int,
    data: ad_monitoring_schema.WorkOrderADMonitoringUpdate,
    session: AsyncSession = Depends(get_session),
):
    updated = await update_work_order_ad_monitoring(
        session, work_order_id, data
    )
    if not updated:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    return updated


@router_work_order.delete(
    "/{work_order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def api_delete_work_order_ad_monitoring(
    work_order_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await soft_delete_work_order_ad_monitoring(
        session, work_order_id
    )
    if not deleted:
        raise HTTPException(
            status_code=404, detail="WorkOrderADMonitoring not found"
        )
    return None


