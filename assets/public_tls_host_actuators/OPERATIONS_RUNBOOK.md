# Operations Runbook

## Audience
Operators, administrators, maintainers and automation agents responsible for public TLS issuance and SERVER_ROOT binding.

## Normal operation
1. Confirm intended branch and commit SHA.
2. Confirm the resident self-hosted runner is online and exposes the expected fabric.
3. Confirm Dependency Graph Admission for the exact SHA.
4. Confirm GitHub dependency submission reports `SUCCESS`.
5. Run the public deployment workflow.
6. Inspect host discovery and binding artifacts.
7. Confirm DNS-01 publication readback.
8. Confirm ACME issuance receipt.
9. Confirm SERVER_ROOT live certificate fingerprint correspondence.
10. Confirm external hostname and system-trust readback.
11. Preserve receipts and report the actual promotion state.

## Administration checks
Verify Python, OpenSSL and the configured ACME client. Verify the resident fabric root, restart command, registrar database, certificate target and key target resolve to absolute unambiguous paths.

## Help: queued or pending with zero jobs
This means no runner instantiated the job. Do not diagnose DNS, TLS or application code from that state.

## Help: binding resolution blocked
Inspect `BRAINK_HOST_ACTUATOR_DISCOVERY.json`. Resolve ambiguity explicitly. Never choose the first candidate merely to continue.

## Help: DNS-01 rejected
Verify zone ownership, registrar database identity, exact TXT readback and SOA serial mutation. Do not mutate an unrelated DNS provider without an explicit authority adapter.

## Help: ACME issuance rejected
Preserve challenge and CA receipts. Inspect public challenge visibility, account/directory configuration, SAN/CSR correctness and CA error/rate-limit state.

## Help: SERVER_ROOT mismatch
If the live certificate fingerprint differs from the installed leaf, invoke rollback, restart, confirm restored fingerprint and inspect the actual server TLS loader.

## Administrative mutation rule
No manual file copy, database edit or certificate replacement is considered governed unless the same action is represented by an approved actuator and produces equivalent readback/evidence.