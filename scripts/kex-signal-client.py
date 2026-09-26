#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from dataclasses import asdict
from typing import Any

from runtime.signal_fabric import SignalRequest


def _required_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise SystemExit(f"{name} must be configured")
    return value


def _request(url: str, token: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {detail}") from exc


def read_state(base_url: str, token: str, target: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"target": target})
    return _request(f"{base_url.rstrip('/')}/v1/state?{query}", token)


def compile_from_live_state(
    *, base_url: str, token: str, source: str, target: str, authority: str,
    operation: str, payload: dict[str, Any], invariants: tuple[str, ...],
) -> SignalRequest:
    observed = read_state(base_url, token, target)
    return SignalRequest.compile(
        source=source,
        target=target,
        operation=operation,
        state=observed["state"],
        payload=payload,
        invariants=invariants,
        authority=authority,
        sequence=int(observed["next_sequence"]),
        previous_receipt=str(observed["head_receipt"]),
    )


def propagate(base_url: str, token: str, request: SignalRequest) -> dict[str, Any]:
    return _request(f"{base_url.rstrip('/')}/v1/propagate", token, body=asdict(request))


def parse_json(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise SystemExit("payload must decode to a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="KEX/BRAINK canonical window signal client")
    parser.add_argument("--url", default=os.getenv("KEX_SIGNAL_URL", "http://127.0.0.1:18033"))
    parser.add_argument("--source", default=os.getenv("KEX_SIGNAL_SOURCE", "app://braink/workbook"))
    parser.add_argument("--authority", default=os.getenv("KEX_SIGNAL_AUTHORITY", ""))
    sub = parser.add_subparsers(dest="command", required=True)

    state = sub.add_parser("state")
    state.add_argument("target")

    invoke = sub.add_parser("invoke")
    invoke.add_argument("target")
    invoke.add_argument("operation")
    invoke.add_argument("payload_json")

    patch = sub.add_parser("patch")
    patch.add_argument("target")
    patch.add_argument("patch_json")

    args = parser.parse_args()
    token = _required_env("KEX_SIGNAL_AUTH_TOKEN")
    authority = args.authority or _required_env("KEX_SIGNAL_AUTHORITY")

    if args.command == "state":
        print(json.dumps(read_state(args.url, token, args.target), indent=2, sort_keys=True))
        return

    if args.command == "patch":
        operation = "STATE_PATCH"
        payload = {"patch": parse_json(args.patch_json)}
        target = args.target
    else:
        operation = args.operation
        payload = parse_json(args.payload_json)
        target = args.target

    request = compile_from_live_state(
        base_url=args.url,
        token=token,
        source=args.source,
        target=target,
        authority=authority,
        operation=operation,
        payload=payload,
        invariants=("state_must_be_object", "no_null_state"),
    )
    receipt = propagate(args.url, token, request)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
