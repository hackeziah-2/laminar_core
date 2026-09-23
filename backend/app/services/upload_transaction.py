"""Compensate file writes when the owning business transaction fails.

Only newly created files are tracked. Unknown COMMIT outcomes retain a pending
marker for reconciliation; deleting potentially committed content is unsafe.
"""
import logging
from pathlib import Path
from sqlalchemy import event

logger = logging.getLogger(__name__)


def marker(path: Path) -> Path:
    return path.with_name(path.name + '.pending')


def track_upload(session, path: Path):
    sync = session.sync_session
    if not sync.in_transaction():
        sync.begin()
    if '_upload_tracking' not in sync.info:
        sync.info['_upload_tracking'] = True
        def cleanup(target, committed=False):
            paths = target.info.pop('_upload_paths', [])
            uncertain = target.info.pop('_upload_commit_attempted', False)
            for item in paths:
                if uncertain and not committed:
                    logger.warning('Upload needs reconciliation after uncertain commit: %s', item)
                    continue
                try:
                    if not committed:
                        item.unlink(missing_ok=True)
                    marker(item).unlink(missing_ok=True)
                except OSError:
                    logger.exception('Upload cleanup failed for %s', item)
        def before_commit(target):
            if target.info.get('_upload_paths'):
                target.info['_upload_commit_attempted'] = True
        def after_commit(target):
            if not target.in_nested_transaction():
                cleanup(target, committed=True)
        def after_end(target, transaction):
            if transaction.parent is None:
                cleanup(target)
        event.listen(sync, 'before_commit', before_commit)
        event.listen(sync, 'after_commit', after_commit)
        event.listen(sync, 'after_transaction_end', after_end)
    sync.info.setdefault('_upload_paths', []).append(path)


from contextlib import asynccontextmanager


@asynccontextmanager
async def release_upload_reads(session):
    """Release the upload callers' clean, implicit read transaction during the copy.

    Existing objects keep their loaded values and are reattached afterward. Explicit
    transactions and pending writes are never committed, rolled back or detached.
    Upload repositories call this before changes/locking queries, not after them.
    """
    objects = []
    if session is not None:
        sync = session.sync_session
        transaction = sync.get_transaction()
        if (transaction is not None and getattr(transaction.origin, 'name', '') == 'AUTOBEGIN'
                and not sync.new and not sync.dirty and not sync.deleted
                and not sync.info.get('_upload_paths')):
            objects = list(sync.identity_map.values())
            sync.expunge_all()
            await session.rollback()
    try:
        yield
    finally:
        if objects:
            # Attaching starts an ORM transaction but checks out no DB connection.
            session.add_all(objects)
