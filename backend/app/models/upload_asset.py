"""Metadata only; bytes remain on the shared upload volume."""
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, UniqueConstraint, func
from app.database import Base


class UploadAsset(Base):
    __tablename__ = 'upload_assets'
    file_path = Column(String(500), primary_key=True)
    owner_id = Column(Integer, ForeignKey('account_information.id'), nullable=False)
    module_folder = Column(String(80), nullable=False)
    sha256 = Column(String(64), nullable=False)
    original_filename = Column(String(1024), nullable=False)
    filename = Column(String(255), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint('owner_id', 'module_folder', 'sha256', name='uq_upload_owner_module_sha256'),)

    def payload(self):
        return dict(file_path=self.file_path, filename=self.filename, size_bytes=self.size_bytes,
                    content_type=self.content_type, original_filename=self.original_filename,
                    stored_filename=self.filename, size=self.size_bytes)
