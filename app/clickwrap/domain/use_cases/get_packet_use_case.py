import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.data.postgres.db_repo import PacketDBRepository
from app.clickwrap.domain.domain_models import PacketDetailDomainModel

logger = logging.getLogger(__name__)


class GetPacketUseCase:
    def __init__(self, session: AsyncSession, repo: PacketDBRepository | None = None) -> None:
        self._repo = repo or PacketDBRepository(session)

    async def execute(self, packet_id: int, workspace_id: int) -> PacketDetailDomainModel:
        detail = await self._repo.get_detail(packet_id=packet_id, workspace_id=workspace_id)
        logger.info(
            "GetPacketUseCase completed",
            extra={
                "workspace_id": workspace_id,
                "packet_id": packet_id,
                "agreement_count": len(detail.agreements),
            },
        )
        return detail
