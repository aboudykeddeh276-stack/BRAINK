# V98 Deployment Runbook

## Branch deployment

This pack is deployed through branch `keddeh/v98-protocol-compliance-deployment-os` and reviewed through pull request gates.

## Local target-host execution

```bash
cd v98_protocol_compliance_config
bash scripts/run.command
bash scripts/status.command
```

## macOS launchd service

```bash
cd v98_protocol_compliance_config
bash scripts/install.command
bash scripts/status.command
bash scripts/stop.command
bash scripts/uninstall.command
```

The LaunchAgent template is populated at install time so the working directory is bound to the actual checkout path.

## GitHub self-hosted runner

The workflow `.github/workflows/v98-host-acceptance.yml` requires runner labels:

```text
self-hosted, macOS, ARM64, KEDDEH-M3
```

Hosted runners can run syntax checks, but they are not the final authority for M3/iostat/launchd/workstation-state claims.

## Evidence outputs

- `evidence/FINAL_VERIFICATION.json`
- `runtime_volume/proof_bundles.ledger`
- `runtime_volume/outbox/*.handoff.json`
- `exports/service_execution_receipts.csv`
- `exports/target_gate_matrix.csv`
- `exports/orphan_resolution_matrix.csv`

## Promotion control

Only the V98 acceptance harness can promote `LOCAL_PASS`. Provider, target-host and external-certification states stay gated until receipts exist.
