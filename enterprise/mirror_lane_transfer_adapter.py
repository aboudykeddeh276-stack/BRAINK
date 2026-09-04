from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import subprocess


@dataclass(frozen=True)
class MirrorLaneTransferReceipt:
    status: str
    source_root: str
    mirror_root: str
    manifest_digest: str
    file_count: int
    byte_count: int
    runtime: str


class MirrorLaneTransferAdapter:
    """Adapter from BRAINK logical-computer migration to the KEDDEH mirror-lane runtime.

    The mirror/update mechanic remains owned by KEDDEH-CLOUD-SERVERS-ID-1. BRAINK
    supplies source/destination state roots and consumes the returned proof receipt.
    """

    def __init__(self, runtime_executable: str | Path):
        self.runtime_executable = Path(runtime_executable)

    def update(self, source_root: str | Path, mirror_root: str | Path) -> MirrorLaneTransferReceipt:
        if not self.runtime_executable.exists():
            raise RuntimeError(f"MIRROR_LANE_RUNTIME_UNAVAILABLE:{self.runtime_executable}")
        proc = subprocess.run(
            [str(self.runtime_executable), "update", "--source", str(source_root), "--mirror", str(mirror_root), "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"MIRROR_LANE_UPDATE_FAILED:{proc.stderr.strip() or proc.stdout.strip()}")
        payload: dict[str, Any] = json.loads(proc.stdout)
        if payload.get("status") != "MIRROR_VERIFIED":
            raise RuntimeError(f"MIRROR_LANE_NOT_VERIFIED:{payload}")
        return MirrorLaneTransferReceipt(
            status=payload["status"], source_root=payload["source_root"], mirror_root=payload["mirror_root"],
            manifest_digest=payload["manifest_digest"], file_count=int(payload["file_count"]),
            byte_count=int(payload["byte_count"]), runtime=payload["runtime"],
        )

    def restore(self, mirror_root: str | Path, destination_root: str | Path) -> MirrorLaneTransferReceipt:
        proc = subprocess.run(
            [str(self.runtime_executable), "restore", "--mirror", str(mirror_root), "--destination", str(destination_root), "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"MIRROR_LANE_RESTORE_FAILED:{proc.stderr.strip() or proc.stdout.strip()}")
        payload = json.loads(proc.stdout)
        if payload.get("status") != "RESTORE_VERIFIED":
            raise RuntimeError(f"MIRROR_LANE_RESTORE_NOT_VERIFIED:{payload}")
        return MirrorLaneTransferReceipt(
            status=payload["status"], source_root=payload["source_root"], mirror_root=payload["mirror_root"],
            manifest_digest=payload["manifest_digest"], file_count=int(payload["file_count"]),
            byte_count=int(payload["byte_count"]), runtime=payload["runtime"],
        )
