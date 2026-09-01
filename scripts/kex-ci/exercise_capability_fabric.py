#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from capability_fabric import exercise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engage-tl2", action="store_true")
    args = parser.parse_args()
    report = exercise(engage_tl2=args.engage_tl2)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == "LOCAL_CAPABILITY_FABRIC_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
