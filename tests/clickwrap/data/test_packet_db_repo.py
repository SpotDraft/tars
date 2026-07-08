from app.clickwrap.data.postgres.db_repo import PacketDBRepository
from app.clickwrap.domain.domain_models import (
    PacketDomainModel,
    PacketFilterRequest,
    PacketListDomainModel,
)
from tests.base_db_repo_test import BaseDBRepoTestCase
from tests.factories import PacketFactory


class TestPacketDBRepositoryFilter(BaseDBRepoTestCase):
    async def test_filter_workspace_isolation(self, db_session):
        """
        Each workspace sees only its own packets, ordered by id DESC.

        Creates packets in two workspaces and asserts that a filter scoped to
        workspace A returns only workspace A's packets (newest first), and
        workspace B's packets are invisible to it.
        """
        # setup
        ws_a, ws_b = 100, 101
        packet_a1 = await PacketFactory.create(db_session, workspace_id=ws_a)
        packet_a2 = await PacketFactory.create(db_session, workspace_id=ws_a)
        await PacketFactory.create(db_session, workspace_id=ws_b)  # must not appear

        repo = PacketDBRepository(db_session)

        # make the call
        result = await repo.filter(PacketFilterRequest(workspace_id=ws_a))

        # assert — workspace isolation + id DESC ordering
        assert result == PacketListDomainModel(
            items=[
                PacketDomainModel.model_validate(packet_a2),
                PacketDomainModel.model_validate(packet_a1),
            ]
        )

    async def test_filter_by_packet_ids(self, db_session):
        """
        When packet_ids is provided, only those IDs are returned.
        Cross-workspace IDs are silently excluded (workspace isolation still
        applies even when an explicit ID list is passed).
        """
        # setup
        ws_a, ws_b = 200, 201
        packet_a1 = await PacketFactory.create(db_session, workspace_id=ws_a)
        packet_a2 = await PacketFactory.create(db_session, workspace_id=ws_a)
        packet_b = await PacketFactory.create(db_session, workspace_id=ws_b)

        repo = PacketDBRepository(db_session)

        # only packet_a1 requested
        result = await repo.filter(
            PacketFilterRequest(workspace_id=ws_a, packet_ids=[packet_a1.id])
        )
        assert len(result.items) == 1
        assert result.items[0].id == packet_a1.id

        # packet_a2 + cross-workspace packet_b — packet_b must be excluded
        result = await repo.filter(
            PacketFilterRequest(workspace_id=ws_a, packet_ids=[packet_a2.id, packet_b.id])
        )
        assert len(result.items) == 1
        assert result.items[0].id == packet_a2.id

    async def test_filter_soft_delete_behaviour(self, db_session):
        """
        Soft-deleted packets are excluded by default (Packet.objects()).
        Passing include_deleted=True switches to Packet.objects_including_deleted()
        and returns all packets regardless of deletion status.
        """
        # setup
        workspace_id = 300
        active = await PacketFactory.create(db_session, workspace_id=workspace_id)
        deleted = await PacketFactory.create(
            db_session, workspace_id=workspace_id, is_deleted=True
        )

        repo = PacketDBRepository(db_session)

        # default — deleted packet must not appear
        result = await repo.filter(PacketFilterRequest(workspace_id=workspace_id))
        assert len(result.items) == 1
        assert result.items[0].id == active.id

        # opt-in — both packets returned
        result = await repo.filter(
            PacketFilterRequest(workspace_id=workspace_id, include_deleted=True)
        )
        result_ids = {item.id for item in result.items}
        assert active.id in result_ids
        assert deleted.id in result_ids
