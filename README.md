# sws-sdk

Official Python SDK for the **SWS** cloud platform.

## Install

```bash
pip install sws-sdk
```

## Quickstart

```python
from sws import Client

client = Client(api_key="sws_...", region="ng-lagos-1")

# List virtual machines
for vm in client.compute.list_instances():
    print(vm.name, vm.status)

# Launch an instance
instance = client.compute.create_instance(
    name="web-01",
    image="ubuntu-22.04",
    plan="m1.medium",
    network_id="net-uuid",
    key_name="my-key",
)

# Create + attach a volume
vol = client.storage.create_volume(name="data", size=100, type="ssd")
client.storage.attach_volume(vol.id, instance_id=instance.id)

# Open SSH (port 22) from anywhere
sg = client.network.create_security_group("web", description="Allow SSH")
client.network.add_security_group_rule(
    sg.id, protocol="tcp", port_range_min=22, port_range_max=22,
    remote_ip_prefix="0.0.0.0/0",
)
```

Configure via constructor or environment variables:

| Argument    | Env var         | Default                    |
| ----------- | --------------- | -------------------------- |
| `api_key`   | `SWS_API_KEY`   | _(required)_               |
| `region`    | `SWS_REGION`    | `ng-lagos-1`               |
| `base_url`  | `SWS_BASE_URL`  | `https://savannaa.com`     |

## Resources

| Namespace          | Operations                                                                                         |
| ------------------ | -------------------------------------------------------------------------------------------------- |
| `client.compute`   | instances (CRUD + start/stop/reboot/resize), plans, images, keypairs                               |
| `client.network`   | networks, subnets, security groups + rules, public IPs (allocate/assign/release)                   |
| `client.storage`   | volumes (create, delete, attach, detach)                                                           |
| `client.database`  | managed database instances (mysql, postgresql, …)                                                  |

## Error handling

```python
from sws import Client, QuotaExceededError, NotFoundError

try:
    client.compute.create_instance(...)
except QuotaExceededError:
    print("Out of instance quota — request a bump in the console.")
except NotFoundError:
    print("Image or plan does not exist in this region.")
```

All exceptions inherit from `sws.SWSError`. Subclasses: `AuthenticationError`,
`ValidationError`, `NotFoundError`, `QuotaExceededError`, `APIError`.

## Development

```bash
pip install -e ".[dev]"
pytest                # unit tests use respx, no live API required
ruff check sws tests
mypy sws
```

## License

MIT
