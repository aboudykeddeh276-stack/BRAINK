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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(os.environ.get("BRAINK_ROOT") or Path(__file__).resolve().parents[1]).resolve()


def runtime_dir(root: Path) -> Path:
    return Path(os.environ.get("BRAINK_DIRECT_RUNTIME_DIR") or root / ".kex" / "run").resolve()


def state_dir(root: Path) -> Path:
    return Path(os.environ.get("BRAINK_DIRECT_STATE_DIR") or root / ".kex" / "state" / "direct-saas").resolve()


def saas_endpoint() -> str:
    return os.environ.get("BRAINK_SAAS_ENDPOINT", "http://127.0.0.1:8000").rstrip("/")


def paths(root: Path) -> dict[str, Path]:
    run = runtime_dir(root)
    state = state_dir(root)
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
        "saas_data": state / "saas-data",
    }


def write_json(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "ABSENT", "socket": str(path)}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(2)
        s.connect(str(path))
        s.sendall(b'{"op":"PROBE"}\n')
        raw = b""
        while not raw.endswith(b"\n"):
            part = s.recv(65536)
            if not part:
                break
            raw += part
        result = json.loads(raw.decode("utf-8")) if raw else {}
        return {"status": "RESPONDED", "socket": str(path), "response": result}
    except Exception as exc:
        return {"status": "UNREACHABLE", "socket": str(path), "error": f"{type(exc).__name__}:{exc}"}
    finally:
        s.close()


def http_probe(endpoint: str) -> dict[str, Any]:
    url = endpoint.rstrip("/") + "/saas/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
            return {"status": "RESPONDED", "url": url, "http_status": response.status, "response": body}
    except Exception as exc:
        return {"status": "UNREACHABLE", "url": url, "error": f"{type(exc).__name__}:{exc}"}


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


def status(root: Path) -> dict[str, Any]:
    p = paths(root)
    current = read_pid_state(p["pid"])
    kpid = current.get("kex_pid") if isinstance(current.get("kex_pid"), int) else None
    spid = current.get("stripe_pid") if isinstance(current.get("stripe_pid"), int) else None
    apid = current.get("saas_pid") if isinstance(current.get("saas_pid"), int) else None
    mode = current.get("saas_mode") or os.environ.get("BRAINK_SAAS_MODE", "managed")
    saas_alive = True if mode == "external" else process_alive(apid)
    saas_readback = http_probe(current.get("saas_endpoint") or saas_endpoint())
    all_live = process_alive(kpid) and process_alive(spid) and saas_alive and saas_readback.get("status") == "RESPONDED"
    return {
        "status": "RUNNING" if all_live else "NOT_RUNNING",
        "deployment": "DIRECT_KEX_FIRST_PORTABLE",
        "github_required": False,
        "systemd_required": False,
        "saas_mode": mode,
        "saas_endpoint": current.get("saas_endpoint") or saas_endpoint(),
        "saas_pid": apid,
        "kex_pid": kpid,
        "stripe_pid": spid,
        "saas_process_alive": saas_alive,
        "kex_process_alive": process_alive(kpid),
        "stripe_process_alive": process_alive(spid),
        "saas_probe": saas_readback,
        "kex_probe": probe(p["kex_socket"]),
        "stripe_probe": probe(p["stripe_socket"]),
        "receipt": str(p["receipt"]),
    }


def stop(root: Path) -> dict[str, Any]:
    p = paths(root)
    current = read_pid_state(p["pid"])
    stopped: list[int] = []
    for key in ("stripe_pid", "kex_pid", "saas_pid"):
        pid = current.get(key)
        if not isinstance(pid, int) or not process_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except OSError:
            pass
    deadline = time.time() + 5
    while time.time() < deadline and any(process_alive(pid) for pid in stopped):
        time.sleep(0.05)
    for pid in stopped:
        if process_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    for key in ("kex_socket", "stripe_socket"):
        try:
            p[key].unlink()
        except FileNotFoundError:
            pass
    try:
        p["pid"].unlink()
    except FileNotFoundError:
        pass
    return {"status": "STOPPED", "pids": stopped}


