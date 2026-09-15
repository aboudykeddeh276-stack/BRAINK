from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import re

from enterprise.self_addressing_runtime import SelfAddressingRuntime

_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


class NodeVFS:
    """Node-scoped logical VFS projected through SelfAddressingRuntime."""

    def __init__(self, runtime: SelfAddressingRuntime, backing_root: str | Path):
        self.runtime = runtime
        self.backing_root = Path(backing_root)
        self.backing_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_node_id(node_id: str) -> str:
        node_id = str(node_id).strip()
        if not node_id or not _SEGMENT.fullmatch(node_id):
            raise ValueError("INVALID_NODE_ID")
        return node_id

    @staticmethod
    def _validate_relative(logical_path: str) -> tuple[str, ...]:
        raw = str(logical_path).strip().strip("/")
        if not raw:
            raise ValueError("VFS_PATH_REQUIRED")
        parts = tuple(raw.split("/"))
        if any(part in {"", ".", ".."} or not _SEGMENT.fullmatch(part) for part in parts):
            raise ValueError("INVALID_VFS_PATH")
        return parts

    def logical_uri(self, node_id: str, logical_path: str) -> str:
        node = self._validate_node_id(node_id)
        parts = self._validate_relative(logical_path)
        return "vfs://node/" + node + "/" + "/".join(parts)

    def _backing_uri(self, node_id: str, logical_path: str) -> str:
        logical = self.logical_uri(node_id, logical_path)
        key = hashlib.sha256(logical.encode("utf-8")).hexdigest()
        physical = self.backing_root / node_id / f"{key}.json"
        physical.parent.mkdir(parents=True, exist_ok=True)
        return "file://" + str(physical)

    def _ensure_binding(self, logical: str, backing: str, operation: str) -> None:
        existing = self.runtime.binder.bindings.get(logical)
        if existing is not None:
            if existing.backing != backing:
                raise RuntimeError(f"VFS_COLLISION:{logical}")
            return
        bound = self.runtime.binder.bind(logical, backing, operation)
        if bound.get("status") != "BOUND":
            raise RuntimeError(f"VFS_BIND_FAILED:{logical}:{bound.get('status')}")
        self.runtime.checkpoint()

    def write(self, node_id: str, logical_path: str, value: Any) -> dict[str, Any]:
        logical = self.logical_uri(node_id, logical_path)
        backing = self._backing_uri(node_id, logical_path)
        self._ensure_binding(logical, backing, "WRITE")
        result = self.runtime.route(logical, backing, "WRITE", value)
        if result.get("status") != "COMMITTED":
            raise RuntimeError(f"VFS_WRITE_FAILED:{logical}:{result.get('status')}")
        return {"logical": logical, "backing": backing, "result": result}

    def cas_write(self, node_id: str, logical_path: str, value: Any, expected_hash: str | None) -> dict[str, Any]:
        """Compare-and-swap through the resident file adapter.

        `expected_hash=None` means the logical cell must not yet have a committed
        value. Conflict is returned to the caller so higher-level authority code
        can classify it rather than silently overwriting another writer.
        """
        logical = self.logical_uri(node_id, logical_path)
        backing = self._backing_uri(node_id, logical_path)
        self._ensure_binding(logical, backing, "CAS_WRITE")
        result = self.runtime.route(
            logical,
            backing,
            "CAS_WRITE",
            {"expected_hash": expected_hash, "value": value},
        )
        if result.get("status") not in {"COMMITTED", "CONFLICT"}:
            raise RuntimeError(f"VFS_CAS_WRITE_FAILED:{logical}:{result.get('status')}")
        return {"logical": logical, "backing": backing, "result": result}

    def read(self, node_id: str, logical_path: str) -> dict[str, Any]:
        logical = self.logical_uri(node_id, logical_path)
        backing = self._backing_uri(node_id, logical_path)
        self._ensure_binding(logical, backing, "READ")
        result = self.runtime.route(logical, backing, "READ")
        if result.get("status") not in {"READ", "HOLE"}:
            raise RuntimeError(f"VFS_READ_FAILED:{logical}:{result.get('status')}")
        return {"logical": logical, "backing": backing, "result": result}
