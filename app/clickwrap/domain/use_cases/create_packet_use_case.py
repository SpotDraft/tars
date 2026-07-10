import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.data.postgres.db_repo import PacketDBRepository, slugify
from app.clickwrap.domain.domain_models import (
    PacketCreateRequest,
    PacketDomainModel,
    PacketFilterRequest,
)
from app.clickwrap.exceptions import PacketInvalidNameError

logger = logging.getLogger(__name__)


class CreatePacketUseCase:
    def __init__(self, session: AsyncSession, repo: PacketDBRepository | None = None) -> None:
        self._session = session
        self._repo = repo or PacketDBRepository(session)

    async def execute(
        self,
        request: PacketCreateRequest,
        workspace_id: int,
        org_user_id: int,
    ) -> PacketDomainModel:
        name_slug = slugify(request.name)
        existing_count = await self._repo.get_count(
            PacketFilterRequest(workspace_id=workspace_id, name_slugs=[name_slug])
        )
        if existing_count > 0:
            logger.info(
                "CreatePacketUseCase rejected duplicate name",
                extra={
                    "workspace_id": workspace_id,
                    "org_user_id": org_user_id,
                    "packet_name": request.name,
                    "name_slug": name_slug,
                },
            )
            raise PacketInvalidNameError()

        try:
            packet = await self._repo.create(
                request=request,
                workspace_id=workspace_id,
                org_user_id=org_user_id,
            )
        except IntegrityError as exc:
            raise PacketInvalidNameError() from exc

        logger.info(
            "CreatePacketUseCase completed",
            extra={
                "workspace_id": workspace_id,
                "org_user_id": org_user_id,
                "packet_id": packet.id,
            },
        )
        return packet
