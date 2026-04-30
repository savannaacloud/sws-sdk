"""Mock-based tests using respx — no live API required."""

from __future__ import annotations

import httpx
import pytest
import respx

from sws import (
    AuthenticationError,
    Client,
    NotFoundError,
    QuotaExceededError,
    ValidationError,
)


@pytest.fixture
def client() -> Client:
    return Client(api_key="sws_test", region="ng-lagos-1", base_url="https://api.example")


@respx.mock
def test_auth_header_and_region_sent(client: Client) -> None:
    route = respx.get("https://api.example/api/compute/servers").mock(
        return_value=httpx.Response(200, json=[]),
    )
    client.compute.list_instances()
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer sws_test"
    assert req.headers["x-region"] == "ng-lagos-1"
    assert req.headers["user-agent"].startswith("sws-sdk-python/")


@respx.mock
def test_list_instances_parses_flavor_as_plan(client: Client) -> None:
    respx.get("https://api.example/api/compute/servers").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "i-1",
                    "name": "web-1",
                    "status": "ACTIVE",
                    "flavor": {"id": "m1.small", "vcpus": 1, "ram": 2048},
                }
            ],
        )
    )
    instances = client.compute.list_instances()
    assert len(instances) == 1
    assert instances[0].id == "i-1"
    assert instances[0].plan == {"id": "m1.small", "vcpus": 1, "ram": 2048}


@respx.mock
def test_create_instance_translates_plan_to_flavor_id(client: Client) -> None:
    """SDK takes ``plan=`` from the caller but sends ``flavor_id`` over
    the wire — the backend hasn't been renamed yet."""
    route = respx.post("https://api.example/api/compute/servers").mock(
        return_value=httpx.Response(
            201,
            json={"id": "i-2", "name": "web-2", "status": "BUILD"},
        )
    )
    inst = client.compute.create_instance(
        name="web-2",
        image="ubuntu-22.04",
        plan="m1.medium",
        network_id="net-1",
        key_name="my-key",
    )
    assert inst.id == "i-2"
    body = route.calls.last.request.content.decode()
    assert '"flavor_id":"m1.medium"' in body.replace(" ", "")
    assert "plan" not in body  # SDK keyword shouldn't leak into the wire payload


@respx.mock
def test_404_raises_not_found(client: Client) -> None:
    respx.get("https://api.example/api/compute/servers/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )
    with pytest.raises(NotFoundError) as exc:
        client.compute.get_instance("missing")
    assert exc.value.status_code == 404


@respx.mock
def test_403_quota_message_raises_quota_exceeded(client: Client) -> None:
    respx.post("https://api.example/api/compute/servers").mock(
        return_value=httpx.Response(
            403, json={"detail": "Quota exceeded for instances: 10/10"}
        )
    )
    with pytest.raises(QuotaExceededError):
        client.compute.create_instance(name="x", image="i", plan="m1.tiny")


@respx.mock
def test_401_raises_auth_error(client: Client) -> None:
    respx.get("https://api.example/api/compute/servers").mock(
        return_value=httpx.Response(401, json={"detail": "bad token"})
    )
    with pytest.raises(AuthenticationError):
        client.compute.list_instances()


@respx.mock
def test_422_raises_validation_error(client: Client) -> None:
    respx.post("https://api.example/api/network/subnets").mock(
        return_value=httpx.Response(422, json={"detail": "cidr required"})
    )
    with pytest.raises(ValidationError):
        client.network.create_subnet(name="s", network_id="n", cidr="")


@respx.mock
def test_security_group_rule_payload(client: Client) -> None:
    route = respx.post("https://api.example/api/network/security-group-rules").mock(
        return_value=httpx.Response(201, json={"id": "r-1"})
    )
    client.network.add_security_group_rule(
        "sg-1",
        protocol="tcp",
        port_range_min=22,
        port_range_max=22,
        remote_ip_prefix="0.0.0.0/0",
    )
    body = route.calls.last.request.content.decode()
    assert '"security_group_id":"sg-1"' in body.replace(" ", "")
    assert '"direction":"ingress"' in body.replace(" ", "")


@respx.mock
def test_volume_attach_uses_instance_id(client: Client) -> None:
    route = respx.post("https://api.example/api/block-storage/volumes/v-1/attach").mock(
        return_value=httpx.Response(202)
    )
    client.storage.attach_volume("v-1", instance_id="i-9")
    body = route.calls.last.request.content.decode()
    assert '"instance_id":"i-9"' in body.replace(" ", "")


def test_missing_api_key_raises() -> None:
    import os

    old = os.environ.pop("SWS_API_KEY", None)
    try:
        with pytest.raises(AuthenticationError):
            Client()
    finally:
        if old:
            os.environ["SWS_API_KEY"] = old


def test_env_var_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWS_API_KEY", "sws_from_env")
    monkeypatch.setenv("SWS_REGION", "ng-abuja-1")
    c = Client(base_url="https://api.example")
    assert c.region == "ng-abuja-1"
    assert c._http.headers["authorization"] == "Bearer sws_from_env"
    assert c._http.headers["x-region"] == "ng-abuja-1"
