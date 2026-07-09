import logging
import math
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clickwrap.domain.domain_models import (
    DEFAULT_CLICKWRAP_TEXT_SINGLE_CHECKBOX,
    AgreementSummary,
    AgreementVersionSummary,
    ClickwrapTextDomainModel,
    PacketAgreementMappingDomainModel,
    PacketAgreementMappingListDomainModel,
    PacketCreateRequest,
    PacketDetailDomainModel,
    PacketDomainModel,
    PacketFilterRequest,
    PacketListDomainModel,
    PacketMappingsUpdateRequest,
    PacketMinimalDomainModel,
    PacketPaginatedListDomainModel,
    PacketPaginatedRequest,
    PacketSettingsDomainModel,
    PacketUpdateRequest,
)
from app.clickwrap.exceptions import (
    AgreementNotFoundError,
    PacketNotFoundError,
    PacketPaginationError,
)
from app.db.enums import AgreementUiType, AgreementVersionStatus
from app.db.models import (
    Agreement,
    AgreementVersion,
    Packet,
    PacketAgreementMapping,
    PacketSettings,
)

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[-\s]+", "-", value)
    return value.strip("-")


class PacketDBRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def filter(self, request: PacketFilterRequest) -> PacketListDomainModel:
        """
        Returns packets for the given workspace, ordered by id descending
        (most recently created first).

        Workspace isolation is always applied — request.workspace_id is a
        required field and is always included in the WHERE clause.
        """
        query = self._base_filter_query(request)
        result = await self._session.execute(query)
        packets = result.scalars().unique().all()

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
            items=[self._to_packet_domain(p, include_settings=False) for p in packets]
        )

    async def get_count(self, request: PacketFilterRequest) -> int:
        query = select(func.count()).select_from(Packet)
        if not request.include_deleted:
            query = query.where(Packet.is_deleted.is_(False))
        query = query.where(Packet.workspace_id == request.workspace_id)
        if request.packet_ids is not None:
            query = query.where(Packet.id.in_(request.packet_ids))
        if request.name_slugs is not None:
            query = query.where(Packet.name_slug.in_(request.name_slugs))

        result = await self._session.execute(query)
        return int(result.scalar_one())

    async def get_by_id(self, packet_id: int, workspace_id: int) -> PacketDomainModel:
        packet = await self._get_packet_orm(
            packet_id=packet_id, workspace_id=workspace_id, load_settings=True
        )
        settings = await self._get_settings_orm(packet.packet_settings_id, workspace_id)
        return self._to_packet_domain(packet, settings=settings, include_settings=True)

    async def get_detail(self, packet_id: int, workspace_id: int) -> PacketDetailDomainModel:
        packet = await self._get_packet_orm(
            packet_id=packet_id, workspace_id=workspace_id, load_settings=True
        )
        agreements = await self._get_mapped_agreement_summaries(
            packet_id=packet_id, workspace_id=workspace_id
        )
        settings = self._to_settings_domain(
            await self._get_settings_orm(packet.packet_settings_id, workspace_id)
        )
        return PacketDetailDomainModel(
            id=packet.id,
            name=packet.name,
            name_slug=packet.name_slug,
            description=packet.description,
            public_id=packet.public_id,
            workspace_id=packet.workspace_id,
            settings=settings,
            created_by_org_user_id=packet.created_by_org_user_id,
            updated_by_org_user_id=packet.updated_by_org_user_id,
            updated_by_org_user_at=packet.updated_by_org_user_at,
            agreements=agreements,
        )

    async def get_paginated_list(
        self, request: PacketPaginatedRequest
    ) -> PacketPaginatedListDomainModel:
        filter_request = PacketFilterRequest(workspace_id=request.workspace_id)
        total_results = await self.get_count(filter_request)
        total_pages = max(1, math.ceil(total_results / request.limit)) if total_results else 1
        if request.page > total_pages and total_results > 0:
            raise PacketPaginationError()

        offset = (request.page - 1) * request.limit
        query = (
            Packet.objects()
            .where(Packet.workspace_id == request.workspace_id)
            .order_by(Packet.id.desc())
            .offset(offset)
            .limit(request.limit)
        )
        result = await self._session.execute(query)
        packets = result.scalars().all()

        return PacketPaginatedListDomainModel(
            page=request.page,
            limit=request.limit,
            total_results=total_results,
            results=[
                PacketMinimalDomainModel(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    created_by_org_user_id=p.created_by_org_user_id,
                    updated_by_org_user_at=p.updated_by_org_user_at,
                    public_id=p.public_id,
                )
                for p in packets
            ],
        )

    async def create(
        self,
        request: PacketCreateRequest,
        workspace_id: int,
        org_user_id: int,
    ) -> PacketDomainModel:
        now = datetime.now(UTC).replace(tzinfo=None)
        settings = PacketSettings(
            workspace_id=workspace_id,
            created_by_org_user_id=org_user_id,
            updated_by_org_user_id=org_user_id,
            agreement_ui_type=AgreementUiType.SINGLE_CHECKBOX,
            clickwrap_texts=[{"text": DEFAULT_CLICKWRAP_TEXT_SINGLE_CHECKBOX}],
            whitelisted_domains=[],
            show_audit_click_status=False,
            send_executed_audit_email=False,
            allow_all_domains=False,
        )
        self._session.add(settings)
        await self._session.flush()

        packet = Packet(
            workspace_id=workspace_id,
            created_by_org_user_id=org_user_id,
            updated_by_org_user_id=org_user_id,
            updated_by_org_user_at=now,
            name=request.name,
            name_slug=slugify(request.name),
            description=request.description,
            public_id=uuid.uuid4(),
            packet_settings_id=settings.id,
        )
        self._session.add(packet)
        await self._session.flush()
        await self._session.refresh(packet)
        await self._session.refresh(settings)

        logger.info(
            "PacketDBRepository.create completed",
            extra={
                "workspace_id": workspace_id,
                "packet_id": packet.id,
                "org_user_id": org_user_id,
            },
        )
        return self._to_packet_domain(packet, settings=settings, include_settings=True)

    async def update(
        self,
        packet_id: int,
        workspace_id: int,
        org_user_id: int,
        request: PacketUpdateRequest,
    ) -> PacketDomainModel:
        packet = await self._get_packet_orm(
            packet_id=packet_id, workspace_id=workspace_id, load_settings=True
        )
        settings = await self._get_settings_orm(packet.packet_settings_id, workspace_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        if request.name is not None:
            packet.name = request.name
            packet.name_slug = slugify(request.name)
        if request.description is not None:
            packet.description = request.description

        if request.settings is not None:
            settings_update = request.settings
            if settings_update.type is not None:
                settings.agreement_ui_type = settings_update.type
            if settings_update.whitelisted_domains is not None:
                settings.whitelisted_domains = settings_update.whitelisted_domains
            if settings_update.clickwrap_texts is not None:
                settings.clickwrap_texts = [
                    {"text": item.text} for item in settings_update.clickwrap_texts
                ]
            if settings_update.send_executed_audit_email is not None:
                settings.send_executed_audit_email = settings_update.send_executed_audit_email
            if settings_update.show_audit_click_status is not None:
                settings.show_audit_click_status = settings_update.show_audit_click_status
            if settings_update.allow_all_domains is not None:
                settings.allow_all_domains = settings_update.allow_all_domains
            settings.updated_by_org_user_id = org_user_id

        packet.updated_by_org_user_id = org_user_id
        packet.updated_by_org_user_at = now

        await self._session.flush()
        await self._session.refresh(packet)
        await self._session.refresh(settings)

        logger.info(
            "PacketDBRepository.update completed",
            extra={
                "workspace_id": workspace_id,
                "packet_id": packet.id,
                "org_user_id": org_user_id,
            },
        )
        return self._to_packet_domain(packet, settings=settings, include_settings=True)

    async def update_mappings(
        self,
        packet_id: int,
        workspace_id: int,
        org_user_id: int,
        request: PacketMappingsUpdateRequest,
    ) -> PacketAgreementMappingListDomainModel:
        await self._get_packet_orm(
            packet_id=packet_id, workspace_id=workspace_id, load_settings=False
        )

        if request.remove_agreement_ids:
            await self._soft_delete_mappings(
                packet_id=packet_id,
                workspace_id=workspace_id,
                org_user_id=org_user_id,
                agreement_ids=request.remove_agreement_ids,
            )

        if request.add_agreement_ids:
            await self._add_mappings(
                packet_id=packet_id,
                workspace_id=workspace_id,
                org_user_id=org_user_id,
                agreement_ids=request.add_agreement_ids,
            )

        return await self.list_mappings(packet_id=packet_id, workspace_id=workspace_id)

    async def list_mappings(
        self, packet_id: int, workspace_id: int
    ) -> PacketAgreementMappingListDomainModel:
        query = (
            PacketAgreementMapping.objects()
            .where(PacketAgreementMapping.workspace_id == workspace_id)
            .where(PacketAgreementMapping.packet_id == packet_id)
            .order_by(PacketAgreementMapping.id.asc())
        )
        result = await self._session.execute(query)
        mappings = result.scalars().all()
        return PacketAgreementMappingListDomainModel(
            items=[
                PacketAgreementMappingDomainModel.model_validate(mapping) for mapping in mappings
            ]
        )

    def _base_filter_query(self, request: PacketFilterRequest):
        base = Packet.objects_including_deleted() if request.include_deleted else Packet.objects()
        query = base.where(Packet.workspace_id == request.workspace_id).order_by(Packet.id.desc())
        if request.packet_ids is not None:
            query = query.where(Packet.id.in_(request.packet_ids))
        if request.name_slugs is not None:
            query = query.where(Packet.name_slug.in_(request.name_slugs))
        return query

    async def _get_packet_orm(
        self, packet_id: int, workspace_id: int, load_settings: bool
    ) -> Packet:
        query = (
            Packet.objects()
            .where(Packet.id == packet_id)
            .where(Packet.workspace_id == workspace_id)
        )
        result = await self._session.execute(query)
        packet = result.scalar_one_or_none()
        if packet is None:
            raise PacketNotFoundError(packet_id)
        if load_settings:
            # Ensure settings row is loaded in the same session
            await self._get_settings_orm(packet.packet_settings_id, workspace_id)
        return packet

    async def _get_settings_orm(self, settings_id: int, workspace_id: int) -> PacketSettings:
        query = (
            PacketSettings.objects()
            .where(PacketSettings.id == settings_id)
            .where(PacketSettings.workspace_id == workspace_id)
        )
        result = await self._session.execute(query)
        settings = result.scalar_one_or_none()
        if settings is None:
            raise PacketNotFoundError()
        return settings

    async def _get_mapped_agreement_summaries(
        self, packet_id: int, workspace_id: int
    ) -> list[AgreementSummary]:
        mapping_query = (
            PacketAgreementMapping.objects()
            .where(PacketAgreementMapping.packet_id == packet_id)
            .where(PacketAgreementMapping.workspace_id == workspace_id)
            .order_by(PacketAgreementMapping.id.asc())
        )
        mapping_result = await self._session.execute(mapping_query)
        mappings = mapping_result.scalars().all()
        if not mappings:
            return []

        agreement_ids = [m.agreement_id for m in mappings]
        agreement_query = (
            Agreement.objects()
            .where(Agreement.workspace_id == workspace_id)
            .where(Agreement.id.in_(agreement_ids))
        )
        agreement_result = await self._session.execute(agreement_query)
        agreements = {agreement.id: agreement for agreement in agreement_result.scalars().all()}

        version_query = (
            AgreementVersion.objects()
            .where(AgreementVersion.workspace_id == workspace_id)
            .where(AgreementVersion.agreement_id.in_(agreement_ids))
            .where(AgreementVersion.is_current.is_(True))
            .where(AgreementVersion.status == AgreementVersionStatus.PUBLISHED)
        )
        version_result = await self._session.execute(version_query)
        versions = {version.agreement_id: version for version in version_result.scalars().all()}

        summaries: list[AgreementSummary] = []
        for mapping in mappings:
            if mapping.agreement_id not in agreements:
                continue
            version = versions.get(mapping.agreement_id)
            summaries.append(
                AgreementSummary(
                    id=mapping.agreement_id,
                    current_version=(
                        AgreementVersionSummary(
                            id=version.id,
                            name=version.name,
                            status=version.status,
                            modified_by_org_user_at=version.modified_by_org_user_at,
                            version_number=version.version_number,
                            sub_version_number=version.sub_version_number,
                            public_url=None,
                        )
                        if version is not None
                        else None
                    ),
                )
            )
        return summaries

    async def _soft_delete_mappings(
        self,
        packet_id: int,
        workspace_id: int,
        org_user_id: int,
        agreement_ids: list[int],
    ) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        query = (
            PacketAgreementMapping.objects()
            .where(PacketAgreementMapping.packet_id == packet_id)
            .where(PacketAgreementMapping.workspace_id == workspace_id)
            .where(PacketAgreementMapping.agreement_id.in_(agreement_ids))
        )
        result = await self._session.execute(query)
        mappings = result.scalars().all()
        for mapping in mappings:
            mapping.is_deleted = True
            mapping.deleted_at = now
            mapping.deleted_by_org_user_id = org_user_id
            mapping.updated_by_org_user_id = org_user_id
        await self._session.flush()

    async def _add_mappings(
        self,
        packet_id: int,
        workspace_id: int,
        org_user_id: int,
        agreement_ids: list[int],
    ) -> None:
        unique_ids = list(dict.fromkeys(agreement_ids))
        agreement_query = (
            Agreement.objects()
            .where(Agreement.workspace_id == workspace_id)
            .where(Agreement.id.in_(unique_ids))
        )
        agreement_result = await self._session.execute(agreement_query)
        found_ids = {agreement.id for agreement in agreement_result.scalars().all()}
        missing = [agreement_id for agreement_id in unique_ids if agreement_id not in found_ids]
        if missing:
            raise AgreementNotFoundError(missing[0])

        existing_query = (
            PacketAgreementMapping.objects()
            .where(PacketAgreementMapping.packet_id == packet_id)
            .where(PacketAgreementMapping.workspace_id == workspace_id)
            .where(PacketAgreementMapping.agreement_id.in_(unique_ids))
        )
        existing_result = await self._session.execute(existing_query)
        already_mapped = {mapping.agreement_id for mapping in existing_result.scalars().all()}

        for agreement_id in unique_ids:
            if agreement_id in already_mapped:
                continue
            self._session.add(
                PacketAgreementMapping(
                    workspace_id=workspace_id,
                    created_by_org_user_id=org_user_id,
                    updated_by_org_user_id=org_user_id,
                    packet_id=packet_id,
                    agreement_id=agreement_id,
                )
            )
        await self._session.flush()

    def _to_settings_domain(self, settings: PacketSettings) -> PacketSettingsDomainModel:
        raw_texts = settings.clickwrap_texts or []
        clickwrap_texts = [
            ClickwrapTextDomainModel(text=item["text"] if isinstance(item, dict) else str(item))
            for item in raw_texts
        ]
        return PacketSettingsDomainModel(
            id=settings.id,
            type=AgreementUiType(settings.agreement_ui_type),
            clickwrap_texts=clickwrap_texts,
            whitelisted_domains=list(settings.whitelisted_domains or []),
            allow_all_domains=settings.allow_all_domains,
            send_executed_audit_email=settings.send_executed_audit_email,
            show_audit_click_status=settings.show_audit_click_status,
        )

    def _to_packet_domain(
        self,
        packet: Packet,
        *,
        settings: PacketSettings | None = None,
        include_settings: bool,
    ) -> PacketDomainModel:
        return PacketDomainModel(
            id=packet.id,
            workspace_id=packet.workspace_id,
            name=packet.name,
            name_slug=packet.name_slug,
            description=packet.description,
            public_id=packet.public_id,
            packet_settings_id=packet.packet_settings_id,
            created_by_org_user_id=packet.created_by_org_user_id,
            updated_by_org_user_id=packet.updated_by_org_user_id,
            updated_by_org_user_at=packet.updated_by_org_user_at,
            created_at=packet.created_at,
            updated_at=packet.updated_at,
            is_deleted=packet.is_deleted,
            deleted_at=packet.deleted_at,
            deleted_by_org_user_id=packet.deleted_by_org_user_id,
            settings=self._to_settings_domain(settings) if include_settings and settings else None,
        )
