from __future__ import annotations

import ast
import hashlib
import hmac
import json
from dataclasses import dataclass, asdict
from typing import Any, Mapping

SCHEMA = "braink.metacircular-vfs-executor.r40/v1"
DEFAULT_LOGICAL_CAPACITY_BYTES = 100 * 1024 * 1024 * 1024 * 1024

EMBEDDED_CORE_SOURCE = """def run_nested_verification(key, seed, deep_generation):
    payload = f\"AKIH_GENESIS::LAYER_{deep_generation}::{seed}\".encode(\"utf-8\")
    return hmac.new(key, payload, digestmod=hashlib.sha256).hexdigest()
"""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SourcePolicy:
    REQUIRED_FUNCTION = "run_nested_verification"
    FORBIDDEN_NODES = (
        ast.Import, ast.ImportFrom, ast.ClassDef, ast.AsyncFunctionDef, ast.Lambda,
        ast.With, ast.AsyncWith, ast.Try, ast.Raise, ast.Delete, ast.Global,
        ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await, ast.NamedExpr,
    )
    FORBIDDEN_CALL_NAMES = {
        "exec", "eval", "compile", "open", "input", "breakpoint",
        "globals", "locals", "vars", "getattr", "setattr", "delattr", "__import__",
    }
    ALLOWED_ATTRIBUTE_NAMES = {"new", "sha256", "encode", "hexdigest"}

    @classmethod
    def validate(cls, source: str) -> dict[str, Any]:
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as exc:
            return {"status": "FAILED:SOURCE_SYNTAX", "detail": str(exc)}

        top_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        if len(tree.body) != 1 or len(top_functions) != 1 or top_functions[0].name != cls.REQUIRED_FUNCTION:
            return {"status": "FAILED:SOURCE_SHAPE"}

        for node in ast.walk(tree):
            if isinstance(node, cls.FORBIDDEN_NODES):
                return {"status": f"FAILED:SOURCE_POLICY:{type(node).__name__}"}
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("__") or node.attr not in cls.ALLOWED_ATTRIBUTE_NAMES:
                    return {"status": f"FAILED:SOURCE_ATTRIBUTE:{node.attr}"}
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                return {"status": f"FAILED:SOURCE_NAME:{node.id}"}
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in cls.FORBIDDEN_CALL_NAMES:
                    return {"status": f"FAILED:SOURCE_CALL:{node.func.id}"}

        return {
            "status": "VALIDATED",
            "ast_root": sha256_hex(ast.dump(tree, include_attributes=False).encode()),
        }


