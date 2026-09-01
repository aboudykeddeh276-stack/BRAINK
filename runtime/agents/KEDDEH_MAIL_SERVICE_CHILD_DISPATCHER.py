#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
PACKET_PATH = HERE / "KEDDEH_MAIL_SERVICE_CHILD_TEAM_R1.json"
PACKET = json.loads(PACKET_PATH.read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def resolve_process(process_id: str):
    for process in PACKET["processes"]:
        if process["id"] == process_id:
            return process
    raise KeyError(process_id)


def dispatch(process_id: str, input_state: dict):
    process = resolve_process(process_id)
    owner_key = process["owner"]
    agents = PACKET["agents"].get(owner_key, [])
    receipt = {
        "schema": "kex.braink.mail-child-dispatch-receipt.v1",
        "team": PACKET["identity"],
        "domain": PACKET["domain"],
        "process": process_id,
        "owner": owner_key,
        "lead": process["lead"],
        "assigned_agents": agents,
        "actions": process["actions"],
        "outputs": process["outputs"],
        "promotion_gate": process["promotion_gate"],
        "input_hash": sha(input_state),
        "state": "STATE_DISPATCHED",
        "execution_state": "NOT_YET_READ_BACK",
        "provider_mutation": "NOT_CLAIMED",
        "at": time.time(),
    }
    receipt["receipt_sha256"] = sha(receipt)
    return receipt


def dispatch_all(input_state: dict):
    receipts = [dispatch(process["id"], input_state) for process in PACKET["processes"]]
    aggregate = {
        "schema": "kex.braink.mail-child-dispatch-batch.v1",
        "team": PACKET["identity"],
        "domain": PACKET["domain"],
        "state": "CHILD_TEAM_DISPATCHED",
        "receipts": receipts,
        "promotion": "NOT_PROMOTED",
        "reason": "Execution/readback remains required for every provider and DNS gate.",
    }
    aggregate["batch_sha256"] = sha(aggregate)
    return aggregate


def main():
    payload = json.loads(sys.stdin.read() or "{}")
    if len(sys.argv) == 1 or sys.argv[1] == "--all":
        result = dispatch_all(payload)
    else:
        result = dispatch(sys.argv[1], payload)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
