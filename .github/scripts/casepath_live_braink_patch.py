#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request

LIVE_BUILD_MARKER = "20260727iosscroll1"
LIVE_TITLE_MARKERS = (
    "CasePath Public Beta - Australian Family Court Guide",
    "CasePath Public Beta",
)
BRAINK_MARKER = "BRAINK-CASEPATH-LIVE-20260829"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    explicit = os.environ.get("CASEPATH_DOCROOT", "").strip()
    if explicit:
        roots.append(Path(explicit).expanduser())
    home = Path.home()
    for p in (
        home / "Desktop",
        home / "Documents",
        home / "Sites",
        home / "public_html",
        home / "Library" / "CloudStorage",
        Path("/Volumes"),
        home,
    ):
        if p.exists() and p not in roots:
            roots.append(p)
    return roots


def discover() -> tuple[Path, dict]:
    skip = {
        ".git", "node_modules", ".cache", "Caches", "DerivedData", ".Trash",
        "venv", ".venv", "__pycache__", "Applications", "Pictures", "Movies", "Music"
    }
    home = Path.home()
    matches: dict[str, dict] = {}
    inspected = 0

    for root in candidate_roots():
        if root.is_file():
            files = [root]
        else:
            files = []
            for dirpath, dirnames, filenames in os.walk(root):
                dp = Path(dirpath)
                # Never traverse the general macOS Library tree from HOME. CloudStorage
                # is scanned explicitly as a separate root above.
                if root == home and dp == home / "Library":
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames if d not in skip]
                if "index.html" in filenames:
                    files.append(dp / "index.html")

        for path in files:
            try:
                if path.stat().st_size > 8_000_000:
                    continue
                raw = path.read_bytes()
            except Exception:
                continue
            inspected += 1
            text = raw.decode("utf-8", "ignore")
            if LIVE_BUILD_MARKER in text and any(t in text for t in LIVE_TITLE_MARKERS):
                matches[str(path.resolve())] = {
                    "index": str(path.resolve()),
                    "root": str(path.parent.resolve()),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "contact_exists": (path.parent / "contact.html").exists(),
                }

    receipt = {
        "schema": "casepath.braink.live-origin-discovery.v2",
        "fingerprint": {
            "build_marker": LIVE_BUILD_MARKER,
            "title_markers": list(LIVE_TITLE_MARKERS),
        },
        "scanned_roots": [str(p) for p in candidate_roots()],
        "inspected_index_files": inspected,
        "candidates": list(matches.values()),
    }
    Path("CASEPATH_LIVE_ORIGIN_DISCOVERY.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2), flush=True)
    if len(matches) != 1:
        raise RuntimeError(f"REFUSE_PATCH: expected exactly one current production tree, found {len(matches)}")
    return Path(next(iter(matches.values()))["root"]), receipt


def backup(root: Path) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = root / f".casepath-backup-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    for name in ("index.html", "contact.html", "braink-admin.html"):
        src = root / name
        if src.exists():
            shutil.copy2(src, out / name)
    Path("CASEPATH_BACKUP_PATH.txt").write_text(str(out))
    return out


def patch(root: Path) -> dict:
    index = root / "index.html"
    contact = root / "contact.html"
    if not contact.exists():
        raise RuntimeError("REFUSE_PATCH: current production candidate lacks contact.html")

    html = index.read_text(encoding="utf-8")
    if LIVE_BUILD_MARKER not in html or not any(t in html for t in LIVE_TITLE_MARKERS):
        raise RuntimeError("REFUSE_PATCH: production fingerprint changed between discovery and mutation")

    if BRAINK_MARKER not in html:
        if "</head>" not in html or "</body>" not in html:
            raise RuntimeError("REFUSE_PATCH: malformed current index; head/body close tags required")
        meta = f'<meta name="casepath-braink" content="{BRAINK_MARKER}">'
        html = html.replace("</head>", meta + "\n</head>", 1)
        control = (
            '<a href="/braink-admin.html" data-braink-control="true" '
            'style="position:fixed;right:18px;bottom:18px;z-index:9998;padding:10px 14px;'
            'border-radius:999px;background:#173f3a;color:#fff;text-decoration:none;'
            'font:700 12px system-ui;box-shadow:0 8px 28px rgba(0,0,0,.18)">BRAINK</a>'
        )
        html = html.replace("</body>", control + "\n</body>", 1)
        index.write_text(html, encoding="utf-8")

    admin = root / "braink-admin.html"
    admin.write_text(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="casepath-braink" content="BRAINK-CASEPATH-LIVE-20260829"><title>CasePath · BRAINK Control</title><style>body{margin:0;background:#07110f;color:#e8f2ef;font-family:system-ui}main{max-width:900px;margin:0 auto;padding:48px 24px}.card{border:1px solid #29443f;border-radius:18px;background:#0c1916;padding:24px;margin:16px 0}code,pre{font-family:ui-monospace,monospace}a{color:#9cdbcb}.pill{display:inline-block;border:1px solid #3d7568;border-radius:999px;padding:6px 10px}.muted{color:#9db2ac}</style></head><body><main><div class="pill">BRAINK-CASEPATH-LIVE-20260829</div><h1>CasePath · BRAINK Control Surface</h1><p class="muted">Resident CasePath/BRAINK operational surface. No passwords, API tokens or private keys are embedded in browser-delivered code.</p><section class="card"><h2>Projection</h2><pre>app://casepath\n→ casepath.com.au\n→ current production tree</pre></section><section class="card"><h2>Authority boundary</h2><p>Content and runtime mutation remains behind the authenticated owner execution path. This public surface provides the BRAINK production marker and runtime lineage without exposing secret-bearing authority.</p></section><section class="card"><h2>Runtime marker</h2><pre id="state"></pre></section><p><a href="/">← Return to CasePath</a></p></main><script>document.getElementById('state').textContent=JSON.stringify({schema:'casepath.braink.public-control.v1',marker:'BRAINK-CASEPATH-LIVE-20260829',host:location.host,path:location.pathname,observed_at:new Date().toISOString()},null,2)</script></body></html>""",
        encoding="utf-8",
    )

    receipt = {
        "schema": "casepath.braink.live-patch.v2",
        "state": "PATCHED_CURRENT_PRODUCTION_TREE",
        "docroot": str(root),
        "index_sha256": sha256(index),
        "contact_sha256": sha256(contact),
        "admin_sha256": sha256(admin),
        "marker": BRAINK_MARKER,
        "time_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    Path("CASEPATH_BRAINK_LIVE_PATCH_RECEIPT.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2), flush=True)
    return receipt


def fetch_public(url: str) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BRAINK-CasePath-Readback/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.read().decode("utf-8", "ignore")


def public_readback() -> dict:
    attempts = []
    for i in range(1, 7):
        nonce = int(time.time())
        try:
            root_status, root_body = fetch_public(f"https://casepath.com.au/?braink_readback={nonce}")
            admin_status, admin_body = fetch_public(f"https://casepath.com.au/braink-admin.html?braink_readback={nonce}")
            contact_status, contact_body = fetch_public(f"https://casepath.com.au/contact.html?braink_readback={nonce}")
            state = {
                "attempt": i,
                "root_status": root_status,
                "admin_status": admin_status,
                "contact_status": contact_status,
                "root_marker": BRAINK_MARKER in root_body,
                "admin_marker": BRAINK_MARKER in admin_body,
                "current_product_preserved": "Start Your Case" in root_body and "CasePath Public Beta" in root_body,
                "contact_preserved": contact_status == 200,
            }
            attempts.append(state)
            print(json.dumps(state, indent=2), flush=True)
            if all((
                state["root_status"] == 200,
                state["admin_status"] == 200,
                state["contact_status"] == 200,
                state["root_marker"],
                state["admin_marker"],
                state["current_product_preserved"],
                state["contact_preserved"],
            )):
                receipt = {
                    "schema": "casepath.braink.public-readback.v1",
                    "state": "PUBLIC_READBACK_PASS",
                    "marker": BRAINK_MARKER,
                    "attempts": attempts,
                    "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                }
                Path("CASEPATH_BRAINK_PUBLIC_READBACK.json").write_text(json.dumps(receipt, indent=2))
                return receipt
        except Exception as exc:
            attempts.append({"attempt": i, "error": repr(exc)})
            print(f"readback attempt {i}: {exc!r}", flush=True)
        time.sleep(5)

    receipt = {
        "schema": "casepath.braink.public-readback.v1",
        "state": "PUBLIC_READBACK_FAIL",
        "marker": BRAINK_MARKER,
        "attempts": attempts,
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    Path("CASEPATH_BRAINK_PUBLIC_READBACK.json").write_text(json.dumps(receipt, indent=2))
    raise RuntimeError("PUBLIC_READBACK_FAIL: local mutation did not become externally observable")


def main() -> int:
    root, _ = discover()
    b = backup(root)
    print(f"backup={b}", flush=True)
    patch(root)
    public_readback()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CASEPATH_BRAINK_PATCH_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
