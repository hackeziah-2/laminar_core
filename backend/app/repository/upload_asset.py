"""Short upload metadata transactions and concurrent checksum deduplication."""
from sqlalchemy import select
from app.models.upload_asset import UploadAsset


async def register_upload(session_factory, owner_id: int, module_folder: str, result: dict) -> dict:
    """Short metadata transaction. Unique index arbitrates concurrent duplicates."""
    async with session_factory() as session:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert = sqlite_insert if session.bind.dialect.name == 'sqlite' else pg_insert
        values = {key: result[key] for key in ('file_path', 'sha256', 'original_filename',
                                             'filename', 'size_bytes', 'content_type')}
        values.update(owner_id=owner_id, module_folder=module_folder)
        statement = insert(UploadAsset).values(**values).on_conflict_do_nothing(
            index_elements=['owner_id', 'module_folder', 'sha256'])
        await session.execute(statement)
        asset = (await session.execute(select(UploadAsset).where(
            UploadAsset.owner_id == owner_id, UploadAsset.module_folder == module_folder,
            UploadAsset.sha256 == result['sha256'],
        ))).scalar_one()
        payload = asset.payload()
        await session.commit()
        return payload


