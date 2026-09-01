#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def path_mutex(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


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


def atomic_write_bytes(path: Path, data: bytes, *, preserve_mode_from: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        if preserve_mode_from is not None and preserve_mode_from.exists():
            try:
                os.fchmod(fd, preserve_mode_from.stat().st_mode & 0o7777)
            except OSError:
                pass
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


def atomic_write_text(path: Path, text: str, *, preserve_mode_from: Path | None = None) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), preserve_mode_from=preserve_mode_from)


def append_jsonl_fsync(
    path: Path,
    value: Any,
    *,
    row_field: str | None = None,
    hash_field: str | None = None,
    parent_hash_field: str | None = None,
) -> tuple[int, Any]:
    """Append one canonical JSON event under process-local and inter-process locks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mutex = path_mutex(path)
    with mutex:
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if fcntl is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)

            row = 1
            previous_hash = "GENESIS"
            if path.exists():
                with path.open("rb") as existing:
                    lines = [line for line in existing if line.strip()]
                row += len(lines)
                if lines and hash_field:
                    try:
                        previous = json.loads(lines[-1].decode("utf-8"))
                        previous_hash = str(previous.get(hash_field) or "GENESIS")
                    except Exception as exc:
                        raise RuntimeError("cannot extend malformed ledger tail") from exc

            persisted = dict(value) if isinstance(value, dict) else value
            if isinstance(persisted, dict) and row_field:
                persisted[row_field] = row
            if isinstance(persisted, dict) and parent_hash_field:
                persisted[parent_hash_field] = previous_hash
            if isinstance(persisted, dict) and hash_field:
                unsigned = dict(persisted)
                unsigned.pop(hash_field, None)
                persisted[hash_field] = sha256_bytes(canonical_json_bytes(unsigned))

            line = canonical_json_bytes(persisted) + b"\n"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line)
                os.fsync(fd)
            finally:
                os.close(fd)
            return row, persisted
        finally:
            if fcntl is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
