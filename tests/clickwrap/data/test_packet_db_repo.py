import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.data.postgres.db_repo import PacketDBRepository
from app.clickwrap.domain.domain_models import (
    ClickwrapTextDomainModel,
    PacketCreateRequest,
    PacketFilterRequest,
    PacketMappingsUpdateRequest,
    PacketPaginatedRequest,
    PacketSettingsUpdateRequest,
    PacketUpdateRequest,
)
from app.clickwrap.exceptions import (
    AgreementNotFoundError,
    PacketNotFoundError,
    PacketPaginationError,
)
from app.db.enums import AgreementUiType, AgreementVersionStatus
from app.db.models import Agreement, AgreementVersion, PacketAgreementMapping
from tests.base_db_repo_test import BaseDBRepoTestCase
from tests.factories import PacketFactory


class TestPacketDBRepository(BaseDBRepoTestCase):
    async def test_filter_workspace_isolation(self, db_session: AsyncSession):
        ws_a, ws_b = 100, 101
        packet_a1 = await PacketFactory.create(db_session, workspace_id=ws_a)
        packet_a2 = await PacketFactory.create(db_session, workspace_id=ws_a)
        await PacketFactory.create(db_session, workspace_id=ws_b)

        repo = PacketDBRepository(db_session)
        result = await repo.filter(PacketFilterRequest(workspace_id=ws_a))

        assert [p.id for p in result.items] == [packet_a2.id, packet_a1.id]

    async def test_filter_by_packet_ids(self, db_session: AsyncSession):
        """
        When packet_ids is provided, only those IDs are returned.
        Cross-workspace IDs are silently excluded (workspace isolation still
        applies even when an explicit ID list is passed).
        """
        ws_a, ws_b = 200, 201
        packet_a1 = await PacketFactory.create(db_session, workspace_id=ws_a)
        packet_a2 = await PacketFactory.create(db_session, workspace_id=ws_a)
        packet_b = await PacketFactory.create(db_session, workspace_id=ws_b)

        repo = PacketDBRepository(db_session)

        result = await repo.filter(
            PacketFilterRequest(workspace_id=ws_a, packet_ids=[packet_a1.id])
        )
        assert len(result.items) == 1
        assert result.items[0].id == packet_a1.id

        result = await repo.filter(
            PacketFilterRequest(workspace_id=ws_a, packet_ids=[packet_a2.id, packet_b.id])
        )
        assert len(result.items) == 1
        assert result.items[0].id == packet_a2.id

    async def test_filter_soft_delete_behaviour(self, db_session: AsyncSession):
        """
        Soft-deleted packets are excluded by default (Packet.objects()).
        Passing include_deleted=True switches to Packet.objects_including_deleted()
        and returns all packets regardless of deletion status.
        """
        workspace_id = 300
        active = await PacketFactory.create(db_session, workspace_id=workspace_id)
        deleted = await PacketFactory.create(db_session, workspace_id=workspace_id, is_deleted=True)

        repo = PacketDBRepository(db_session)

        default_result = await repo.filter(PacketFilterRequest(workspace_id=workspace_id))
        assert [p.id for p in default_result.items] == [active.id]

        including_deleted = await repo.filter(
            PacketFilterRequest(workspace_id=workspace_id, include_deleted=True)
        )
        assert {p.id for p in including_deleted.items} == {active.id, deleted.id}

    async def test_create_packet_with_default_settings(self, db_session: AsyncSession):
        repo = PacketDBRepository(db_session)
        created = await repo.create(
            request=PacketCreateRequest(
                name="Vendor Onboarding",
                description="Onboarding pack",
            ),
            workspace_id=42,
            org_user_id=7,
        )

        assert created.id > 0
        assert created.workspace_id == 42
        assert created.name == "Vendor Onboarding"
        assert created.name_slug == "vendor-onboarding"
        assert created.description == "Onboarding pack"
        assert created.created_by_org_user_id == 7
        assert created.updated_by_org_user_id == 7
        assert created.settings is not None
        assert created.settings.type == AgreementUiType.SINGLE_CHECKBOX
        assert created.settings.clickwrap_texts[0].text == (
            "I agree to {#agreement_list#} as per the laws."
        )

        fetched = await repo.get_by_id(packet_id=created.id, workspace_id=42)
        assert fetched.id == created.id
        assert fetched.settings is not None
        assert fetched.settings.id == created.settings.id

    async def test_get_by_id_raises_for_other_workspace(self, db_session: AsyncSession):
        packet = await PacketFactory.create(db_session, workspace_id=10)
        repo = PacketDBRepository(db_session)

        with pytest.raises(PacketNotFoundError):
            await repo.get_by_id(packet_id=packet.id, workspace_id=99)

    async def test_get_by_id_excludes_soft_deleted(self, db_session: AsyncSession):
        packet = await PacketFactory.create(db_session, workspace_id=11, is_deleted=True)
        repo = PacketDBRepository(db_session)

        with pytest.raises(PacketNotFoundError):
            await repo.get_by_id(packet_id=packet.id, workspace_id=11)

    async def test_get_count_by_name_slug(self, db_session: AsyncSession):
        await PacketFactory.create(db_session, workspace_id=12, name_slug="vendor-onboarding")
        repo = PacketDBRepository(db_session)

        count = await repo.get_count(
            PacketFilterRequest(workspace_id=12, name_slugs=["vendor-onboarding"])
        )
        assert count == 1

        other = await repo.get_count(PacketFilterRequest(workspace_id=12, name_slugs=["missing"]))
        assert other == 0

    async def test_get_paginated_list(self, db_session: AsyncSession):
        workspace_id = 13
        p1 = await PacketFactory.create(db_session, workspace_id=workspace_id)
        p2 = await PacketFactory.create(db_session, workspace_id=workspace_id)
        p3 = await PacketFactory.create(db_session, workspace_id=workspace_id)
        repo = PacketDBRepository(db_session)

        page_1 = await repo.get_paginated_list(
            PacketPaginatedRequest(workspace_id=workspace_id, page=1, limit=2)
        )
        assert page_1.total_results == 3
        assert [r.id for r in page_1.results] == [p3.id, p2.id]

        page_2 = await repo.get_paginated_list(
            PacketPaginatedRequest(workspace_id=workspace_id, page=2, limit=2)
        )
        assert [r.id for r in page_2.results] == [p1.id]

        with pytest.raises(PacketPaginationError):
            await repo.get_paginated_list(
                PacketPaginatedRequest(workspace_id=workspace_id, page=5, limit=2)
            )

    async def test_update_packet_name_and_settings(self, db_session: AsyncSession):
        packet = await PacketFactory.create(
            db_session,
            workspace_id=14,
            name="Old Name",
            name_slug="old-name",
            description="Old desc",
        )
        repo = PacketDBRepository(db_session)

        updated = await repo.update(
            packet_id=packet.id,
            workspace_id=14,
            org_user_id=99,
            request=PacketUpdateRequest(
                name="New Name",
                description="New desc",
                settings=PacketSettingsUpdateRequest(
                    type=AgreementUiType.SINGLE_CHECKBOX,
                    allow_all_domains=True,
                    whitelisted_domains=["app.acme.com"],
                    clickwrap_texts=[
                        ClickwrapTextDomainModel(
                            text="I agree to {#agreement_list#} as per the laws."
                        )
                    ],
                    send_executed_audit_email=True,
                    show_audit_click_status=True,
                ),
            ),
        )

        assert updated.name == "New Name"
        assert updated.name_slug == "new-name"
        assert updated.description == "New desc"
        assert updated.updated_by_org_user_id == 99
        assert updated.settings is not None
        assert updated.settings.allow_all_domains is True
        assert updated.settings.whitelisted_domains == ["app.acme.com"]
        assert updated.settings.send_executed_audit_email is True
        assert updated.settings.show_audit_click_status is True

    async def test_update_mappings_add_and_remove(self, db_session: AsyncSession):
        workspace_id = 15
        org_user_id = 3
        packet = await PacketFactory.create(db_session, workspace_id=workspace_id)
        agreement_1 = await _create_agreement(db_session, workspace_id, org_user_id)
        agreement_2 = await _create_agreement(db_session, workspace_id, org_user_id)
        agreement_3 = await _create_agreement(db_session, workspace_id, org_user_id)

        existing = PacketAgreementMapping(
            workspace_id=workspace_id,
            created_by_org_user_id=org_user_id,
            packet_id=packet.id,
            agreement_id=agreement_1.id,
        )
        db_session.add(existing)
        await db_session.flush()

        repo = PacketDBRepository(db_session)
        result = await repo.update_mappings(
            packet_id=packet.id,
            workspace_id=workspace_id,
            org_user_id=org_user_id,
            request=PacketMappingsUpdateRequest(
                add_agreement_ids=[agreement_2.id, agreement_3.id],
                remove_agreement_ids=[agreement_1.id],
            ),
        )

        assert sorted(m.agreement_id for m in result.items) == [
            agreement_2.id,
            agreement_3.id,
        ]

    async def test_update_mappings_unknown_agreement_raises(self, db_session: AsyncSession):
        packet = await PacketFactory.create(db_session, workspace_id=16)
        repo = PacketDBRepository(db_session)

        with pytest.raises(AgreementNotFoundError):
            await repo.update_mappings(
                packet_id=packet.id,
                workspace_id=16,
                org_user_id=1,
                request=PacketMappingsUpdateRequest(add_agreement_ids=[999999]),
            )

    async def test_get_detail_includes_mapped_agreements(self, db_session: AsyncSession):
        workspace_id = 17
        org_user_id = 4
        packet = await PacketFactory.create(db_session, workspace_id=workspace_id)
        agreement = await _create_agreement(db_session, workspace_id, org_user_id)
        version = await _create_published_version(
            db_session, workspace_id, org_user_id, agreement.id
        )
        db_session.add(
            PacketAgreementMapping(
                workspace_id=workspace_id,
                created_by_org_user_id=org_user_id,
                packet_id=packet.id,
                agreement_id=agreement.id,
            )
        )
        await db_session.flush()

        repo = PacketDBRepository(db_session)
        detail = await repo.get_detail(packet_id=packet.id, workspace_id=workspace_id)

        assert detail.id == packet.id
        assert detail.settings is not None
        assert len(detail.agreements) == 1
        assert detail.agreements[0].id == agreement.id
        assert detail.agreements[0].current_version is not None
        assert detail.agreements[0].current_version.id == version.id


async def _create_agreement(
    session: AsyncSession, workspace_id: int, org_user_id: int
) -> Agreement:
    agreement = Agreement(
        workspace_id=workspace_id,
        created_by_org_user_id=org_user_id,
        url_slug=f"agr-{uuid.uuid4().hex[:12]}",
    )
    session.add(agreement)
    await session.flush()
    await session.refresh(agreement)
    return agreement


async def _create_published_version(
    session: AsyncSession,
    workspace_id: int,
    org_user_id: int,
    agreement_id: int,
) -> AgreementVersion:
    version = AgreementVersion(
        workspace_id=workspace_id,
        created_by_org_user_id=org_user_id,
        agreement_id=agreement_id,
        name="MSA",
        name_slug="msa",
        status=AgreementVersionStatus.PUBLISHED,
        version_number=1,
        sub_version_number=0,
        is_current=True,
        modified_by_org_user_at=datetime.now(UTC).replace(tzinfo=None),
        published_at=datetime.now(UTC).replace(tzinfo=None),
        published_by_org_user_id=org_user_id,
    )
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version
