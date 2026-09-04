from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _probe_process() -> dict[str, Any]:
    p = subprocess.run([sys.executable, "-c", "print('BRAINK_EXECUTOR_SENTINEL')"], capture_output=True, text=True, check=False)
    return {"ok": p.returncode == 0 and p.stdout.strip() == "BRAINK_EXECUTOR_SENTINEL", "returncode": p.returncode}


def _probe_tcp() -> dict[str, Any]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    conn, _ = server.accept()
    client.sendall(b"BRAINK_TCP_SENTINEL")
    data = conn.recv(64)
    conn.close(); client.close(); server.close()
    return {"ok": data == b"BRAINK_TCP_SENTINEL", "port": port}


def _probe_sqlite() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        db = sqlite3.connect(Path(td) / "probe.sqlite")
        db.execute("create table probe (value text not null)")
        db.execute("insert into probe values (?)", ("BRAINK_SQLITE_SENTINEL",))
        db.commit()
        value = db.execute("select value from probe").fetchone()[0]
        db.close()
    return {"ok": value == "BRAINK_SQLITE_SENTINEL"}


def _probe_filesystem() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); source = root / "source"; target = root / "target"
        source.write_text("BRAINK_FS_SENTINEL", encoding="utf-8")
        os.replace(source, target)
        return {"ok": target.read_text("utf-8") == "BRAINK_FS_SENTINEL"}


def probe() -> dict[str, Any]:
    checks = {
        "python": sys.version,
        "openssl": ssl.OPENSSL_VERSION,
        "process_spawn": _probe_process(),
        "tcp_loopback": _probe_tcp(),
        "sqlite": _probe_sqlite(),
        "filesystem_mutation": _probe_filesystem(),
        "git": shutil.which("git") is not None,
    }
    serial = json.dumps({"platform": platform.platform(), "machine": platform.machine(), "checks": checks}, sort_keys=True)
    fingerprint = hashlib.sha256(serial.encode("utf-8")).hexdigest()
    ok = all(v.get("ok", v) if isinstance(v, dict) else bool(v) for v in checks.values())
    return {
        "schema": "braink.kex.qualification-executor.v1",
        "executor_id": os.environ.get("BRAINK_EXECUTOR_ID", "runtime-probe"),
        "kind": os.environ.get("BRAINK_EXECUTOR_KIND", "local-executor"),
        "capabilities": sorted(k for k, v in checks.items() if (v.get("ok", False) if isinstance(v, dict) else bool(v))),
        "availability": "AVAILABLE" if ok else "BLOCKED",
        "environment_fingerprint": fingerprint,
        "probe": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = probe()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["availability"] == "AVAILABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
