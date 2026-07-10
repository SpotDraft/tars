import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.data.postgres.db_repo import PacketDBRepository
from app.clickwrap.domain.domain_models import (
    PacketAgreementMappingListDomainModel,
    PacketMappingsUpdateRequest,
)

logger = logging.getLogger(__name__)


class UpdatePacketMappingsUseCase:
    def __init__(self, session: AsyncSession, repo: PacketDBRepository | None = None) -> None:
        self._repo = repo or PacketDBRepository(session)

    async def execute(
        self,
        packet_id: int,
        workspace_id: int,
        org_user_id: int,
        request: PacketMappingsUpdateRequest,
    ) -> PacketAgreementMappingListDomainModel:
        result = await self._repo.update_mappings(
            packet_id=packet_id,
            workspace_id=workspace_id,
            org_user_id=org_user_id,
            request=request,
        )
        logger.info(
            "UpdatePacketMappingsUseCase completed",
            extra={
                "workspace_id": workspace_id,
                "packet_id": packet_id,
                "org_user_id": org_user_id,
                "mapping_count": len(result.items),
            },
        )
        return result
