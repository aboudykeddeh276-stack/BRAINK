from __future__ import annotations
from typing import Any, Dict, List
import hashlib, json


def root(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class BusinessReplicator:
    """Creates business-specific server-set configuration from a canonical server-room genome."""

    def replicate(self, room, business_id: str, domains: List[str], region: str) -> Dict[str, Any]:
        server_sets = []
        for server in room.servers:
            server_sets.append({
                "family": server.family,
                "instance_set": f"{business_id}:{server.family}",
                "replicas": server.replicas,
                "dependencies": list(server.dependencies),
                "services": list(server.services),
                "source_config_root": server.config_root,
                "environment": {"business_id": business_id, "region": region, "domains": domains},
            })
        packet = {
            "business_id": business_id,
            "undertaking": room.undertaking,
            "room_root": room.room_root,
            "domains": domains,
            "region": region,
            "server_sets": server_sets,
        }
        packet["replication_root"] = root(packet)
        return packet
