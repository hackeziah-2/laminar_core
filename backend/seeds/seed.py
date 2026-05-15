import asyncio
import json
from datetime import date
from pathlib import Path

import httpx
from httpx import ASGITransport
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.main import app
from app.models import Role, Module
from app.models.role_permission import RolePermission

SEED_DIR = Path(__file__).resolve().parent
# Seed JSON processing order: roles depend on modules; account_information API needs committed roles.
SEED_DB_JSON_FILES = ("module.json", "roles.json")

MODEL_MAP = {
    "roles": Role,
    "module": Module,
}

# Keys parsed as date when loading account_information JSON
ACCOUNT_DATE_KEYS = ("auth_initial_doi",)


def _parse_date_value(v):
    if v is None or isinstance(v, date):
        return v
    if isinstance(v, str):
        return date.fromisoformat(v)
    return v


def _coerce_account_information_record(record):
    out = dict(record)
    for key in ACCOUNT_DATE_KEYS:
        if key in out and out[key] is not None:
            out[key] = _parse_date_value(out[key])
    return out


def _account_record_to_json(record):
    """Build JSON body for POST /api/v1/account-information/ (dates as ISO strings)."""
    payload = {}
    for k, v in record.items():
        if isinstance(v, date):
            payload[k] = v.isoformat()
        else:
            payload[k] = v
    return payload


def _perm_flags(p):
    read = bool(p.get("read", False))
    create = bool(p.get("create", False))
    update = bool(p.get("update", False))
    delete = bool(p.get("delete", False))
    approve = bool(p.get("approve", False))
    return read, create, update, delete, approve, create or update or delete


async def _seed_roles(db, records):
    """Upsert roles and role_permissions from JSON (module names must exist in modules)."""
    for raw in records:
        rec = dict(raw)
        permissions = rec.pop("permissions", [])
        name = rec["name"]
        description = rec.get("description")

        result = await db.execute(
            select(Role).where(Role.name == name, Role.is_deleted.is_(False))
        )
        role = result.scalar_one_or_none()
        if not role:
            role = Role(name=name, description=description)
            db.add(role)
            await db.flush()
        elif description is not None:
            role.description = description

        existing_rp = await db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )
        by_module_id = {rp.module_id: rp for rp in existing_rp.scalars().all()}
        wanted_module_ids = set()

        for p in permissions:
            mname = p["module"]
            mod_result = await db.execute(
                select(Module).where(Module.name == mname, Module.is_deleted.is_(False))
            )
            module = mod_result.scalar_one_or_none()
            if not module:
                print(f"  Skip permission: module {mname!r} not found for role {name!r}")
                continue

            wanted_module_ids.add(module.id)
            read, create, update, delete, approve, can_write = _perm_flags(p)
            rp = by_module_id.get(module.id)
            if rp:
                rp.is_deleted = False
                rp.can_read = read
                rp.can_write = can_write
                rp.can_create = create
                rp.can_update = update
                rp.can_delete = delete
                rp.can_approve = approve
                db.add(rp)
            else:
                rp = RolePermission(
                    role_id=role.id,
                    module_id=module.id,
                    can_read=read,
                    can_write=can_write,
                    can_create=create,
                    can_update=update,
                    can_delete=delete,
                    can_approve=approve,
                )
                db.add(rp)
                by_module_id[module.id] = rp

        for mid, rp in by_module_id.items():
            if mid not in wanted_module_ids and not rp.is_deleted:
                rp.soft_delete()
                db.add(rp)


async def _seed_db_table(db, table_name, model, records):
    if table_name == "roles":
        await _seed_roles(db, records)
        return
    for record in records:
        filter_record = dict(record)
        conditions = [getattr(model, k) == v for k, v in filter_record.items()]
        stmt = select(model).where(*conditions)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(model(**record))


def _asgi_transport():
    """ASGITransport with lifespan when supported (runs FastAPI startup on same loop)."""
    try:
        return ASGITransport(app=app, lifespan="on")
    except TypeError:
        return ASGITransport(app=app)


async def _seed_account_information_via_api(records):
    """POST each row to /api/v1/account-information/ (no auth), same stack as production.

    Uses async httpx + ASGITransport so asyncpg runs on the same event loop as
    ``asyncio.run(seed())``. Starlette ``TestClient`` uses a different loop and breaks.
    """
    transport = _asgi_transport()
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://seed.local",
    ) as client:
        for raw in records:
            record = _coerce_account_information_record(raw)
            payload = _account_record_to_json(record)
            resp = await client.post("/api/v1/account-information/", json=payload)
            if resp.status_code == 201:
                continue
            if resp.status_code == 400:
                try:
                    body = resp.json()
                except Exception:
                    body = {}
                detail = body.get("detail", "")
                if "already exists" in str(detail).lower():
                    print(
                        f"  Skip account_information (duplicate username/email): "
                        f"{payload.get('username')!r}"
                    )
                    continue
            resp.raise_for_status()


async def seed():
    async with AsyncSessionLocal() as db:
        for fname in SEED_DB_JSON_FILES:
            path = SEED_DIR / fname
            if not path.is_file():
                print(f"Missing seed file (skipped): {path}")
                continue
            table_name = fname.replace(".json", "")
            model = MODEL_MAP.get(table_name)
            if not model:
                print(f"No model mapping for {table_name}")
                continue
            with open(path) as f:
                records = json.load(f)
            await _seed_db_table(db, table_name, model, records)
            print(f"Seeded {table_name}")
        await db.commit()

    acc_path = SEED_DIR / "account_information.json"
    if acc_path.is_file():
        with open(acc_path) as f:
            acc_records = json.load(f)
        await _seed_account_information_via_api(acc_records)
        print("Seeded account_information (POST /api/v1/account-information/)")
    else:
        print(f"Missing seed file (skipped): {acc_path}")


if __name__ == "__main__":
    asyncio.run(seed())
