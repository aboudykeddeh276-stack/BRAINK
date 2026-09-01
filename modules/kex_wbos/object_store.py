#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hardening import atomic_write_bytes, atomic_write_text, canonical_json_bytes, contained_path, sha256_bytes


class ContentAddressedStore:
    """Immutable SHA-256 object store over the existing filesystem substrate.

    The physical filesystem remains the carrier. Object identity is derived from
    content, so logical identity is independent of the mutable source path.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.objects = self.root / "sha256"
        self.refs = self.root / "refs"

    def put_bytes(self, data: bytes, *, media_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        digest = sha256_bytes(data)
        object_path = contained_path(self.root, self.objects / digest[:2] / digest)
        meta_path = object_path.with_suffix(".meta.json")
        if object_path.exists():
            if sha256_bytes(object_path.read_bytes()) != digest:
                raise RuntimeError("content-address collision or object-store corruption detected")
        else:
            atomic_write_bytes(object_path, data)
        meta = {
            "objectId": f"sha256:{digest}",
            "sha256": digest,
            "bytes": len(data),
            "mediaType": media_type,
            "metadata": metadata or {},
        }
        if not meta_path.exists():
            atomic_write_text(meta_path, json.dumps(meta, indent=2, sort_keys=True) + "\n")
        return {**meta, "carrierPath": object_path.as_posix()}

    def put_json(self, value: Any, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.put_bytes(canonical_json_bytes(value), media_type="application/json", metadata=metadata)

    def bind_ref(self, ref_name: str, object_id: str) -> dict[str, str]:
        if not ref_name or any(part in ref_name for part in ("..", "\\")) or ref_name.startswith("/"):
            raise ValueError("invalid object-store ref")
        ref_path = contained_path(self.refs, self.refs / f"{ref_name}.json")
        payload = {"ref": ref_name, "objectId": object_id}
        atomic_write_text(ref_path, json.dumps(payload, sort_keys=True) + "\n")
        return payload

    def get(self, object_id: str) -> bytes:
        if not object_id.startswith("sha256:"):
            raise ValueError("unsupported object id")
        digest = object_id.split(":", 1)[1]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid sha256 object id")
        path = contained_path(self.root, self.objects / digest[:2] / digest)
        data = path.read_bytes()
        if sha256_bytes(data) != digest:
            raise RuntimeError("object-store integrity verification failed")
        return data
