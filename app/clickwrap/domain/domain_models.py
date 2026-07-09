import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import AgreementUiType

DEFAULT_CLICKWRAP_TEXT_SINGLE_CHECKBOX = "I agree to {#agreement_list#} as per the laws."
AGREEMENT_ID_REGEX = r"\{#agreement_([1-9]\d*)#\}"
CLICKWRAP_DOMAIN_VALIDATION_REGEX = (
    r"^(?!.*\.\.)(?!.*-$)(?!.*_$)(?!.*\.$)(?!-)(?!_)"
    r"[a-zA-Z0-9_](?:[a-zA-Z0-9_-]*[a-zA-Z0-9_]\.)+[a-zA-Z]{1,63}$"
)


class ClickwrapTextDomainModel(BaseModel):
    text: str = Field(min_length=1)


class PacketSettingsDomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: AgreementUiType
    clickwrap_texts: list[ClickwrapTextDomainModel]
    whitelisted_domains: list[str] = Field(default_factory=list)
    allow_all_domains: bool = False
    send_executed_audit_email: bool = False
    show_audit_click_status: bool = False

    @field_validator("whitelisted_domains")
    @classmethod
    def validate_whitelisted_domains(cls, domains: list[str]) -> list[str]:
        for domain in domains:
            if not re.match(CLICKWRAP_DOMAIN_VALIDATION_REGEX, domain):
                raise ValueError(f"Invalid domain in settings: {domain}.")
        return domains

    @model_validator(mode="after")
    def validate_clickwrap_texts_for_type(self) -> "PacketSettingsDomainModel":
        _validate_clickwrap_texts_for_type(self.type, self.clickwrap_texts)
        return self


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

    settings: PacketSettingsDomainModel | None = None


class PacketListDomainModel(BaseModel):
    items: list[PacketDomainModel]


class PacketFilterRequest(BaseModel):
    workspace_id: int
    packet_ids: list[int] | None = None
    name_slugs: list[str] | None = None
    include_deleted: bool = False


class PacketCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)


class PacketSettingsUpdateRequest(BaseModel):
    type: AgreementUiType | None = None
    whitelisted_domains: list[str] | None = None
    clickwrap_texts: list[ClickwrapTextDomainModel] | None = None
    send_executed_audit_email: bool | None = None
    show_audit_click_status: bool | None = None
    allow_all_domains: bool | None = None

    @field_validator("whitelisted_domains")
    @classmethod
    def validate_whitelisted_domains(cls, domains: list[str] | None) -> list[str] | None:
        if domains is None:
            return None
        for domain in domains:
            if not re.match(CLICKWRAP_DOMAIN_VALIDATION_REGEX, domain):
                raise ValueError(f"Invalid domain in settings: {domain}.")
        return domains

    @model_validator(mode="after")
    def validate_optional_clickwrap_texts(self) -> "PacketSettingsUpdateRequest":
        if self.clickwrap_texts is None:
            return self
        ui_type = self.type or AgreementUiType.SINGLE_CHECKBOX
        _validate_clickwrap_texts_for_type(ui_type, self.clickwrap_texts)
        return self


class PacketUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    settings: PacketSettingsUpdateRequest | None = None


class PacketPaginatedRequest(BaseModel):
    workspace_id: int
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)


class PacketMinimalDomainModel(BaseModel):
    id: int
    name: str
    description: str | None
    created_by_org_user_id: int
    updated_by_org_user_at: datetime | None
    public_id: uuid.UUID


class PacketPaginatedListDomainModel(BaseModel):
    page: int
    limit: int
    total_results: int
    results: list[PacketMinimalDomainModel]


class AgreementVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str | None
    modified_by_org_user_at: datetime | None = None
    version_number: int
    sub_version_number: int
    public_url: str | None = None

    @property
    def full_version_number(self) -> str:
        return f"{self.version_number}.{self.sub_version_number}"


class AgreementSummary(BaseModel):
    id: int
    current_version: AgreementVersionSummary | None = None


class PacketDetailDomainModel(BaseModel):
    id: int
    name: str
    name_slug: str
    description: str | None
    public_id: uuid.UUID
    workspace_id: int
    settings: PacketSettingsDomainModel
    created_by_org_user_id: int
    updated_by_org_user_id: int | None
    updated_by_org_user_at: datetime | None
    agreements: list[AgreementSummary] = Field(default_factory=list)


class PacketAgreementMappingDomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    packet_id: int
    agreement_id: int
    workspace_id: int
    created_by_org_user_id: int


class PacketAgreementMappingListDomainModel(BaseModel):
    items: list[PacketAgreementMappingDomainModel]


class PacketMappingsUpdateRequest(BaseModel):
    add_agreement_ids: list[int] | None = None
    remove_agreement_ids: list[int] | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "PacketMappingsUpdateRequest":
        if not self.add_agreement_ids and not self.remove_agreement_ids:
            raise ValueError(
                "At least one of add_agreement_ids or remove_agreement_ids must be present"
            )
        return self


def _validate_clickwrap_texts_for_type(
    ui_type: AgreementUiType, clickwrap_texts: list[ClickwrapTextDomainModel]
) -> None:
    if ui_type in (AgreementUiType.SINGLE_CHECKBOX, AgreementUiType.INLINE):
        if len(clickwrap_texts) > 1:
            raise ValueError(
                "clickwrap_texts cannot have more than one item when type is single checkbox/inline"
            )
        if "{#agreement_list#}" not in clickwrap_texts[0].text:
            raise ValueError(
                "Compulsory to have agreement_list in text field when type is single checkbox/inline"
            )
        if re.search(AGREEMENT_ID_REGEX, clickwrap_texts[0].text):
            raise ValueError(
                "Not allowed to have agreement_id in text field when type is single checkbox/inline"
            )
        return

    if ui_type == AgreementUiType.MULTIPLE_CHECKBOX:
        if len(clickwrap_texts) == 1:
            raise ValueError("clickwrap_texts cannot have one item when type is multiple checkbox")
        for clickwrap_text in clickwrap_texts:
            if "{#agreement_list#}" in clickwrap_text.text:
                raise ValueError(
                    "Not allowed to have agreement_list in text field when type is multiple checkbox"
                )
            if not re.search(AGREEMENT_ID_REGEX, clickwrap_text.text):
                raise ValueError(
                    "Compulsory to have agreement_id in text field when type is multiple checkbox"
                )
