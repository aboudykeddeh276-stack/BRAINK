#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def repo_root() -> Path:
    return Path(os.environ.get("BRAINK_ROOT") or Path(__file__).resolve().parents[1]).resolve()


def runtime_dir(root: Path) -> Path:
    return Path(os.environ.get("BRAINK_DIRECT_RUNTIME_DIR") or root / ".kex" / "run").resolve()


def state_dir(root: Path) -> Path:
    return Path(os.environ.get("BRAINK_DIRECT_STATE_DIR") or root / ".kex" / "state" / "direct-saas").resolve()


def endpoint() -> str:
    return os.environ.get("BRAINK_SAAS_ENDPOINT", "http://127.0.0.1:8000").rstrip("/")


def paths(root: Path) -> dict[str, Path]:
    run, state = runtime_dir(root), state_dir(root)
    return {
        "run": run,
        "state": state,
        "pid": state / "supervisor.json",
        "receipt": state / "deployment-receipt.json",
        "kex_socket": Path(os.environ.get("KEX_RUNNER_SOCKET") or run / "kex-runner.sock"),
        "stripe_socket": Path(os.environ.get("BRAINK_STRIPE_SOCKET") or run / "braink-stripe.sock"),
        "kex_log": state / "kex-runner.log",
        "stripe_log": state / "stripe-payment-rail.log",
        "saas_log": state / "saas-control-plane.log",
        "worker_log": state / "saas-provisioning-worker.log",
        "saas_data": state / "saas-data",
        "runtime_db": state / "runtimes.sqlite",
    }


def write_json(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def unix_probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "ABSENT", "socket": str(path)}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(2); s.connect(str(path)); s.sendall(b'{"op":"PROBE"}\n')
        raw = b""
        while not raw.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk: break
            raw += chunk
        return {"status": "RESPONDED", "socket": str(path), "response": json.loads(raw.decode()) if raw else {}}
    except Exception as exc:
        return {"status": "UNREACHABLE", "socket": str(path), "error": f"{type(exc).__name__}:{exc}"}
    finally:
        s.close()


def http_probe(url_base: str) -> dict[str, Any]:
    url = url_base.rstrip("/") + "/saas/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return {"status": "RESPONDED", "url": url, "http_status": response.status, "response": json.loads(response.read().decode())}
    except Exception as exc:
        return {"status": "UNREACHABLE", "url": url, "error": f"{type(exc).__name__}:{exc}"}


