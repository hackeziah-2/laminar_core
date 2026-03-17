import asyncio
import os
import json
from datetime import date
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Role, Module, AccountInformation


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