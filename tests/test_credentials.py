"""The first code anyone copies must not contain a secret: Client() has to find
credentials on its own, and say exactly what is missing when it cannot."""
from __future__ import annotations

import pytest

from sws import Client
from sws.credentials import MISSING_MESSAGE, resolve
from sws.exceptions import AuthenticationError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for var in ("SWS_API_KEY", "SWS_REGION", "SWS_BASE_URL", "SWS_API_URL", "SWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SWS_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    return tmp_path


def test_argument_wins(monkeypatch):
    monkeypatch.setenv("SWS_API_KEY", "ctk_env")
    key, _r, _b, source = resolve("ctk_explicit")
    assert key == "ctk_explicit" and source == "argument"


def test_environment_is_used_when_no_argument(monkeypatch):
    monkeypatch.setenv("SWS_API_KEY", "ctk_env")
    key, _r, _b, source = resolve()
    assert key == "ctk_env" and source == "SWS_API_KEY"


def test_credentials_file_and_profiles(clean_env, monkeypatch):
    (clean_env / "credentials").write_text(
        "[default]\napi_key = ctk_default\nregion = ng-abuja-1\n\n"
        "[ci]\napi_key = ctk_ci\napi_url = https://savannaa.com\n",
        encoding="utf-8",
    )
    key, region, _b, source = resolve()
    assert key == "ctk_default" and region == "ng-abuja-1" and "credentials" in source
    monkeypatch.setenv("SWS_PROFILE", "ci")
    key, _r, base, _s = resolve()
    assert key == "ctk_ci" and base == "https://savannaa.com"


def test_token_file_from_sws_auth_login(clean_env):
    (clean_env / "token").write_text("eyJhbGciOi.session.token\n", encoding="utf-8")
    key, _r, _b, source = resolve()
    assert key == "eyJhbGciOi.session.token" and source.endswith("token")


def test_environment_beats_the_file(clean_env, monkeypatch):
    (clean_env / "credentials").write_text("[default]\napi_key = ctk_file\n", encoding="utf-8")
    monkeypatch.setenv("SWS_API_KEY", "ctk_env")
    key, _r, _b, source = resolve()
    assert key == "ctk_env" and source == "SWS_API_KEY"


def test_missing_credentials_names_the_env_var():
    with pytest.raises(AuthenticationError) as e:
        Client()
    assert "SWS_API_KEY" in str(e.value)
    assert MISSING_MESSAGE in str(e.value)


def test_client_reads_the_environment(monkeypatch):
    monkeypatch.setenv("SWS_API_KEY", "ctk_env")
    with Client() as c:
        assert c.credential_source == "SWS_API_KEY"
