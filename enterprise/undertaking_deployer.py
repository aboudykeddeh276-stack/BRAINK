from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Mapping
import hashlib
import json
import time

from enterprise.service_genome import GenomeComposer, ServiceGenome, default_server_classes


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class UndertakingDeployer:
    """Materializes a business/service undertaking from one or more service genomes."""

    def __init__(self):
        self.composer = GenomeComposer(default_server_classes())
        self.deployments: list[Mapping[str, Any]] = []

    def deploy(
        self,
        undertaking_id: str,
        room_id: str,
        genomes: Iterable[ServiceGenome],
        profile: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        genomes = tuple(genomes)
        replication = dict(profile.get("replication", {}))
        environment = dict(profile.get("environment", {}))
        enabled_optional_functions = tuple(profile.get("enabled_optional_functions", ()))
        room = self.composer.compose_room(
            room_id=room_id,
            undertaking_id=undertaking_id,
            genomes=genomes,
            replication_overrides=replication,
            environment=environment,
            enabled_optional_functions=enabled_optional_functions,
        )
        record = {
            "schema": "braink.undertaking-deployment/v1",
            "undertaking_id": undertaking_id,
            "room_id": room_id,
            "genome_roots": list(room.genome_roots),
            "room_root": room.room_root,
            "dependency_root": room.dependency_root,
            "server_instances": [asdict(i) for i in room.server_instances],
            "profile": dict(profile),
            "produced_at_ns": time.time_ns(),
        }
        record["deployment_root"] = root(record)
        self.deployments.append(record)
        return record

    def reconfigure(self, prior: Mapping[str, Any], genomes: Iterable[ServiceGenome], profile: Mapping[str, Any]) -> Mapping[str, Any]:
        successor = self.deploy(
            undertaking_id=prior["undertaking_id"],
            room_id=prior["room_id"],
            genomes=genomes,
            profile=profile,
        )
        successor = dict(successor)
        successor["predecessor_deployment_root"] = prior["deployment_root"]
        successor["reconfiguration_root"] = root({
            "predecessor": prior["deployment_root"],
            "successor": successor["deployment_root"],
        })
        return successor
