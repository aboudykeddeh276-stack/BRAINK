from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Mapping, Iterable
import hashlib, json, time


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class FoundaryAddress:
    foundary_id: str
    class_id: str
    process_count: int
    server_set_count: int
    team_count: int
    data_class_count: int
    repository_count: int
    virtual_root_count: int
    state: str
    foundary_root: str


@dataclass(frozen=True)
class FoundaryWorkPacket:
    packet_id: str
    undertaking: str
    foundary_id: str
    process_domains: tuple[str, ...]
    server_sets: tuple[str, ...]
    agent_teams: tuple[str, ...]
    data_classes: tuple[str, ...]
    repositories: tuple[str, ...]
    virtual_roots: tuple[str, ...]
    predecessor_root: str | None
    created_ns: int

    @property
    def packet_root(self) -> str:
        return root(asdict(self))


class FoundaryRuntime:
    """Federates large foundaries without reducing them to single capabilities.

    A foundary remains a compound process/data/service/agent/server construct.
    Genomes and undertakings may consume a foundary packet, but packet creation
    preserves every declared process domain, server set, team, data class,
    repository and virtual root from the canonical foundary registry.
    """

    def __init__(self, registry: Mapping[str, Any]):
        self.registry = dict(registry)
        self.foundaries: Dict[str, Mapping[str, Any]] = dict(self.registry["foundaries"])
        self.events: list[dict[str, Any]] = []

    def address(self, foundary_id: str) -> FoundaryAddress:
        f = self.foundaries[foundary_id]
        body = {
            "foundary_id": foundary_id,
            "class": f["class"],
            "process_domains": f["process_domains"],
            "server_sets": f["server_sets"],
            "agent_teams": f["agent_teams"],
            "data_classes": f["data_classes"],
            "repositories": f["repositories"],
            "virtual_roots": f["virtual_roots"],
            "state": f["state"],
        }
        return FoundaryAddress(
            foundary_id=foundary_id,
            class_id=f["class"],
            process_count=len(f["process_domains"]),
            server_set_count=len(f["server_sets"]),
            team_count=len(f["agent_teams"]),
            data_class_count=len(f["data_classes"]),
            repository_count=len(f["repositories"]),
            virtual_root_count=len(f["virtual_roots"]),
            state=f["state"],
            foundary_root=root(body),
        )

    def materialize(self, undertaking: str, foundary_id: str, predecessor_root: str | None = None) -> FoundaryWorkPacket:
        f = self.foundaries[foundary_id]
        packet = FoundaryWorkPacket(
            packet_id=f"foundary-packet://{undertaking}/{foundary_id}/{time.time_ns()}",
            undertaking=undertaking,
            foundary_id=foundary_id,
            process_domains=tuple(f["process_domains"]),
            server_sets=tuple(f["server_sets"]),
            agent_teams=tuple(f["agent_teams"]),
            data_classes=tuple(f["data_classes"]),
            repositories=tuple(f["repositories"]),
            virtual_roots=tuple(f["virtual_roots"]),
            predecessor_root=predecessor_root,
            created_ns=time.time_ns(),
        )
        self.events.append({
            "kind": "FOUNDARY_MATERIALIZED",
            "undertaking": undertaking,
            "foundary_id": foundary_id,
            "packet_root": packet.packet_root,
        })
        return packet

    def compose_undertaking(self, undertaking: str, foundary_ids: Iterable[str]) -> Mapping[str, Any]:
        packets = [self.materialize(undertaking, fid) for fid in foundary_ids]
        all_processes = sorted({p for packet in packets for p in packet.process_domains})
        all_server_sets = sorted({s for packet in packets for s in packet.server_sets})
        all_teams = sorted({t for packet in packets for t in packet.agent_teams})
        all_data = sorted({d for packet in packets for d in packet.data_classes})
        all_repositories = sorted({r for packet in packets for r in packet.repositories})
        all_virtual_roots = sorted({v for packet in packets for v in packet.virtual_roots})
        result = {
            "schema": "braink.foundary-undertaking.r21/v1",
            "undertaking": undertaking,
            "foundaries": [p.foundary_id for p in packets],
            "packet_roots": [p.packet_root for p in packets],
            "process_domains": all_processes,
            "server_sets": all_server_sets,
            "agent_teams": all_teams,
            "data_classes": all_data,
            "repositories": all_repositories,
            "virtual_roots": all_virtual_roots,
        }
        result["undertaking_root"] = root(result)
        return result
