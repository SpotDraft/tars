import pytest

from app.core.hmac_auth import (
    build_signature_message,
    compute_signature,
    is_admin_path,
    verify_hmac_headers,
)


@pytest.mark.unit
class TestHMACHelpers:
    def test_is_admin_path(self):
        assert is_admin_path("/api/v2/clickwraps") is True
        assert is_admin_path("/api/v2/clickwraps/1") is True
        assert is_admin_path("/ht") is False
        assert is_admin_path("/api/v3/public/clickwrap/abc") is False

    def test_verify_valid_signature(self):
        secret = "test-secret"
        timestamp = "1710000000"
        method = "POST"
        path = "/api/v2/clickwraps"
        body = '{"name":"A"}'
        signature = compute_signature(
            secret, build_signature_message(timestamp, method, path, body)
        )

        assert (
            verify_hmac_headers(
                method=method,
                path=path,
                body_str=body,
                signature=signature,
                timestamp=timestamp,
                secret=secret,
                tolerance_seconds=300,
                now=1710000000,
            )
            is None
        )

    def test_verify_rejects_bad_signature(self):
        error = verify_hmac_headers(
            method="GET",
            path="/api/v2/clickwraps",
            body_str="",
            signature="nope",
            timestamp="1710000000",
            secret="test-secret",
            tolerance_seconds=300,
            now=1710000000,
        )
        assert error == "Invalid HMAC signature"