def wait(check, timeout: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {"status": "UNOBSERVED"}
    while time.time() < deadline:
        last = check()
        if last.get("status") == "RESPONDED": return last
        time.sleep(0.1)
    return last


def status(root: Path) -> dict[str, Any]:
    p, current = paths(root), read_state(paths(root)["pid"])
    mode = current.get("saas_mode") or os.environ.get("BRAINK_SAAS_MODE", "managed")
    ids = {name: current.get(name) if isinstance(current.get(name), int) else None for name in ("saas_pid", "kex_pid", "stripe_pid", "worker_pid")}
    ap = http_probe(current.get("saas_endpoint") or endpoint())
    managed_ok = True if mode == "external" else alive(ids["saas_pid"])
    all_live = managed_ok and alive(ids["kex_pid"]) and alive(ids["stripe_pid"]) and alive(ids["worker_pid"]) and ap.get("status") == "RESPONDED"
    return {
        "status": "RUNNING" if all_live else "NOT_RUNNING",
        "deployment": "DIRECT_KEX_FIRST_PORTABLE",
        "github_required": False,
        "systemd_required": False,
        "saas_mode": mode,
        "saas_endpoint": current.get("saas_endpoint") or endpoint(),
        **ids,
        "saas_process_alive": managed_ok,
        "kex_process_alive": alive(ids["kex_pid"]),
        "stripe_process_alive": alive(ids["stripe_pid"]),
        "worker_process_alive": alive(ids["worker_pid"]),
        "saas_probe": ap,
        "kex_probe": unix_probe(p["kex_socket"]),
        "stripe_probe": unix_probe(p["stripe_socket"]),
        "receipt": str(p["receipt"]),
    }


def stop(root: Path) -> dict[str, Any]:
    p, current, stopped = paths(root), read_state(paths(root)["pid"]), []
    for key in ("worker_pid", "stripe_pid", "kex_pid", "saas_pid"):
        pid = current.get(key)
        if isinstance(pid, int) and alive(pid):
            try: os.kill(pid, signal.SIGTERM); stopped.append(pid)
            except OSError: pass
    deadline = time.time() + 5
    while time.time() < deadline and any(alive(pid) for pid in stopped): time.sleep(0.05)
    for pid in stopped:
        if alive(pid):
            try: os.kill(pid, signal.SIGKILL)
            except OSError: pass
    for key in ("kex_socket", "stripe_socket"):
        try: p[key].unlink()
        except FileNotFoundError: pass
    try: p["pid"].unlink()
    except FileNotFoundError: pass
    return {"status": "STOPPED", "pids": stopped}


def local_endpoint_parts(url_base: str) -> tuple[str, int]:
    parsed = urlsplit(url_base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("MANAGED_SAAS_ENDPOINT_MUST_BE_LOCAL_HTTP")
    return parsed.hostname, int(parsed.port or 8000)


def start(root: Path) -> dict[str, Any]:
    p = paths(root)
    for key in ("run", "state", "saas_data"):
        p[key].mkdir(parents=True, exist_ok=True)
    runner = root / "modules/kex_wbos/capability_runner.py"
    rail = root / "runtime/stripe_payment_rail.py"
    worker = root / "runtime/saas_provisioning_worker.py"
    qualifier = root / "scripts/kex-ci/test_kex_capability_runner.py"
    publish_src = root / "runtime/publish/src"
    resolver_raw = os.environ.get("KEX_SECRET_RESOLVER", "").strip()
    resolver = Path(resolver_raw).expanduser() if resolver_raw else None
    mode, url_base = os.environ.get("BRAINK_SAAS_MODE", "managed").strip().lower(), endpoint()
    if mode not in {"managed", "external"}: raise RuntimeError("BRAINK_SAAS_MODE_MUST_BE_MANAGED_OR_EXTERNAL")
    for path, reason in ((runner,"KEX_CAPABILITY_RUNNER_MISSING"),(rail,"STRIPE_PAYMENT_RAIL_MISSING"),(worker,"SAAS_PROVISIONING_WORKER_MISSING"),(qualifier,"KEX_QUALIFIER_MISSING")):
        if not path.is_file(): raise RuntimeError(reason)
    if resolver is None or not resolver.is_file() or not os.access(resolver, os.X_OK): raise RuntimeError("KEX_SECRET_RESOLVER_UNBOUND_OR_NOT_EXECUTABLE")
    if mode == "managed" and not publish_src.is_dir(): raise RuntimeError("BRAINK_SAAS_RUNTIME_SOURCE_MISSING")
    existing = status(root)
    if existing["status"] == "RUNNING": return {**existing, "idempotent": True}
    stop(root)
    qualify = subprocess.run([sys.executable, str(qualifier)], cwd=str(root), text=True, capture_output=True, timeout=30, check=False)
    if qualify.returncode != 0 or "KEX_CAPABILITY_RUNNER_PASS" not in qualify.stdout: raise RuntimeError("KEX_CAPABILITY_QUALIFICATION_FAILED")

    env = os.environ.copy()
    token = env.get("BRAINK_SAAS_AUTH_TOKEN") or env.get("BRAINK_AUTH_TOKEN") or secrets.token_urlsafe(32)
    pythonpath = os.pathsep.join(x for x in (str(root), str(publish_src), env.get("PYTHONPATH", "")) if x)
    env.update({
        "BRAINK_ROOT": str(root), "BRAINK_REPO_ROOT": str(root), "BRAINK_DATA_DIR": str(p["saas_data"]),
        "BRAINK_AUTH_TOKEN": token, "BRAINK_SAAS_AUTH_TOKEN": token, "BRAINK_SAAS_ENDPOINT": url_base,
        "BRAINK_RUNTIME_DB": str(p["runtime_db"]), "PYTHONPATH": pythonpath,
        "KEX_RUNNER_SOCKET": str(p["kex_socket"]), "BRAINK_STRIPE_SOCKET": str(p["stripe_socket"]),
        "KEX_CAPABILITY_LEDGER": str(p["state"] / "capability-ledger.jsonl"), "KEX_SECRET_RESOLVER": str(resolver.resolve()),
        "KEX_CAPABILITY_CALLERS": env.get("KEX_CAPABILITY_CALLERS", "service://braink/stripe-payment-rail"),
    })
    logs = {name: p[key].open("ab", buffering=0) for name, key in (("saas","saas_log"),("kex","kex_log"),("stripe","stripe_log"),("worker","worker_log"))}
    saas_proc = None
    try:
        if mode == "managed":
            deps = subprocess.run([sys.executable,"-c","import fastapi,uvicorn,pydantic"], cwd=str(root), env=env, text=True, capture_output=True, timeout=15)
            if deps.returncode != 0: raise RuntimeError("BRAINK_SAAS_RUNTIME_DEPENDENCIES_MISSING")
            host, port = local_endpoint_parts(url_base)
            saas_proc = subprocess.Popen([sys.executable,"-m","uvicorn","braink_runtime.casepath_app:app","--host",host,"--port",str(port)], cwd=str(root / "runtime/publish"), env=env, stdin=subprocess.DEVNULL, stdout=logs["saas"], stderr=logs["saas"], start_new_session=True)
        ap = wait(lambda: http_probe(url_base), 10)
        if ap.get("status") != "RESPONDED":
            if saas_proc: saas_proc.terminate()
            raise RuntimeError("BRAINK_SAAS_CONTROL_PLANE_NOT_LIVE")
        kex = subprocess.Popen([sys.executable,str(runner)], cwd=str(root), env=env, stdin=subprocess.DEVNULL, stdout=logs["kex"], stderr=logs["kex"], start_new_session=True)
        kp = wait(lambda: unix_probe(p["kex_socket"]), 8)
        if kp.get("status") != "RESPONDED" or (kp.get("response") or {}).get("error") != "UNKNOWN_OPERATION":
            kex.terminate();
            if saas_proc: saas_proc.terminate()
            raise RuntimeError("KEX_FAIL_CLOSED_PROBE_FAILED")
        stripe = subprocess.Popen([sys.executable,str(rail)], cwd=str(root), env=env, stdin=subprocess.DEVNULL, stdout=logs["stripe"], stderr=logs["stripe"], start_new_session=True)
        sp = wait(lambda: unix_probe(p["stripe_socket"]), 8)
        if sp.get("status") != "RESPONDED" or (sp.get("response") or {}).get("error") != "UNKNOWN_OPERATION":
            stripe.terminate(); kex.terminate();
            if saas_proc: saas_proc.terminate()
            raise RuntimeError("STRIPE_FAIL_CLOSED_PROBE_FAILED")
        provision = subprocess.Popen([sys.executable,str(worker)], cwd=str(root), env=env, stdin=subprocess.DEVNULL, stdout=logs["worker"], stderr=logs["worker"], start_new_session=True)
        time.sleep(0.35)
        if not alive(provision.pid):
            stripe.terminate(); kex.terminate();
            if saas_proc: saas_proc.terminate()
            raise RuntimeError("SAAS_PROVISIONING_WORKER_NOT_LIVE")
        body = {
            "status":"VERIFIED", "deployment":"DIRECT_KEX_FIRST_PORTABLE", "github_required":False, "systemd_required":False,
            "host":socket.gethostname(), "timestamp_ns":time.time_ns(), "saas_mode":mode, "saas_endpoint":url_base,
            "saas_pid":saas_proc.pid if saas_proc else None, "kex_pid":kex.pid, "stripe_pid":stripe.pid, "worker_pid":provision.pid,
            "kex_socket":str(p["kex_socket"]), "stripe_socket":str(p["stripe_socket"]), "runtime_db":str(p["runtime_db"]),
            "saas_probe":ap, "kex_probe":kp, "stripe_probe":sp, "secret_resolver":"KEX_OWNED_BOUND_EXECUTABLE",
            "internal_auth":"EPHEMERAL_OR_PREBOUND_NOT_EMITTED",
            "claim_boundary":"SaaS, KEX runner, payment rail and provisioning worker are locally resident. A tenant service is VERIFIED only after registered runtime actuation and health readback."
        }
        write_json(p["pid"], body); write_json(p["receipt"], body); return body
    finally:
        for handle in logs.values(): handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable direct KEX-first BRAINK SaaS supervisor")
    parser.add_argument("command", choices=("start","status","stop","restart")); args = parser.parse_args(); root = repo_root()
    try:
        result = start(root) if args.command == "start" else status(root) if args.command == "status" else stop(root) if args.command == "stop" else (stop(root) and start(root))
        print(json.dumps(result, sort_keys=True, indent=2)); return 0 if result.get("status") in {"VERIFIED","RUNNING","STOPPED"} else 2
    except Exception as exc:
        result={"status":"BLOCKED","deployment":"DIRECT_KEX_FIRST_PORTABLE","github_required":False,"systemd_required":False,"reason":f"{type(exc).__name__}:{exc}"}
        print(json.dumps(result, sort_keys=True, indent=2)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
