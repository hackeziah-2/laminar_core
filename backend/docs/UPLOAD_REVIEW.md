# Upload review and verification

Date: 2026-09-21. Baseline commit: `5b2d22aa1cd681cb853650aebbaa8fc46fdd8e5c`. Changes are uncommitted; nothing was deployed.

## Outcome

The generic upload and shared attachment storage now have bounded worker copies, cancellation-safe cleanup, no-clobber publication, content checks, and durable file/directory synchronization. The generic route authenticates before consuming the body, records only metadata, and deduplicates by account + module + SHA-256. Its URL, multipart `file` field, optional `name` query parameter, response keys and HTTP 201 remain unchanged.

**There is no demonstrated overall upload speedup.** The final durability checks increased multipart benchmark latency. Peak Python allocations under eight concurrent transfers decreased, and the CSV delimiter probe stopped allocating an entire file. These are separately measured improvements, not evidence that the full secured endpoint is faster or uses less total process memory than the old endpoint.

## Root causes inspected before editing

| Finding | Evidence and action |
|---|---|
| Double storage pass and executor handoffs | Existing FastAPI multipart parsing spooled files before the shared service copied them again using 1 MiB async reads/writes. Both phases were benchmarked separately. The second pass now runs as one bounded worker operation with hashing; framework spooling remains. |
| Unbounded CSV sampling | `_read_csv_dataframe_from_path` used `path.read_bytes()[:8192]`, loading a full file for an 8 KiB sample. Replaced with `read(8192)` and measured separately. |
| CPU work on the API event loop | CSV/Excel parsing and row conversion were synchronous inside async functions; ATL background tasks also ran in the API process. Synchronous import parsing is now offloaded with two parse slots per process. ATL jobs run in Celery. |
| Long-lived read transactions | Authentication/context reads remained open while copying or parsing. The generic route uses a short independent auth session. Import routes end prerequisite reads. Attachment helpers release clean implicit read transactions and reattach loaded objects afterward. Explicit transactions or pending writes are preserved. |
| Cancellation and collision bugs | `except Exception` missed cancellation, deterministic `.part` names and preemptive unlink could delete an existing destination, and cancellation could race a worker write. Unique private temporary files, cooperative stopping/draining and atomic no-clobber hard links address these cases. |
| Security gaps | Generic uploads/downloads were public; storage roots used string-prefix checks; Office validation trusted ZIP signatures. Added module permissions, owner-scoped registry, component-aware containment, declared MIME checks, bounded structural validation and early multipart rejection. |
| Failure after file storage | Business failures could leave files behind. New files are tracked until commit; rollback/close removes uncommitted files. Uncertain commit outcomes retain a marker for conservative reconciliation. |
| Limits disagreed | Nginx capped the entire request at 50 MiB while the app allowed a 50 MiB file. Provided configs now allow 51 MiB for the envelope. Timeouts were not increased. |

## Repeatable measurements

Each upload sample uses a freshly launched Python process, a generated 16 MiB CSV on local disk, and one, four or eight concurrent transfers. Five samples per configuration; tables show medians. Both implementations used identical dependencies. Payload creation and pre-spooling for storage-only measurements are outside the timer. Files are cache-warm; no production network, Nginx or object store is involved.

`storage` measures the shared storage service starting with disk-spooled input. `api` adds multipart parsing in a minimal FastAPI ASGI harness. These isolation measurements intentionally exclude authorization, metadata PostgreSQL work and post-response broker dispatch. The actual secured route is measured separately below. HTTPX client and server share a process; RSS and tracemalloc are not server-only measurements. RSS includes imports and setup, while traced allocations cover the timed region. Tracemalloc itself adds overhead.

| Scope | Concurrent files | Batch ms before | Batch ms after | Mean response ms before | Mean response ms after |
|---|---:|---:|---:|---:|---:|
| storage | 1 | 64.18 | 64.71 | 61.82 | 62.04 |
| storage | 4 | 86.39 | 84.92 | 78.99 | 80.26 |
| storage | 8 | 118.79 | 142.11 | 107.18 | 109.58 |
| api | 1 | 138.16 | 156.54 | 135.73 | 153.92 |
| api | 4 | 355.33 | 410.11 | 324.34 | 372.39 |
| api | 8 | 661.50 | 706.96 | 610.47 | 635.68 |

| Scope | Concurrent files | Peak Python MiB before | Peak Python MiB after | Peak RSS MiB before | Peak RSS MiB after |
|---|---:|---:|---:|---:|---:|
| storage | 1 | 3.03 | 2.18 | 58.06 | 57.50 |
| storage | 4 | 9.14 | 8.23 | 71.14 | 68.19 |
| storage | 8 | 16.27 | 8.16 | 77.83 | 75.02 |
| api | 1 | 3.13 | 3.12 | 54.42 | 56.19 |
| api | 4 | 9.31 | 9.32 | 66.92 | 67.52 |
| api | 8 | 16.59 | 10.76 | 80.02 | 74.50 |

