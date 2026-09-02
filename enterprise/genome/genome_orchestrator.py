from __future__ import annotations
from .service_genome import ServiceGenomeEngine
from .server_room import ServerRoomComposer
from .business_replication import BusinessReplicator


class GenomeOrchestrator:
    """Genome -> paired services -> server room -> business-specific replicated server sets."""

    def __init__(self, catalog):
        self.genomes = ServiceGenomeEngine(catalog)
        self.rooms = ServerRoomComposer(catalog)
        self.replicator = BusinessReplicator()

    def provision_plan(self, undertaking, business_id, domains, region="AU-SA", scale="SMALL", extra_genes=None):
        genome = self.genomes.genome(undertaking, extra_genes)
        room = self.rooms.compose(genome, scale)
        replication = self.replicator.replicate(room, business_id, domains, region)
        return {"genome": genome, "room": room, "replication": replication}
