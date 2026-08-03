# V99 K-APP to K-Cloud Deployment Model

## Canonical rule

```text
Dependency failure != global application failure
```

A missing provider, runner, speaker, GPU, network route, certificate, worker or mesh node removes only the capability supplied by that domain unless continuing would violate a proven safety, integrity or semantic invariant.

## Pipeline

```text
SOURCE APPLICATION / APPLET
  -> VITE BUILD AND COMPILATION
  -> IMMUTABLE K-APP PACKAGE
  -> K-CLOUD ADMISSION AND POLICY RESOLUTION
  -> MESH REGISTRATION
  -> NODE / AGENT / MICROVM / SERVICE DEPLOYMENT
  -> HEALTH AND CAPABILITY READBACK
  -> EVIDENCE-BASED PROMOTION
```

## Integrity readback gate

Before node-side execution, the adapter reads back `k-app.manifest.json`, loads `integrity.sha256`, recomputes the manifest hash, verifies every required package file, and confirms that `dependency-contracts.json` and `degraded-mode-policy.json` exist. Node execution is not allowed when the manifest readback fails.

## FailureLedger

`FailureLedger` is an append-only recovery ledger for dependency failures. It records blocked capability, blocked domain, criticality, root cause, impact radius, unaffected domains, continuation mode, fallback adapter, durable outbox, tests, re-entry conditions, promotion evidence and owner. It also reconciles deferred work when a dependency returns.

## HealthState monitor

`HealthStateMonitor` observes registered mesh nodes and projects both operational state and capability state. The UI becomes degraded when a node dependency fails, but the core application remains operational if mandatory semantic dependencies remain healthy.

## Circuit breaker

The K-Cloud adapter uses circuit breakers around external services such as `service.mesh-registry` and `service.remote-telemetry`. Repeated failures open the circuit so unavailable providers cannot cascade into scheduler, ledger, VFS, local runtime or application-core failure.

## Evidence outputs

Running the adapter emits:

```text
evidence/k_cloud_deployment_receipt.json
exports/k_cloud_health_matrix.csv
runtime_volume/failure_ledger.jsonl
runtime_volume/continuation_workflows/k_cloud/*.json
runtime_volume/outbox/k_cloud/*.handoff.json
```

## Boundary

The package can prove local package integrity, policy resolution, fallback activation and receipt generation. It cannot claim real domain authorization, TLS readback, remote mesh registration, remote telemetry, M3 host validation or external provider health until those domains emit their own receipts.
