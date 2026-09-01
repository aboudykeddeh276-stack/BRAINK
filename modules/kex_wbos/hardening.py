#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def constant_time_bearer_matches(header: str, token: str) -> bool:
    prefix = "Bearer "
    if not header.startswith(prefix):
        return False
    supplied = header[len(prefix):]
    return hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8"))


def is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def require_secure_bind(host: str, token: str | None) -> None:
    if is_loopback_host(host):
        return
    if not token:
        raise RuntimeError(
            "KEX_BEARER_TOKEN is required for any non-loopback action-runtime bind. "
            "Refusing to expose mutation routes without an authentication membrane."
        )


def contained_path(base: Path, candidate: Path) -> Path:
    base_resolved = base.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes runtime root: {resolved}") from exc
    return resolved


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def append_jsonl_fsync(path: Path, value: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json_bytes(value) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)
    with path.open("rb") as handle:
        return sum(1 for _ in handle)
