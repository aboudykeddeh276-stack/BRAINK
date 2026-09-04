from __future__ import annotations

import os
from pathlib import Path

import pytest

from enterprise.logical_computer_identity import LogicalComputerController, MachineProjection
from enterprise.mirror_lane_transfer_adapter import MirrorLaneTransferAdapter
from enterprise.recursive_computer_runtime_r26 import RecursiveComputer


@pytest.fixture
def mirror_runtime() -> Path:
    raw = os.environ.get("KEDDEH_MIRROR_LANE_RUNTIME")
    if not raw:
        pytest.skip("KEDDEH_MIRROR_LANE_RUNTIME not bound")
    path = Path(raw)
    if not path.exists():
        pytest.fail(f"mirror lane runtime missing: {path}")
    return path


def projection(name: str, host: str) -> MachineProjection:
    return MachineProjection(
        projection_id=name,
        host_fingerprint=host,
        platform="qualification-linux",
        carrier=f"tcp://{name}",
    )


def test_logical_identity_survives_machine_projection_change_via_mirror_lane(tmp_path: Path, mirror_runtime: Path):
    source = tmp_path / "host-a" / "computer"
    mirror = tmp_path / "mirror-lane"
    destination = tmp_path / "host-b" / "computer"

    r26 = RecursiveComputer(computer_id="ROOT-A", state_root=source)
    r26.write_state("workload", {"sequence": [1, 2, 3], "status": "BOUND"})
    r26.write_memory("semantic", {"address": "LEX://BRAINK/ROOT-A"})
    child = r26.instantiate("CHILD-B")
    child.write_state("role", "descendant")

    logical = LogicalComputerController.create(
        source,
        lineage=("ROOT-A",),
        authority_id="A.KEDDEH/KEDDEH_SYSTEMS",
        projection=projection("machine-a", "host-a-fingerprint"),
    )
    before_identity = logical.read_identity()
    before_state_digest = logical.state_digest()

    migrated = logical.migrate_via_mirror_lane(
        destination,
        mirror_root=mirror,
        new_projection=projection("machine-b", "host-b-fingerprint"),
        mirror_adapter=MirrorLaneTransferAdapter(mirror_runtime),
    )

    after_identity = migrated.read_identity()
    assert after_identity.logical_id == before_identity.logical_id
    assert after_identity.lineage == before_identity.lineage
    assert after_identity.authority_id == before_identity.authority_id
    assert migrated.read_projection().projection_id == "machine-b"
    assert migrated.read_projection().host_fingerprint != logical.read_projection().host_fingerprint
    assert migrated.state_digest() == before_state_digest

    restored_r26 = RecursiveComputer.restore_tree(destination)
    assert restored_r26.identity.computer_id == "ROOT-A"
    assert restored_r26.state["workload"]["status"] == "BOUND"
    assert restored_r26.memory["semantic"]["address"] == "LEX://BRAINK/ROOT-A"
    assert restored_r26.children["CHILD-B"].identity.lineage == ("ROOT-A", "CHILD-B")

    receipts = (destination / "logical-computer-receipts.jsonl").read_text("utf-8")
    assert "LOGICAL_COMPUTER_MIGRATED_VIA_MIRROR_LANE" in receipts
    assert "logical_id_unchanged" in receipts
    assert "MIRROR_VERIFIED" in receipts
    assert "RESTORE_VERIFIED" in receipts
