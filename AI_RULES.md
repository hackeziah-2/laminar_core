# AI Rules — Laminar Core Backend (FastAPI)

Use this document when adding or changing APIs, services, repositories, or imports. Follow existing patterns in `backend/app/` unless a better enterprise pattern is introduced here.

## Architecture (clean layers)

```
HTTP Request
    → api/v1/<resource>.py     # Routing, deps, HTTP status, thin handlers
    → services/                # Business rules, orchestration, transactions
    → repository/              # SQLAlchemy queries, persistence, no HTTP
    → models/                  # SQLAlchemy ORM
    → schemas/                 # Pydantic request/response/validation
```

**Rules**

| Layer | May import | Must not |
|-------|------------|----------|
| `api/` | deps, schemas, services, repository (rare: simple reads) | Raw SQL, pandas, business rules |
| `services/` | repository, models, schemas, core | `HTTPException`, FastAPI types |
| `repository/` | models, database helpers | FastAPI, Pydantic (except dict payloads) |
| `schemas/` | stdlib, pydantic | SQLAlchemy sessions |

Raise domain errors in services (`AppError` subclasses in `app/core/exceptions.py`). Map them to HTTP in the API layer only.

## New API checklist (copy for each feature)

1. **Module (RBAC)** — Name must exist in `modules` table (`backend/seeds/module.json`). Add constant in `app/core/rbac_modules.py`.
2. **Schemas** — `*Create`, `*Update`, `*Read` in `app/schemas/<entity>_schema.py`. Use validators for enums and empty strings.
3. **Model** — SQLAlchemy model with `TimestampMixin`, `SoftDeleteMixin`, `AuditMixin` when applicable.
4. **Repository** — `create_*`, `get_*`, `list_*_paged`, `update_*`, `soft_delete_*` in `app/repository/<entity>.py`. Pass `audit_account_id` and call `set_audit_fields()`.
5. **Service** — Only if logic spans multiple repos or non-trivial rules.
6. **Router** — `APIRouter(prefix="/api/v1/...", tags=[...])`. Register in `app/main.py`.
7. **Auth** — `Depends(get_current_active_account)` minimum; `Depends(require_permission(MODULE, "can_<action>"))` for protected writes.
8. **Audit** — `audit_account_id=current_account.id` on create/update/delete.
9. **Errors** — 404 not found, 400 validation/business, 403 permission, 422 Pydantic (automatic).
10. **OpenAPI** — `summary`, `description`, `response_model`, meaningful `Query`/`Form` descriptions.

### Router template

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_account, require_permission
from app.core.exceptions import NotFoundError
from app.core.rbac_modules import EXAMPLE_MODULE
from app.database import get_session
from app.models.account import AccountInformation
from app.repository.example import create_example, get_example
from app.schemas.example_schema import ExampleCreate, ExampleRead

router = APIRouter(prefix="/api/v1/example", tags=["example"])


@router.post("/", response_model=ExampleRead, status_code=status.HTTP_201_CREATED)
async def api_create(
    payload: ExampleCreate,
    session: AsyncSession = Depends(get_session),
    current_account: AccountInformation = Depends(
        require_permission(EXAMPLE_MODULE, "can_create")
    ),
):
    return await create_example(session, payload, audit_account_id=current_account.id)
```

### Repository template

```python
async def create_example(
    session: AsyncSession,
    data: ExampleCreate,
    *,
    audit_account_id: int | None = None,
) -> ExampleRead:
    obj = Example(**data.model_dump())
    session.add(obj)
    if audit_account_id is not None:
        await set_audit_fields(obj, audit_account_id, is_create=True)
    await session.commit()
    await session.refresh(obj)
    return ExampleRead.model_validate(obj)
