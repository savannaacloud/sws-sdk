"""Live checks against a real console. Skipped unless SWS_LIVE_BASE is set:

    SWS_LIVE_BASE=https://savannaa.com python -m pytest tests/test_live.py -v

Read-only; creates nothing. The mocked tests can only prove the SDK builds the URL it
intends to — only a real gateway proves that URL exists. A wrong path (a doubled
prefix, or the alias after it is withdrawn) returns 404, which surfaces as
NotFoundError rather than AuthenticationError, so these tests fail loudly instead of
silently passing.
"""
from __future__ import annotations

import os

import pytest

from sws import AuthenticationError, Client, NotFoundError

BASE = os.environ.get("SWS_LIVE_BASE")
BOGUS = "ctk_live_probe_never_issued_000000000000"

pytestmark = pytest.mark.skipif(not BASE, reason="set SWS_LIVE_BASE to run live checks")


@pytest.mark.parametrize(
    "suffix",
    ["", "/", "/api", "/api/v1", "/api/v1/"],
    ids=["bare", "slash", "api", "api-v1", "api-v1-slash"],
)
def test_the_versioned_path_exists_and_the_key_is_refused(suffix: str) -> None:
    client = Client(api_key=BOGUS, base_url=f"{BASE.rstrip('/')}{suffix}")
    with pytest.raises(AuthenticationError) as excinfo:
        client.compute.list_instances()
    assert not isinstance(excinfo.value, NotFoundError), (
        f"base_url {BASE}{suffix} did not reach /api/v1/compute/servers"
    )
    assert excinfo.value.status_code in (401, 403)
