# V99 Software Design and Deployment Workflow

## Purpose

The software design and deployment workflow converts a user objective into a deployed, receipt-backed system slice. It is not a roadmap diagram and it is not a manifest. It is an executable lifecycle that binds design, implementation, verification, deployment, observation and improvement into one governed path.

## Operating rule

A work unit is complete only when it has:

```text
source code
+ executable command
+ tests executed
+ receipt write
+ ledger readback
+ outbox handoff
+ target-host/provider receipt where required
```

The following are useful but insufficient by themselves:

```text
manifest
telemetry
hash
report
dashboard render
documentation
```

## Lifecycle phases

1. Intake and work identity: validate work reference, portable slug, title, scope and metadata.
2. Architecture and boundary design: define control plane, data plane, runtime boundary and vCPU/vGPU separation.
3. Security and threat model: classify secrets, provider gates, trust boundaries and failure paths.
4. Implementation planning: decompose the work into small receipt-backed batches.
5. Code implementation: authorize the worker or agent and write bounded code changes.
6. Verification and validation: compile, execute tests, run negative vectors and write the test receipt.
7. Release candidate packaging: preserve artifact inventory, release candidate metadata and handoff.
8. Deployment gate: classify local, target-host, provider and external-certification gates.
9. Target-host deployment: execute on the M3 self-hosted runner and launchd path.
10. Post-deployment observability: collect telemetry as diagnosis and audit support, not proof.
11. Rollback and improvement: preserve failures and re-enter the workflow as new work.

## Framework alignment

The workflow is aligned as a reference implementation to:

- ISO/IEC/IEEE 12207: software lifecycle structure
- NIST SSDF: secure development practices integrated into the SDLC
- OWASP SAMM: governance, design, implementation, verification and operations
- DORA continuous delivery: small batches, automated tests, deployment automation and fast feedback
- GitHub Actions environments: explicit deployment targets, protection rules and environment-scoped secrets
- SLSA and CycloneDX: supply-chain and software inventory/custody alignment
- OpenTelemetry: traces, metrics and logs as observability signals

This is reference alignment and executable control evidence. It is not external certification.

## Deployment command

```bash
cd v98_protocol_compliance_config
bash scripts/design_deployment.command
```

## Outputs

```text
evidence/software_design_deployment_workflow_receipt.json
exports/software_design_deployment_workflow_matrix.csv
runtime_volume/proof_bundles.ledger
runtime_volume/outbox/design_deployment_workflow/*.handoff.json
```
