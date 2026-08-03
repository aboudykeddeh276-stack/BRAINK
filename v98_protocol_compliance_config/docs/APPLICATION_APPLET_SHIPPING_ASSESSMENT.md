# V99 Application/Applet Shipping Assessment

This document binds every service module in `service_protocols.json` to the K-APP deployment model. The rule is canonical: dependency failure is not global application failure. Each application, applet, service, infrastructure adapter and agent-facing runtime receives an independent package, manifest, dependency contract, degraded-mode policy, recovery policy, integrity readback and receipt.

## Execution command

```bash
cd v98_protocol_compliance_config
bash scripts/ship_applications.command
```

The command compiles source and tests, generates K-APP packages, performs manifest integrity readback before node-side execution is allowed, writes a shipping matrix, emits a receipt and runs the application/applet tests.

## Generated artifacts

```text
runtime_volume/k_app_packages/application_applet_shipping/<component>/
runtime_volume/application_catalog/index.html
exports/application_applet_shipping_matrix.csv
evidence/application_applet_shipping_receipt.json
runtime_volume/outbox/application_applet_shipping/*.handoff.json
```

## K-APP package rule

Every generated package contains:

```text
application/index.html
k-app.manifest.json
asset-manifest.json
route-manifest.json
agent-bindings.json
vfs-namespaces.json
telemetry-schema.json
permission-policy.json
dependency-contracts.json
degraded-mode-policy.json
recovery-policy.json
SBOM.spdx.json
build-receipt.json
integrity.sha256
```

`dependency-contracts.json` and `degraded-mode-policy.json` are mandatory. A package without them is not safely deployable because its failure radius cannot be determined.

## Runtime independence contract

Every package manifest declares:

```text
identity
suppliedCapabilities
startupDependencies
runtimeDependencies
optionalDependencies
criticalityClass
fallbackAdapter
degradedModeBehaviour
queueOutboxPolicy
circuitBreakerLimits
rollbackContract
recoveryConditions
reintegrationTests
```

The packager rejects a component as not shippable when that contract is incomplete or when manifest integrity readback fails.

## Shipping states

`LOCAL_SHIPPABLE_K_APP` means the local browser-openable package, manifests, contracts, receipts and outbox handoff exist and passed readback. It does not claim external DNS, TLS, M3, provider or certification proof.

`TARGET_HOST_REQUIRED` means the package is ready to be admitted into K-Cloud and read back by an eligible node, but target-host evidence is still required.

`NOT_SHIPPABLE_MISSING_CONTRACT` and `NOT_SHIPPABLE_INTEGRITY_FAILURE` are fail-closed states.

## Promotion rule

A module is not complete merely because it has a manifest, telemetry event, dashboard or report. A module becomes locally shippable only when it has source, an executable command, tests, required K-APP files, manifest integrity readback, receipt write, ledger/outbox handoff and explicit target/provider gates.
