
import itertools
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgreementUiType
from app.db.models import Packet, PacketSettings

_counter = itertools.count(1)


def _seq() -> int:
    return next(_counter)

class PacketSettingsFactory:
    @classmethod
    async def create(cls, session: AsyncSession, **kwargs: object) -> PacketSettings:
        n = _seq()
        obj = PacketSettings(
            workspace_id=kwargs.get("workspace_id", n),
            created_by_org_user_id=kwargs.get("created_by_org_user_id", n),
            agreement_ui_type=kwargs.get("agreement_ui_type", AgreementUiType.SINGLE_CHECKBOX),
            clickwrap_texts=kwargs.get("clickwrap_texts", [{"text": "I agree to the terms."}]),
            whitelisted_domains=kwargs.get("whitelisted_domains", []),
            show_audit_click_status=kwargs.get("show_audit_click_status", False),
            send_executed_audit_email=kwargs.get("send_executed_audit_email", False),
            allow_all_domains=kwargs.get("allow_all_domains", False),
            is_deleted=kwargs.get("is_deleted", False),
        )
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

class PacketFactory:
    @classmethod
    async def create(cls, session: AsyncSession, **kwargs: object) -> Packet:
        n = _seq()
        workspace_id: int = int(kwargs.get("workspace_id", n))  # type: ignore[arg-type]

        # SubFactory equivalent: create PacketSettings unless caller supplied one.
        packet_settings = kwargs.get("packet_settings")
        if packet_settings is None:
            packet_settings = await PacketSettingsFactory.create(
                session, workspace_id=workspace_id
            )

        obj = Packet(
            workspace_id=workspace_id,
            created_by_org_user_id=kwargs.get("created_by_org_user_id", n),
            updated_by_org_user_id=kwargs.get("updated_by_org_user_id"),
            name=kwargs.get("name", f"Packet-{n}"),
            name_slug=kwargs.get("name_slug", f"packet-{n}"),
            description=kwargs.get("description"),
            public_id=kwargs.get("public_id", uuid.uuid4()),
            packet_settings_id=packet_settings.id,
            is_deleted=kwargs.get("is_deleted", False),
        )
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj
