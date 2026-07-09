import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.domain.domain_models import (
    PacketCreateRequest,
    PacketMappingsUpdateRequest,
    PacketPaginatedRequest,
    PacketUpdateRequest,
)
from app.clickwrap.domain.use_cases.create_packet_use_case import CreatePacketUseCase
from app.clickwrap.domain.use_cases.get_packet_use_case import GetPacketUseCase
from app.clickwrap.domain.use_cases.list_packets_use_case import ListPacketsUseCase
from app.clickwrap.domain.use_cases.update_packet_mappings_use_case import (
    UpdatePacketMappingsUseCase,
)
from app.clickwrap.domain.use_cases.update_packet_use_case import UpdatePacketUseCase
from app.clickwrap.exceptions import (
    AgreementNotFoundError,
    PacketInvalidNameError,
    PacketNotFoundError,
    PacketPaginationError,
)
from app.clickwrap.presentation.schemas import (
    PacketDetailResponse,
    PacketMappingResponse,
    PacketMinimalResponse,
    PacketPaginatedResponse,
)
from app.core.deps import RequestContext, get_db_session, get_request_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/clickwraps", tags=["clickwraps"])


@router.get("")
@router.get("/")
async def list_packets(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> PacketPaginatedResponse:
    try:
        result = await ListPacketsUseCase(session).execute(
            PacketPaginatedRequest(workspace_id=ctx.workspace_id, page=page, limit=limit)
        )
    except PacketPaginationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PacketPaginatedResponse.from_domain(result)


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_packet(
    body: PacketCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> PacketMinimalResponse:
    try:
        packet = await CreatePacketUseCase(session).execute(
            request=body,
            workspace_id=ctx.workspace_id,
            org_user_id=ctx.org_user_id,
        )
    except PacketInvalidNameError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PacketMinimalResponse.from_packet_domain(packet)


@router.get("/{clickwrap_id}")
@router.get("/{clickwrap_id}/")
async def get_packet(
    clickwrap_id: int,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> PacketDetailResponse:
    try:
        detail = await GetPacketUseCase(session).execute(
            packet_id=clickwrap_id, workspace_id=ctx.workspace_id
        )
    except PacketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PacketDetailResponse.from_domain(detail)


@router.patch("/{clickwrap_id}")
@router.patch("/{clickwrap_id}/")
async def update_packet(
    clickwrap_id: int,
    body: PacketUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> PacketDetailResponse:
    try:
        detail = await UpdatePacketUseCase(session).execute(
            packet_id=clickwrap_id,
            workspace_id=ctx.workspace_id,
            org_user_id=ctx.org_user_id,
            request=body,
        )
    except PacketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PacketInvalidNameError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PacketDetailResponse.from_domain(detail)


@router.patch("/{clickwrap_id}/clickwrap-agreement-mappings")
async def update_packet_mappings(
    clickwrap_id: int,
    body: PacketMappingsUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[PacketMappingResponse]:
    try:
        result = await UpdatePacketMappingsUseCase(session).execute(
            packet_id=clickwrap_id,
            workspace_id=ctx.workspace_id,
            org_user_id=ctx.org_user_id,
            request=body,
        )
    except PacketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AgreementNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [PacketMappingResponse.from_domain(item) for item in result.items]
