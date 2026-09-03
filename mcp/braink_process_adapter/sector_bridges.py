from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any


def _load_module(path: str | Path | None, name: str):
    if not path:
        return None, {"status": "UNBOUND_RUNTIME_PATH", "module": name}
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return None, {"status": "UNBOUND_RUNTIME_PATH", "module": name, "path": str(p)}
    spec = importlib.util.spec_from_file_location(name, p)
    if not spec or not spec.loader:
        return None, {"status": "LOAD_FAILED", "module": name, "path": str(p)}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, None


class ServerRuntimeBridge:
    """Cross-repo bridge to SERVERS-KEDDEHSYSTEMS ProductionActuatorAdapter."""

    def __init__(self):
        self.runtime_path = os.environ.get("BRAINK_SERVERS_RUNTIME_PATH")
        self.actuator_path = os.environ.get("BRAINK_PRODUCTION_ACTUATOR_PATH")

    def _adapter(self):
        mod, err = _load_module(self.runtime_path, "keddeh_server_actuation_runtime")
        if err:
            return None, err
        return mod.ProductionActuatorAdapter(self.actuator_path), None

    def probe(self) -> dict[str, Any]:
        adapter, err = self._adapter()
        return err or adapter.apply("PROBE")

    def apply(self, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        allowed = {"PROBE", "VALIDATE_ORIGIN", "AMEND", "RELEASE", "READBACK"}
        op = operation.upper()
        if op not in allowed:
            return {"status": "UNSUPPORTED_OPERATION", "operation": op, "allowed": sorted(allowed)}
        adapter, err = self._adapter()
        return err or adapter.apply(op, payload or {})


class VirtualMemoryBridge:
    """Cross-repo bridge to VIRTUALISED_MEMORY VirtualMemoryRuntime."""

    def __init__(self):
        self.runtime_path = os.environ.get("BRAINK_VFS_RUNTIME_PATH")

    def _runtime(self):
        mod, err = _load_module(self.runtime_path, "keddeh_virtual_memory_runtime")
        if err:
            return None, err
        return mod.VirtualMemoryRuntime(), None

    def bind(self, logical: str, backing: str) -> dict[str, Any]:
        rt, err = self._runtime()
        return err or rt.bind(logical, backing)

    def write(self, logical: str, backing: str, payload: dict[str, Any]) -> dict[str, Any]:
        rt, err = self._runtime()
        if err:
            return err
        bound = rt.bind(logical, backing)
        if bound.get("status") != "BOUND":
            return {"bind": bound, "write": {"status": "NOT_EXECUTED"}}
        return {"bind": bound, "write": rt.apply(logical, "WRITE", payload)}

    def read(self, logical: str, backing: str) -> dict[str, Any]:
        rt, err = self._runtime()
        if err:
            return err
        bound = rt.bind(logical, backing)
        if bound.get("status") != "BOUND":
            return {"bind": bound, "readback": {"status": "NOT_EXECUTED"}}
        return {"bind": bound, "readback": rt.apply(logical, "READ")}

    def migrate(self, logical: str, current_backing: str, new_backing: str) -> dict[str, Any]:
        rt, err = self._runtime()
        if err:
            return err
        bound = rt.bind(logical, current_backing)
        if bound.get("status") != "BOUND":
            return {"bind": bound, "migration": {"status": "NOT_EXECUTED"}}
        return {"bind": bound, "migration": rt.migrate(logical, new_backing)}
