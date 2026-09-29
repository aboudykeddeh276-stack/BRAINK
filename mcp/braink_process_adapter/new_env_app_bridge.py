from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class NewEnvAppRouteError(RuntimeError):
    pass


class NewEnvAppBridge:
    """BRAINK carrier for the NEW-ENV-APP MCP/runtime repository."""

    def __init__(self, root: str | Path | None = None):
        self.explicit_root = Path(root).expanduser().resolve() if root else None

    @staticmethod
    def _candidate_roots() -> list[Path]:
        here = Path(__file__).resolve()
        braink_root = here.parents[2]
        parent = braink_root.parent
        candidates: list[Path] = []
        env = os.environ.get("NEW_ENV_APP_ROOT", "").strip()
        if env:
            candidates.append(Path(env).expanduser())
        candidates.extend([
            parent / "NEW-ENV-APP",
            Path("/mnt/data/NEW-ENV-APP"),
            Path("/workspace/NEW-ENV-APP"),
            Path.home() / "NEW-ENV-APP",
        ])
        out: list[Path] = []
        seen: set[str] = set()
        for value in candidates:
            try:
                resolved = value.resolve()
            except OSError:
                resolved = value
            key = str(resolved)
            if key not in seen:
                seen.add(key)
                out.append(resolved)
        return out

    def locate(self) -> Path:
        candidates = [self.explicit_root] if self.explicit_root else self._candidate_roots()
        checked: list[str] = []
        for root in candidates:
            if root is None:
                continue
            checked.append(str(root))
            if (root / "mcp" / "server.mjs").is_file() and (root / "mcp" / "runtime-manifest.json").is_file():
                return root
        raise NewEnvAppRouteError(
            "NEW_ENV_APP_ROUTE_UNBOUND:" + json.dumps({"checked": checked}, separators=(",", ":"))
        )

    @staticmethod
    def _node() -> str:
        node = shutil.which("node")
        if not node:
            raise NewEnvAppRouteError("NEW_ENV_APP_NODE_ROUTE_UNBOUND")
        return node

    def manifest(self) -> dict[str, Any]:
        root = self.locate()
        return json.loads((root / "mcp" / "runtime-manifest.json").read_text(encoding="utf-8"))

    def invoke(self, tool: str, payload: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
        root = self.locate()
        cmd = [self._node(), str(root / "mcp" / "server.mjs"), "--invoke", tool, json.dumps(payload or {}, separators=(",", ":"))]
        proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=timeout)
        result: dict[str, Any] = {
            "route": "new-env-app-mcp",
            "repository_root": str(root),
            "tool": tool,
            "exit_code": proc.returncode,
            "stderr": proc.stderr.strip() or None,
        }
        stdout = proc.stdout.strip()
        try:
            result["result"] = json.loads(stdout) if stdout else None
        except json.JSONDecodeError:
            result["result"] = {"raw_stdout": stdout}
        result["status"] = "RETURNED" if proc.returncode == 0 else "FAILED"
        if proc.returncode != 0:
            raise NewEnvAppRouteError(json.dumps(result, sort_keys=True))
        return result

    def self_test(self) -> dict[str, Any]:
        return self.invoke("runtime_self_test", {})
