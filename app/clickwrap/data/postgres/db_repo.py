import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.domain.domain_models import (
    PacketDomainModel,
    PacketFilterRequest,
    PacketListDomainModel,
)
from app.db.models import Packet

logger = logging.getLogger(__name__)


class PacketDBRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def filter(self, request: PacketFilterRequest) -> PacketListDomainModel:
        """
        Returns packets for the given workspace, ordered by id descending
        (most recently created first).

        Workspace isolation is always applied — request.workspace_id is a
        required field and is always included in the WHERE clause.

        Soft-delete: starts from Packet.objects() (excludes deleted) by default.
        Pass include_deleted=True to use Packet.objects_including_deleted() instead.

        Args:
            request.workspace_id:    Required. Scopes results to this workspace.
            request.packet_ids:      Optional. Further filters to only these IDs.
            request.include_deleted: When True, includes soft-deleted packets.
        """
        base = (
            Packet.objects_including_deleted()
            if request.include_deleted
            else Packet.objects()
        )

        query = (
            base.where(Packet.workspace_id == request.workspace_id)
            .order_by(Packet.id.desc())
        )

        if request.packet_ids is not None:
            query = query.where(Packet.id.in_(request.packet_ids))

        result = await self._session.execute(query)
        packets = result.scalars().all()

        logger.info(
            "PacketDBRepository.filter completed",
            extra={
                "workspace_id": request.workspace_id,
                "packet_count": len(packets),
                "filtered_by_ids": request.packet_ids is not None,
                "include_deleted": request.include_deleted,
            },
        )

        return PacketListDomainModel(
            items=[PacketDomainModel.model_validate(p) for p in packets]
        )
