#!/usr/bin/env python3
from __future__ import annotations

import json, os, pathlib, re, ssl, subprocess, sys, time, urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
ACTUATOR = REPO / "casepath/deploy/casepath_public_optimization_actuator_v51.py"
FABRIC = pathlib.Path(os.environ.get("KEDDEH_DOMAIN_FABRIC_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5"))
EVIDENCE = pathlib.Path(os.environ.get("KEDDEH_EVIDENCE_ROOT", "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE"))
DOMAIN = "casepath.com.au"
RELEASE = "CP-PUBLIC-OPT-V51-20260902"
OUT = REPO / "casepath/deploy/CASEPATH_V52_DEPLOYMENT_READBACK.json"


def run(cmd, **kw):
    p = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if p.returncode:
        raise RuntimeError("COMMAND_FAILED " + repr(cmd) + "\n" + p.stdout + "\n" + p.stderr)
    return p.stdout


def valid_docroot(p: pathlib.Path) -> bool:
    try:
        idx = p / "index.html"
        return idx.is_file() and "casepath" in idx.read_text("utf-8", errors="replace").lower()
    except Exception:
        return False


def _extract_paths_from_json(obj):
    found = []
    if isinstance(obj, dict):
        domainish = any(str(v).lower() == DOMAIN for v in obj.values() if isinstance(v, str)) or DOMAIN in json.dumps(obj).lower()
        for k, v in obj.items():
            lk = str(k).lower()
            if isinstance(v, str) and any(x in lk for x in ("docroot", "document_root", "webroot", "site_root", "root_dir")):
                found.append(pathlib.Path(v))
            found.extend(_extract_paths_from_json(v))
        if domainish:
            for k, v in obj.items():
                if isinstance(v, str) and ("/" in v or v.startswith(".")) and any(x in str(k).lower() for x in ("path", "root", "dir")):
                    found.append(pathlib.Path(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_extract_paths_from_json(v))
    return found


def resolve_docroot() -> tuple[pathlib.Path, str]:
    explicit = os.environ.get("CASEPATH_DOCROOT")
    if explicit:
        p = pathlib.Path(explicit).expanduser().resolve()
        if valid_docroot(p):
            return p, "CASEPATH_DOCROOT"

    # Read resident fabric configuration first. This follows the fabric's own state before path fallback.
    config_candidates = []
    for ext in ("*.json", "*.manifest", "*.config"):
        config_candidates.extend(FABRIC.rglob(ext))
    for cfg in config_candidates:
        try:
            if cfg.stat().st_size > 4_000_000:
                continue
            raw = cfg.read_text("utf-8", errors="replace")
            if DOMAIN not in raw.lower():
                continue
            obj = json.loads(raw)
            for candidate in _extract_paths_from_json(obj):
                if not candidate.is_absolute():
                    candidate = (cfg.parent / candidate).resolve()
                if valid_docroot(candidate):
                    return candidate, f"FABRIC_CONFIG:{cfg}"
        except Exception:
            continue

    # Known resident webspace shapes are fallback adapters, not new topology.
    for rel in (
        f"webspace/{DOMAIN}", f"webspaces/{DOMAIN}", f"sites/{DOMAIN}",
        f"hosts/{DOMAIN}", f"domains/{DOMAIN}", "webspace/casepath", "sites/casepath"
    ):
        p = (FABRIC / rel).resolve()
        if valid_docroot(p):
            return p, f"FABRIC_PATH:{rel}"

    # Final bounded search: only directories immediately representing CasePath inside the resident fabric.
    for p in FABRIC.rglob("*"):
        if not p.is_dir():
            continue
        name = p.name.lower()
        if name not in {"casepath", DOMAIN}:
            continue
        if valid_docroot(p):
            return p.resolve(), f"FABRIC_DISCOVERED:{p}"

    raise RuntimeError("CASEPATH_DOCROOT_NOT_RESOLVED_FROM_RESIDENT_FABRIC")


def local_readback() -> dict:
    urls = [
        "https://127.0.0.1:8443/",
        "http://127.0.0.1:8080/",
        "http://127.0.0.1:8000/",
    ]
    last = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"Host": DOMAIN})
            ctx = ssl._create_unverified_context() if url.startswith("https:") else None
            with urllib.request.urlopen(req, context=ctx, timeout=6) as r:
                body = r.read().decode("utf-8", errors="replace")
                return {
                    "url": url,
                    "status": r.status,
                    "bytes": len(body.encode()),
                    "casepath": "casepath" in body.lower(),
                    "release_marker": RELEASE in body,
                }
        except Exception as e:
            last = f"{type(e).__name__}:{e}"
    return {"status": None, "casepath": False, "release_marker": False, "error": last}


def main() -> int:
    if not ACTUATOR.is_file():
        raise SystemExit("ACTUATOR_NOT_PRESENT")
    if not FABRIC.is_dir():
        raise SystemExit("RESIDENT_DOMAIN_FABRIC_NOT_MOUNTED")

    docroot, source = resolve_docroot()
    before = run([sys.executable, str(ACTUATOR), "status", "--docroot", str(docroot)])
    deploy = run([sys.executable, str(ACTUATOR), "deploy", "--docroot", str(docroot)])
    after = run([sys.executable, str(ACTUATOR), "status", "--docroot", str(docroot)])

    start = FABRIC / "START_FULL_DOMAIN_FABRIC.command"
    fabric_output = None
    if start.is_file():
        env = os.environ.copy()
        env["KEDDEH_EVIDENCE_ROOT"] = str(EVIDENCE)
        fabric_output = run(["bash", str(start)], env=env)[-12000:]

    rb = local_readback()
    result = {
        "schema": "kex.casepath.v52.resident-fabric-deployment.v1",
        "domain": DOMAIN,
        "release": RELEASE,
        "docroot": str(docroot),
        "docroot_source": source,
        "status_before": json.loads(before),
        "deployment": json.loads(deploy),
        "status_after": json.loads(after),
        "fabric_rehydrated": start.is_file(),
        "fabric_output_tail": fabric_output,
        "local_host_readback": rb,
        "promotion": "RESIDENT_FABRIC_DEPLOYED_AND_READ_BACK" if rb.get("release_marker") else "RESIDENT_MUTATION_EXECUTED_READBACK_PENDING",
        "at": time.time(),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if rb.get("release_marker") else 3


if __name__ == "__main__":
    raise SystemExit(main())
