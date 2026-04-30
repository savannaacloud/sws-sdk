"""Top-level :class:`Client` and resource handlers.

Resource handlers live as inner classes so users get attribute access
(``client.compute.list_instances()``) without us having to maintain a
service-locator dict.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from sws._version import __version__
from sws.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    QuotaExceededError,
    ValidationError,
)
from sws.models import (
    Database,
    Instance,
    Keypair,
    Network,
    Plan,
    PublicIP,
    SecurityGroup,
    Subnet,
    Volume,
)

DEFAULT_BASE_URL = "https://savannaa.com"
DEFAULT_REGION = "ng-lagos-1"
DEFAULT_TIMEOUT = 30.0


def _raise_for_status(r: httpx.Response) -> None:
    """Translate non-2xx responses into the SDK exception hierarchy.

    Quota errors arrive as 403 with a body containing "Quota" — they get
    their own subclass so callers can retry with smaller requests.
    """
    if r.is_success:
        return
    try:
        body: Any = r.json()
        msg = body.get("detail") or body.get("error") or body.get("message") or r.text
    except Exception:
        body = r.text
        msg = r.text or r.reason_phrase

    if r.status_code in (401, 403):
        if isinstance(msg, str) and "quota" in msg.lower():
            raise QuotaExceededError(r.status_code, msg, body)
        raise AuthenticationError(r.status_code, msg, body)
    if r.status_code == 404:
        raise NotFoundError(r.status_code, msg, body)
    if r.status_code in (400, 422):
        raise ValidationError(r.status_code, msg, body)
    raise APIError(r.status_code, msg, body)


class Client:
    """SWS API client.

    Example::

        from sws import Client

        client = Client(api_key="sws_...", region="ng-lagos-1")
        for vm in client.compute.list_instances():
            print(vm.name, vm.status)

    Auth resolution order: ``api_key`` argument → ``SWS_API_KEY`` env var.
    Region: ``region`` argument → ``SWS_REGION`` env var → ``ng-lagos-1``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        region: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        verify_tls: bool = True,
    ) -> None:
        api_key = api_key or os.environ.get("SWS_API_KEY")
        if not api_key:
            raise AuthenticationError(
                401,
                "missing api_key (pass to Client(api_key=...) or set SWS_API_KEY env var)",
            )
        region = region or os.environ.get("SWS_REGION") or DEFAULT_REGION
        base_url = base_url or os.environ.get("SWS_BASE_URL") or DEFAULT_BASE_URL

        self._http = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "x-region": region,
                "User-Agent": f"sws-sdk-python/{__version__}",
                "Accept": "application/json",
            },
            timeout=timeout,
            verify=verify_tls,
        )
        self.region = region
        self.compute = Compute(self._http)
        self.network = NetworkResource(self._http)
        self.storage = Storage(self._http)
        self.database = DatabaseResource(self._http)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


class _Resource:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def _get(self, path: str, **kwargs: Any) -> Any:
        r = self._http.get(path, **kwargs)
        _raise_for_status(r)
        return r.json() if r.content else None

    def _post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        r = self._http.post(path, json=json, **kwargs)
        _raise_for_status(r)
        return r.json() if r.content else None

    def _delete(self, path: str, **kwargs: Any) -> None:
        r = self._http.delete(path, **kwargs)
        _raise_for_status(r)


