"""Where credentials come from when the caller does not pass them.

The first code anybody copies should not contain a secret. The resolution order is the
one every modern SDK uses, so a quick start is `Client()` and nothing else:

    1. the ``api_key`` argument
    2. ``$SWS_API_KEY``
    3. the credentials file ``sws auth login`` writes — ``~/.config/sws/credentials``
       (INI, profile-aware) or the plain ``~/.config/sws/token`` the CLI has always
       written. ``$SWS_PROFILE`` selects the profile, default ``default``.
    4. otherwise: an error that names the env var rather than a bare 401 later.

``$SWS_CREDENTIALS_FILE`` overrides the path (used by the tests).
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

DEFAULT_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sws"
MISSING_MESSAGE = (
    "Missing credentials: set SWS_API_KEY, run `sws auth login`, "
    "or pass api_key= to Client()"
)


def credentials_path() -> Path:
    override = os.environ.get("SWS_CREDENTIALS_FILE")
    return Path(override) if override else DEFAULT_DIR / "credentials"


def token_path() -> Path:
    return credentials_path().with_name("token")


def _from_file(profile: str) -> dict[str, str]:
    """A profile out of the INI credentials file, or {} if there is none."""
    path = credentials_path()
    if not path.is_file():
        return {}
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except Exception:
        return {}
    for section in (profile, "default"):
        if parser.has_section(section):
            return {k.lower(): v.strip() for k, v in parser.items(section)}
    if parser.defaults():
        return {k.lower(): v.strip() for k, v in parser.defaults().items()}
    return {}


def _from_token_file() -> str:
    """The session token `sws auth login` writes. Useful on a developer machine; it
    expires, which is why an API key still wins."""
    try:
        text = token_path().read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return text if text and "\n" not in text else ""


def resolve(api_key: str | None = None, region: str | None = None, base_url: str | None = None) -> tuple[str, str | None, str | None, str]:
    """(api_key, region, base_url, source). Raises nothing — the caller decides what an
    empty key means, so the error can name the env var."""
    if api_key:
        return api_key, region, base_url, "argument"
    profile = os.environ.get("SWS_PROFILE") or "default"
    env_key = os.environ.get("SWS_API_KEY")
    if env_key:
        return (env_key,
                region or os.environ.get("SWS_REGION"),
                base_url or os.environ.get("SWS_API_URL") or os.environ.get("SWS_BASE_URL"),
                "SWS_API_KEY")
    fromfile = _from_file(profile)
    key = fromfile.get("api_key") or fromfile.get("token")
    if key:
        return (key,
                region or os.environ.get("SWS_REGION") or fromfile.get("region"),
                base_url or os.environ.get("SWS_API_URL") or os.environ.get("SWS_BASE_URL") or fromfile.get("api_url") or fromfile.get("base_url"),
                "%s [%s]" % (credentials_path(), profile))
    token = _from_token_file()
    if token:
        return (token,
                region or os.environ.get("SWS_REGION"),
                base_url or os.environ.get("SWS_API_URL") or os.environ.get("SWS_BASE_URL"),
                str(token_path()))
    return ("",
            region or os.environ.get("SWS_REGION"),
            base_url or os.environ.get("SWS_API_URL") or os.environ.get("SWS_BASE_URL"),
            "none")
