from __future__ import annotations
from typing import Any, Dict
from enterprise.research.exposed_illlm import ExposedILLLM


class GeneResearchBridge:
    """Binds service genome genes into the exposed IL-LLM research graph."""

    def __init__(self, repo: ExposedILLLM, catalog: Dict[str, Any]):
        self.repo = repo
        self.catalog = catalog

    def ingest_catalog(self) -> dict:
        genes = {}
        for gid, gene in self.catalog["genes"].items():
            node = self.repo.upsert(
                node_type="SERVICE",
                term=gid,
                definition=f"Service genome gene {gid}: {gene['class']} capability family for {gene['server_family']}.",
                subject="KEDDEH SYSTEMS SERVICE GENOME",
                topic=gene["class"],
                matter=gene["server_family"],
            )
            genes[gid] = node
            self.repo.alias(node.node_id, gene["server_family"], f"gene:{gid}")
            for capability in gene["provides"]:
                cap = self.repo.upsert(
                    node_type="FUNCTION",
                    term=capability,
                    definition=f"Capability exposed by service genome gene {gid}: {capability}.",
                    subject=gid,
                    topic="GENE CAPABILITY",
                    matter=gene["server_family"],
                )
                self.repo.relate(node.node_id, "PROVIDES", cap.node_id)

        for undertaking, gene_ids in self.catalog["undertaking_templates"].items():
            undertaking_node = self.repo.upsert(
                node_type="SERVICE",
                term=undertaking,
                definition=f"Business undertaking genome template: {undertaking}.",
                subject="KEDDEH SYSTEMS BUSINESS UNDERTAKINGS",
                topic="UNDERTAKING",
                matter=undertaking,
            )
            for gid in gene_ids:
                self.repo.relate(undertaking_node.node_id, "EXPRESSES_GENE", genes[gid].node_id)
        return {"genes": len(genes), "undertakings": len(self.catalog["undertaking_templates"])}

    def link_requirement(self, gene_id: str, requirement_type: str, name: str, definition: str = "") -> dict:
        gene = self.repo.resolve(gene_id)
        if not gene:
            return {"status": "HOLE", "gene_id": gene_id}
        requirement_type = requirement_type.upper()
        node_type = "CONTROL" if requirement_type == "CONTROL" else "ADAPTER"
        node = self.repo.upsert(
            node_type=node_type,
            term=name,
            definition=definition or f"{requirement_type} required by {gene_id}: {name}",
            subject=gene_id,
            topic=f"GENE {requirement_type}",
            matter=name,
        )
        relation = self.repo.relate(gene["node_id"], f"REQUIRES_{requirement_type}", node.node_id)
        return {"status": "BOUND", "node": node.__dict__, "relation": relation}

    def attach_research(self, gene_id: str, source_ref: str, content: Any, confidence: float = 1.0) -> dict:
        gene = self.repo.resolve(gene_id)
        if not gene:
            return {"status": "HOLE", "gene_id": gene_id}
        return self.repo.attach_evidence(gene["node_id"], "GENE_RESEARCH", source_ref, content, confidence)

    def packet(self, gene_id: str) -> dict:
        return self.repo.research_packet(gene_id)
