"""ATL orchestration service."""

from __future__ import annotations

from typing import List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.events.atl_notification_events import publish_atl_status_change_notification
from app.models.account import AccountInformation
from app.models.aircraft_techinical_log import AircraftTechnicalLog, WorkStatus


class AtlService:
    """ATL service wrapper for post-commit side effects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish_status_change_notifications(
        self,
        *,
        atl: AircraftTechnicalLog,
        old_status: Union[WorkStatus, str, None],
        changed_by_account: Optional[AccountInformation] = None,
    ) -> List[int]:
        return await publish_atl_status_change_notification(
            self.session,
            atl=atl,
            old_status=old_status,
            new_status=atl.work_status,
            changed_by_account=changed_by_account,
        )