class Compute(_Resource):
    """Virtual machines, plans, images, keypairs."""

    # ── instances ──────────────────────────────────────────────────────
    def list_instances(self) -> list[Instance]:
        data = self._get("/api/compute/servers") or []
        return [Instance.from_api(d) for d in data]

    def get_instance(self, instance_id: str) -> Instance:
        return Instance.from_api(self._get(f"/api/compute/servers/{instance_id}"))

    def create_instance(
        self,
        *,
        name: str,
        image: str,
        plan: str,
        network_id: str | None = None,
        key_name: str | None = None,
        security_groups: list[str] | None = None,
        user_data: str | None = None,
    ) -> Instance:
        # The backend still takes flavor_id over the wire — translate the
        # SDK's "plan" surface to it here so callers never see the legacy
        # term.
        payload: dict[str, Any] = {
            "name": name,
            "image_id": image,
            "flavor_id": plan,
        }
        if network_id:
            payload["network_id"] = network_id
        if key_name:
            payload["key_name"] = key_name
        if security_groups:
            payload["security_groups"] = security_groups
        if user_data is not None:
            payload["user_data"] = user_data
        return Instance.from_api(self._post("/api/compute/servers", json=payload))

    def delete_instance(self, instance_id: str) -> None:
        self._delete(f"/api/compute/servers/{instance_id}")

    def start_instance(self, instance_id: str) -> None:
        self._post(f"/api/compute/servers/{instance_id}/start")

    def stop_instance(self, instance_id: str) -> None:
        self._post(f"/api/compute/servers/{instance_id}/stop")

    def reboot_instance(self, instance_id: str, *, hard: bool = False) -> None:
        self._post(
            f"/api/compute/servers/{instance_id}/reboot",
            json={"type": "HARD" if hard else "SOFT"},
        )

    def resize_instance(self, instance_id: str, *, plan: str) -> None:
        self._post(
            f"/api/compute/servers/{instance_id}/resize",
            json={"flavor_id": plan},
        )

    # ── plans / images / keypairs ─────────────────────────────────────
    def list_plans(self) -> list[Plan]:
        data = self._get("/api/compute/plans") or []
        return [Plan.from_api(d) for d in data]

    def list_images(self) -> list[dict]:
        data = self._get("/api/images") or []
        return list(data)

    def list_keypairs(self) -> list[Keypair]:
        data = self._get("/api/compute/keypairs") or []
        return [Keypair.from_api(d) for d in data]

    def create_keypair(self, name: str, *, public_key: str | None = None) -> Keypair:
        payload: dict[str, Any] = {"name": name}
        if public_key:
            payload["public_key"] = public_key
        return Keypair.from_api(self._post("/api/compute/keypairs", json=payload))

    def delete_keypair(self, name: str) -> None:
        self._delete(f"/api/compute/keypairs/{name}")


class NetworkResource(_Resource):
    """Networks, subnets, security groups, public IPs."""

    # ── networks ──────────────────────────────────────────────────────
    def list_networks(self) -> list[Network]:
        data = self._get("/api/network/networks") or []
        return [Network.from_api(d) for d in data]

    def create_network(self, name: str, *, description: str | None = None) -> Network:
        payload: dict[str, Any] = {"name": name}
        if description is not None:
            payload["description"] = description
        return Network.from_api(self._post("/api/network/networks", json=payload))

    def delete_network(self, network_id: str) -> None:
        self._delete(f"/api/network/networks/{network_id}")

    # ── subnets ───────────────────────────────────────────────────────
    def list_subnets(self) -> list[Subnet]:
        data = self._get("/api/network/subnets") or []
        return [Subnet.from_api(d) for d in data]

    def create_subnet(
        self,
        *,
        name: str,
        network_id: str,
        cidr: str,
        ip_version: int = 4,
        enable_dhcp: bool = True,
        dns_nameservers: list[str] | None = None,
    ) -> Subnet:
        payload: dict[str, Any] = {
            "name": name,
            "network_id": network_id,
            "cidr": cidr,
            "ip_version": ip_version,
            "enable_dhcp": enable_dhcp,
        }
        if dns_nameservers:
            payload["dns_nameservers"] = dns_nameservers
        return Subnet.from_api(self._post("/api/network/subnets", json=payload))

    def delete_subnet(self, subnet_id: str) -> None:
        self._delete(f"/api/network/subnets/{subnet_id}")

    # ── security groups ───────────────────────────────────────────────
    def list_security_groups(self) -> list[SecurityGroup]:
        data = self._get("/api/network/security-groups") or []
        return [SecurityGroup.from_api(d) for d in data]

    def create_security_group(self, name: str, *, description: str = "") -> SecurityGroup:
        return SecurityGroup.from_api(
            self._post(
                "/api/network/security-groups",
                json={"name": name, "description": description},
            )
        )

    def delete_security_group(self, group_id: str) -> None:
        self._delete(f"/api/network/security-groups/{group_id}")

    def add_security_group_rule(
        self,
        group_id: str,
        *,
        direction: str = "ingress",
        protocol: str = "tcp",
        port_range_min: int,
        port_range_max: int,
        remote_ip_prefix: str = "0.0.0.0/0",
        ethertype: str = "IPv4",
    ) -> dict:
        return self._post(
            "/api/network/security-group-rules",
            json={
                "security_group_id": group_id,
                "direction": direction,
                "protocol": protocol,
                "port_range_min": port_range_min,
                "port_range_max": port_range_max,
                "remote_ip_prefix": remote_ip_prefix,
                "ethertype": ethertype,
            },
        )

    def remove_security_group_rule(self, rule_id: str) -> None:
        self._delete(f"/api/network/security-group-rules/{rule_id}")

    # ── public IPs ────────────────────────────────────────────────────
    def list_public_ips(self) -> list[PublicIP]:
        data = self._get("/api/network/public-ips") or []
        return [PublicIP.from_api(d) for d in data]

    def allocate_public_ip(self, *, floating_network_id: str | None = None) -> PublicIP:
        payload: dict[str, Any] = {}
        if floating_network_id:
            payload["floating_network_id"] = floating_network_id
        return PublicIP.from_api(self._post("/api/network/public-ips", json=payload))

    def assign_public_ip(self, ip_id: str, *, instance_id: str) -> None:
        self._post(
            f"/api/network/public-ips/{ip_id}/associate",
            json={"instance_id": instance_id},
        )

    def unassign_public_ip(self, ip_id: str) -> None:
        self._post(f"/api/network/public-ips/{ip_id}/disassociate")

    def release_public_ip(self, ip_id: str) -> None:
        self._delete(f"/api/network/public-ips/{ip_id}")


