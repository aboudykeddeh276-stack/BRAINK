#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hardening import atomic_write_text, canonical_json_bytes, sha256_bytes
from lease_fencing import LeaseFenceRegistry


class VFSGenerationStore:
    """Immutable generation descriptors with one atomic canonical-head switch.

    KEX identity remains semantic identity. Generation descriptors are durable
    carrier/proof objects and MUST NOT be treated as the identity itself.
    """

    SCHEMA = "kex.vfs.generation.v1"

    def __init__(self, root: Path, leases: LeaseFenceRegistry):
        self.root = root
        self.generations = root / "generations"
        self.head = root / "HEAD.json"
        self.leases = leases

    @staticmethod
    def _hash_payload(payload: dict[str, Any]) -> str:
        unsigned = dict(payload)
        unsigned.pop("generationHash", None)
        return sha256_bytes(canonical_json_bytes(unsigned))

    def prepare(
        self,
        *,
        kex_identity: str,
        parent_generation: str | None,
        objects: list[dict[str, Any]],
        semantic_bindings: list[dict[str, Any]] | None = None,
        proof_refs: list[str] | None = None,
        observer_state: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        ts = time.time() if now is None else float(now)
        normalized_objects: list[dict[str, Any]] = []
        for obj in objects:
            item = dict(obj)
            if "identity" not in item:
                raise ValueError("generation object missing identity")
            if "contentHash" not in item:
                content = item.get("content")
                if content is None:
                    raise ValueError("generation object requires contentHash or content")
                item["contentHash"] = sha256_bytes(canonical_json_bytes(content))
                item.pop("content", None)
            normalized_objects.append(item)
        normalized_objects.sort(key=lambda x: str(x["identity"]))

        descriptor: dict[str, Any] = {
            "schema": self.SCHEMA,
            "kexIdentity": kex_identity,
            "parentGeneration": parent_generation,
            "createdAt": ts,
            "objects": normalized_objects,
            "semanticBindings": semantic_bindings or [],
            "proofRefs": proof_refs or [],
            "observerState": observer_state or {},
        }
        descriptor["generationHash"] = self._hash_payload(descriptor)
        return descriptor

    def persist_candidate(self, descriptor: dict[str, Any]) -> Path:
        expected = self._hash_payload(descriptor)
        if descriptor.get("generationHash") != expected:
            raise ValueError("generation descriptor hash mismatch")
        self.generations.mkdir(parents=True, exist_ok=True)
        path = self.generations / f"{expected}.json"
        encoded = json.dumps(descriptor, indent=2, sort_keys=True) + "\n"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != descriptor:
                raise RuntimeError("immutable generation hash collision or mutation")
            return path
        atomic_write_text(path, encoded)
        return path

    def promote(
        self,
        *,
        descriptor: dict[str, Any],
        lease_resource: str,
        owner: str,
        fence: int,
        now: float | None = None,
    ) -> dict[str, Any]:
        verdict = self.leases.validate_fence(lease_resource, owner, fence, now=now)
        if verdict.get("state") != "VALID":
            return {"state": "REJECTED", "reason": verdict.get("state")}

        generation_hash = str(descriptor.get("generationHash") or "")
        candidate = self.generations / f"{generation_hash}.json"
        if not candidate.exists():
            return {"state": "REJECTED", "reason": "CANDIDATE_NOT_PERSISTED"}
        persisted = json.loads(candidate.read_text(encoding="utf-8"))
        if self._hash_payload(persisted) != generation_hash:
            return {"state": "REJECTED", "reason": "CANDIDATE_HASH_INVALID"}

        current = self.read_head(allow_missing=True)
        if current and descriptor.get("parentGeneration") != current.get("generationHash"):
            return {
                "state": "REJECTED",
                "reason": "STALE_PARENT",
                "currentGeneration": current.get("generationHash"),
            }

        head = {
            "schema": "kex.vfs.head.v1",
            "kexIdentity": descriptor["kexIdentity"],
            "generationHash": generation_hash,
            "fence": int(fence),
            "owner": owner,
            "promotedAt": time.time() if now is None else float(now),
        }
        head["headHash"] = sha256_bytes(canonical_json_bytes(head))
        atomic_write_text(self.head, json.dumps(head, indent=2, sort_keys=True) + "\n")
        self.leases.mark_effect(lease_resource, owner, fence, "COMPLETED", now=now)
        return {"state": "PROMOTED", **head}

    def read_head(self, *, allow_missing: bool = False) -> dict[str, Any] | None:
        if not self.head.exists():
            if allow_missing:
                return None
            raise FileNotFoundError(self.head)
        head = json.loads(self.head.read_text(encoding="utf-8"))
        unsigned = dict(head)
        observed = unsigned.pop("headHash", None)
        expected = sha256_bytes(canonical_json_bytes(unsigned))
        if observed != expected:
            raise RuntimeError("VFS HEAD integrity failure")
        return head

    def rehydrate(self) -> dict[str, Any]:
        head = self.read_head()
        generation_hash = str(head["generationHash"])
        path = self.generations / f"{generation_hash}.json"
        if not path.exists():
            return {"state": "REBUILD_REQUIRED", "reason": "GENERATION_MISSING", "head": head}
        descriptor = json.loads(path.read_text(encoding="utf-8"))
        if self._hash_payload(descriptor) != generation_hash:
            return {"state": "STALE_REJECTED", "reason": "GENERATION_HASH_INVALID", "head": head}
        if descriptor.get("kexIdentity") != head.get("kexIdentity"):
            return {"state": "STALE_REJECTED", "reason": "IDENTITY_MISMATCH", "head": head}
        return {
            "state": "REHYDRATED",
            "kexIdentity": head["kexIdentity"],
            "generationHash": generation_hash,
            "descriptor": descriptor,
            "observerProjection": descriptor.get("observerState", {}),
        }
