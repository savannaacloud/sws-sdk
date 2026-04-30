"""Typed dataclass models for SWS API resources.

Models accept the raw API response via :meth:`from_api` and translate
internal/legacy field names into the SDK's stable surface (e.g. the
backend still returns ``flavor`` for what the SDK exposes as ``plan``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _coerce_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@dataclass
class Plan:
    """A compute plan (size/SKU) — what the underlying platform calls a flavor."""

    id: str
    name: str
    vcpus: int | None = None
    ram: int | None = None  # MB
    disk: int | None = None  # GB

    @classmethod
    def from_api(cls, data: dict) -> Plan:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            vcpus=_coerce_int(data.get("vcpus")),
            ram=_coerce_int(data.get("ram")),
            disk=_coerce_int(data.get("disk")),
        )


@dataclass
class Instance:
    id: str
    name: str
    status: str
    plan: dict | None = None
    image: dict | None = None
    addresses: dict[str, Any] | None = None
    key_name: str | None = None
    created_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict) -> Instance:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            status=str(data.get("status", "")),
            plan=data.get("flavor") or data.get("plan"),
            image=data.get("image"),
            addresses=data.get("addresses"),
            key_name=data.get("key_name"),
            created_at=data.get("created") or data.get("created_at"),
            raw=dict(data),
        )


@dataclass
class Keypair:
    name: str
    fingerprint: str | None = None
    public_key: str | None = None
    private_key: str | None = None  # only present on create

    @classmethod
    def from_api(cls, data: dict) -> Keypair:
        return cls(
            name=str(data.get("name", "")),
            fingerprint=data.get("fingerprint"),
            public_key=data.get("public_key"),
            private_key=data.get("private_key"),
        )


@dataclass
class Network:
    id: str
    name: str
    status: str | None = None
    subnets: list[str] | None = None

    @classmethod
    def from_api(cls, data: dict) -> Network:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            status=data.get("status"),
            subnets=data.get("subnets"),
        )


@dataclass
class Subnet:
    id: str
    name: str
    network_id: str
    cidr: str
    ip_version: int = 4
    enable_dhcp: bool = True

    @classmethod
    def from_api(cls, data: dict) -> Subnet:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            network_id=str(data.get("network_id", "")),
            cidr=str(data.get("cidr", "")),
            ip_version=int(data.get("ip_version", 4)),
            enable_dhcp=bool(data.get("enable_dhcp", True)),
        )


@dataclass
class SecurityGroup:
    id: str
    name: str
    description: str | None = None
    rules: list[dict] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> SecurityGroup:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=data.get("description"),
            rules=list(data.get("security_group_rules") or data.get("rules") or []),
        )


@dataclass
class PublicIP:
    """A public (floating) IP address."""

    id: str
    address: str
    instance_id: str | None = None
    status: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> PublicIP:
        return cls(
            id=str(data.get("id", "")),
            address=str(data.get("floating_ip_address") or data.get("address", "")),
            instance_id=data.get("port_id") or data.get("instance_id"),
            status=data.get("status"),
        )


@dataclass
class Volume:
    id: str
    name: str
    size: int  # GB
    status: str | None = None
    type: str | None = None
    attached_to: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> Volume:
        attachments = data.get("attachments") or []
        attached = (
            attachments[0].get("server_id") if attachments and isinstance(attachments[0], dict) else None
        )
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            size=int(data.get("size", 0) or 0),
            status=data.get("status"),
            type=data.get("volume_type") or data.get("type"),
            attached_to=attached,
        )


@dataclass
class Database:
    id: str
    name: str
    datastore: str
    status: str | None = None
    plan: dict | None = None

    @classmethod
    def from_api(cls, data: dict) -> Database:
        ds = data.get("datastore")
        if isinstance(ds, dict):
            ds_type = str(ds.get("type", ""))
        else:
            ds_type = str(ds or data.get("datastore_type", ""))
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            datastore=ds_type,
            status=data.get("status"),
            plan=data.get("flavor") or data.get("plan"),
        )