```

## RBAC

- Dependency: `require_permission(module_name, action)` in `app/api/deps.py`.
- Actions: `can_read`, `can_write`, `can_create`, `can_update`, `can_delete`, `can_approve`.
- Module names are **display names** from seed data (e.g. `"General Information"`, `"Maintenance"`).
- Define module string once in `app/core/rbac_modules.py`.

## Audit fields

Models using `AuditMixin` have `created_by`, `updated_by`. After building or mutating an instance:

```python
await set_audit_fields(obj, audit_account_id, is_create=True)   # create
await set_audit_fields(obj, audit_account_id, is_create=False)  # update
```

## Soft delete

- Filter with `Model.is_deleted.is_(False)` (or `== False` to match existing code).
- Prefer `soft_delete_*` repository functions over hard deletes.

## Excel / CSV import

Use the shared stack (do not duplicate pandas/upsert logic in routers):

| Piece | Location |
|-------|----------|
| Config + orchestration | `app/services/excel_import_service.py` |
| File read / row build | `app/services/excel_import/` |
| DB upsert | `app/repository/excel_import.py` |
| Hooks (entity-specific) | `app/services/excel_import/hooks/` |
| API | `app/api/v1/data_import.py` |
| Target registry | `app/data_imports/` (`targets/<entity>.py` + `registry.py`) |
| Response schema | `app/schemas/data_import_schema.py` |

**Add a new import target**

1. Add Pydantic `*ImportSchema` with row validators.
2. Implement `ImportHook` in `app/services/excel_import/hooks/<entity>.py` (optional `preprocess_records`, `transform_row`, `after_upsert`).
3. Register hook in `hooks/registry.py`.
4. Add `ExcelImportTarget` in `app/data_imports/targets/<entity>.py` and call `register_import_target()` (set `key`, model, schema, `unique_fields`, `hook_key`, RBAC module, optional `resolve_context` for form → `inject_fields`).
5. No new API route required: clients use `POST /api/v1/excel-data/{target_key}/import` (see `GET /api/v1/excel-data/targets`). Optional legacy alias via `legacy_paths` on the target.
6. Pass `audit_account_id` via config (handled by `_run_registered_import` in the API layer).

### Readable variables (API, registry, spreadsheet)

Use these exact names in code, clients, and docs. Spreadsheet headers are matched **case-insensitively** unless a `column_mapping` alias is defined.

#### HTTP endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/excel-data/targets` | List registered import targets |
| `POST` | `/api/v1/excel-data/{target_key}/import` | Upload and import rows for one target |

#### Request (multipart)

| Variable | Where | Type | Description |
|----------|-------|------|-------------|
| `target_key` | URL path | string | Registry key (e.g. `aircraft`, `aircraft-technical-log`). Same value as `legacy_paths` when set. |
| `file` | form file | file | `.xlsx`, `.xls`, or `.csv` |
| `dry_run` | query | boolean | `true` = validate only; no DB write |
| `batch_id` | form field | string/int | **ATL only.** `atl_batch.id`; injected as `atl_batch_fk` |
| `aircraft_id` | form field | string/int | **ATL / LDND.** Injected as `aircraft_fk` |
| `registration` | form field | string | **ATL / LDND.** Lookup aircraft when `aircraft_id` omitted |

#### Response JSON (`ExcelImportResult`)

| Variable | Type | Values / meaning |
|----------|------|------------------|
| `status` | string | `success`, `failed`, `dry-run` |
| `inserted` | int | Rows that would be / were created |
| `updated` | int | Rows that would be / were updated |
| `errors` | array | Per-row issues |
| `errors[].row` | int | 1-based sheet row (row 1 = header) |
| `errors[].error` | string | Human-readable message |

#### Discovery JSON (`ImportTargetInfo` from `GET /targets`)

| Variable | Meaning |
|----------|---------|
| `key` | URL segment for `POST .../{key}/import` |
| `label` | Display name |
| `summary` | Short description |
| `rbac_module` | Module name for permission check (see `app/core/rbac_modules.py`) |
| `required_form_fields` | Multipart form keys required before import |
| `optional_form_fields` | Optional multipart form keys |
| `legacy_paths` | Alternate URL segments resolving to the same target |

#### Registry: `ExcelImportTarget` fields

| Field | Purpose |
|-------|---------|
| `key` | Stable slug in API path |
| `label` | Human-readable name |
| `summary` | Description for `/targets` |
| `model` | SQLAlchemy model class |
| `schema` | Pydantic `*ImportSchema` per row |
| `unique_fields` | Upsert match columns (DB field names) |
| `hook_key` | Key for `get_import_hook()` in `hooks/registry.py` |
| `rbac_module` | RBAC module display name |
| `rbac_action` | Permission flag (default `can_create`) |
| `column_mapping` | Optional map: **lowercase Excel header** → **schema field name** |
| `integrity_error_messages` | Optional map: DB constraint keyword → user message |
| `required_form_fields` | Documented form keys (enforced in `resolve_context`) |
| `optional_form_fields` | Documented optional form keys |
| `resolve_context` | Async `(session, form) → inject_fields` dict merged into each row |
| `legacy_paths` | Extra path aliases for `target_key` |

#### Runtime: `ExcelImportConfig` fields

| Field | Purpose |
|-------|---------|
| `model`, `schema`, `unique_fields`, `hook_key` | Same as registry |
| `dry_run` | Validate-only pass |
| `column_mapping` | Header aliases for this run |
| `integrity_error_messages` | DB error text mapping |
| `inject_fields` | Fixed columns set on every row (from `resolve_context`) |
| `audit_account_id` | Account id for `created_by` / `updated_by` |

#### Registered targets (current)