@dataclass(frozen=True)
class MetacircularReceipt:
    schema: str
    node_id: str
    generation: int
    source_uri: str
    source_sha256: str
    ast_root: str
    seed_root: str
    parent_proof_root: str
    nested_proof_root: str
    capability: str
    capability_implementation_ref: str
    logical_capacity_bytes: int
    execution_model: str
    receipt_root: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetacircularVFSExecutor:
    """Hash-pinned dynamic verification executor over the resident NodeVFS.

    This is not an OS sandbox. It only executes source that was written/read back
    through NodeVFS, matches an expected SHA-256, passes SourcePolicy, and is
    covered by an already RESOLVED resident capability receipt.
    """

    def __init__(self, *, node_vfs: Any, logical_capacity_bytes: int = DEFAULT_LOGICAL_CAPACITY_BYTES):
        self.node_vfs = node_vfs
        self.logical_capacity_bytes = int(logical_capacity_bytes)
        if self.logical_capacity_bytes < 1:
            raise ValueError("LOGICAL_CAPACITY_INVALID")

    @staticmethod
    def _require_capability(capability_resolution: Mapping[str, Any]) -> tuple[str, str]:
        status = str(capability_resolution.get("status", ""))
        if status != "RESOLVED":
            raise PermissionError(f"BLOCKED:CAPABILITY:{status or 'UNRESOLVED'}")
        name = str(capability_resolution.get("name") or capability_resolution.get("capability") or "").strip()
        impl = str(capability_resolution.get("implementation_ref") or "").strip()
        if not name or not impl:
            raise PermissionError("BLOCKED:CAPABILITY_RECEIPT_INCOMPLETE")
        return name, impl

    @staticmethod
    def _read_value(read_receipt: Mapping[str, Any]) -> Any:
        result = read_receipt.get("result")
        if not isinstance(result, Mapping):
            raise RuntimeError("FAILED:VFS_READ_RECEIPT")
        if result.get("status") != "READ":
            raise RuntimeError(f"FAILED:VFS_READ:{result.get('status')}")
        if "value" not in result:
            raise RuntimeError("FAILED:VFS_READ_VALUE_MISSING")
        return result["value"]

    def execute(
        self,
        *,
        node_id: str,
        root_seed: str,
        secret_key: bytes,
        generation: int,
        source: str,
        expected_source_sha256: str,
        capability_resolution: Mapping[str, Any],
        parent_proof_root: str = "",
    ) -> dict[str, Any]:
        capability, implementation_ref = self._require_capability(capability_resolution)

        if int(generation) < 1:
            raise ValueError("GENERATION_MUST_BE_POSITIVE")
        if not secret_key:
            raise ValueError("SECRET_KEY_REQUIRED")
        if not root_seed:
            raise ValueError("ROOT_SEED_REQUIRED")

        source_bytes = source.encode("utf-8")
        source_hash = sha256_hex(source_bytes)
        if not hmac.compare_digest(source_hash, str(expected_source_sha256)):
            raise ValueError("SOURCE_HASH_MISMATCH")

        policy = SourcePolicy.validate(source)
        if policy.get("status") != "VALIDATED":
            raise ValueError(policy["status"])

        source_path = f"sys/metacircular/generation_{int(generation)}_core"
        source_record = {
            "schema": SCHEMA,
            "encoding": "utf-8",
            "generation": int(generation),
            "logical_capacity_bytes": self.logical_capacity_bytes,
            "source_sha256": source_hash,
            "source": source,
        }
        write_receipt = self.node_vfs.write(node_id, source_path, source_record)
        read_receipt = self.node_vfs.read(node_id, source_path)
        readback = self._read_value(read_receipt)

        if not isinstance(readback, Mapping):
            raise RuntimeError("FAILED:VFS_SOURCE_RECORD_TYPE")
        if readback.get("source_sha256") != source_hash:
            raise RuntimeError("FAILED:VFS_SOURCE_HASH_READBACK")
        readback_source = str(readback.get("source", ""))
        if sha256_hex(readback_source.encode("utf-8")) != source_hash:
            raise RuntimeError("FAILED:VFS_SOURCE_BYTES_READBACK")

        code = compile(readback_source, write_receipt["logical"], "exec")
        global_ns = {"__builtins__": {}, "hmac": hmac, "hashlib": hashlib}
        local_ns: dict[str, Any] = {}
        exec(code, global_ns, local_ns)
        fn = local_ns.get(SourcePolicy.REQUIRED_FUNCTION)
        if not callable(fn):
            raise RuntimeError("FAILED:NESTED_ENTRYPOINT_MISSING")

        nested_root = str(fn(bytes(secret_key), str(root_seed), int(generation) + 1))
        expected_nested = hmac.new(
            bytes(secret_key),
            f"AKIH_GENESIS::LAYER_{int(generation)+1}::{root_seed}".encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(nested_root, expected_nested):
            raise RuntimeError("FAILED:NESTED_PROOF_MISMATCH")

        receipt_body = {
            "schema": SCHEMA,
            "node_id": str(node_id),
            "generation": int(generation),
            "source_uri": write_receipt["logical"],
            "source_sha256": source_hash,
            "ast_root": policy["ast_root"],
            "seed_root": sha256_hex(root_seed.encode("utf-8")),
            "parent_proof_root": str(parent_proof_root),
            "nested_proof_root": nested_root,
            "capability": capability,
            "capability_implementation_ref": implementation_ref,
            "logical_capacity_bytes": self.logical_capacity_bytes,
            "execution_model": "HASH_PINNED_VFS_PYTHON",
        }
        receipt_root = sha256_hex(canonical_json(receipt_body))
        receipt = MetacircularReceipt(**receipt_body, receipt_root=receipt_root)

        receipt_path = f"sys/metacircular/generation_{int(generation)}_receipt"
        self.node_vfs.write(node_id, receipt_path, receipt.to_dict())

        return {
            "status": "VALIDATED_BOUNDED",
            "receipt": receipt.to_dict(),
            "source_write": write_receipt,
            "source_read": read_receipt,
        }
