from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import AsyncSessionLocal


@dataclass(frozen=True, slots=True)
class RequestContext:
    workspace_id: int
    org_user_id: int
    user_id: int | None = None
    request_id: str | None = None
    client_ip: str | None = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_request_context(
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    x_org_user_id: str | None = Header(default=None, alias="X-Org-User-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_client_ip: str | None = Header(default=None, alias="X-Client-IP"),
) -> RequestContext:
    if not x_workspace_id or not x_org_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID and X-Org-User-ID headers are required",
        )
    try:
        workspace_id = int(x_workspace_id)
        org_user_id = int(x_org_user_id)
        user_id = int(x_user_id) if x_user_id else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace and org user header values must be integers",
        ) from exc

    return RequestContext(
        workspace_id=workspace_id,
        org_user_id=org_user_id,
        user_id=user_id,
        request_id=x_request_id,
        client_ip=x_client_ip,
    )
