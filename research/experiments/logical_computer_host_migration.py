from __future__ import annotations

import argparse
import json
import platform
import socket
import time
from pathlib import Path

from enterprise.logical_computer_identity import LogicalComputerController, MachineProjection
from enterprise.mirror_lane_transfer_adapter import MirrorLaneTransferAdapter
from enterprise.recursive_computer_runtime_r26 import RecursiveComputer

CLAIM_ID = "BRAINK_LOGICAL_COMPUTER_HOST_INDEPENDENCE_R1"
AUTHORITY = "A.KEDDEH/KEDDEH_SYSTEMS"


def projection(projection_id: str, carrier: str) -> MachineProjection:
    host_material = f"{socket.gethostname()}|{platform.platform()}|{platform.machine()}"
    return MachineProjection(
        projection_id=projection_id,
        host_fingerprint=host_material,
        platform=platform.platform(),
        carrier=carrier,
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def prepare(args: argparse.Namespace) -> int:
    state_root = Path(args.state_root)
    mirror_root = Path(args.mirror_root)
    baseline_path = Path(args.baseline)
    runtime = MirrorLaneTransferAdapter(args.mirror_runtime)

    root = RecursiveComputer(computer_id="ROOT-A", state_root=state_root)
    root.write_state("workload", {"sequence": [1, 2, 3], "status": "BOUND"})
    root.write_memory("semantic", {"address": "LEX://BRAINK/ROOT-A"})
    child = root.instantiate("CHILD-B")
    child.write_state("role", "descendant")

    controller = LogicalComputerController.create(
        state_root,
        lineage=("ROOT-A",),
        authority_id=AUTHORITY,
        projection=projection("HOST_A", args.carrier),
    )
    ident = controller.read_identity()
    before_digest = controller.state_digest()
    mirror_receipt = runtime.update(state_root, mirror_root)

    baseline = {
        "schema": "braink.logical-computer.host-a-baseline.v1",
        "claim_id": CLAIM_ID,
        "logical_id": ident.logical_id,
        "lineage": list(ident.lineage),
        "authority_id": ident.authority_id,
        "state_digest": before_digest,
        "projection": controller.read_projection().__dict__,
        "mirror_manifest_digest": mirror_receipt.manifest_digest,
        "mirror_runtime": mirror_receipt.runtime,
        "mirror_file_count": mirror_receipt.file_count,
        "mirror_byte_count": mirror_receipt.byte_count,
        "recorded_ns": time.time_ns(),
    }
    write_json(baseline_path, baseline)
    print(json.dumps({"status": "HOST_A_BASELINE_VERIFIED", **baseline}, sort_keys=True))
    return 0


def rehydrate(args: argparse.Namespace) -> int:
    mirror_root = Path(args.mirror_root)
    destination_root = Path(args.destination_root)
    baseline = json.loads(Path(args.baseline).read_text("utf-8"))
    output = Path(args.output)
    runtime = MirrorLaneTransferAdapter(args.mirror_runtime)

    restore_receipt = runtime.restore(mirror_root, destination_root)
    if restore_receipt.manifest_digest != baseline["mirror_manifest_digest"]:
        raise RuntimeError("HOST_B_MIRROR_MANIFEST_MISMATCH")

    controller = LogicalComputerController(destination_root)
    before_projection = controller.read_projection()
    identity = controller.read_identity()
    controller.bind_projection(projection("HOST_B", args.carrier))
    after_identity = controller.read_identity()
    after_digest = controller.state_digest()

    restored = RecursiveComputer.restore_tree(destination_root)
    child = restored.children["CHILD-B"]

    checks = {
        "logical_id_unchanged": after_identity.logical_id == baseline["logical_id"],
        "lineage_unchanged": list(after_identity.lineage) == baseline["lineage"],
        "authority_unchanged": after_identity.authority_id == baseline["authority_id"],
        "state_digest_unchanged": after_digest == baseline["state_digest"],
        "projection_changed": controller.read_projection().projection_id != before_projection.projection_id,
        "host_fingerprint_changed": controller.read_projection().host_fingerprint != baseline["projection"]["host_fingerprint"],
        "r26_state_restored": restored.state["workload"]["status"] == "BOUND",
        "r26_memory_restored": restored.memory["semantic"]["address"] == "LEX://BRAINK/ROOT-A",
        "r26_lineage_restored": list(child.identity.lineage) == ["ROOT-A", "CHILD-B"],
        "mirror_restore_verified": restore_receipt.status == "RESTORE_VERIFIED",
    }
    passed = all(checks.values())
    result = {
        "schema": "braink.logical-computer.host-b-rehydration.v1",
        "claim_id": CLAIM_ID,
        "status": "PASS" if passed else "FAIL",
        "logical_id": after_identity.logical_id,
        "source_projection_id": baseline["projection"]["projection_id"],
        "destination_projection": controller.read_projection().__dict__,
        "state_digest": after_digest,
        "mirror_manifest_digest": restore_receipt.manifest_digest,
        "mirror_runtime": restore_receipt.runtime,
        "checks": checks,
        "recorded_ns": time.time_ns(),
    }
    write_json(output, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("prepare")
    a.add_argument("--state-root", required=True)
    a.add_argument("--mirror-root", required=True)
    a.add_argument("--mirror-runtime", required=True)
    a.add_argument("--baseline", required=True)
    a.add_argument("--carrier", default="local://host-a")
    a.set_defaults(func=prepare)

    b = sub.add_parser("rehydrate")
    b.add_argument("--mirror-root", required=True)
    b.add_argument("--destination-root", required=True)
    b.add_argument("--mirror-runtime", required=True)
    b.add_argument("--baseline", required=True)
    b.add_argument("--output", required=True)
    b.add_argument("--carrier", default="local://host-b")
    b.set_defaults(func=rehydrate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
