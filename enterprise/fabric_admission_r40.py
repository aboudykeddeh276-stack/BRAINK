from __future__ import annotations

from typing import Any, Callable
from urllib.request import Request, urlopen
import hashlib

from enterprise.resident_root_projection_r39 import ResidentRootProjection
from runtime.R25.system_evolution_runtime import canonical_json


def _proof_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body).encode()).hexdigest()


def http_reachability(endpoint: str, timeout: float = 2.0) -> bool:
    url = str(endpoint).rstrip("/") + "/healthz"
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


class FabricAdmissionR40:
    """Admission/server/subscription edges layered onto the resident R38 fabric node."""

    def __init__(self, node):
        self.node = node

    @staticmethod
    def verify_peer_manifest(peer: dict[str, Any]) -> None:
        required = {"node_id", "endpoint", "state_root", "resident_root_snapshot", "authority", "capabilities", "subscriptions", "proof"}
        missing = sorted(required.difference(peer))
        if missing:
            raise ValueError("MISSING_ADMISSION_FIELDS:" + ",".join(missing))
        if not ResidentRootProjection.verify_snapshot(peer["resident_root_snapshot"]):
            raise ValueError("INVALID_RESIDENT_ROOT_SNAPSHOT")
        if not isinstance(peer["capabilities"], list) or not peer["capabilities"]:
            raise ValueError("CAPABILITY_MANIFEST_REQUIRED")
        if not str(peer["authority"]).startswith("authority://"):
            raise ValueError("INVALID_PEER_AUTHORITY")
        proof = peer["proof"]
        if not isinstance(proof, dict) or proof.get("status") != "PROVED":
            raise ValueError("IDENTITY_PROOF_REQUIRED")
        body = proof.get("body")
        if not isinstance(body, dict) or _proof_hash(body) != proof.get("proof"):
            raise ValueError("IDENTITY_PROOF_INVALID")
        expected = {
            "node_id": str(peer["node_id"]),
            "state_root": str(peer["state_root"]),
            "resident_root_set_digest": str(peer["resident_root_snapshot"]["root_set_digest"]),
        }
        for key, value in expected.items():
            if str(body.get(key)) != value:
                raise ValueError(f"IDENTITY_PROOF_MISMATCH:{key}")

    def register_local_node(self, *, node_id: str, lineage: list[str], state_root: str,
                            capabilities: list[str], authority: str, network_id: str,
                            vfs_root: str) -> dict[str, Any]:
        if not capabilities:
            return {"status": "BLOCKED:CAPABILITY_MANIFEST_REQUIRED", "node_id": str(node_id)}
        if not str(authority).startswith("authority://"):
            return {"status": "BLOCKED:INVALID_NODE_AUTHORITY", "node_id": str(node_id)}
        entries = dict(self.node.computer.readback().get("memory", {}).get("fabric_local_nodes", {}))
        entries[str(node_id)] = {
            "lineage": list(lineage),
            "state_root": str(state_root),
            "capabilities": sorted(set(map(str, capabilities))),
            "authority": str(authority),
            "network_id": str(network_id),
            "vfs_root": str(vfs_root),
            "admission": "LOCAL_VERIFIED",
        }
        self.node.computer.write_memory("fabric_local_nodes", entries)
        readback = self.node.computer.readback().get("memory", {}).get("fabric_local_nodes", {})
        if str(node_id) not in readback:
            raise RuntimeError("LOCAL_NODE_REGISTRATION_READBACK_FAILED")
        return {"status": "MESH_REGISTERED", "node_id": str(node_id), "readback": readback[str(node_id)],
                "ledger_verified": self.node.computer.ledger.verify()}

    def admit(self, peer: dict[str, Any], reachability_probe: Callable[[str], bool] = http_reachability) -> dict[str, Any]:
        self.verify_peer_manifest(peer)
        if not reachability_probe(str(peer["endpoint"])):
            return {"status": "BLOCKED:REACHABILITY_UNVERIFIED", "node_id": str(peer["node_id"])}
        joined = self.node.join({
            "node_id": peer["node_id"], "endpoint": peer["endpoint"], "state_root": peer["state_root"],
            "resident_root_snapshot": peer["resident_root_snapshot"], "authority": peer["authority"],
        })
        admissions = dict(self.node.computer.readback().get("memory", {}).get("fabric_admissions", {}))
        admissions[str(peer["node_id"])] = {
            "capabilities": sorted(set(map(str, peer["capabilities"]))),
            "subscriptions": sorted(set(map(str, peer["subscriptions"]))),
            "authority": str(peer["authority"]), "endpoint": str(peer["endpoint"]), "acknowledged": True,
        }
        self.node.computer.write_memory("fabric_admissions", admissions)
        readback = self.node.computer.readback().get("memory", {}).get("fabric_admissions", {})
        if str(peer["node_id"]) not in readback:
            raise RuntimeError("MESH_ADMISSION_READBACK_FAILED")
        return {"status": "ADMITTED", "peer_id": str(peer["node_id"]), "join": joined,
                "registration": readback[str(peer["node_id"])], "ledger_verified": self.node.computer.ledger.verify()}

    def register_server(self, server: dict[str, Any]) -> dict[str, Any]:
        required = {"server_id", "endpoint", "capabilities", "health"}
        missing = sorted(required.difference(server))
        if missing:
            raise ValueError("MISSING_SERVER_FIELDS:" + ",".join(missing))
        if server["health"] not in {"READY", "LIVE"}:
            return {"status": "BLOCKED:SERVER_NOT_READY", "server_id": str(server["server_id"])}
        bindings = dict(self.node.computer.readback().get("memory", {}).get("server_bindings", {}))
        bindings[str(server["server_id"])] = {
            "endpoint": str(server["endpoint"]),
            "capabilities": sorted(set(map(str, server["capabilities"]))),
            "health": str(server["health"]),
        }
        self.node.computer.write_memory("server_bindings", bindings)
        check = self.node.computer.readback().get("memory", {}).get("server_bindings", {})
        if str(server["server_id"]) not in check:
            raise RuntimeError("SERVER_REGISTRATION_READBACK_FAILED")
        return {"status": "SERVER_REGISTERED", "server_id": str(server["server_id"]), "readback": check[str(server["server_id"])]}

    def subscribe_node(self, node_id: str, topics: list[str]) -> dict[str, Any]:
        normalized = sorted(set(map(str, topics)))
        subscriptions = dict(self.node.computer.readback().get("memory", {}).get("node_subscriptions", {}))
        subscriptions[str(node_id)] = normalized
        self.node.computer.write_memory("node_subscriptions", subscriptions)
        check = self.node.computer.readback().get("memory", {}).get("node_subscriptions", {})
        if check.get(str(node_id)) != normalized:
            raise RuntimeError("SUBSCRIPTION_READBACK_FAILED")
        return {"status": "SUBSCRIBED", "node_id": str(node_id), "topics": normalized}

    def subscribe(self, topics: list[str]) -> dict[str, Any]:
        return self.subscribe_node(self.node.node_id, topics)
