"""
Postgres ORM models for the tars control-plane.

All 10 tables live in this single file — same pattern as Django's per-app
models.py. Module packages (clickwrap/, agreement/, legal_hub/) import from
here for queries; they do not define their own ORM models.

Table mapping from Django clickwraps/models.py:
  Clickwrap                           -> packet
  ClickwrapSettings                   -> packet_settings
  ClickwrapDomainSetting              -> domain_setting
  ClickwrapAgreementWhitelabelConfig  -> whitelabel_config
  ClickwrapAgreementMapping           -> packet_agreement_mapping
  ClickwrapAgreement                  -> agreement
  ClickwrapAgreementVersion           -> agreement_version
  ClickwrapLegalHub                   -> legal_hub
  ClickwrapLegalHubAgreementMapping   -> legal_hub_agreement_mapping
  ClickwrapLegalHubAgreementCustomURLMapping -> legal_hub_custom_url_mapping

Not migrated (replaced by Firestore):
  ClickwrapConsent, ClickwrapUser, ClickwrapConsentAgreementVersionMapping

FK policy:
  - Tables defined in this file use DB-level ForeignKey constraints.
  - Cross-service references (workspace_id, org_user_id, etc.) are raw
    BigInteger columns — integrity enforced at the application layer.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.enums import (
    AgreementUiType,
    AgreementVersionSource,
    AgreementVersionStatus,
    DomainStatusType,
)
from app.db.postgres import RuntimeBaseModel, SoftDeleteMixin

# ---------------------------------------------------------------------------
# packet_settings  (Django: ClickwrapSettings)
# Holds UI / domain configuration for a packet. Created before the packet
# and referenced via a FK on packet. 1:1 relationship.
# ---------------------------------------------------------------------------


class PacketSettings(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "packet_settings"

    agreement_ui_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AgreementUiType.SINGLE_CHECKBOX,
        server_default=AgreementUiType.SINGLE_CHECKBOX,
        comment="Maps ClickwrapType — controls SDK presentation",
    )
    clickwrap_texts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    whitelisted_domains: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    show_audit_click_status: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    send_executed_audit_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    allow_all_domains: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


# ---------------------------------------------------------------------------
# packet  (Django: Clickwrap)
# Top-level container. Holds a reference to its settings via packet_settings_id.
# contract_type FK removed per design decision.
# ---------------------------------------------------------------------------


class Packet(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "packet"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid.uuid4,
        comment="Stable public identifier exposed to SDK callers",
    )
    packet_settings_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packet_settings.id"), nullable=False, unique=True
    )
    updated_by_org_user_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Last time an org user explicitly saved changes",
    )

    __table_args__ = (
        Index(
            "packet_name_unique_per_workspace",
            "workspace_id",
            "name_slug",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("packet_workspace_idx", "workspace_id"),
        Index(
            "packet_name_slug_gin_idx",
            "name_slug",
            postgresql_using="gin",
            postgresql_ops={"name_slug": "gin_trgm_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# domain_setting  (Django: ClickwrapDomainSetting)
# Custom domain verification record per workspace.
# ---------------------------------------------------------------------------


class DomainSetting(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "domain_setting"

    custom_domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    custom_domain_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DomainStatusType.DRAFT,
        server_default=DomainStatusType.DRAFT,
    )
    default_domain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "Set by the service from settings.CLUSTER_ID on creation. "
            "Format: clickwrap.{cluster_id}.spotdraft.com"
        ),
    )

    __table_args__ = (
        # Maps Django's custom_domain_unique_per_workspace
        Index(
            "domain_setting_custom_domain_unique_per_workspace",
            "workspace_id",
            "custom_domain",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # Maps Django's cwd_index_workspace_index
        Index("domain_setting_workspace_idx", "workspace_id"),
        # Maps Django's cwd_index_custom_domain
        Index("domain_setting_custom_domain_idx", "custom_domain"),
    )


# ---------------------------------------------------------------------------
# whitelabel_config  (Django: ClickwrapAgreementWhitelabelConfig)
# GCS paths stored as Text — same as what Django FileField persists in the DB.
# Upload logic and favicon validation live in the use-case / Pydantic layer.
# ---------------------------------------------------------------------------


class WhitelabelConfig(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "whitelabel_config"

    company_logo: Mapped[str] = mapped_column(
        Text, nullable=False, comment="GCS object path for company logo"
    )
    logo_redirect_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_styles: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="Brand CSS overrides e.g. primary_color"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    header_text: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="Legal Hub"
    )
    brand_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    add_footer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    display_dropdown_and_download: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    display_published_agreements: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    favicon_icon: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="GCS object path for favicon (.ico)"
    )

    __table_args__ = (
        Index(
            "whitelabel_config_unique_per_workspace",
            "workspace_id",
            "is_active",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("whitelabel_config_workspace_is_active_idx", "workspace_id", "is_active"),
    )


# ---------------------------------------------------------------------------
# agreement  (Django: ClickwrapAgreement)
# Reusable agreement entity. Can belong to multiple packets via
# packet_agreement_mapping.
# ---------------------------------------------------------------------------


class Agreement(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "agreement"

    url_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    header_code: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Custom HTML injected into the agreement header"
    )
    footer_code: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Custom HTML injected into the agreement footer"
    )

    __table_args__ = (
        Index(
            "agreement_url_slug_unique_per_workspace",
            "workspace_id",
            "url_slug",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )


# ---------------------------------------------------------------------------
# packet_agreement_mapping  (Django: ClickwrapAgreementMapping)
# Junction table linking packets to their agreements.
# ---------------------------------------------------------------------------


class PacketAgreementMapping(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "packet_agreement_mapping"

    packet_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packet.id"), nullable=False
    )
    agreement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agreement.id"), nullable=False
    )

    __table_args__ = (
        Index(
            "packet_agreement_mapping_unique",
            "packet_id",
            "agreement_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("packet_agreement_mapping_packet_idx", "packet_id"),
        Index("packet_agreement_mapping_agreement_idx", "agreement_id"),
    )


# ---------------------------------------------------------------------------
# agreement_version  (Django: ClickwrapAgreementVersion)
# Immutable content snapshot for an agreement. html_content / pdf_document
# are GCS object paths (same storage pattern as Django FileField).
# ---------------------------------------------------------------------------


class AgreementVersion(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "agreement_version"

    agreement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agreement.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="AgreementVersionStatus: DRAFT | PUBLISHED | PAST_PUBLISHED",
    )
    source: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=AgreementVersionSource.EDITOR,
        server_default=AgreementVersionSource.EDITOR,
        comment="AgreementVersionSource: EDIT | EDITOR | UPLOAD",
    )
    # GCS object paths — equivalent to Django FileField column values
    html_content: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="GCS object path for the HTML version file"
    )
    pdf_document: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="GCS object path for the PDF version file"
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_current: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid.uuid4,
    )
    modified_by_org_user_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Raw bigint — references OrganizationUser which lives in Django, not here
    published_by_org_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    is_re_acceptance_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        Index(
            "agreement_version_unique_version_number",
            "version_number",
            "sub_version_number",
            "agreement_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # Maps Django's unique_status_equals_published_per_agreement
        Index(
            "agreement_version_unique_published_per_agreement",
            "agreement_id",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED' AND is_deleted = false"),
        ),
        # Maps Django's unique_status_equals_draft_per_agreement
        Index(
            "agreement_version_unique_draft_per_agreement",
            "agreement_id",
            unique=True,
            postgresql_where=text("status = 'DRAFT' AND is_deleted = false"),
        ),
        # Maps Django's cw_agg_ver_name_slug_gin_index
        # Requires pg_trgm extension (enabled in migration)
        Index(
            "agreement_version_name_slug_gin_idx",
            "name_slug",
            postgresql_using="gin",
            postgresql_ops={"name_slug": "gin_trgm_ops"},
        ),
    )


# ---------------------------------------------------------------------------
# legal_hub  (Django: ClickwrapLegalHub)
# Curated collection of agreements surfaced as a hosted page.
# ---------------------------------------------------------------------------


class LegalHub(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "legal_hub"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Renamed from Django's `default` field (reserved word)",
    )

    __table_args__ = (
        Index(
            "legal_hub_slug_unique_per_workspace",
            "workspace_id",
            "url_slug",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # Maps Django's lh_name_unique_per_workspace (Lower(F("name")))
        Index(
            "legal_hub_name_unique_per_workspace",
            func.lower(name),
            "workspace_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # Maps Django's lh_one_default_per_workspace
        Index(
            "legal_hub_one_default_per_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_deleted = false AND is_default = true"),
        ),
        # Maps Django's legal_hub_name_index
        Index("legal_hub_name_idx", "name"),
        # Maps Django's legal_hub_url_slug_index
        Index("legal_hub_url_slug_idx", "url_slug"),
    )


# ---------------------------------------------------------------------------
# legal_hub_agreement_mapping  (Django: ClickwrapLegalHubAgreementMapping)
# Ordered list of agreements within a legal hub.
# ---------------------------------------------------------------------------


class LegalHubAgreementMapping(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "legal_hub_agreement_mapping"

    legal_hub_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("legal_hub.id"), nullable=False
    )
    agreement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agreement.id"), nullable=False
    )
    display_order: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Renamed from Django's `order` field (reserved SQL word)",
    )

    __table_args__ = (
        Index(
            "legal_hub_agreement_mapping_unique",
            "agreement_id",
            "legal_hub_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("legal_hub_agreement_mapping_hub_idx", "legal_hub_id"),
        Index("legal_hub_agreement_mapping_agreement_idx", "agreement_id"),
    )


# ---------------------------------------------------------------------------
# legal_hub_custom_url_mapping  (Django: ClickwrapLegalHubAgreementCustomURLMapping)
# Custom URI routing for individual agreements within a legal hub.
# ---------------------------------------------------------------------------


class LegalHubCustomUrlMapping(SoftDeleteMixin, RuntimeBaseModel):
    __tablename__ = "legal_hub_custom_url_mapping"

    custom_uri: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_hub_agreement_mapping_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("legal_hub_agreement_mapping.id"), nullable=True
    )

    __table_args__ = (
        Index(
            "legal_hub_custom_url_unique_per_agreement",
            "custom_uri",
            "legal_hub_agreement_mapping_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("legal_hub_custom_url_mapping_uri_idx", "custom_uri"),
    )
