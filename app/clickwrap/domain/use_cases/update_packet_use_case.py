import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.data.postgres.db_repo import PacketDBRepository, slugify
from app.clickwrap.domain.domain_models import (
    PacketDetailDomainModel,
    PacketFilterRequest,
    PacketUpdateRequest,
)
from app.clickwrap.exceptions import PacketInvalidNameError

logger = logging.getLogger(__name__)


class UpdatePacketUseCase:
    def __init__(self, session: AsyncSession, repo: PacketDBRepository | None = None) -> None:
        self._repo = repo or PacketDBRepository(session)

    async def execute(
        self,
        packet_id: int,
        workspace_id: int,
        org_user_id: int,
        request: PacketUpdateRequest,
    ) -> PacketDetailDomainModel:
        if request.name is not None:
            name_slug = slugify(request.name)
            existing = await self._repo.filter(
                PacketFilterRequest(workspace_id=workspace_id, name_slugs=[name_slug])
            )
            if any(item.id != packet_id for item in existing.items):
                raise PacketInvalidNameError()

        try:
            await self._repo.update(
                packet_id=packet_id,
                workspace_id=workspace_id,
                org_user_id=org_user_id,
                request=request,
            )
        except IntegrityError as exc:
            raise PacketInvalidNameError() from exc

        detail = await self._repo.get_detail(packet_id=packet_id, workspace_id=workspace_id)
        logger.info(
            "UpdatePacketUseCase completed",
            extra={
                "workspace_id": workspace_id,
                "packet_id": packet_id,
                "org_user_id": org_user_id,
            },
        )
        return detail
