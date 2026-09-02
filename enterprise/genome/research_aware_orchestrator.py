from __future__ import annotations
from .service_genome import ServiceGenomeEngine
from .server_room import ServerRoomComposer
from .business_replication import BusinessReplicator
from .gene_server_resolver import GeneServerResolver


class ResearchAwareGenomeOrchestrator:
    """Requires every expressed gene to resolve through exposed IL-LLM before composing a server room."""

    def __init__(self, catalog, bridge):
        self.genomes = ServiceGenomeEngine(catalog)
        self.rooms = ServerRoomComposer(catalog)
        self.replicator = BusinessReplicator()
        self.resolver = GeneServerResolver(bridge, catalog)

    def provision_plan(self, undertaking, business_id, domains, region="AU-SA", scale="SMALL", extra_genes=None):
        genome = self.genomes.genome(undertaking, extra_genes)
        research = self.resolver.resolve_genome(genome)
        if research["status"] != "QUALIFIED":
            return {"status": "HELD_RESEARCH_HOLES", "genome": genome, "research": research}
        room = self.rooms.compose(genome, scale)
        replication = self.replicator.replicate(room, business_id, domains, region)
        return {"status": "READY", "genome": genome, "research": research, "room": room, "replication": replication}
