from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Text

from app.database import Base, TimestampMixin


class AtlExcelImportJob(Base, TimestampMixin):
    """Tracks background ATL Excel import progress."""

    __tablename__ = "atl_excel_import_job"

    job_id = Column(String(36), primary_key=True, index=True)
    status = Column(String(20), nullable=False, default="PENDING")
    message = Column(Text, nullable=True)
    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    failed_rows = Column(Integer, nullable=False, default=0)
    errors = Column(JSON, nullable=False)
    temp_file_path = Column(Text, nullable=True)
    aircraft_fk = Column(Integer, ForeignKey("aircrafts.id"), nullable=False)
    atl_batch_fk = Column(Integer, ForeignKey("atl_batch.id"), nullable=False)
    started_by = Column(Integer, ForeignKey("account_information.id"), nullable=True)
