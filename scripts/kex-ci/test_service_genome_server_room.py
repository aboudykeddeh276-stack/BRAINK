from __future__ import annotations

import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.service_genome import GenomeComposer, GenomeFunction, GenomePairing, ServiceGenome, default_server_classes
from enterprise.server_room_runtime import AIServerRoomRuntime
from enterprise.undertaking_deployer import UndertakingDeployer


genome = ServiceGenome(
    genome_id="genome://casepath/service/r1",
    service_class="legal_preparation_platform",
    functions=(
        GenomeFunction("hr.casepath.agent_assignment", "hr_governance", "hr.assign", "hr"),
        GenomeFunction("agent.casepath.intake", "research_learning_evolution", "agent.casepath.intake", "agentic_ai"),
        GenomeFunction("mail.casepath.transactional", "runtime_servers", "mail.transactional", "mailing"),
        GenomeFunction("runtime.casepath.service", "runtime_servers", "runtime.service.launch", "runtime"),
        GenomeFunction("vfs.casepath.matter", "storage_memory", "vfs.commit", "storage"),
        GenomeFunction("security.casepath.audit", "mesh_nodes", "audit.receipt", "security"),
        GenomeFunction("web.casepath.public", "console_ui", "web.casepath.public", "web"),
    ),
    pairings=(
        GenomePairing("hr.casepath.agent_assignment", "agent.casepath.intake", "assigns_authority"),
        GenomePairing("agent.casepath.intake", "vfs.casepath.matter", "writes_matter_state"),
        GenomePairing("runtime.casepath.service", "web.casepath.public", "serves_projection"),
        GenomePairing("runtime.casepath.service", "mail.casepath.transactional", "emits_notifications"),
        GenomePairing("vfs.casepath.matter", "security.casepath.audit", "emits_proof_receipts"),
    ),
)

assert genome.validate()["valid"] is True
composer = GenomeComposer(default_server_classes())
room = composer.compose_room("room://casepath/sa", "undertaking://casepath/sa", (genome,))
classes = {x.server_class for x in room.server_instances}
assert {"hr", "agentic_ai", "mailing", "runtime", "storage", "security", "web"}.issubset(classes)

runtime = AIServerRoomRuntime(room)
r0 = runtime.invoke("agent.casepath.intake", {"story": "example"})
assert r0.status == "DEFERRED_FUNCTION_HOLE"
runtime.bind_function("agent.casepath.intake", lambda p: {"matter_state": "NORMALIZED", "story_present": bool(p.get("story"))})
r1 = runtime.invoke("agent.casepath.intake", {"story": "example"})
assert r1.status == "EXECUTED"
assert r1.effect["matter_state"] == "NORMALIZED"

deployer = UndertakingDeployer()
small = deployer.deploy(
    "undertaking://casepath/sa", "room://casepath/sa", (genome,),
    {"replication": {"agentic_ai": 2, "runtime": 2, "storage": 2, "web": 2}, "environment": {"mode": "pilot"}},
)
large = deployer.reconfigure(
    small, (genome,),
    {"replication": {"agentic_ai": 5, "runtime": 4, "storage": 4, "web": 6, "mailing": 2}, "environment": {"mode": "expanded"}},
)
assert small["genome_roots"] == large["genome_roots"]
assert small["dependency_root"] == large["dependency_root"]
assert len(large["server_instances"]) > len(small["server_instances"])
assert large["predecessor_deployment_root"] == small["deployment_root"]

print("SERVICE_GENOME_SERVER_ROOM_PASS")
