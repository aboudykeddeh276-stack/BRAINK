# BRAINK Public TLS Host Actuators R1

This asset implements the concrete host-side interfaces required by the existing BRAINK public TLS control path without moving authority out of the resident BRAINK/KEX object graph.

## Ownership boundary

The asset does **not** define `TLS_ROOT`, `DOMAIN_ROOT`, or `SERVER_ROOT`.

It consumes them through these executable boundaries:

```text
TLS_ROOT resident state
  -> PUBLIC_CA_ADAPTER
  -> DNS-01 host actuator
  -> public CA/ACME carrier
  -> SERVER_ROOT certificate actuator
  -> running TLS listener readback
```

## Modules

- `dns01_resident_actuator.py`
  - consumes Certbot-compatible `CERTBOT_DOMAIN` / `CERTBOT_VALIDATION` inputs;
  - resolves the longest resident zone in the actual KEX registrar SQLite database;
  - writes/removes `_acme-challenge.<domain>` TXT state transactionally;
  - increments the zone serial;
  - reads the exact state back before success;
  - refuses a domain that is not covered by a resident authoritative zone.

- `server_tls_actuator.py`
  - consumes `KEDDEH_TLS_DOMAIN`, `KEDDEH_TLS_CERTIFICATE`, `KEDDEH_TLS_FULLCHAIN`, and `KEDDEH_TLS_PRIVATE_KEY`;
  - resolves certificate/key targets from explicit environment bindings or a discovered host-binding manifest;
  - snapshots previous material before mutation;
  - installs using write+fsync+atomic replace+directory fsync;
  - restarts the resident fabric through `START_FULL_DOMAIN_FABRIC.command`;
  - connects to the local TLS endpoint using SNI and verifies the certificate actually presented by the running server;
  - rolls back automatically if readback does not match.

- `rollback_server_tls.py`
  - restores the most recent per-domain snapshot;
  - restarts the resident fabric;
  - records a rollback receipt.

- `host_bindings.example.json`
  - schema for binding the asset to the resident host after `discover_host_actuators.py` resolves the actual target paths.

## Required host state

The package expects the existing production fabric root:

`/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5`

but all host-specific paths can be overridden. It intentionally fails closed when a target cannot be proven.

## Integration

The production workflow should bind:

```text
KEDDEH_PUBLIC_CA_AUTH_HOOK
  = python3 .../dns01_resident_actuator.py auth

KEDDEH_PUBLIC_CA_CLEANUP_HOOK
  = python3 .../dns01_resident_actuator.py cleanup

KEDDEH_SERVER_TLS_INSTALL_HOOK
  = python3 .../server_tls_actuator.py install

KEDDEH_SERVER_TLS_ROLLBACK_HOOK
  = python3 .../rollback_server_tls.py
```

Because Certbot manual hooks require executable paths rather than shell fragments, the integration layer installs tiny generated launchers on the resident host that exec these Python modules. The Python modules remain the canonical implementation and are independently testable.

## Promotion rule

No certificate is considered deployed because files were copied. Promotion requires:

```text
requested certificate fingerprint
  ==
certificate fingerprint presented by the restarted resident TLS listener
```

followed by the existing external system-trust + hostname readback in `PublicCAAdapter`.
