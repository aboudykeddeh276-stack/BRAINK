#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from hardening import append_jsonl_fsync, atomic_write_bytes, atomic_write_text, canonical_json_bytes, contained_path, sha256_bytes


class ContentAddressedStore:
    """Immutable SHA-256 object store over the existing filesystem substrate.

    Content identity is immutable. Per-ingest provenance is append-only and kept
    separate from the canonical object metadata so deduplicated ingests cannot
    silently rewrite the object's durable identity record.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.objects = self.root / "sha256"
        self.refs = self.root / "refs"
        self.ingest_events = self.root / "ingest-events.jsonl"

    def put_bytes(self, data: bytes, *, media_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        digest = sha256_bytes(data)
        object_path = contained_path(self.root, self.objects / digest[:2] / digest)
        meta_path = object_path.with_suffix(".meta.json")
        created = False
        if object_path.exists():
            if sha256_bytes(object_path.read_bytes()) != digest:
                raise RuntimeError("content-address collision or object-store corruption detected")
        else:
            atomic_write_bytes(object_path, data)
            created = True

        if meta_path.exists():
            persisted_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if persisted_meta.get("sha256") != digest or int(persisted_meta.get("bytes", -1)) != len(data):
                raise RuntimeError("content-address metadata divergence detected")
        else:
            persisted_meta = {
                "objectId": f"sha256:{digest}",
                "sha256": digest,
                "bytes": len(data),
                "canonicalMediaType": media_type,
                "createdAt": time.time(),
            }
            atomic_write_text(meta_path, json.dumps(persisted_meta, indent=2, sort_keys=True) + "\n")

        ingest_event = {
            "eventId": f"INGEST-{uuid.uuid4().hex[:16]}",
            "ts": time.time(),
            "objectId": f"sha256:{digest}",
            "sha256": digest,
            "mediaType": media_type,
            "metadata": metadata or {},
            "deduplicated": not created,
        }
        ingest_row, persisted_event = append_jsonl_fsync(self.ingest_events, ingest_event, row_field="ingestRow")
        return {
            **persisted_meta,
            "carrierPath": object_path.as_posix(),
            "objectMetadataPath": meta_path.as_posix(),
            "ingestEvent": persisted_event,
            "ingestRow": ingest_row,
        }

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
