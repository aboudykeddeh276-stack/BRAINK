from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_canonical(payload) + "\n", encoding="utf-8")
    tmp.replace(path)


def _artifact_inventory(path: Path) -> tuple[int, int, str]:
    """Return file_count, total_bytes and a deterministic content root.

    Registration performs the expensive byte walk once. Normal readiness checks use
    the recorded file count/size plus bridge readback, so large model trees are not
    re-hashed every time an IDE asks whether a node is ready.
    """
    if not path.exists():
        raise FileNotFoundError(f"MODEL_ARTIFACT_NOT_FOUND:{path}")

    files: Iterable[Path]
    if path.is_file():
        files = (path,)
        root = path.parent
    elif path.is_dir():
        files = tuple(sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: p.as_posix()))
        root = path
    else:
        raise ValueError(f"MODEL_ARTIFACT_NOT_FILE_OR_DIRECTORY:{path}")

    files = tuple(files)
    if not files:
        raise ValueError(f"MODEL_ARTIFACT_EMPTY:{path}")

    digest = hashlib.sha256()
    total = 0
    for item in files:
        rel = item.relative_to(root).as_posix() if item != path or path.is_dir() else item.name
        stat = item.stat()
        total += stat.st_size
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        with item.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)

    if total <= 0:
        raise ValueError(f"MODEL_ARTIFACT_ZERO_BYTES:{path}")
    return len(files), total, digest.hexdigest()


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    backing_path: str
    vfs_uri: str
    model_format: str
    content_root: str
    file_count: int
    total_bytes: int
    capabilities: dict[str, Any]
    authority: str = "BRAINK_AGENT_AUTHORITY"
    authorship: str = "KEDDEH_SYSTEMS"


