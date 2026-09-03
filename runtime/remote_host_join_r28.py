#!/usr/bin/env python3
"""Join an independent BRAINK host without trusting its carrier as identity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request

from runtime.resident_root_projection_r28 import ResidentRootResolver, verify_remote_join


def fetch_json(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "BRAINK-R28/1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def join(base_url: str, *, domain: str = "keddeh.com", repo_root: str | Path = ".", timeout: float = 10.0) -> dict:
    base = base_url.rstrip("/")
    encoded = urllib.parse.quote(domain, safe="")

    # The endpoint is transport used to obtain proof material; it is not identity.
    remote_root_response = fetch_json(f"{base}/braink/resident-roots?domain={encoded}", timeout)
    remote_projection_response = fetch_json(f"{base}/braink/carrier-projection?domain={encoded}", timeout)
    if remote_root_response.get("status") != "PASS":
        return {"status": "REJECTED", "reason": "REMOTE_RESIDENT_ROOT_RESPONSE_NOT_PASS"}
    if remote_projection_response.get("status") != "PASS":
        return {"status": "REJECTED", "reason": "REMOTE_CARRIER_PROJECTION_NOT_PASS"}

    remote_snapshot = {
        "canonical_state": remote_root_response["canonical_state"],
        "snapshot_digest": remote_root_response["snapshot_digest"],
    }
    remote_projection = remote_projection_response["projection"]
    local_snapshot = ResidentRootResolver(repo_root).canonical_snapshot(domain)
    verification = verify_remote_join(local_snapshot, remote_projection, remote_snapshot)
    return {
        **verification,
        "domain": domain,
        "bootstrap_transport": base,
        "trusted_identity": remote_projection.get("resident_identity") if verification["carrier_trusted"] else None,
        "trusted_carrier": remote_projection.get("endpoint") if verification["carrier_trusted"] else None,
        "authority_order": [
            "LOCAL_RESIDENT_GRAPH",
            "REMOTE_RESIDENT_GRAPH",
            "RECOMPUTED_ROOT_DIGESTS",
            "RECOMPUTED_CANONICAL_SNAPSHOT",
            "CARRIER_PROJECTION",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--domain", default="keddeh.com")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--receipt")
    args = parser.parse_args()
    result = join(args.base_url, domain=args.domain, repo_root=args.repo_root, timeout=args.timeout)
    text = json.dumps(result, indent=2)
    print(text)
    if args.receipt:
        Path(args.receipt).write_text(text + "\n")
    return 0 if result.get("status") == "ACCEPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
