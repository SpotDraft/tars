import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PacketDomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int

    name: str
    name_slug: str
    description: str | None
    public_id: uuid.UUID
    packet_settings_id: int

    created_by_org_user_id: int
    updated_by_org_user_id: int | None
    updated_by_org_user_at: datetime | None

    created_at: datetime
    updated_at: datetime

    is_deleted: bool
    deleted_at: datetime | None
    deleted_by_org_user_id: int | None


class PacketListDomainModel(BaseModel):
    items: list[PacketDomainModel]


class PacketFilterRequest(BaseModel):
    workspace_id: int
    packet_ids: list[int] | None = None
    include_deleted: bool = False
