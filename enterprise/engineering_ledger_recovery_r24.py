from __future__ import annotations

from pathlib import Path
from typing import Any
import fcntl
import hashlib
import json
import os

from enterprise.engineering_control_plane_r24 import root


def _verify_records(records: list[dict[str, Any]]) -> None:
    predecessor = None
    for record in records:
        body = {k: v for k, v in record.items() if k != "record_root"}
        if body.get("predecessor_root") != predecessor:
            raise RuntimeError("LEDGER_CHAIN_BROKEN")
        if root(body) != record.get("record_root"):
            raise RuntimeError("LEDGER_HASH_MISMATCH")
        predecessor = record["record_root"]


def recover_incomplete_tail(path: str | Path) -> dict[str, Any]:
    """Recover only a torn, non-newline-terminated final JSONL append.

    The verified prefix is preserved byte-for-byte. The incomplete fragment is
    content-addressed and quarantined before the canonical file is truncated.
    Complete-line corruption, chain corruption, and concurrent mutation are never
    repaired implicitly.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    raw = path.read_bytes()
    if not raw:
        return {"status": "NOOP_EMPTY", "recovered_root": None, "quarantine_path": None}
    if raw.endswith(b"\n"):
        raise RuntimeError("LEDGER_TAIL_IS_COMPLETE_REFUSE_RECOVERY")

    cut = raw.rfind(b"\n")
    prefix = raw[: cut + 1] if cut >= 0 else b""
    fragment = raw[cut + 1 :]
    if not fragment:
        raise RuntimeError("NO_INCOMPLETE_TAIL")

    records: list[dict[str, Any]] = []
    for line in prefix.decode("utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    _verify_records(records)

    fragment_sha256 = hashlib.sha256(fragment).hexdigest()
    quarantine_dir = path.parent / ".ledger-recovery"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_path = quarantine_dir / f"{path.name}.{fragment_sha256}.fragment"
    if quarantine_path.exists() and quarantine_path.read_bytes() != fragment:
        raise RuntimeError("QUARANTINE_HASH_COLLISION")
    if not quarantine_path.exists():
        with quarantine_path.open("wb") as fh:
            fh.write(fragment)
            fh.flush()
            os.fsync(fh.fileno())

    lock_path = path.with_name(path.name + ".lock")
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock_fh:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            if path.read_bytes() != raw:
                raise RuntimeError("LEDGER_CHANGED_DURING_RECOVERY")
            tmp = path.with_name(path.name + ".recover.tmp")
            with tmp.open("wb") as fh:
                fh.write(prefix)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    return {
        "status": "RECOVERED_INCOMPLETE_TAIL",
        "fragment_sha256": fragment_sha256,
        "fragment_bytes": len(fragment),
        "quarantine_path": str(quarantine_path),
        "recovered_root": records[-1]["record_root"] if records else None,
    }