| Scope | Concurrent files | Throughput MiB/s before | Throughput MiB/s after |
|---|---:|---:|---:|
| storage | 1 | 249.29 | 247.24 |
| storage | 4 | 740.80 | 753.68 |
| storage | 8 | 1077.55 | 900.74 |
| api | 1 | 115.81 | 102.21 |
| api | 4 | 180.11 | 156.06 |
| api | 8 | 193.50 | 181.06 |

Actual secured endpoint, **after only**, with real JWT validation, module permissions, PostgreSQL 15 on a private local Unix socket, filesystem synchronization and metadata commits. The concurrent requests deliberately contain identical bytes for one account, exercising duplicate races. Every sample starts with a new schema/process, so initial ORM/connection costs are included. These numbers are not directly comparable to the storage-only harness:

| Concurrent files | Batch ms | Mean response ms | Peak Python MiB | Peak RSS MiB |
|---:|---:|---:|---:|---:|
| 1 | 658.04 | 655.71 | 10.95 | 108.05 |
| 4 | 1014.51 | 676.29 | 16.36 | 119.50 |
| 8 | 1410.80 | 980.29 | 17.90 | 123.44 |

CSV delimiter probe on a 50 MiB file, five repetitions. Pandas parsing is stubbed identically in both versions to isolate sampling; this does not benchmark a complete spreadsheet import:

| Version | Median ms | Peak Python MiB |
|---|---:|---:|
| before | 10.974 | 50.008 |
| after | 2.078 | 0.147 |

Environment: 3.13.13 (main, Apr  7 2026, 18:19:01) [Clang 17.0.0 (clang-1700.6.4.2)]; macOS-15.6.1-arm64-arm-64bit-Mach-O.

Measured dependency versions: `{"aiofiles": "25.1.0", "fastapi": "0.125.0", "httpx": "0.28.1", "python-multipart": "0.0.32", "sqlalchemy": "2.0.54", "starlette": "0.50.0"}`.

Raw samples, including per-sample ranges, throughput, response times, RSS and traced allocation peaks: [before](upload_benchmark_results/before.json), [after](upload_benchmark_results/after.json), [secured PostgreSQL endpoint](upload_benchmark_results/secured-postgres.json), [CSV probe](upload_benchmark_results/csv-probe.json). No statistical significance or production throughput claim is made.

Run from `backend` in a disposable test environment:
```sh
git show 5b2d22aa1cd681cb853650aebbaa8fc46fdd8e5c:backend/app/services/file_upload_service.py > /tmp/upload-before.py
git show 5b2d22aa1cd681cb853650aebbaa8fc46fdd8e5c:backend/app/services/excel_import/reader.py > /tmp/reader-before.py
python scripts/benchmark_uploads.py --service /tmp/upload-before.py > /tmp/before.json
python scripts/benchmark_uploads.py --service app/services/file_upload_service.py > /tmp/after.json
python scripts/benchmark_csv_probe.py --before /tmp/reader-before.py --after app/services/excel_import/reader.py
# Set UPLOAD_BENCH_DATABASE_URL to a disposable PostgreSQL database for this run.
# Without it, secured-api uses a temporary SQLite database.
python scripts/benchmark_uploads.py --service app/services/file_upload_service.py --modes secured-api
```

## Validation results

- 49 focused upload tests passed on SQLite. The PostgreSQL run also passed all 49, including actual migration upgrade/downgrade, concurrent deduplication, connection release, ownership isolation and lost-commit-acknowledgement handling. A final durable-write benchmark exercised the real PostgreSQL endpoint afterward.
- The focused suite covers success; the actual 50 MiB boundary and one byte over; invalid extension/MIME; empty/truncated/malformed content; valid image formats; unauthenticated/inactive/forbidden users; duplicates and missing-file repair; cancelled/interrupted bodies and worker copies; concurrent requests and admission rejection; path traversal, symlinks, collisions; rollback/close cleanup; stale-marker reconciliation; and worker dispatch claiming.
- Existing upload/import tests: 88 passed, one failed. The failing `test_import_duplicate_row_in_file_reports_errors` also fails on the untouched baseline with the same environment.
- Broader attachment/aircraft/logbook/AD/certificate/ATL tests: 167 passed, nine failed. All nine failures reproduce in the untouched ATL suite. They concern existing time-field formatting/schema and ATL work-status permissions, not the upload changes.
- The complete repository suite was not run. Live Redis/Celery end-to-end execution and deployment-image testing were not performed. PostgreSQL tests used a disposable cluster, which was stopped after verification.

