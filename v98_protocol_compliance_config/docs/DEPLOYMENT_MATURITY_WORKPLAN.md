# V99 Deployment Maturity Workplan

## Purpose

This workplan turns the V99 module estate into an actionable deployment maturity map. It assesses each service, applet, application, runtime domain, function/protocol lane and governance lane against the canonical rule:

```text
DEPENDENCY FAILURE != GLOBAL APPLICATION FAILURE
```

The workplan does not treat documentation, telemetry, simulation, manifests or hashes as shippable execution proof. A component is only promoted when the required executable command, tests, package/readback evidence, ledger readback, outbox handoff and target-host/provider receipts exist.

## Inputs

The lane reads:

- `config/service_protocols.json`
- `config/application_applet_registry.json`
- `config/deployment_maturity_workplan.json`
- local K-APP packages generated under `runtime_volume/k_app_packages/application_applet_shipping/`
- local evidence receipts and ledgers

## Issues identified

The lane uses explicit issue codes:

- `MISSING_K_APP_PACKAGE`
- `TARGET_HOST_GATE_PENDING`
- `PROVIDER_GATE_PENDING`
- `REVIEW_SURFACE_TOO_LARGE`
- `TEST_RECEIPT_REQUIRED`
- `INTEGRITY_READBACK_REQUIRED`
- `DEPENDENCY_ISOLATION_REQUIRED`

Each issue is mapped to an owner, corrective workflow, pending workload, required receipt set, fallback path and re-entry condition.

## Corrective workflows

The default local corrective sequence is:

```bash
bash scripts/ship_applications.command
bash scripts/k_cloud_deploy.command
bash scripts/deployment_maturity.command
bash scripts/run.command
```

Target-host and provider work remains gated by receipt:

- self-hosted M3 runner with `[self-hosted, macOS, ARM64, KEDDEH-M3]`
- launchd status receipt
- iostat or target-host throughput receipt
- browser/K-APP catalog readback
- provider or peer acknowledgement envelopes
- DNS/TLS/certification receipts where applicable

## Outputs

```text
evidence/deployment_maturity_workplan_receipt.json
exports/deployment_maturity_workplan_matrix.csv
runtime_volume/workplans/deployment_maturity/*.json
runtime_volume/outbox/deployment_maturity_workplan/*.handoff.json
runtime_volume/proof_bundles.ledger
```

## Deployment maturity meaning

`LOCAL_SHIPPABLE` means the module has a local executable package/receipt path and can be exercised locally. It does not imply target-host, provider or certification proof.

`LOCAL_SHIPPABLE_WITH_TARGET_GATES` means the local package remains valid while external proof is pending.

`TARGET_HOST_REQUIRED`, `PROVIDER_REQUIRED` and `EXTERNAL_CERTIFICATION_REQUIRED` remain bounded continuation workflows until their receipts exist.

## Direct command

```bash
cd v98_protocol_compliance_config
bash scripts/deployment_maturity.command
```
