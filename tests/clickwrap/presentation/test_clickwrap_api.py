import json
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db_session
from app.core.hmac_auth import (
    build_signature_message,
    compute_signature,
)
from app.db.models import Agreement, PacketAgreementMapping
from app.main import app
from tests.factories import PacketFactory


def _sign_headers(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    workspace_id: int = 42,
    org_user_id: int = 7,
    timestamp: int | None = None,
    signature: str | None = None,
) -> dict[str, str]:
    body_str = json.dumps(body, sort_keys=True) if body is not None else ""
    ts = str(timestamp if timestamp is not None else int(time.time()))
    message = build_signature_message(ts, method, path, body_str)
    sig = (
        signature
        if signature is not None
        else compute_signature(settings.TARS_HMAC_SECRET, message)
    )
    return {
        "X-Workspace-ID": str(workspace_id),
        "X-Org-User-ID": str(org_user_id),
        "X-User-ID": "100",
        "Content-Type": "application/json",
        "X-Clickwrap-Timestamp": ts,
        "X-Clickwrap-Signature": sig,
    }


@pytest.fixture
async def api_client(db_session: AsyncSession):
    async def _override_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestClickwrapAPI:
    async def test_create_list_get_update_flow(self, api_client):
        create_body = {"name": "Vendor Onboarding", "description": "Pack desc"}
        create_resp = await api_client.post(
            "/api/v2/clickwraps",
            headers=_sign_headers("POST", "/api/v2/clickwraps", create_body),
            content=json.dumps(create_body, sort_keys=True),
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["name"] == "Vendor Onboarding"
        assert created["description"] == "Pack desc"
        assert "contract_type_id" not in created
        packet_id = created["id"]

        list_resp = await api_client.get(
            "/api/v2/clickwraps",
            headers=_sign_headers("GET", "/api/v2/clickwraps"),
            params={"page": 1, "limit": 10},
        )
        assert list_resp.status_code == 200
        listed = list_resp.json()
        assert listed["total_results"] == 1
        assert listed["results"][0]["id"] == packet_id

        get_path = f"/api/v2/clickwraps/{packet_id}"
        get_resp = await api_client.get(
            get_path,
            headers=_sign_headers("GET", get_path),
        )
        assert get_resp.status_code == 200
        detail = get_resp.json()
        assert detail["name"] == "Vendor Onboarding"
        assert detail["settings"]["type"] == "SINGLE_CHECKBOX"
        assert detail["agreements"] == []
        assert "contract_type_id" not in detail

        patch_body = {
            "name": "Vendor Onboarding v2",
            "settings": {
                "allow_all_domains": True,
                "whitelisted_domains": ["app.acme.com"],
            },
        }
        patch_path = f"/api/v2/clickwraps/{packet_id}"
        patch_resp = await api_client.patch(
            patch_path,
            headers=_sign_headers("PATCH", patch_path, patch_body),
            content=json.dumps(patch_body, sort_keys=True),
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["name"] == "Vendor Onboarding v2"
        assert updated["name_slug"] == "vendor-onboarding-v2"
        assert updated["settings"]["allow_all_domains"] is True
        assert updated["settings"]["whitelisted_domains"] == ["app.acme.com"]

    async def test_create_duplicate_name_returns_400(self, api_client, db_session):
        await PacketFactory.create(
            db_session,
            workspace_id=42,
            name="Dup Name",
            name_slug="dup-name",
        )
        body = {"name": "Dup Name", "description": "desc"}
        resp = await api_client.post(
            "/api/v2/clickwraps",
            headers=_sign_headers("POST", "/api/v2/clickwraps", body),
            content=json.dumps(body, sort_keys=True),
        )
        assert resp.status_code == 400
        assert "same name already exists" in resp.json()["detail"]

    async def test_get_missing_packet_returns_404(self, api_client):
        path = "/api/v2/clickwraps/999999"
        resp = await api_client.get(
            path,
            headers=_sign_headers("GET", path),
        )
        assert resp.status_code == 404

    async def test_missing_workspace_header_returns_400(self, api_client):
        headers = _sign_headers("GET", "/api/v2/clickwraps")
        del headers["X-Workspace-ID"]
        resp = await api_client.get(
            "/api/v2/clickwraps",
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_update_mappings(self, api_client, db_session):
        workspace_id = 42
        org_user_id = 7
        packet = await PacketFactory.create(db_session, workspace_id=workspace_id)
        agreement = Agreement(
            workspace_id=workspace_id,
            created_by_org_user_id=org_user_id,
            url_slug="msa-api-test",
        )
        db_session.add(agreement)
        await db_session.flush()

        path = f"/api/v2/clickwraps/{packet.id}/clickwrap-agreement-mappings"
        add_body = {"add_agreement_ids": [agreement.id]}
        add_resp = await api_client.patch(
            path,
            headers=_sign_headers(
                "PATCH",
                path,
                add_body,
                workspace_id=workspace_id,
                org_user_id=org_user_id,
            ),
            content=json.dumps(add_body, sort_keys=True),
        )
        assert add_resp.status_code == 200
        mappings = add_resp.json()
        assert len(mappings) == 1
        assert mappings[0]["agreement_id"] == agreement.id
        assert mappings[0]["packet_id"] == packet.id

        remove_body = {"remove_agreement_ids": [agreement.id]}
        remove_resp = await api_client.patch(
            path,
            headers=_sign_headers(
                "PATCH",
                path,
                remove_body,
                workspace_id=workspace_id,
                org_user_id=org_user_id,
            ),
            content=json.dumps(remove_body, sort_keys=True),
        )
        assert remove_resp.status_code == 200
        assert remove_resp.json() == []

        remaining = (
            (
                await db_session.execute(
                    PacketAgreementMapping.objects().where(
                        PacketAgreementMapping.packet_id == packet.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert remaining == []


@pytest.mark.integration
class TestAdminHMACMiddleware:
    async def test_health_check_skips_hmac(self, api_client):
        resp = await api_client.get("/ht")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_missing_signature_returns_401(self, api_client):
        resp = await api_client.get(
            "/api/v2/clickwraps",
            headers={
                "X-Workspace-ID": "42",
                "X-Org-User-ID": "7",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing HMAC signature headers"

    async def test_invalid_signature_returns_401(self, api_client):
        headers = _sign_headers(
            "GET",
            "/api/v2/clickwraps",
            signature="deadbeef",
        )
        resp = await api_client.get("/api/v2/clickwraps", headers=headers)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid HMAC signature"

    async def test_expired_timestamp_returns_401(self, api_client):
        expired = int(time.time()) - settings.TARS_HMAC_TIMESTAMP_TOLERANCE_SECONDS - 10
        headers = _sign_headers(
            "GET",
            "/api/v2/clickwraps",
            timestamp=expired,
        )
        resp = await api_client.get("/api/v2/clickwraps", headers=headers)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "HMAC timestamp outside allowed window"
