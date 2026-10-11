import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import auth


class Counter:
    def __init__(self):
        self.count = 0
    def incr(self, key):
        self.count += 1
        return self.count
    def expire(self, key, seconds):
        assert seconds == 900
    def close(self):
        pass


def request():
    return Request({"type": "http", "method": "POST", "path": "/api/v1/auth/bootstrap-login",
                    "headers": [], "client": ("127.0.0.1", 12345)})


def test_bootstrap_disabled_by_default(monkeypatch):
    monkeypatch.setattr(auth.settings, "bootstrap_login_enabled", False)
    with pytest.raises(HTTPException) as exc:
        auth.bootstrap_login(auth.BootstrapCredentials(identifier="justy@ithute.co.ls", password="wrong"), request())
    assert exc.value.status_code == 404


def test_bootstrap_token_and_rejections(monkeypatch):
    monkeypatch.setattr(auth.settings, "bootstrap_login_enabled", True)
    monkeypatch.setattr(auth.settings, "bootstrap_admin_email", "justy@ithute.co.ls")
    monkeypatch.setattr(auth.settings, "bootstrap_admin_password", "Very-long-unique-password")
    monkeypatch.setattr(auth.settings, "bootstrap_signing_secret", "really-long-independent-signing-secret-value")
    counter = Counter()
    monkeypatch.setattr(auth.Redis, "from_url", lambda *args, **kwargs: counter)
    with pytest.raises(HTTPException) as exc:
        auth.bootstrap_login(auth.BootstrapCredentials(identifier="justy@ithute.co.ls", password="incorrect"), request())
    assert exc.value.status_code == 401
    token = auth.bootstrap_login(auth.BootstrapCredentials(identifier="justy@ithute.co.ls", password="Very-long-unique-password"), request())["access_token"]
    claims = auth.decode_local_bootstrap_token(token)
    assert claims["sub"] == str(auth.BOOTSTRAP_SUB)
    assert claims["email"] == "justy@ithute.co.ls"
    with pytest.raises(HTTPException) as exc:
        auth.decode_local_bootstrap_token(token + "tampered")
    assert exc.value.status_code == 401
    for _ in range(3):
        with pytest.raises(HTTPException):
            auth.bootstrap_login(auth.BootstrapCredentials(identifier="justy@ithute.co.ls", password="incorrect"), request())
    with pytest.raises(HTTPException) as exc:
        auth.bootstrap_login(auth.BootstrapCredentials(identifier="justy@ithute.co.ls", password="Very-long-unique-password"), request())
    assert exc.value.status_code == 429


def test_bootstrap_requires_strong_secrets(monkeypatch):
    monkeypatch.setattr(auth.settings, "bootstrap_login_enabled", True)
    monkeypatch.setattr(auth.settings, "bootstrap_admin_password", "short")
    monkeypatch.setattr(auth.settings, "bootstrap_signing_secret", "short")
    with pytest.raises(HTTPException) as exc:
        auth.bootstrap_login(auth.BootstrapCredentials(identifier="justy@ithute.co.ls", password="short"), request())
    assert exc.value.status_code == 404
