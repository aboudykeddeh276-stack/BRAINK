from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("KEX_BTC_STATE_DIR", ROOT / "state" / "kex_btc")).resolve()
DATA_DIR = STATE_DIR / "data"
LEDGER_DIR = STATE_DIR / "ledgers"
LIVE_TEMPLATE_PATH = DATA_DIR / "live_block_template.json"
LIVE_CANDIDATE_PATH = DATA_DIR / "live_block_candidate.json"
LIVE_SUBMISSION_PATH = DATA_DIR / "live_submission_result.json"
FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
NETWORK_PORTS = {"mainnet": 8332, "testnet": 18332, "signet": 38332, "regtest": 18443}
COOKIE_SUBDIRS = {"mainnet": "", "testnet": "testnet3", "signet": "signet", "regtest": "regtest"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() not in FALSE_VALUES


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def rpc_configuration() -> dict[str, Any]:
    network = os.environ.get("BTC_NETWORK", "mainnet").strip().lower()
    home = Path.home()
    candidates = [
        Path(os.environ["BTC_DATADIR"]).expanduser() if os.environ.get("BTC_DATADIR") else None,
        home / "Library" / "Application Support" / "BRAINK" / "bitcoin-main",
        home / "Library" / "Application Support" / "BRAINK" / "bitcoin-main-sync",
        home / "Library" / "Application Support" / "Bitcoin",
        home / ".bitcoin",
        STATE_DIR / "bitcoin_core",
    ]
    candidates = [path.resolve() for path in candidates if path is not None]
    subdir = COOKIE_SUBDIRS.get(network, "")
    candidates.sort(
        key=lambda path: (
            32 * int((path / subdir / ".cookie").is_file())
            + 16 * int((path / "bitcoin.conf").is_file())
            + 8 * int((path / "chainstate").exists())
            + 4 * int((path / "blocks").exists())
            + int(path.exists())
        ),
        reverse=True,
    )
    datadir = candidates[0]
    host = os.environ.get("BTC_RPC_HOST", "127.0.0.1")
    port = int(os.environ.get("BTC_RPC_PORT", NETWORK_PORTS.get(network, 8332)))
    return {
        "network": network,
        "datadir": datadir,
        "cookie": Path(os.environ["BTC_RPC_COOKIE"]).expanduser().resolve()
        if os.environ.get("BTC_RPC_COOKIE")
        else (datadir / subdir / ".cookie").resolve(),
        "rpc_url": os.environ.get("BTC_RPC_URL", f"http://{host}:{port}"),
        "rpc_host": host,
        "rpc_user": os.environ.get("BTC_RPC_USER"),
        "rpc_password": os.environ.get("BTC_RPC_PASSWORD"),
        "candidates": [str(path) for path in candidates],
    }


def rpc_auth(config: dict[str, Any]) -> tuple[str, str]:
    cookie = config["cookie"]
    if cookie.is_file():
        raw = cookie.read_text(encoding="utf-8").strip()
        if ":" in raw:
            user, password = raw.split(":", 1)
            if user and password:
                return user, password
    if config["rpc_user"] and config["rpc_password"]:
        return str(config["rpc_user"]), str(config["rpc_password"])
    raise RuntimeError("No usable Bitcoin Core RPC cookie or client credentials were resolved")


def rpc_call(method: str, params: list[Any] | None = None, timeout: int = 10) -> Any:
    config = rpc_configuration()
    user, password = rpc_auth(config)
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    body = json.dumps({"jsonrpc": "2.0", "id": "braink-btc", "method": method, "params": params or []}).encode()
    request = Request(config["rpc_url"], data=body, headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode())
    except HTTPError as exc:
        raise RuntimeError(f"RPC HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
    except URLError as exc:
        raise RuntimeError(f"RPC connection failed: {exc.reason}") from exc
    if result.get("error") is not None:
        raise RuntimeError(f"RPC error for {method}: {result['error']}")
    return result.get("result")


def check_rpc() -> tuple[bool, dict[str, Any]]:
    try:
        value = rpc_call("getblockchaininfo", [], int(os.environ.get("BTC_RPC_TIMEOUT", "10")))
        return (isinstance(value, dict), value if isinstance(value, dict) else {"error": "non-object response"})
    except Exception as exc:
        return False, {"error": str(exc), "attempted_at": utc_now()}


def start_or_resolve_node() -> dict[str, Any]:
    running, info = check_rpc()
    if running:
        return {"attempted": False, "started": False, "reason": "rpc_already_available", "rpc": info}
    config = rpc_configuration()
    if config["rpc_host"] not in {"127.0.0.1", "localhost", "::1"}:
        return {"attempted": False, "started": False, "reason": "remote_rpc_configured", "rpc": info}
    binary = os.environ.get("BITCOIND_BIN") or shutil.which("bitcoind")
    if not binary:
        return {"attempted": True, "started": False, "reason": "bitcoind_binary_not_found", "datadir": str(config["datadir"]), "rpc": info}
    if not config["datadir"].exists():
        return {"attempted": True, "started": False, "reason": "configured_datadir_not_found", "datadir": str(config["datadir"]), "rpc": info}
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    command = [str(binary), f"-datadir={config['datadir']}"]
    with (LEDGER_DIR / "bitcoind_stdout.log").open("ab") as stdout, (LEDGER_DIR / "bitcoind_stderr.log").open("ab") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
    deadline = time.monotonic() + int(os.environ.get("BTC_NODE_START_TIMEOUT", "20"))
    while time.monotonic() < deadline:
        running, info = check_rpc()
        if running:
            return {"attempted": True, "started": True, "pid": process.pid, "rpc": info}
        if process.poll() is not None:
            break
        time.sleep(1)
    return {"attempted": True, "started": process.poll() is None, "pid": process.pid, "rpc": info, "reason": "rpc_not_available_before_timeout"}


def request_template() -> tuple[bool, dict[str, Any]]:
    try:
        value = rpc_call("getblocktemplate", [{"mode": "template", "rules": ["segwit"], "capabilities": ["longpoll", "coinbasetxn", "workid"]}], int(os.environ.get("BTC_TEMPLATE_TIMEOUT", "30")))
        return (isinstance(value, dict), value if isinstance(value, dict) else {"error": "non-object template"})
    except Exception as exc:
        return False, {"error": str(exc), "requested_at": utc_now()}


def run_command(variable: str, template_path: Path, result_path: Path | None = None) -> dict[str, Any]:
    configured = os.environ.get(variable)
    if not configured:
        return {"attempted": False, "reason": f"{variable}_not_configured"}
    environment = os.environ.copy()
    environment["KEX_TEMPLATE_PATH"] = str(template_path)
    if result_path is not None:
        environment["KEX_RESULT_PATH"] = str(result_path)
    completed = subprocess.run(shlex.split(configured), cwd=ROOT, env=environment, text=True, capture_output=True, timeout=int(os.environ.get("KEX_SOLVER_TIMEOUT", "300")), check=False)
    candidate = load_json(result_path) if result_path else None
    return {"attempted": True, "completed": True, "returncode": completed.returncode, "stdout_tail": completed.stdout[-2000:], "stderr_tail": completed.stderr[-2000:], "candidate": candidate}


def compact_target(bits: int) -> int:
    exponent, mantissa = bits >> 24, bits & 0x007FFFFF
    if bits & 0x00800000 or mantissa == 0:
        raise ValueError("invalid compact target")
    return mantissa >> (8 * (3 - exponent)) if exponent <= 3 else mantissa << (8 * (exponent - 3))


def validate_and_submit(candidate: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    block_hex = candidate.get("block_hex") or candidate.get("hexdata")
    if not isinstance(block_hex, str) or not block_hex:
        return {"attempted": False, "accepted": False, "reason": "candidate has no block_hex"}
    try:
        raw = bytes.fromhex(block_hex)
    except ValueError as exc:
        return {"attempted": False, "accepted": False, "reason": str(exc)}
    if len(raw) < 81:
        return {"attempted": False, "accepted": False, "reason": "candidate shorter than header plus transaction count"}
    header = raw[:80]
    digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
    bits = int.from_bytes(header[72:76], "little")
    validation = {
        "block_hash": digest[::-1].hex(),
        "target_valid": int.from_bytes(digest, "little") <= compact_target(bits),
        "previousblockhash_matches_template": header[4:36][::-1].hex() == str(template.get("previousblockhash") or "").lower(),
        "bits_matches_template": f"{bits:08x}" == str(template.get("bits") or "").lower(),
    }
    validation["valid"] = all(validation[key] for key in ("target_valid", "previousblockhash_matches_template", "bits_matches_template"))
    if not validation["valid"]:
        return {"attempted": False, "accepted": False, "validation": validation, "reason": "candidate rejected locally"}
    if not env_flag("KEX_ALLOW_LIVE_SUBMIT", False):
        return {"attempted": False, "accepted": False, "validation": validation, "reason": "live submit disabled"}
    current_tip = rpc_call("getbestblockhash", [])
    if str(current_tip).lower() != str(template.get("previousblockhash") or "").lower():
        return {"attempted": False, "accepted": False, "stale": True, "validation": validation}
    workid = candidate.get("workid") or template.get("workid")
    params: list[Any] = [block_hex] + ([str(workid)] if workid is not None else [])
    response = rpc_call("submitblock", params, int(os.environ.get("BTC_SUBMIT_TIMEOUT", "30")))
    result = {"attempted": True, "accepted": response is None, "rpc_result": response, "validation": validation, "submitted_at": utc_now()}
    save_json(LIVE_SUBMISSION_PATH, result)
    append_jsonl(LEDGER_DIR / "submission_ledger.jsonl", result)
    return result


def execute_btc_workload() -> dict[str, Any]:
    started_at = utc_now()
    node = start_or_resolve_node()
    connected, chain = check_rpc()
    if not connected:
        result = {"started_at": started_at, "completed_at": utc_now(), "node": node, "connected": False, "chain": chain, "next": "retry_chain_read"}
    else:
        template_received, template = request_template()
        if not template_received:
            result = {"started_at": started_at, "completed_at": utc_now(), "node": node, "connected": True, "chain": chain, "template_received": False, "template_result": template, "next": "retry_template_request"}
        else:
            save_json(LIVE_TEMPLATE_PATH, template)
            engine = run_command("KEX_ENGINE_CMD", LIVE_TEMPLATE_PATH)
            solver = run_command("KEX_OWNER_SOLVER_CMD", LIVE_TEMPLATE_PATH, LIVE_CANDIDATE_PATH)
            candidate = solver.get("candidate") if isinstance(solver, dict) else None
            if not isinstance(candidate, dict) and env_flag("KEX_ACCEPT_CANDIDATE_FILE", True):
                candidate = load_json(LIVE_CANDIDATE_PATH)
            submission = validate_and_submit(candidate, template) if isinstance(candidate, dict) else None
            result = {"started_at": started_at, "completed_at": utc_now(), "node": node, "connected": True, "chain": chain, "template_received": True, "template": {key: template.get(key) for key in ("height", "previousblockhash", "bits", "target", "workid")}, "engine": engine, "solver": {key: value for key, value in solver.items() if key not in {"candidate", "stdout_tail", "stderr_tail"}}, "candidate_received": isinstance(candidate, dict), "submission": submission, "next": "request_next_template" if submission and submission.get("accepted") else "continue_current_work"}
    save_json(DATA_DIR / "btc_workload_latest.json", result)
    append_jsonl(LEDGER_DIR / "btc_workload.jsonl", result)
    return result


if __name__ == "__main__":
    print(json.dumps(execute_btc_workload(), indent=2, sort_keys=True))
