import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.data.postgres.db_repo import PacketDBRepository
from app.clickwrap.domain.domain_models import (
    PacketPaginatedListDomainModel,
    PacketPaginatedRequest,
)

logger = logging.getLogger(__name__)


class ListPacketsUseCase:
    def __init__(self, session: AsyncSession, repo: PacketDBRepository | None = None) -> None:
        self._repo = repo or PacketDBRepository(session)

    async def execute(self, request: PacketPaginatedRequest) -> PacketPaginatedListDomainModel:
        result = await self._repo.get_paginated_list(request)
        logger.info(
            "ListPacketsUseCase completed",
            extra={
                "workspace_id": request.workspace_id,
                "page": request.page,
                "limit": request.limit,
                "total_results": result.total_results,
            },
        )
        return result
