from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from enterprise.substrate_adapters import FileJsonAdapter, SQLiteJsonAdapter, digest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


payload = {"generation": 18, "capability": "hash", "state": "resident"}
expected = hashlib.sha256(canonical(payload)).hexdigest()

assert digest(payload) == expected
assert digest(payload) == digest({"state": "resident", "capability": "hash", "generation": 18})
assert digest({**payload, "generation": 19}) != expected

with tempfile.TemporaryDirectory() as td:
    root = Path(td)

    file_adapter = FileJsonAdapter()
    file_result = file_adapter.apply(
        f"file://{root / 'object.json'}",
        "KEX://R18/VFS/HASH",
        "WRITE",
        payload,
    )
    assert file_result["status"] == "COMMITTED"
    assert file_result["value_hash"] == expected

    sqlite_adapter = SQLiteJsonAdapter()
    backing = f"sqlite://{root / 'objects.sqlite3'}#objects"
    sqlite_result = sqlite_adapter.apply(
        backing,
        "KEX://R18/VFS/HASH",
        "WRITE",
        payload,
    )
    assert sqlite_result["status"] == "COMMITTED"
    assert sqlite_result["value_hash"] == expected
    readback = sqlite_adapter.apply(backing, "KEX://R18/VFS/HASH", "READ")
    assert readback["status"] == "READ"
    assert readback["value_hash"] == expected
    assert readback["value"] == payload

print(json.dumps({
    "status": "PASS",
    "capability": "hash",
    "classification": "REUSE_AND_QUALIFY",
    "implementation_ref": "enterprise/substrate_adapters.py::digest",
    "sha256": expected,
    "claim_boundary": "software SHA-256 content hashing and adapter value-hash persistence only; no hardware-rooted integrity or remote durability implied",
}, sort_keys=True))