def wait_for_socket(path: Path, timeout: float = 8.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {"status": "ABSENT", "socket": str(path)}
    while time.time() < deadline:
        last = probe(path)
        if last.get("status") == "RESPONDED":
            return last
        time.sleep(0.1)
    return last


def wait_for_http(endpoint: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {"status": "UNREACHABLE", "url": endpoint}
    while time.time() < deadline:
        last = http_probe(endpoint)
        if last.get("status") == "RESPONDED":
            return last
        time.sleep(0.15)
    return last


def _parse_managed_endpoint(endpoint: str) -> tuple[str, int]:
    from urllib.parse import urlsplit
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("MANAGED_SAAS_ENDPOINT_MUST_BE_LOCAL_HTTP")
    return parsed.hostname, int(parsed.port or 8000)


def start(root: Path) -> dict[str, Any]:
    p = paths(root)
    p["run"].mkdir(parents=True, exist_ok=True)
    p["state"].mkdir(parents=True, exist_ok=True)
    p["saas_data"].mkdir(parents=True, exist_ok=True)

    runner = root / "modules" / "kex_wbos" / "capability_runner.py"
    rail = root / "runtime" / "stripe_payment_rail.py"
    qualifier = root / "scripts" / "kex-ci" / "test_kex_capability_runner.py"
    publish_src = root / "runtime" / "publish" / "src"
    resolver_raw = os.environ.get("KEX_SECRET_RESOLVER", "").strip()
    resolver = Path(resolver_raw).expanduser() if resolver_raw else None
    mode = os.environ.get("BRAINK_SAAS_MODE", "managed").strip().lower()
    endpoint = saas_endpoint()

    if mode not in {"managed", "external"}:
        raise RuntimeError("BRAINK_SAAS_MODE_MUST_BE_MANAGED_OR_EXTERNAL")
    if not runner.is_file():
        raise RuntimeError("KEX_CAPABILITY_RUNNER_MISSING")
    if not rail.is_file():
        raise RuntimeError("STRIPE_PAYMENT_RAIL_MISSING")
    if not qualifier.is_file():
        raise RuntimeError("KEX_QUALIFIER_MISSING")
    if resolver is None or not resolver.is_file() or not os.access(resolver, os.X_OK):
        raise RuntimeError("KEX_SECRET_RESOLVER_UNBOUND_OR_NOT_EXECUTABLE")
    if mode == "managed" and not publish_src.is_dir():
        raise RuntimeError("BRAINK_SAAS_RUNTIME_SOURCE_MISSING")

    existing = status(root)
    if existing["status"] == "RUNNING":
        return {**existing, "idempotent": True}
    stop(root)

    qualify = subprocess.run(
        [sys.executable, str(qualifier)],
        cwd=str(root), text=True, capture_output=True, timeout=30, check=False,
    )
    if qualify.returncode != 0 or "KEX_CAPABILITY_RUNNER_PASS" not in qualify.stdout:
        raise RuntimeError("KEX_CAPABILITY_QUALIFICATION_FAILED")

    env = os.environ.copy()
    internal_token = env.get("BRAINK_SAAS_AUTH_TOKEN") or env.get("BRAINK_AUTH_TOKEN") or secrets.token_urlsafe(32)
    pythonpath = str(publish_src)
    if env.get("PYTHONPATH"):
        pythonpath += os.pathsep + env["PYTHONPATH"]
    env.update({
        "BRAINK_ROOT": str(root),
        "BRAINK_REPO_ROOT": str(root),
        "BRAINK_DATA_DIR": str(p["saas_data"]),
        "BRAINK_AUTH_TOKEN": internal_token,
        "BRAINK_SAAS_AUTH_TOKEN": internal_token,
        "BRAINK_SAAS_ENDPOINT": endpoint,
        "PYTHONPATH": pythonpath,
        "KEX_RUNNER_SOCKET": str(p["kex_socket"]),
        "BRAINK_STRIPE_SOCKET": str(p["stripe_socket"]),
        "KEX_CAPABILITY_LEDGER": str(p["state"] / "capability-ledger.jsonl"),
        "KEX_SECRET_RESOLVER": str(resolver.resolve()),
        "KEX_CAPABILITY_CALLERS": env.get("KEX_CAPABILITY_CALLERS", "service://braink/stripe-payment-rail"),
    })

    klog = p["kex_log"].open("ab", buffering=0)
    slog = p["stripe_log"].open("ab", buffering=0)
    alog = p["saas_log"].open("ab", buffering=0)
    saas_proc: subprocess.Popen[bytes] | None = None
    try:
        if mode == "managed":
            deps = subprocess.run(
                [sys.executable, "-c", "import fastapi,uvicorn,pydantic"],
                cwd=str(root), env=env, text=True, capture_output=True, timeout=15, check=False,
            )
            if deps.returncode != 0:
                raise RuntimeError("BRAINK_SAAS_RUNTIME_DEPENDENCIES_MISSING")
            host, port = _parse_managed_endpoint(endpoint)
            saas_proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "braink_runtime.app:app", "--host", host, "--port", str(port)],
                cwd=str(root / "runtime" / "publish"), env=env,
                stdin=subprocess.DEVNULL, stdout=alog, stderr=alog, start_new_session=True,
            )
        ap = wait_for_http(endpoint)
        if ap.get("status") != "RESPONDED":
            if saas_proc:
                saas_proc.terminate()
            raise RuntimeError("BRAINK_SAAS_CONTROL_PLANE_NOT_LIVE")

        kex = subprocess.Popen(
            [sys.executable, str(runner)], cwd=str(root), env=env,
            stdin=subprocess.DEVNULL, stdout=klog, stderr=klog, start_new_session=True,
        )
        kp = wait_for_socket(p["kex_socket"])
        if kp.get("status") != "RESPONDED":
            kex.terminate()
            if saas_proc:
                saas_proc.terminate()
            raise RuntimeError("KEX_SOCKET_NOT_LIVE")
        response = kp.get("response") or {}
        if response.get("status") != "REJECTED" or response.get("error") != "UNKNOWN_OPERATION":
            kex.terminate()
            if saas_proc:
                saas_proc.terminate()
            raise RuntimeError("KEX_FAIL_CLOSED_PROBE_FAILED")

        stripe = subprocess.Popen(
            [sys.executable, str(rail)], cwd=str(root), env=env,
            stdin=subprocess.DEVNULL, stdout=slog, stderr=slog, start_new_session=True,
        )
        sp = wait_for_socket(p["stripe_socket"])
        if sp.get("status") != "RESPONDED":
            stripe.terminate(); kex.terminate()
            if saas_proc:
                saas_proc.terminate()
            raise RuntimeError("STRIPE_SOCKET_NOT_LIVE")
        response = sp.get("response") or {}
        if response.get("status") != "REJECTED" or response.get("error") != "UNKNOWN_OPERATION":
            stripe.terminate(); kex.terminate()
            if saas_proc:
                saas_proc.terminate()
            raise RuntimeError("STRIPE_FAIL_CLOSED_PROBE_FAILED")

        body = {
            "status": "VERIFIED",
            "deployment": "DIRECT_KEX_FIRST_PORTABLE",
            "github_required": False,
            "systemd_required": False,
            "host": socket.gethostname(),
            "timestamp_ns": time.time_ns(),
            "saas_mode": mode,
            "saas_endpoint": endpoint,
            "saas_pid": saas_proc.pid if saas_proc else None,
            "kex_pid": kex.pid,
            "stripe_pid": stripe.pid,
            "kex_socket": str(p["kex_socket"]),
            "stripe_socket": str(p["stripe_socket"]),
            "saas_probe": ap,
            "kex_probe": kp,
            "stripe_probe": sp,
            "secret_resolver": "KEX_OWNED_BOUND_EXECUTABLE",
            "internal_auth": "EPHEMERAL_OR_PREBOUND_NOT_EMITTED",
            "claim_boundary": "SaaS control plane, KEX runner and payment rail read back locally. Provider execution still requires KEX authorization and KEX-resolved credentials.",
        }
        write_json(p["pid"], body)
        write_json(p["receipt"], body)
        return body
    finally:
        klog.close(); slog.close(); alog.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Portable direct KEX-first BRAINK SaaS supervisor")
    parser.add_argument("command", choices=("start", "status", "stop", "restart"))
    args = parser.parse_args()
    root = repo_root()
    try:
        if args.command == "start":
            result = start(root)
        elif args.command == "status":
            result = status(root)
        elif args.command == "stop":
            result = stop(root)
        else:
            stop(root)
            result = start(root)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result.get("status") in {"VERIFIED", "RUNNING", "STOPPED"} else 2
    except Exception as exc:
        result = {
            "status": "BLOCKED",
            "deployment": "DIRECT_KEX_FIRST_PORTABLE",
            "github_required": False,
            "systemd_required": False,
            "reason": f"{type(exc).__name__}:{exc}",
        }
        print(json.dumps(result, sort_keys=True, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
