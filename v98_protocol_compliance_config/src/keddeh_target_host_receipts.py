#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class TargetHostReceipt:
    check_id: str
    status: str
    detail: str


def run_command(command: List[str]) -> str:
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=10)
        return (result.stdout or result.stderr or "").strip()
    except Exception as exc:
        return f"ERROR:{exc}"


def collect_target_host_receipts() -> List[TargetHostReceipt]:
    system = platform.system()
    machine = platform.machine()
    receipts = [
        TargetHostReceipt("host_os", "LOCAL_PASS" if system == "Darwin" else "TARGET_HOST_REQUIRED", f"system={system}"),
        TargetHostReceipt("host_arch", "LOCAL_PASS" if machine in {"arm64", "aarch64"} else "TARGET_HOST_REQUIRED", f"machine={machine}"),
    ]
    if system == "Darwin":
        receipts.append(TargetHostReceipt("launchctl", "LOCAL_PASS" if run_command(["/bin/launchctl", "help"]) else "LOCAL_FAIL", "launchctl reachable"))
        receipts.append(TargetHostReceipt("iostat", "LOCAL_PASS" if run_command(["/usr/sbin/iostat", "-d", "-c", "1"]) else "LOCAL_FAIL", "iostat sample attempted"))
    else:
        receipts.append(TargetHostReceipt("launchctl", "TARGET_HOST_REQUIRED", "macOS launchd unavailable in this runtime"))
        receipts.append(TargetHostReceipt("iostat", "TARGET_HOST_REQUIRED", "macOS iostat unavailable in this runtime"))
    return receipts


def main() -> int:
    out = Path("evidence/target_host_receipts.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in collect_target_host_receipts()]
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