class Storage(_Resource):
    """Block storage volumes."""

    def list_volumes(self) -> list[Volume]:
        data = self._get("/api/block-storage/volumes") or []
        return [Volume.from_api(d) for d in data]

    def get_volume(self, volume_id: str) -> Volume:
        return Volume.from_api(self._get(f"/api/block-storage/volumes/{volume_id}"))

    def create_volume(
        self,
        *,
        name: str,
        size: int,
        type: str | None = None,
        description: str | None = None,
    ) -> Volume:
        payload: dict[str, Any] = {"name": name, "size": size}
        if type is not None:
            payload["volume_type"] = type
        if description is not None:
            payload["description"] = description
        return Volume.from_api(self._post("/api/block-storage/volumes", json=payload))

    def delete_volume(self, volume_id: str) -> None:
        self._delete(f"/api/block-storage/volumes/{volume_id}")

    def attach_volume(self, volume_id: str, *, instance_id: str) -> None:
        self._post(
            f"/api/block-storage/volumes/{volume_id}/attach",
            json={"instance_id": instance_id},
        )

    def detach_volume(self, volume_id: str) -> None:
        self._post(f"/api/block-storage/volumes/{volume_id}/detach")


class DatabaseResource(_Resource):
    """Managed database instances (mysql, postgresql, etc.)."""

    def list_instances(self) -> list[Database]:
        data = self._get("/api/database/instances") or []
        return [Database.from_api(d) for d in data]

    def get_instance(self, db_id: str) -> Database:
        return Database.from_api(self._get(f"/api/database/instances/{db_id}"))

    def create_instance(
        self,
        *,
        name: str,
        datastore: str,
        version: str,
        plan: str,
        size: int,
        admin_user: str = "admin",
        admin_password: str,
        network_id: str | None = None,
    ) -> Database:
        payload: dict[str, Any] = {
            "name": name,
            "datastore_type": datastore,
            "datastore_version": version,
            "flavor": plan,
            "size": size,
            "admin_user": admin_user,
            "admin_password": admin_password,
        }
        if network_id:
            payload["network_id"] = network_id
        return Database.from_api(self._post("/api/database/instances", json=payload))

    def delete_instance(self, db_id: str) -> None:
        self._delete(f"/api/database/instances/{db_id}")
