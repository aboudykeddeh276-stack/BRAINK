#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import signal
import socketserver
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise.orchestration.resident_execution_fabric import ResidentExecutionFabric

DEFAULT_SOCKET = "/tmp/braink-execution.sock"


def load_key() -> bytes:
    raw = os.environ.get("BRAINK_EXECUTION_HMAC_KEY_HEX", "").strip()
    if not raw:
        raise SystemExit("BRAINK_EXECUTION_HMAC_KEY_HEX is required")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise SystemExit("BRAINK_EXECUTION_HMAC_KEY_HEX must be hexadecimal") from exc
    if len(key) < 32:
        raise SystemExit("BRAINK_EXECUTION_HMAC_KEY_HEX must encode at least 32 bytes")
    return key


class Handler(socketserver.StreamRequestHandler):
    fabric: ResidentExecutionFabric
    def write(self, obj: dict) -> None:
        self.wfile.write(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n")
    def handle(self) -> None:
        line = self.rfile.readline(4 * 1024 * 1024)
        if not line:return
        try:
            request=json.loads(line); op=request.get("op")
            if op=="HEALTH":return self.write(self.fabric.health())
            if op=="READBACK":
                work_id=request.get("work_id")
                if not isinstance(work_id,str) or not work_id:return self.write({"status":"REJECTED","error":"work_id required"})
                state=self.fabric.journal.get(work_id); return self.write({"status":"PASS" if state else "NOT_FOUND","work":state,"events":self.fabric.journal.events(work_id) if state else []})
            if op!="DISPATCH":return self.write({"status":"REJECTED","error":"unsupported op"})
            envelope=request.get("envelope")
            if not isinstance(envelope,dict):return self.write({"status":"REJECTED","error":"envelope required"})
            return self.write(self.fabric.dispatch(envelope))
        except Exception as exc:self.write({"status":"REJECTED","error":f"{type(exc).__name__}:{exc}"})


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True
    allow_reuse_address=True


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--socket",default=os.environ.get("BRAINK_EXECUTION_SOCKET",DEFAULT_SOCKET)); ap.add_argument("--state-dir",default=os.environ.get("BRAINK_EXECUTION_STATE",str(ROOT/"runtime"/"resident-execution"))); args=ap.parse_args()
    socket_path=Path(args.socket); socket_path.parent.mkdir(parents=True,exist_ok=True)
    if socket_path.exists() or socket_path.is_symlink():socket_path.unlink()
    Handler.fabric=ResidentExecutionFabric(ROOT,args.state_dir,load_key()); server=Server(str(socket_path),Handler); os.chmod(socket_path,0o600)
    def stop(*_):
        # BaseServer.shutdown must run from a different thread than serve_forever.
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    try:server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        if socket_path.exists():socket_path.unlink()
    return 0


if __name__=="__main__":raise SystemExit(main())
