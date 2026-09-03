from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from enterprise.addressability_fabric import AddressabilityFabric, root


ROOT_ORDER = (
    "DOMAIN_ROOT",
    "DNS_ROOT",
    "REGISTRAR_ROOT",
    "TLS_ROOT",
    "SERVER_ROOT",
    "CLOUD_ROOT",
)


@dataclass(frozen=True)
class ResidentRoot:
    root_id: str
    logical: str
    object_class: str
    source_components: tuple[str, ...]
    adapter_ref: str | None
    adapter_binding: str
    authority: str

    @property
    def digest(self) -> str:
        return root(asdict(self))


class ResidentRootProjection:
    """Project stable BRAINK/KEX typed roots into the addressability fabric.

    Root identity and digest are authoritative. Carrier endpoints are deliberately
    excluded from the root body so a route/IP/tunnel may change without changing
    semantic machine identity.
    """

    def __init__(self, runtime_id: str = "braink://runtime/resident-roots/r39"):
        self.fabric = AddressabilityFabric(runtime_id=runtime_id)
        self.backing_id = "resident://braink/root-state/r39"
        self.adapter_id = "adapter://kex/resident-root/r39"
        self.fabric.create_backing(self.backing_id)
        self.fabric.register_backing_adapter(self.adapter_id, self.backing_id)
        self._roots = self._build_roots()
        self._mount()

    @staticmethod
    def _build_roots() -> Dict[str, ResidentRoot]:
        # These are stable semantic identities projected from mechanics present in
        # the R26 branch. External carrier/provider state is not used as identity.
        return {
            "DOMAIN_ROOT": ResidentRoot(
                "DOMAIN_ROOT",
                "LEX://BRAINK/DOMAIN_ROOT",
                "DOMAIN_AUTHORITY",
                ("enterprise/domain_replication.py", "enterprise/addressability_fabric.py"),
                "repository://github/aboudykeddeh276-stack/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority",
                "RESOLVED_REPOSITORY_AUTHORITY",
                "authority://braink/domain",
            ),
            "DNS_ROOT": ResidentRoot(
                "DNS_ROOT",
                "LEX://BRAINK/DNS_ROOT",
                "DNS_AUTHORITY",
                ("enterprise/addressability_fabric.py",),
                "repository://github/aboudykeddeh276-stack/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority/kex_dns.py",
                "RESOLVED_REPOSITORY_AUTHORITY",
                "authority://kex/dns",
            ),
            "REGISTRAR_ROOT": ResidentRoot(
                "REGISTRAR_ROOT",
                "LEX://BRAINK/REGISTRAR_ROOT",
                "REGISTRAR_AUTHORITY",
                ("enterprise/domain_replication.py",),
                "repository://github/aboudykeddeh276-stack/SERVERS-KEDDEHSYSTEMS/runtime/domain_authority/kex_registrar_service.py",
                "RESOLVED_REPOSITORY_AUTHORITY",
                "authority://kex/registrar",
            ),
            "TLS_ROOT": ResidentRoot(
                "TLS_ROOT",
                "LEX://BRAINK/TLS_ROOT",
                "TLS_AUTHORITY",
                ("enterprise/addressability_fabric.py",),
                None,
                "UNRESOLVED_ADAPTER",
                "authority://braink/tls",
            ),
            "SERVER_ROOT": ResidentRoot(
                "SERVER_ROOT",
                "LEX://BRAINK/SERVER_ROOT",
                "SERVER_RUNTIME",
                ("enterprise/server_room.py", "deployment/independent_fabric_node_r38.py"),
                "adapter://kex/server-runtime",
                "RESOLVED_INTERNAL_RUNTIME",
                "runtime://kex/server",
            ),
            "CLOUD_ROOT": ResidentRoot(
                "CLOUD_ROOT",
                "LEX://BRAINK/CLOUD_ROOT",
                "MACHINE_FABRIC",
                ("enterprise/addressability_fabric.py", "enterprise/market/live_service_fabric_r25.py"),
                "adapter://kex/machine-fabric",
                "RESOLVED_INTERNAL_RUNTIME",
                "authority://braink/machine-fabric",
            ),
        }

    def _mount(self) -> None:
        for root_id in ROOT_ORDER:
            item = self._roots[root_id]
            self.fabric.map(
                item.logical,
                aperture=f"typed-root://{root_id}",
                adapter=self.adapter_id,
                backing=self.backing_id,
            )
            result = self.fabric.apply(item.logical, "WRITE", asdict(item))
            if result.get("status") != "COMMITTED":
                raise RuntimeError(f"ROOT_MOUNT_FAILED:{root_id}:{result.get('status')}")

    def resolve(self, root_id: str) -> Dict[str, Any]:
        if root_id not in self._roots:
            raise KeyError(f"UNKNOWN_RESIDENT_ROOT:{root_id}")
        item = self._roots[root_id]
        result = self.fabric.apply(item.logical, "READ")
        if result.get("status") != "READ":
            raise RuntimeError(f"ROOT_READ_FAILED:{root_id}:{result.get('status')}")
        body = result["value"]
        return {
            "root_id": root_id,
            "logical": item.logical,
            "digest": root(body),
            "adapter_binding": item.adapter_binding,
            "authority": item.authority,
            "body": body,
        }

    def snapshot(self) -> Dict[str, Any]:
        roots = {root_id: self.resolve(root_id) for root_id in ROOT_ORDER}
        digest_material = {
            root_id: {
                "logical": roots[root_id]["logical"],
                "digest": roots[root_id]["digest"],
                "adapter_binding": roots[root_id]["adapter_binding"],
                "authority": roots[root_id]["authority"],
            }
            for root_id in ROOT_ORDER
        }
        return {
            "schema": "braink.resident-root-projection.r39/v1",
            "roots": roots,
            "root_set_digest": root(digest_material),
            "mapping_root": self.fabric.ring1.state_root,
            "carrier_runtime_id": self.fabric.carrier.runtime_id,
        }

    @staticmethod
    def verify_snapshot(snapshot: Dict[str, Any]) -> bool:
        roots = snapshot.get("roots")
        if not isinstance(roots, dict) or tuple(roots.keys()) != ROOT_ORDER:
            return False
        digest_material: Dict[str, Any] = {}
        for root_id in ROOT_ORDER:
            item = roots.get(root_id)
            if not isinstance(item, dict) or item.get("root_id") != root_id:
                return False
            body = item.get("body")
            if root(body) != item.get("digest"):
                return False
            digest_material[root_id] = {
                "logical": item.get("logical"),
                "digest": item.get("digest"),
                "adapter_binding": item.get("adapter_binding"),
                "authority": item.get("authority"),
            }
        return root(digest_material) == snapshot.get("root_set_digest")
