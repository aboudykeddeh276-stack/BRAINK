from __future__ import annotations

import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from enterprise.service_genome import GenomeComposer, GenomeFunction, GenomePairing, ServiceGenome, default_server_classes
from enterprise.server_room_runtime import AIServerRoomRuntime
from enterprise.undertaking_deployer import UndertakingDeployer


def load_genome(path: Path) -> ServiceGenome:
    data = json.loads(path.read_text("utf-8"))
    return ServiceGenome(
        genome_id=data["genome_id"],
        service_class=data["service_class"],
        functions=tuple(GenomeFunction(**item) for item in data["functions"]),
        pairings=tuple(GenomePairing(**item) for item in data["pairings"]),
        policies=tuple(data.get("policies", ())),
    )


genome = load_genome(ROOT / "enterprise/genomes/CASEPATH_SERVICE_GENOME_R1.json")
assert genome.validate()["valid"] is True
assert genome.genome_id == "genome://casepath/service/r1"

composer = GenomeComposer(default_server_classes())
room = composer.compose_room("room://casepath/sa", "undertaking://casepath/sa", (genome,))
classes = {x.server_class for x in room.server_instances}
assert {"hr", "agentic_ai", "mailing", "runtime", "storage", "security", "web"}.issubset(classes)
assert "payments" not in classes
assert all("payment.casepath.entitlement" not in i.assigned_functions for i in room.server_instances)

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
assert not any(i["server_class"] == "payments" for i in large["server_instances"])

paid = deployer.reconfigure(
    large, (genome,),
    {
        "replication": {"agentic_ai": 5, "runtime": 4, "storage": 4, "web": 6, "mailing": 2},
        "environment": {"mode": "expanded", "payments": "enabled"},
        "enabled_optional_functions": ["payment.casepath.entitlement"],
    },
)
assert paid["genome_roots"] == large["genome_roots"]
assert any(i["server_class"] == "payments" for i in paid["server_instances"])
assert any("payment.casepath.entitlement" in i["assigned_functions"] for i in paid["server_instances"])
assert paid["dependency_root"] != large["dependency_root"]
assert paid["predecessor_deployment_root"] == large["deployment_root"]

print("SERVICE_GENOME_SERVER_ROOM_PASS")
