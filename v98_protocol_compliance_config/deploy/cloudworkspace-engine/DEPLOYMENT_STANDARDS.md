# CloudWorkspaceEngine Sovereign Mesh Deployment Standard

## 1. Scope

This standard governs Kubernetes deployment of `CloudWorkspaceEngine` and its communication with the Mesh-Engine Node Registry. It applies the active-word equation `A_W=f(W,C,E,S,V,O,L,T)`, the IL-LLM transition sequence, bounded dependency-failure handling, bilateral evidence links, and receipt-backed promotion.

## 2. Mandatory deployment artifacts

Every deployable release MUST include:

- immutable container image reference and version;
- Kubernetes Namespace, ServiceAccount, ConfigMap, Deployment and ClusterIP Service;
- startup, readiness and liveness probes with distinct semantics;
- PodDisruptionBudget;
- NetworkPolicy;
- resource requests and limits;
- non-root, no-privilege-escalation and read-only-root-filesystem settings;
- K-APP manifest, dependency contracts, degraded-mode policy, recovery policy, SBOM, build receipt and SHA-256 integrity receipt;
- OpenAPI contract for all inter-node HTTP communication;
- rollback target and previous-version retention.

## 3. Probe semantics

### Startup

`/startupz` proves only that initialization has completed. Until it succeeds, Kubernetes must not run liveness or readiness checks.

### Readiness

`/readyz` determines traffic eligibility. It MUST fail when a mandatory capability is unavailable, manifest integrity has not been read back, or policy resolution is incomplete. Optional, replaceable, external-gated and deferred dependencies MUST be represented as capability-scoped degraded states and MUST NOT automatically fail process liveness.

### Liveness

`/healthz` detects an unrecoverable process-progress failure such as an event-loop deadlock. It MUST NOT depend on remote telemetry, optional GPU/audio adapters, external providers or temporary registry unavailability. A liveness probe must not create a cascading restart loop from an external dependency failure.

## 4. Dependency policy

Supported criticality classes:

- `CORE_MANDATORY`: stop only operations whose semantic validity requires the dependency;
- `CORE_DEGRADED`: continue with a declared reduced capability;
- `OPTIONAL`: bypass the feature;
- `EXTERNAL_GATE`: retain local operation while external proof remains pending;
- `REPLACEABLE`: activate a compatible adapter;
- `DEFERRED_COMMIT`: persist work and reconcile after recovery.

Canonical rule:

```text
DEPENDENCY FAILURE != GLOBAL APPLICATION FAILURE
```

A global stop is permitted only for a proven global safety, integrity or semantic invariant violation.

## 5. Configuration

Environment and dependency policy are managed through ConfigMap data. Secrets, private keys, bearer signing keys and provider credentials MUST use Kubernetes Secret resources or an external secret manager and MUST NOT be committed to a ConfigMap.

Configuration changes must produce:

1. a new configuration revision;
2. schema validation;
3. policy-difference receipt;
4. controlled rollout;
5. post-rollout capability readback.

## 6. Network boundary

The default service type is `ClusterIP`. External exposure requires a separately reviewed Gateway or ingress layer with TLS, authorization policy and external readback. NetworkPolicy must default-deny the workload and explicitly allow only required mesh, registry, DNS and observability communication.

## 7. Security context

Pods MUST:

- run as non-root;
- drop all Linux capabilities unless an exception is documented;
- disallow privilege escalation;
- use `RuntimeDefault` seccomp;
- use a read-only root filesystem;
- disable automatic service-account token mounting unless Kubernetes API access is required;
- mount writable state only at declared paths.

## 8. Availability and rollout

Production deployment requires at least three replicas across failure domains, a PodDisruptionBudget, rolling updates with `maxUnavailable: 0`, and topology spread constraints. Autoscaling must include a conservative scale-down stabilization window to avoid oscillation.

## 9. State and persistence

The Deployment manifest uses ephemeral runtime volumes only. Durable server-side failure ledgers, manifests and receipts MUST use a declared persistent backend such as a Stateful service, database or PersistentVolume. Browser-side FailureLedger state uses IndexedDB for refresh persistence and deferred-work reconciliation; it does not replace cluster-authoritative storage.

## 10. Promotion ladder

A capability advances only through explicit evidence:

```text
IMPLEMENTED
→ LOCAL_PASS
→ CI_PASS
→ TARGET_HOST_PASS
→ PROVIDER_PASS
→ DEPLOYED
→ EXTERNALLY_PROVEN
```

Kubernetes object creation alone proves only artifact admission. `DEPLOYED` requires rollout success and capability readback. `EXTERNALLY_PROVEN` requires an independent authorized observer.

## 11. Bilateral evidence

Every deployment, health observation, failure and reconciliation receipt must support:

```text
source definition
→ active word instance
→ expression
→ sector
→ service
→ execution
→ receipt
```

and the reverse traversal back to the source definition and lineage.

## 12. FailureLedger reintegration

When a dependency returns:

1. mark the failure `RECOVERING`;
2. record observer, timestamp and health evidence;
3. replay deferred items idempotently;
4. persist each item result;
5. retain failed items for another bounded retry;
6. mark `REINTEGRATED` only when no deferred work remains;
7. issue a reconciliation receipt with `globalStop: false`.

## 13. Validation commands

Recommended cluster-side validation:

```bash
kubectl apply --server-side --dry-run=server -f cloudworkspace-engine.yaml
kubectl diff -f cloudworkspace-engine.yaml
kubectl apply -f cloudworkspace-engine.yaml
kubectl rollout status deployment/cloudworkspace-engine -n keddeh-sovereign-mesh
kubectl get pods,svc,endpointslices,pdb,hpa,networkpolicy -n keddeh-sovereign-mesh
```

OpenAPI validation should use an OpenAPI 3.0-compatible validator before client or server generation.

## 14. Acceptance boundary

These files are deployable artifacts and standards. They do not by themselves prove that the referenced container image exists, that a cluster accepted the manifests, that the probes are implemented by the application, that NetworkPolicy is enforced by the installed CNI, or that an external mesh route is operational. Those claims require their respective receipts.
