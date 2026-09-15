from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deployment.kex_runtime_service_r40 import CanonicalRuntimeHost
from runtime.R25.system_evolution_runtime import canonical_json


def _load_command(path: str | None):
    if path:
        body = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        body = json.load(sys.stdin)
    if not isinstance(body, dict):
        raise ValueError("CANONICAL_COMMAND_MUST_BE_OBJECT")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one canonical BRAINK/KEX R40 command through the resident runtime graph.")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--computer-id", default="A")
    parser.add_argument("--command-file")
    args = parser.parse_args()
    try:
        command = _load_command(args.command_file)
        host = CanonicalRuntimeHost(args.state_root, args.computer_id)
        result = host.canonical_execute(command)
        print(canonical_json(result))
        status = str(result.get("status", ""))
        return 2 if status.startswith(("BLOCKED:", "FAILED:")) else 0
    except Exception as exc:
        print(canonical_json({"status": "FAILED:CLI_PROJECTION", "error": type(exc).__name__ + ":" + str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
