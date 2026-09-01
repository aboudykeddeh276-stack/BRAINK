#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from resident_runtime_controller import retain_latest_oracle  # noqa: E402


def main() -> int:
    first = {"ok": True, "results": [{"command": "oracle-a", "ok": True}]}
    second = {"ok": False, "results": [{"command": "oracle-b", "ok": False}]}

    assert retain_latest_oracle(None, None) is None
    assert retain_latest_oracle(None, first) == first
    assert retain_latest_oracle(first, None) == first
    assert retain_latest_oracle(first, second) == second
    assert retain_latest_oracle(second, None) == second

    print("RESIDENT_ORACLE_PROJECTION_CONTINUITY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