| `target_key` | `hook_key` | `rbac_module` | `unique_fields` | Form fields |
|--------------|------------|---------------|-----------------|-------------|
| `aircraft` | `aircraft` | `General Information` | `registration`, `msn` | _(none)_ |
| `aircraft-technical-log` | `aircraft_technical_log` | `Maintenance` | `aircraft_fk`, `sequence_no`, `atl_batch_fk` | **required:** `batch_id`; **one of:** `aircraft_id` or `registration` |
| `maintenance-ldnd` | `maintenance_ldnd` | `Maintenance` | `aircraft_fk`, `last_done_tach_done` | **one of:** `aircraft_id` or `registration` |
| `maintenance-ad` | `maintenance_ad` | `Maintenance` | `ad_number` (scoped by form `aircraft_fk`) | **one of:** `aircraft_id` or `registration` |
| `maintenance-ad-work-orders` | `maintenance_ad_work_orders` | `Maintenance` | `work_order_number` (scoped by form `ad_monitoring_fk`) | **one of:** `ad_monitoring_id` or `ad_monitoring_fk` |

#### Spreadsheet columns

- **Default:** column header (any case) must match a field on `*ImportSchema` (snake_case), e.g. `registration`, `manufacturer`, `msn`.
- **Aircraft** (`AircraftImportSchema`): required headers include `registration`, `manufacturer`, `model`, `msn`, `base`, `ownership`; optional include `report_description`, `model_year`, `status`, engine/propeller fields, etc. (see `app/schemas/aircraft_schema.py`).
- **ATL:** many headers use friendly labels; aliases live in `app/constants/atl_excel_import.py` as `ATL_EXCEL_COLUMN_MAPPING` (keys are lowercase labels, values are schema fields such as `sequence_no`, `nature_of_flight`, `origin_station`). `aircraft_fk` and `atl_batch_fk` come from form `inject_fields`, not the sheet.
- **LDND** (`maintenance-ldnd`): friendly headers in `app/constants/ldnd_excel_import.py` as `LDND_EXCEL_COLUMN_MAPPING` (`Inspection Type`, `Unit`, tach columns, performed dates). `aircraft_fk` comes from form `inject_fields`. Dates accept `17-Aug-23`, `8/17/2023`, Excel serials, and ISO values.
- **AD** (`maintenance-ad`): friendly headers in `app/constants/ad_excel_import.py` as `AD_EXCEL_COLUMN_MAPPING` (`AD Number`, `Subject`, `Inspection Interval`, `Date of Effectivity` or `Date of Effectivity or Compliance Date` → `compli_date`). `aircraft_fk` comes from form `inject_fields`. Dates accept `6/5/2023`, `23-Jul-23`, Excel serials, and ISO values.
- **AD work orders** (`maintenance-ad-work-orders`): friendly headers in `app/constants/ad_work_order_excel_import.py` as `AD_WORK_ORDER_EXCEL_COLUMN_MAPPING` (`WO Number`, tach/ACTT columns, `Last Done Date`, `Atl Ref`). `ad_monitoring_fk` comes from form `inject_fields` (`ad_monitoring_id` or `ad_monitoring_fk`). Dates accept `6/5/2023`, `23-Jul-23`, Excel serials, and ISO values.

#### Hook registry keys (`hook_key`)

| `hook_key` | Class | File |
|------------|-------|------|
| `aircraft` | `AircraftImportHook` | `hooks/aircraft.py` |
| `aircraft_technical_log` | `AtlImportHook` | `hooks/atl.py` |
| _(any other)_ | `ImportHook` (no-op defaults) | `hooks/base.py` |

#### RBAC module constants (`app/core/rbac_modules.py`)

Use these for `rbac_module` on new targets (must match `modules.name` in the DB):

`DASHBOARD_MODULE`, `DAILY_UPDATE_MODULE`, `GENERAL_INFORMATION_MODULE`, `LOGBOOK_MODULE`, `MAINTENANCE_MODULE`, `OPERATION_MODULE`, `REGULATORY_COMPLIANCE_MODULE`, `SYSTEM_SETTINGS_MODULE`

(String values: `"Dashboard"`, `"Daily Update"`, `"General Information"`, `"Logbook"`, `"Maintenance"`, `"Operation"`, `"Regulatory Compliance"`, `"System Settings"`.)

## Error handling

- `app/core/exceptions.py`: `AppError`, `NotFoundError`, `ValidationError`, `ConflictError`, `PermissionDeniedError`.
- Services raise `AppError` subclasses; API catches and maps to `HTTPException`.
- For imports, row errors are collected in `errors[]` with `row` (1-based sheet row, header = row 1) and `error` message.

## Pydantic

- Prefer Pydantic v2: `model_dump()`, `model_validate()`. Legacy `dict()` / `from_orm()` remain in older code; match the file you edit.
- Import schemas: strict required fields, `pre` validators for Excel quirks (empty cells, enum aliases).

## Testing Rules

Always include tests for enterprise-level FastAPI features.

### Stack

