# BRAINK Desktop Commander Integration Specification R1

## Scope
This specification defines how BRAINK uses `@wonderwhy-er/desktop-commander` as a host-control carrier for local and remote execution environments.

## Required components
- `runtime/host_control/braink_desktop_commander_runtime.py`
- `NativeChatBot/Sources/BRAINKDesktopCommanderPlugin.swift`
- `integrations/desktop_commander/MCP_CONFIG.example.json`
- `integrations/desktop_commander/BRAINK_DESKTOP_COMMANDER_BUNDLE_R1.json`
- `integrations/desktop_commander/ARCHITECTURE.md`
- `integrations/desktop_commander/GOVERNANCE.md`
- `integrations/desktop_commander/AUTHORSHIP.json`

## Runtime contract
The carrier MUST be treated as unavailable until runtime prerequisites are observed. The runtime supervisor MUST emit STARTING, RUNNING, HEARTBEAT, EXIT, RESTARTING/STOPPED receipts. RUNNING alone does not imply a target host is authoritative or healthy.

## Host-control request contract
Every dispatched operation MUST contain or resolve:
- request_id
- actor
- ingress_class
- capability
- authority_scope
- host_id
- node_id when applicable
- service_id when applicable
- operation
- input_digest
- timeout
- proof_requirement
- return_route

## Completion contract
A host-control operation is COMPLETE only when:
1. dispatch occurred;
2. execution result was captured;
3. observable post-state was read back;
4. the post-state satisfied the requested transition;
5. a canonical receipt/proof root was committed.

## Availability states
- UNOBSERVED: no current carrier/host receipt.
- STARTING: carrier process launch underway.
- RUNNING: carrier process alive; host truth still requires target observation.
- HOST_READY: target host identity/capabilities observed and heartbeat fresh.
- DEGRADED: carrier or host reachable but one or more required capabilities failing.
- STALE: last successful heartbeat exceeded freshness TTL.
- OFFLINE_LOCAL: explicitly selected bounded local mode; external mutations cannot be promoted.
- DOWN: carrier/host unavailable beyond failure threshold.

## Security boundary
The integration MUST NOT convert a front-end request directly into an unrestricted shell. Site/user/admin routes remain distinct. Privileged host operations require an explicit ADMIN or infrastructure capability decision and proof/readback.

## Networking use
BRAINK may use the carrier to inspect and operate resident DNS, DA, registrar, TCP, mesh, routing, mining, storage, API and service-manager processes. External registry, public IP, ASN, transit and peering authority remain external facts and cannot be synthesized by this integration.
