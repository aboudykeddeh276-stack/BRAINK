#!/bin/bash
# Execute a DNS query locally and print an honestly capped proof receipt.
#
# Proof boundary: the sandbox cannot prove an authoritative nameserver replied,
# so the status can never rise above LOCALLY_EXECUTED.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACKAGE_ROOT"

PYTHON="${PYTHON:-python3}"
QUERY_NAME="${1:-${BRAINK_DNS_QUERY_NAME:-example.com}}"
RECORD_TYPE="${2:-${BRAINK_DNS_RECORD_TYPE:-A}}"
RESOLVER="${3:-${BRAINK_DNS_RESOLVER:-8.8.8.8}}"

echo "== BrAInK runtime :: DNS verification =="
echo "query    : $QUERY_NAME ($RECORD_TYPE)"
echo "resolver : $RESOLVER"
echo

PYTHONPATH="$PACKAGE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
QUERY_NAME="$QUERY_NAME" RECORD_TYPE="$RECORD_TYPE" RESOLVER="$RESOLVER" \
"$PYTHON" - <<'PY'
import json
import os

from braink_runtime.dns_transport import DNSTransport, build_query

name = os.environ["QUERY_NAME"]
rtype = os.environ["RECORD_TYPE"]
resolver = os.environ["RESOLVER"]

txid, wire = build_query(name, rtype, txid=0x4242)
print("query wire bytes (%d): %s" % (len(wire), wire.hex()))

transport = DNSTransport()
receipt = transport.generate_proof_receipt(name, rtype, resolver)
payload = receipt.to_dict()
payload["authoritative_external_confirmed"] = False
payload["note"] = (
    "Authoritative DNS not confirmed from sandbox - capped at LOCALLY_EXECUTED per Rule 3"
)
payload["transport_status"] = transport.last_status
payload["transport_error"] = transport.last_error
print(json.dumps(payload, indent=2, sort_keys=True))

assert payload["status"] in ("LOCALLY_EXECUTED", "LOCAL_EXECUTION_FAILED")
assert payload["authoritative"] is False
print("\nstatus cap honoured: never EXTERNALLY_OBSERVED, never PUBLICLY_DEPLOYED.")
PY
