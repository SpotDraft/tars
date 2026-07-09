from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.clickwrap.domain.domain_models import (
    AgreementSummary,
    AgreementVersionSummary,
    PacketAgreementMappingDomainModel,
    PacketDetailDomainModel,
    PacketDomainModel,
    PacketMinimalDomainModel,
    PacketPaginatedListDomainModel,
    PacketSettingsDomainModel,
)
from app.db.enums import AgreementUiType


class ClickwrapTextResponse(BaseModel):
    text: str


class PacketSettingsResponse(BaseModel):
    id: int
    type: AgreementUiType
    clickwrap_texts: list[ClickwrapTextResponse]
    whitelisted_domains: list[str] = Field(default_factory=list)
    allow_all_domains: bool = False
    send_executed_audit_email: bool = False
    show_audit_click_status: bool = False

    @classmethod
    def from_domain(cls, settings: PacketSettingsDomainModel) -> "PacketSettingsResponse":
        return cls(
            id=settings.id,
            type=settings.type,
            clickwrap_texts=[
                ClickwrapTextResponse(text=item.text) for item in settings.clickwrap_texts
            ],
            whitelisted_domains=settings.whitelisted_domains,
            allow_all_domains=settings.allow_all_domains,
            send_executed_audit_email=settings.send_executed_audit_email,
            show_audit_click_status=settings.show_audit_click_status,
        )


class AgreementVersionResponse(BaseModel):
    id: int
    name: str
    status: str | None
    modified_by_org_user_at: datetime | None = None
    version_number: int
    sub_version_number: int
    public_url: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_version_number(self) -> str:
        return f"{self.version_number}.{self.sub_version_number}"

    @classmethod
    def from_domain(cls, version: AgreementVersionSummary) -> "AgreementVersionResponse":
        return cls(
            id=version.id,
            name=version.name,
            status=version.status,
            modified_by_org_user_at=version.modified_by_org_user_at,
            version_number=version.version_number,
            sub_version_number=version.sub_version_number,
            public_url=version.public_url,
        )


class AgreementResponse(BaseModel):
    id: int
    current_version: AgreementVersionResponse | None = None

    @classmethod
    def from_domain(cls, agreement: AgreementSummary) -> "AgreementResponse":
        return cls(
            id=agreement.id,
            current_version=(
                AgreementVersionResponse.from_domain(agreement.current_version)
                if agreement.current_version is not None
                else None
            ),
        )


class PacketMinimalResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_by_org_user_id: int
    updated_by_org_user_at: datetime | None
    public_id: UUID

    @classmethod
    def from_domain(cls, packet: PacketMinimalDomainModel) -> "PacketMinimalResponse":
        return cls(
            id=packet.id,
            name=packet.name,
            description=packet.description,
            created_by_org_user_id=packet.created_by_org_user_id,
            updated_by_org_user_at=packet.updated_by_org_user_at,
            public_id=packet.public_id,
        )

    @classmethod
    def from_packet_domain(cls, packet: PacketDomainModel) -> "PacketMinimalResponse":
        return cls(
            id=packet.id,
            name=packet.name,
            description=packet.description,
            created_by_org_user_id=packet.created_by_org_user_id,
            updated_by_org_user_at=packet.updated_by_org_user_at,
            public_id=packet.public_id,
        )


class PacketPaginatedResponse(BaseModel):
    page: int
    limit: int
    total_results: int
    results: list[PacketMinimalResponse]

    @classmethod
    def from_domain(cls, page: PacketPaginatedListDomainModel) -> "PacketPaginatedResponse":
        return cls(
            page=page.page,
            limit=page.limit,
            total_results=page.total_results,
            results=[PacketMinimalResponse.from_domain(item) for item in page.results],
        )


class PacketDetailResponse(BaseModel):
    id: int
    name: str
    name_slug: str
    description: str | None
    public_id: UUID
    workspace_id: int
    settings: PacketSettingsResponse
    created_by_org_user_id: int
    updated_by_org_user_id: int | None
    updated_by_org_user_at: datetime | None
    agreements: list[AgreementResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, detail: PacketDetailDomainModel) -> "PacketDetailResponse":
        return cls(
            id=detail.id,
            name=detail.name,
            name_slug=detail.name_slug,
            description=detail.description,
            public_id=detail.public_id,
            workspace_id=detail.workspace_id,
            settings=PacketSettingsResponse.from_domain(detail.settings),
            created_by_org_user_id=detail.created_by_org_user_id,
            updated_by_org_user_id=detail.updated_by_org_user_id,
            updated_by_org_user_at=detail.updated_by_org_user_at,
            agreements=[
                AgreementResponse.from_domain(agreement) for agreement in detail.agreements
            ],
        )


class PacketMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    packet_id: int
    agreement_id: int
    workspace_id: int
    created_by_org_user_id: int

    @classmethod
    def from_domain(cls, mapping: PacketAgreementMappingDomainModel) -> "PacketMappingResponse":
        return cls(
            id=mapping.id,
            packet_id=mapping.packet_id,
            agreement_id=mapping.agreement_id,
            workspace_id=mapping.workspace_id,
            created_by_org_user_id=mapping.created_by_org_user_id,
        )
