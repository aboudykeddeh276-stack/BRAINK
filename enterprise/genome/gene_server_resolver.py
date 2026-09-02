from __future__ import annotations
from typing import Any, Dict
from .gene_research_bridge import GeneResearchBridge


class GeneServerResolver:
    """Research-qualifies genome genes before server-room composition."""

    def __init__(self, bridge: GeneResearchBridge, catalog: Dict[str, Any]):
        self.bridge = bridge
        self.catalog = catalog

    def resolve_genome(self, genome) -> dict:
        resolved = []
        holes = []
        for gid in genome.genes:
            packet = self.bridge.packet(gid)
            if packet.get("status") != "OK":
                holes.append({"gene_id": gid, "state": "RESEARCH_HOLE"})
                continue
            cfg = self.catalog["genes"][gid]
            resolved.append({
                "gene_id": gid,
                "server_family": cfg["server_family"],
                "capabilities": cfg["provides"],
                "research_packet_root": packet["packet_root"],
                "relation_count": len(packet["relations"]),
                "evidence_count": len(packet["evidence"]),
            })
        return {"status": "QUALIFIED" if not holes else "PARTIAL", "resolved": resolved, "holes": holes}
