import asyncio
import os
import json
from datetime import date
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Role, Module, AccountInformation
from app.models.role_permission import RolePermission


SEED_FOLDER = "seeds"
MODEL_MAP = {
    "roles": Role,
    "module": Module,
    "account_information": AccountInformation
}

# Keys that should be parsed as date when loading from JSON (for account_information)
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


async def seed():
    async with AsyncSessionLocal() as db:
        for file in os.listdir(SEED_FOLDER):
            if not file.endswith(".json"):
                continue
            table_name = file.replace(".json", "")
            model = MODEL_MAP.get(table_name)
            if not model:
                print(f"No model mapping for {table_name}")
                continue
            path = os.path.join(SEED_FOLDER, file)
            with open(path) as f:
                records = json.load(f)
            if table_name == "roles":
                await _seed_roles(db, records)
                print(f"Seeded {table_name}")
                continue
            for record in records:
                if table_name == "account_information":
                    record = _coerce_account_information_record(record)
                # Build WHERE clause from record (exclude password for lookup)
                filter_record = {k: v for k, v in record.items() if k != "password"}
                conditions = [getattr(model, k) == v for k, v in filter_record.items()]
                stmt = select(model).where(*conditions)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()
                if not existing:
                    db.add(model(**record))
            print(f"Seeded {table_name}")
        await db.commit()

if __name__ == "__main__":
    asyncio.run(seed())