Commands:
```sh
pytest --confcutdir=tests/uploads tests/uploads -o addopts="" -q
# Set UPLOAD_TEST_DATABASE_URL to a disposable PostgreSQL DB to run the same suite there.
pytest tests/services/test_file_upload_service.py tests/services/test_excel_import_service.py tests/api/test_data_import_api.py -o addopts="" -q
pytest tests/test_aircraft.py tests/test_logbooks.py tests/test_ad_monitoring.py tests/test_aircraft_statutory_certificate.py tests/test_aircraft_technical_log.py -o addopts="" -q
```

Known baseline failures reproduced:
```text
CSV: test_import_duplicate_row_in_file_reports_errors
ATL: test_atl_api_read_formats_canonical_time_fields_to_one_decimal
     test_update_aircraft_technical_log
     test_aircraft_technical_log_web_links_crud
     test_update_aircraft_technical_log_allows_meter_start_changes
     test_update_aircraft_technical_log_persists_client_time_fields
     test_create_aircraft_technical_log_persists_client_time_fields_and_rounds_tach_total
     test_quality_manager_can_update_pending_to_completed
     test_quality_manager_can_update_pending_to_rejected_quality
     test_quality_manager_cannot_update_for_review_to_completed
```

## Compatibility, configuration and operational limits