Use:

- `pytest`
- `pytest-asyncio` (`asyncio_mode = auto` in `pytest.ini`)
- `httpx.AsyncClient` with `httpx.ASGITransport(app=app)` for **new** API tests
- In-memory test database via `conftest.py` (`sqlite+aiosqlite:///:memory:` by default)
- `tests/factories/` for reusable RBAC seeds, CSV/Excel bytes, and model payloads

Legacy tests may use sync `fastapi.testclient.TestClient`; do not rewrite them unless touching that file. Prefer `AsyncClient` for new `tests/api/` files.

### Test coverage requirements

For every feature, add tests covering as many of these as apply:

| # | Case | Typical assertion |
|---|------|-------------------|
| 1 | Success | `200`/`201`/`202`, correct response body |
| 2 | Validation error | `400`/`422`, clear `detail` |
| 3 | Not found | `404` when parent FK missing |
| 4 | Permission / RBAC | `403` when role lacks `can_*` on module |
| 5 | Unauthorized | `401` without `Authorization: Bearer` |
| 6 | Duplicate / conflict | `400` or row-level `errors[]` on import |
| 7 | Soft delete | Deleted row excluded; restore on upsert if designed |
| 8 | Pagination | `page`, `limit`, `total`, `pages` on list endpoints |
| 9 | Transaction behavior | `dry_run` / rollback leaves DB unchanged |
| 10 | Edge cases | Empty file, invalid extension, missing required form fields |

Not every endpoint needs all ten (e.g. imports skip pagination). Document skipped cases in a short comment if non-obvious.

### Testing architecture

```text
backend/tests/
  conftest.py              # db session, AsyncClient, auth overrides
  factories/
    __init__.py
    rbac.py                # seed Module, Role, RolePermission, Account
    import_files.py        # CSV/Excel bytes for uploads
  api/
    test_<resource>_api.py # HTTP: auth, RBAC, status codes
  services/
    test_<resource>_service.py
  repositories/
    test_<resource>_repository.py
```

**Layer rules**

- `api/` — HTTP only; use `async_client` + auth fixtures; mock nothing except via `app.dependency_overrides`.
- `services/` — `db_session` fixture; no FastAPI client.
- `repositories/` — `db_session`; assert SQLAlchemy state, commits, soft deletes.
- `factories/` — no assertions; return IDs, bytes, or dicts.

### conftest patterns

- `db_session` — async session, tables created/dropped per test.
- `async_client` — `httpx.AsyncClient` + `get_session` override (see `tests/conftest.py`).
- `client` — legacy sync `TestClient` (existing tests).
- Auth fixtures — seed real `Module` + `RolePermission` + `AccountInformation`, then override `get_current_active_account` with the seeded account (see `client_with_regulatory_compliance_auth`).

### Factory example

```python
# tests/factories/rbac.py
async def seed_account_with_permissions(
    session, *, module_name: str, can_create: bool = True, ...
) -> int:
    """Return account_information.id with the given module permission."""
```

### API test example

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_example_success(
    async_client: AsyncClient,
    client_with_example_auth,  # if RBAC required
):
    response = await async_client.post(
        "/api/v1/example/",
        json={"name": "Test"},
        headers={"Authorization": f"Bearer {token}"},  # or use dependency override fixture
    )
    assert response.status_code == 201
```

### Running tests

```bash
cd backend
pytest                          # all tests
pytest tests/api/ -v            # API layer only
pytest tests/services/ -v
pytest -k "data_import" -v
pytest --cov=app --cov-report=term-missing
```

See `backend/tests/README.md` for Docker and coverage details.

### New feature checklist (testing)

1. Add factories if payloads or RBAC setup are non-trivial.
2. Add `repositories/test_*` for persistence rules.
3. Add `services/test_*` for orchestration and transaction boundaries.
4. Add `api/test_*` for status codes, auth, and RBAC.
5. Run `pytest` before opening a PR.

## Do not

- Ship new features without tests for applicable coverage cases (see **Testing Rules**).
- Put business logic in routers or `main.py`.
- Commit secrets (`.env`, keys).
- Skip `audit_account_id` on mutating endpoints.
- Use `model.__name__` string checks in new code — use `ImportHook` registration instead.
- Return raw exception strings to clients on 500 — log detail server-side; return safe messages.

## File map (reference)

```
backend/app/
  api/deps.py              # auth, require_permission
  api/v1/*.py              # routers
  core/exceptions.py
  core/rbac_modules.py
  database.py              # session, mixins, set_audit_fields
  models/
  repository/
  schemas/
  services/
  constants/               # column mappings, enums
```

When in doubt, mirror `app/api/v1/atl_batch.py` + `app/repository/atl_batch.py` for CRUD, or `app/api/v1/data_import.py` + `app/services/excel_import_service.py` for imports.
