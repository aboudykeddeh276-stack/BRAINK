from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping, Optional
import hashlib
import json


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GenomeFunction:
    function_id: str
    sector: str
    capability: str
    server_class: str
    required: bool = True


@dataclass(frozen=True)
class GenomePairing:
    source_function: str
    target_function: str
    relation: str
    required: bool = True


@dataclass(frozen=True)
class ServiceGenome:
    genome_id: str
    service_class: str
    functions: tuple[GenomeFunction, ...]
    pairings: tuple[GenomePairing, ...]
    policies: tuple[str, ...] = ()

    @property
    def genome_root(self) -> str:
        return root(asdict(self))

    def validate(self) -> Mapping[str, Any]:
        ids = {f.function_id for f in self.functions}
        missing = []
        for p in self.pairings:
            if p.source_function not in ids:
                missing.append(p.source_function)
            if p.target_function not in ids:
                missing.append(p.target_function)
        return {
            "valid": not missing,
            "missing_function_refs": sorted(set(missing)),
            "genome_root": self.genome_root,
        }


@dataclass(frozen=True)
class ServerClass:
    server_class: str
    capability_prefixes: tuple[str, ...]
    replication_min: int = 1
    replication_max: int = 3


@dataclass(frozen=True)
class ServerInstance:
    instance_id: str
    server_class: str
    ordinal: int
    room_id: str
    assigned_functions: tuple[str, ...]
    configuration_root: str


@dataclass(frozen=True)
class AIServerRoom:
    room_id: str
    undertaking_id: str
    genome_roots: tuple[str, ...]
    server_instances: tuple[ServerInstance, ...]
    dependency_root: str
    room_root: str


class GenomeComposer:
    """Composes cross-sector service genomes into server sets and AI server rooms."""

    def __init__(self, server_classes: Iterable[ServerClass]):
        self.server_classes = {s.server_class: s for s in server_classes}

    def compose_room(
        self,
        room_id: str,
        undertaking_id: str,
        genomes: Iterable[ServiceGenome],
        replication_overrides: Optional[Mapping[str, int]] = None,
        environment: Optional[Mapping[str, Any]] = None,
    ) -> AIServerRoom:
        genomes = tuple(genomes)
        replication_overrides = dict(replication_overrides or {})
        environment = dict(environment or {})

        for genome in genomes:
            verdict = genome.validate()
            if not verdict["valid"]:
                raise RuntimeError(f"INVALID_GENOME:{genome.genome_id}:{verdict['missing_function_refs']}")

        by_server: dict[str, list[str]] = {}
        dependency_edges: list[Mapping[str, str]] = []
        for genome in genomes:
            for function in genome.functions:
                if function.server_class not in self.server_classes:
                    raise KeyError(f"UNKNOWN_SERVER_CLASS:{function.server_class}")
                by_server.setdefault(function.server_class, []).append(function.function_id)
            for pairing in genome.pairings:
                dependency_edges.append({
                    "genome_id": genome.genome_id,
                    "source": pairing.source_function,
                    "target": pairing.target_function,
                    "relation": pairing.relation,
                })

        instances: list[ServerInstance] = []
        for server_class, function_ids in sorted(by_server.items()):
            spec = self.server_classes[server_class]
            requested = int(replication_overrides.get(server_class, spec.replication_min))
            replicas = max(spec.replication_min, min(requested, spec.replication_max))
            for ordinal in range(1, replicas + 1):
                config = {
                    "room_id": room_id,
                    "undertaking_id": undertaking_id,
                    "server_class": server_class,
                    "ordinal": ordinal,
                    "functions": sorted(set(function_ids)),
                    "environment": environment,
                }
                instances.append(ServerInstance(
                    instance_id=f"server://{room_id}/{server_class}/{ordinal}",
                    server_class=server_class,
                    ordinal=ordinal,
                    room_id=room_id,
                    assigned_functions=tuple(sorted(set(function_ids))),
                    configuration_root=root(config),
                ))

        dependency_root = root(dependency_edges)
        room_body = {
            "room_id": room_id,
            "undertaking_id": undertaking_id,
            "genome_roots": [g.genome_root for g in genomes],
            "server_instances": [asdict(i) for i in instances],
            "dependency_root": dependency_root,
        }
        room_root = root(room_body)
        return AIServerRoom(
            room_id=room_id,
            undertaking_id=undertaking_id,
            genome_roots=tuple(g.genome_root for g in genomes),
            server_instances=tuple(instances),
            dependency_root=dependency_root,
            room_root=room_root,
        )


def default_server_classes() -> tuple[ServerClass, ...]:
    return (
        ServerClass("hr", ("hr.", "people.", "agent.assignment"), 1, 2),
        ServerClass("agentic_ai", ("agent.", "research.", "evolution.", "orc.", "braink."), 2, 6),
        ServerClass("mailing", ("mail.", "notification.", "campaign."), 1, 4),
        ServerClass("runtime", ("runtime.", "service.", "process."), 2, 6),
        ServerClass("storage", ("vfs.", "memory.", "artifact."), 2, 6),
        ServerClass("security", ("security.", "identity.", "fence.", "audit."), 1, 4),
        ServerClass("web", ("web.", "site.", "public."), 2, 8),
        ServerClass("payments", ("payment.", "billing.", "entitlement."), 1, 4),
    )