- Generic uploads now require a bearer token and create or update permission for a known module. Generic downloads require read permission for that module. Shared module readers may download attachments; this retains shared business access rather than making downloads private to the uploader. Account identity for new metadata and duplicate detection always comes from verified authentication. Existing entity-level CRUD authorization is retained.
- Unknown generic module folders are rejected. Supported folders map to existing RBAC constants: aircraft/document_on_board → General Information; logbooks → Logbook; white_atl/dfp/ad_monitoring → Maintenance; aircraft_statutory_certificates/statutory_certificates → Regulatory Compliance.
- Clients using public links or unauthenticated image/anchor URLs must switch to authenticated downloads. Upload URLs, response JSON keys, status 201, and the multipart file field remain stable. Duplicate bytes for the same account/module return the original metadata; other owners are isolated. Inline business attachments continue to create independent files to preserve their workflows.
- Validation is stricter: CSV must be UTF-8 text; truncated PDFs/images and invalid Office containers are rejected. Office archives cap entry count at 4096, total expanded size at 100 MiB, compression ratio at 200, and core XML at 1 MiB. These are structural checks, not full document-schema validation or antivirus scanning. No antivirus engine or thumbnail workflow existed and none is claimed.
- Limits remain `MAX_UPLOAD_BYTES=52428800` and `UPLOAD_TIMEOUT_SECONDS=120` by default. Generic requests allow one file, no extra form fields, and at most 1 MiB envelope overhead. Parsing and permanent copying have separate timeouts. Admission waits at most one second, then responds 503 with Retry-After. Four copy workers and eight admitted generic uploads per API process; two synchronous import parsers per process. Multiply these by the configured Gunicorn worker count when sizing memory and temporary disk.
- Business attachment routes still use FastAPI multipart spooling and their existing authentication flow. The generic endpoint provides authentication before body consumption; do not extrapolate that guarantee to every multipart business endpoint. Explicit/pending-write transactions are not silently rolled back by the shared helper.
- Dependencies: compatible FastAPI 0.121–0.125/Pydantic 1 constraints, Starlette 0.49.1–0.50, python-multipart >=0.0.32, SQLAlchemy 2.x, Pillow and olefile for structural checks, xlrd for legacy Excel. Existing binary `files.data` storage was not migrated or deleted; the new upload registry stores metadata only.
- Upstream rationale: [Starlette release notes](https://www.starlette.io/release-notes/) describe multipart rollover fixes; [python-multipart advisories](https://github.com/Kludex/python-multipart/security) document parser issues affecting older versions. The tested versions are recorded above; no claim is made that dependency constraints replace ongoing security maintenance.
- New migration `i0j1k2l3m4n5` follows `h9i0j1k2l3m4`: creates `upload_assets` and the unique `(owner_id, module_folder, sha256)` constraint. No bytes are stored there; legacy uploads are not backfilled or deleted.
- The upload volume must support POSIX hard links and file/directory fsync. Temporary files are mode 0600 and publish atomically without replacing existing paths. Normal failures clean immediately; business commit failures with uncertain outcomes retain `.pending` markers. An hourly Celery task reconciles markers/parts older than 24 hours against database references. It never sweeps unmarked legacy files.
- ATL job rows in PENDING serve as a durable dispatch outbox. Celery beat retries their dispatch every minute; a conditional status transition prevents two workers from processing the same pending job. Existing progress response formats remain. Worker hard crashes after claiming PROCESSING still require operational inspection/recovery; do not blindly replay an import with an uncertain business commit.
- Synchronous import endpoints preserve their response contract and still materialize row data; bounded upload I/O does not bound dataframe memory. Prefer the queued ATL endpoint for large ATL imports. Virus scanning, semantic document validation and independent worker resource limits remain deployment concerns.
- Provided Nginx/OpenResty configs now allow 51 MiB envelopes. Existing API proxy timeouts (180s in the main configs) and proxy_request_buffering settings are retained. Verify any external ingress/proxy limits separately; no live proxy configuration was inspected.

## Deployment

1. Back up PostgreSQL and the shared uploads volume; retain the previous application image. Build and test the changed image with the deployment Python version (the local measurements used Python 3.13; the Dockerfile uses 3.11).
2. Check clients send bearer tokens for upload/download and that the existing module roles have the required permissions. Validate representative real PDFs, images and Office files against the stricter checks.
3. Apply `alembic upgrade head` before enabling the new API. Existing entrypoint migration handling may do this; use a single migration runner for the rollout. The new table is additive.
4. Roll out API, Celery worker and Celery beat together, with the same shared upload volume. Keep Celery beat running for pending-job dispatch and stale-file reconciliation. Set worker concurrency according to import memory consumption.
5. Validate and reload the provided 51 MiB Nginx configuration (for example `docker compose -f docker-compose.prod.yml exec nginx nginx -t` before reload). Check any outer ingress has matching body limits.
6. Smoke-test a 50 MiB upload, duplicate retry, unauthorized request, concurrent uploads, authenticated download and a queued ATL import through the real proxy. Watch 4xx/5xx rates, pool utilization, temporary disk usage and PENDING/PROCESSING job age. Measure production-like latency before asserting a speed benefit.

## Rollback

1. Pause new uploads/import submissions and drain or inspect outstanding import jobs before replacing workers.
2. Restore the previous API/worker/beat images and matching proxy configuration. Preserve the uploads volume. The previous application can coexist with the extra metadata table.
3. Prefer leaving `upload_assets` in place during an application rollback. If a schema rollback is required after backing up ownership/dedup metadata and disabling new code, run `alembic downgrade h9i0j1k2l3m4`. Downgrade drops only the new metadata table; it does not remove stored file bytes.
4. Preserve pending markers until their referenced files/commits have been reconciled. Restoring previous code also restores its public generic endpoints, so maintain access controls at ingress during rollback.

## Files changed

- `backend/alembic/env.py`
- `backend/alembic/versions/i0j1k2l3m4n5_upload_assets.py`
- `backend/app/api/v1/aircraft_technical_log.py`
- `backend/app/api/v1/atl_excel_import.py`
- `backend/app/api/v1/data_import.py`
- `backend/app/api/v1/file_upload.py`
- `backend/app/main.py`
- `backend/app/models/upload_asset.py`
- `backend/app/repository/ad_monitoring.py`
- `backend/app/repository/aircraft.py`
- `backend/app/repository/aircraft_statutory_certificate.py`
- `backend/app/repository/document_on_board.py`
- `backend/app/repository/logbooks.py`
- `backend/app/repository/upload_asset.py`
- `backend/app/services/aircraft_history_service.py`
- `backend/app/services/atl_excel_import_job_runner.py`
- `backend/app/services/excel_import/reader.py`
- `backend/app/services/file_upload_service.py`
- `backend/app/services/registered_upload_service.py`
- `backend/app/services/upload_reconciliation.py`
- `backend/app/services/upload_transaction.py`
- `backend/app/tasks/file_upload.py`
- `backend/app/worker.py`
- `backend/docs/upload_benchmark_results/after.json`
- `backend/docs/upload_benchmark_results/before.json`
- `backend/docs/upload_benchmark_results/csv-probe.json`
- `backend/docs/upload_benchmark_results/secured-postgres.json`
- `backend/requirements.txt`
- `backend/scripts/benchmark_csv_probe.py`
- `backend/scripts/benchmark_uploads.py`
- `backend/tests/services/test_excel_import_service.py`
- `backend/tests/services/test_file_upload_service.py`
- `backend/tests/uploads/conftest.py`
- `backend/tests/uploads/test_api.py`
- `backend/tests/uploads/test_imports.py`
- `backend/tests/uploads/test_migration.py`
- `backend/tests/uploads/test_storage.py`
- `nginx/conf.d/dev.conf`
- `nginx/conf.d/prod.conf`
- `nginx/conf.d/uat.conf`
- `nginx/openresty-fleet-ws.example.conf`
- `backend/docs/UPLOAD_REVIEW.md` (this report)