class ModelResidencyManager:
    """Bind physical model artifacts into the BRAINK VFS + IL-LLM node surface.

    MCP exposes this service, but does not own model, node, VFS or IL-LLM authority.
    A node cannot report READY unless the physical artifact, VFS binding, IL-LLM
    projection and agent-authority binding are all observed.
    """

    SCHEMA = "braink.mcp-system-surface.r8/v1"

    def __init__(self, state_dir: str | Path, vfs_bridge: Any, illlm_bridge: Any):
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.models_path = self.state_dir / "models.json"
        self.nodes_path = self.state_dir / "nodes.json"
        self.vfs = vfs_bridge
        self.illlm = illlm_bridge

    @staticmethod
    def _read(path: Path, key: str) -> dict[str, Any]:
        if not path.exists():
            return {"schema": ModelResidencyManager.SCHEMA, key: {}}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get(key, {}), dict):
            raise RuntimeError(f"CORRUPT_SYSTEM_SURFACE_STATE:{path}")
        return value

    def _models(self) -> dict[str, Any]:
        return self._read(self.models_path, "models")

    def _nodes(self) -> dict[str, Any]:
        return self._read(self.nodes_path, "nodes")

    def register_model(
        self,
        model_id: str,
        backing_path: str,
        *,
        model_format: str = "safetensors",
        expected_content_root: str | None = None,
        capabilities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model_id = model_id.strip()
        if not model_id:
            raise ValueError("MODEL_ID_REQUIRED")
        path = Path(backing_path).expanduser().resolve()
        file_count, total_bytes, content_root = _artifact_inventory(path)
        if expected_content_root and content_root != expected_content_root.lower():
            raise ValueError(
                f"MODEL_CONTENT_ROOT_MISMATCH:{model_id}:expected={expected_content_root.lower()}:observed={content_root}"
            )

        descriptor = ModelDescriptor(
            model_id=model_id,
            backing_path=str(path),
            vfs_uri=f"vfs://braink/models/{model_id}",
            model_format=model_format,
            content_root=content_root,
            file_count=file_count,
            total_bytes=total_bytes,
            capabilities=dict(capabilities or {}),
        )
        state = self._models()
        prior = state["models"].get(model_id)
        if prior and prior.get("content_root") != content_root:
            raise ValueError(f"MODEL_ID_CONTENT_CONFLICT:{model_id}")
        state["models"][model_id] = asdict(descriptor)
        _atomic_json_write(self.models_path, state)
        return {"status": "REGISTERED", "model": asdict(descriptor)}

    @staticmethod
    def _normalize_model_ids(models: dict[str, Any]) -> list[str]:
        if not isinstance(models, dict) or not models:
            raise ValueError("NODE_MODELS_REQUIRED")
        result = sorted(str(key) for key in models.keys())
        if any(not item for item in result):
            raise ValueError("NODE_MODEL_ID_INVALID")
        return result

    @staticmethod
    def _normalize_authorities(authorities: dict[str, Any], model_ids: list[str]) -> dict[str, list[str]]:
        if not isinstance(authorities, dict) or not authorities:
            raise ValueError("AGENT_AUTHORITIES_REQUIRED")
        known = set(model_ids)
        normalized: dict[str, list[str]] = {}
        for agent_id, raw in sorted(authorities.items()):
            if not isinstance(agent_id, str) or not agent_id:
                raise ValueError("AGENT_ID_INVALID")
            if not isinstance(raw, list) or not raw or any(not isinstance(item, str) for item in raw):
                raise ValueError(f"AGENT_MODEL_BINDINGS_INVALID:{agent_id}")
            bound = sorted(set(raw))
            unknown = sorted(set(bound) - known)
            if unknown:
                raise ValueError(f"AGENT_MODEL_NOT_IN_NODE:{agent_id}:{','.join(unknown)}")
            normalized[agent_id] = bound
        return normalized

    @staticmethod
    def _physical_readback(descriptor: dict[str, Any]) -> dict[str, Any]:
        path = Path(descriptor["backing_path"])
        if not path.exists():
            return {"status": "MISSING", "path": str(path)}
        if path.is_file():
            files = 1
            total = path.stat().st_size
        else:
            entries = [p for p in path.rglob("*") if p.is_file()]
            files = len(entries)
            total = sum(p.stat().st_size for p in entries)
        expected_files = int(descriptor["file_count"])
        expected_total = int(descriptor["total_bytes"])
        status = "PRESENT" if files == expected_files and total == expected_total and total > 0 else "DRIFTED"
        return {
            "status": status,
            "path": str(path),
            "file_count": files,
            "total_bytes": total,
            "expected_file_count": expected_files,
            "expected_total_bytes": expected_total,
        }

    def bootstrap_node(
        self,
        node_id: str,
        models: dict[str, Any],
        agent_authorities: dict[str, Any],
    ) -> dict[str, Any]:
        node_id = node_id.strip()
        if not node_id:
            raise ValueError("NODE_ID_REQUIRED")
        model_ids = self._normalize_model_ids(models)
        authorities = self._normalize_authorities(agent_authorities, model_ids)
        model_state = self._models()["models"]

        missing = [model_id for model_id in model_ids if model_id not in model_state]
        if missing:
            raise KeyError(f"MODEL_NOT_REGISTERED:{','.join(missing)}")

        bindings: dict[str, Any] = {}
        for model_id in model_ids:
            descriptor = model_state[model_id]
            physical = self._physical_readback(descriptor)
            if physical["status"] != "PRESENT":
                bindings[model_id] = {"physical": physical, "status": "NOT_READY"}
                continue

            backing = f"file://{descriptor['backing_path']}"
            vfs = self.vfs.bind(descriptor["vfs_uri"], backing)
            illlm_payload = {
                **descriptor,
                "node_id": node_id,
                "agent_authorities": {
                    agent_id: bound for agent_id, bound in authorities.items() if model_id in bound
                },
                "residency": "PREINSTALLED_MOUNTED",
            }
            illlm = self.illlm.bind_model(node_id, illlm_payload)
            ready = vfs.get("status") == "BOUND" and illlm.get("status") in {"BOUND", "REGISTERED", "PASS"}
            bindings[model_id] = {
                "status": "READY" if ready else "NOT_READY",
                "physical": physical,
                "vfs": vfs,
                "illlm": illlm,
            }

        status = "READY" if bindings and all(row["status"] == "READY" for row in bindings.values()) else "NOT_READY"
        node_record = {
            "node_id": node_id,
            "status": status,
            "model_ids": model_ids,
            "agent_authorities": authorities,
            "bindings": bindings,
            "readiness_law": "PHYSICAL_AND_VFS_AND_ILLLM_AND_AGENT_AUTHORITY",
        }
        state = self._nodes()
        state["nodes"][node_id] = node_record
        _atomic_json_write(self.nodes_path, state)
        return node_record

    def readiness(self, node_id: str) -> dict[str, Any]:
        node = self._nodes()["nodes"].get(node_id)
        if not node:
            return {"node_id": node_id, "status": "UNREGISTERED"}

        model_state = self._models()["models"]
        checks: dict[str, Any] = {}
        for model_id in node.get("model_ids", []):
            descriptor = model_state.get(model_id)
            if descriptor is None:
                checks[model_id] = {"status": "NOT_READY", "reason": "MODEL_NOT_REGISTERED"}
                continue
            physical = self._physical_readback(descriptor)
            backing = f"file://{descriptor['backing_path']}"
            vfs = self.vfs.read(descriptor["vfs_uri"], backing)
            illlm = self.illlm.read_model(node_id, model_id)
            ready = (
                physical["status"] == "PRESENT"
                and self._vfs_readback_ok(vfs)
                and illlm.get("status") in {"BOUND", "REGISTERED", "PASS"}
            )
            checks[model_id] = {
                "status": "READY" if ready else "NOT_READY",
                "physical": physical,
                "vfs": vfs,
                "illlm": illlm,
            }

        status = "READY" if checks and all(row["status"] == "READY" for row in checks.values()) else "NOT_READY"
        return {
            "node_id": node_id,
            "status": status,
            "checks": checks,
            "agent_authorities": node.get("agent_authorities", {}),
            "readiness_law": node.get("readiness_law"),
        }

    @staticmethod
    def _vfs_readback_ok(value: dict[str, Any]) -> bool:
        if value.get("status") in {"BOUND", "PASS"}:
            return True
        bind = value.get("bind") if isinstance(value, dict) else None
        readback = value.get("readback") if isinstance(value, dict) else None
        return (
            isinstance(bind, dict)
            and bind.get("status") == "BOUND"
            and isinstance(readback, dict)
            and readback.get("status") not in {"NOT_EXECUTED", "UNBOUND_RUNTIME_PATH", "LOAD_FAILED"}
        )

    def system_manifest(self) -> dict[str, Any]:
        models = self._models()["models"]
        nodes = self._nodes()["nodes"]
        return {
            "schema": self.SCHEMA,
            "external_surface": {
                "protocol": "MCP",
                "role": "SYSTEM_SUPERFACE",
                "authority": "PROJECTION_AND_INVOCATION_ONLY",
                "entrypoint": "mcp/braink_process_adapter/main.py",
            },
            "internal_authority": {
                "orchestrator": "braink://local/orchestrator",
                "agent_authority": "braink://agent-control",
                "semantic_traversal": "illlm://local/traversal",
                "vfs": "vfs://kex/root",
                "model_namespace": "vfs://braink/models",
            },
            "loadout": [
                "USER_SURFACES",
                "AGENT_AUTHORITY",
                "IL_LLM",
                "RUNTIME",
                "VFS",
                "NODE_SUBSTRATE",
            ],
            "model_count": len(models),
            "node_count": len(nodes),
            "ready_nodes": sorted(node_id for node_id, row in nodes.items() if row.get("status") == "READY"),
            "non_equivalence": [
                "MCP != BRAINK authority",
                "MCP != IL-LLM",
                "MCP != VFS",
                "model metadata != model weights",
                "logical residency != duplicated physical bytes",
            ],
        }
