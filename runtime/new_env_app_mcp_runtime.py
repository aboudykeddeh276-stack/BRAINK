#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
from pathlib import Path

from mcp.braink_process_adapter.new_env_app_bridge import NewEnvAppBridge


def main() -> int:
    bridge = NewEnvAppBridge()
    root = bridge.locate()
    node = shutil.which("node")
    if not node:
        raise RuntimeError("NEW_ENV_APP_NODE_ROUTE_UNBOUND")
    os.chdir(root)
    os.execv(node, [node, str(root / "mcp" / "server.mjs")])
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
