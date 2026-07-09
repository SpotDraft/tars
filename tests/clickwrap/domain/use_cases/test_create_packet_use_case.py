from unittest.mock import AsyncMock

import pytest

from app.clickwrap.domain.domain_models import (
    PacketCreateRequest,
    PacketDomainModel,
    PacketFilterRequest,
)
from app.clickwrap.domain.use_cases.create_packet_use_case import CreatePacketUseCase
from app.clickwrap.exceptions import PacketInvalidNameError


@pytest.mark.unit
class TestCreatePacketUseCase:
    async def test_execute_creates_when_name_available(self):
        repo = AsyncMock()
        repo.get_count.return_value = 0
        created = AsyncMock(spec=PacketDomainModel)
        created.id = 10
        repo.create.return_value = created

        use_case = CreatePacketUseCase(session=AsyncMock(), repo=repo)
        request = PacketCreateRequest(name="Packet A", description="desc")
        result = await use_case.execute(request=request, workspace_id=1, org_user_id=2)

        assert result is created
        repo.get_count.assert_awaited_once_with(
            PacketFilterRequest(workspace_id=1, name_slugs=["packet-a"])
        )
        repo.create.assert_awaited_once_with(request=request, workspace_id=1, org_user_id=2)

    async def test_execute_raises_on_duplicate_name(self):
        repo = AsyncMock()
        repo.get_count.return_value = 1
        use_case = CreatePacketUseCase(session=AsyncMock(), repo=repo)

        with pytest.raises(PacketInvalidNameError):
            await use_case.execute(
                request=PacketCreateRequest(name="Packet A", description="desc"),
                workspace_id=1,
                org_user_id=2,
            )
        repo.create.assert_not_awaited()
