from enum import StrEnum


class AgreementUiType(StrEnum):
    """Maps Django's ClickwrapType. Controls the UI presentation of the packet."""

    SINGLE_CHECKBOX = "SINGLE_CHECKBOX"
    MULTIPLE_CHECKBOX = "MULTIPLE_CHECKBOX"
    INLINE = "INLINE"


class DomainStatusType(StrEnum):
    """Maps Django's ClickwrapDomainStatusType. Verification state of a custom domain."""

    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"


class AgreementVersionStatus(StrEnum):
    """Maps Django's ClickwrapAgreementVersionStatusType."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    PAST_PUBLISHED = "PAST_PUBLISHED"


class AgreementVersionSource(StrEnum):
    """Maps Django's ClickwrapAgreementVersionSourceType. How the version content was created."""

    EDIT = "EDIT"
    EDITOR = "EDITOR"
    UPLOAD = "UPLOAD"
