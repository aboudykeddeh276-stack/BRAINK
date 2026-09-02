from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Optional
import json
import os

from observer2_federation_r29 import (
    EnvironmentFederation,
    GitRepositoryProbe,
    HttpProjectionProbe,
    ProcessProbe,
)

BLOCK = 4096
BRAINK_OFF = 256 * BLOCK
SERVICE_OFF = 768 * BLOCK
MUTATION_OFF = 1024 * BLOCK


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _read_block(fd: int, off: int) -> Optional[Mapping[str, Any]]:
    head = os.pread(fd, 8, off)
    if len(head) < 8:
        return None
    n = int.from_bytes(head[:4], "big")
    if n <= 0 or n > BLOCK - 8:
        return None
    raw = os.pread(fd, n, off + 8)
    return {"obj": json.loads(raw.decode("utf-8")), "sha256": _sha(raw)}


class BrainkMachineProbe:
    """Read-only probe for the resident BRAINK machine-image contract used by R12/R13/R17."""

    substrate = "braink-machine-image"

    def __init__(self, disk: Path | str, *, environment_id: str = "env://braink/machine",
                 probe_id: str = "probe://braink/machine-image") -> None:
        self.disk = Path(disk).resolve()
        self.environment_id = environment_id
        self.probe_id = probe_id

    def sample(self, observer_id: str) -> Mapping[str, Any]:
        fd = os.open(self.disk, os.O_RDONLY)
        try:
            root = _read_block(fd, BRAINK_OFF)
            fabric = _read_block(fd, SERVICE_OFF)
            mutations = _read_block(fd, MUTATION_OFF)
        finally:
            os.close(fd)
        if not root or not fabric:
            raise RuntimeError("E_MACHINE_NOT_READY")
        root_obj = root["obj"]
        mutation_obj = mutations["obj"] if mutations else {"revision": 0, "objects": {}}
        return {
            "disk": str(self.disk),
            "machine_id": root_obj.get("machine_id"),
            "braink_id": root_obj.get("braink_id"),
            "lineage_root": root_obj.get("lineage_root"),
            "braink_root_sha256": root["sha256"],
            "service_fabric_sha256": fabric["sha256"],
            "service_roots": sorted((fabric["obj"].get("services") or {}).keys()),
            "mutation_revision": int(mutation_obj.get("revision", 0)),
            "mutation_sha256": mutations["sha256"] if mutations else None,
        }


class BrainkPublicEdgeProbe(HttpProjectionProbe):
    """Typed read-only projection probe for the existing R17 public-edge health receipt."""

    def __init__(self, base_url: str, *, environment_id: str = "env://braink/public-edge",
                 probe_id: str = "probe://braink/public-edge", timeout: float = 3.0) -> None:
        super().__init__(
            base_url.rstrip("/") + "/health",
            environment_id=environment_id,
            probe_id=probe_id,
            timeout=timeout,
        )


def build_observer2_federation(*, observer_id: str = "observer2://braink/r29",
                               repository: Optional[Path | str] = None,
                               machine_disk: Optional[Path | str] = None,
                               public_edge_url: Optional[str] = None,
                               include_process: bool = True) -> EnvironmentFederation:
    """Compose already-existing environments without pretending they share one substrate."""

    federation = EnvironmentFederation(observer_id)
    if repository is not None:
        federation.register(GitRepositoryProbe(
            repository,
            environment_id="env://repository/braink",
            probe_id="probe://repository/braink",
        ))
    if machine_disk is not None:
        federation.register(BrainkMachineProbe(machine_disk))
    if public_edge_url is not None:
        federation.register(BrainkPublicEdgeProbe(public_edge_url))
    if include_process:
        federation.register(ProcessProbe(
            environment_id="env://process/observer2",
            probe_id="probe://process/observer2",
        ))
    return federation
