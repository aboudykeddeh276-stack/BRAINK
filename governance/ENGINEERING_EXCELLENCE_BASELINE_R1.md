# BRAINK / KEX Engineering Excellence Baseline R1

## Purpose

This control defines the minimum engineering, research, qualification, deployment, communications, security and evidence baseline for consequential BRAINK/KEX software and infrastructure work.

It exists to prevent confidence, workflow completion, artifact presence, or repository state from being mistaken for system proof.

## 1. Core classification

Every component MUST be classified before implementation or promotion.

```text
COMPUTATION != STORAGE != ADDRESSING != COMMUNICATION != TRANSPORT != VIRTUALISATION != AUTHORITY
```

Each component MUST identify:

- logical identity;
- persistent state;
- execution mechanism;
- address space;
- exposed interfaces;
- producers and consumers;
- communication mechanism;
- transport mechanism where applicable;
- virtualisation boundary where applicable;
- authority boundary;
- persistence mechanism;
- failure and recovery semantics;
- proof conditions.

## 2. Owner-first engineering

For every dependency or capability:

```text
DISCOVER ACTUAL MECHANIC
-> RESOLVE OWNER
-> READ OWNER CONTRACT
-> EVOLVE AT OWNER
-> CONSUME BY ADAPTER
-> QUALIFY CONSUMER
```

A consumer MUST NOT duplicate an existing owner-owned mechanism merely to avoid resolving the dependency.

Cross-repository ownership MUST be represented by an explicit component contract and exact revision.

## 3. Evidence levels

Evidence MUST be reported at the highest level actually observed, never at the level intended by a workflow.

```text
L0 concept stated
L1 formal definition
L2 implementation exists
L3 executes
L4 isolated qualification
L5 integration qualification
L6 adversarial qualification
L7 restart / persistence qualification
L8 cross-process qualification
L9 cross-machine qualification
L10 external interoperability qualification
L11 repeatability qualification
L12 comparative benchmark qualification
```

A lower level MUST NOT be promoted because a higher-level test is merely defined.

## 4. Execution carrier independence

CI, self-hosted runners, containers, local machines, VMs and remote hosts are execution carriers.

They are not the source of application truth.

```text
PROOF REQUIREMENT
-> CAPABILITY REQUIREMENTS
-> EXECUTION ADAPTER
-> OBSERVATION
-> EVIDENCE RECEIPT
```

If the executor cannot instantiate the job, the result is `EXECUTOR_UNAVAILABLE` / `BLOCKED`.

If the application executes and violates its invariant, the result is `REJECTED`.

These states MUST NOT be conflated.

## 5. Build and supply-chain controls

Every consequential build or deployment MUST record:

- exact source revision;
- dependency revisions;
- execution environment identity;
- relevant platform/runtime versions;
- generated artifact digests;
- provenance where supported;
- test/evidence receipt identifiers.

Third-party GitHub Actions SHOULD be pinned to full commit SHAs. Repository workflows MUST use explicit minimum permissions.

Dependency Graph submissions SHOULD represent dependencies that static manifest analysis cannot discover, including cross-repository runtime dependencies where an appropriate package representation is available.

## 6. Research claim controls

A research claim MUST contain:

```text
CLAIM
CLASSIFICATION
KNOWN COMPUTER-SCIENCE ADJACENCY
PRIMITIVE REDUCTION
FALSIFIABLE HYPOTHESIS
BASELINE
EXPERIMENT
INSTRUMENTATION
PASS CONDITION
FAIL CONDITION
OBSERVATIONS
MEASUREMENTS
LIMITATIONS
ENGINEERING CONSEQUENCE
NEXT EXPERIMENT
```

Known computer-science adjacency MUST be used to establish comparison, not to dismiss or automatically validate the proposition.

Novelty MUST be separated from implementation maturity and experimental evidence.

## 7. Interface and authority controls

Every interface MUST identify its producer and consumer.

Every mutation MUST identify the authority permitted to perform it.

The following distinction MUST remain explicit:

```text
SEMANTIC IDENTITY != NETWORK ADDRESS != TRANSPORT ENDPOINT
```

Carrier observations MUST NOT silently become authoritative state.

## 8. Persistence and recovery

State-bearing components MUST define:

- durable state location;
- transaction boundary;
- consistency invariant;
- crash window;
- recovery procedure;
- corruption detection;
- stale writer behaviour;
- rollback behaviour;
- readback condition.

A persisted file MUST NOT be considered proof of a running system consuming that state.

## 9. Communications qualification

Communication claims MUST identify the actual boundary:

```text
same-process
IPC
inter-VM
inter-container
host-to-host
LAN
WAN
Internet
application protocol
```

For networked claims, qualification SHOULD distinguish:

```text
identity
-> addressing
-> route resolution
-> interface
-> carrier
-> transport
-> application protocol
```

A listener bound to `0.0.0.0` MUST NOT be treated as a semantic system identity.

## 10. Security and deployment

Security qualification MUST include, where applicable:

- least-privilege workflow permissions;
- immutable action references;
- secret boundary verification;
- dependency integrity;
- certificate/key correspondence;
- certificate chain verification;
- hostname/SAN verification;
- renewal behaviour;
- rollback;
- externally observable trust state.

Public CA/registry/registrar authority MUST NOT be claimed merely because a local implementation can issue equivalent-looking artifacts.

## 11. Cross-platform adaptation

Components MUST specify capabilities rather than assuming one execution platform.

Example capability vocabulary:

```text
filesystem.atomic_replace
filesystem.durable_write
process.restart
process.spawn
network.tcp_listener
network.udp_listener
crypto.x509
crypto.sha256
storage.sqlite
virtualisation.container
virtualisation.vm
runtime.python
runtime.node
```

Platform-specific implementations MUST map to the same semantic contract wherever equivalent behaviour is claimed.

## 12. Repository filing standard

Consequential components SHOULD contain, as applicable:

```text
README.md
ARCHITECTURE.md
AUTHORITY.md
DEPENDENCIES.md
runtime/
adapters/
tests/
deploy/
evidence/
receipts/
docs/
```

Governed components MUST have a machine-readable component identifier, owner, lifecycle state, authority boundary and dependency representation.

Historical/proposed artifacts MUST remain distinguishable from active specifications.

## 13. Promotion gate

Promotion MUST require:

```text
required implementation
+ required tests
+ required evidence level
+ dependency admission
+ authority admission
+ deployment/readback where applicable
+ unresolved defects disposition
```

The following are explicitly insufficient on their own:

```text
PR exists
workflow triggered
workflow queued
code compiles
test file exists
artifact exists
local test passes
certificate file exists
server process starts
```

## 14. Failure causation record

When a qualification attempt fails, the record MUST distinguish:

```text
APPLICATION FAILURE
TEST HARNESS FAILURE
EXECUTOR FAILURE
ENVIRONMENT FAILURE
DEPENDENCY FAILURE
AUTHORITY FAILURE
TRANSPORT FAILURE
EXTERNAL AUTHORITY FAILURE
```

The first observable failure boundary MUST be recorded before remediation.

## 15. Required case-study output

Every major development investigation MUST produce:

1. a claim record;
2. a component classification;
3. an implementation reference;
4. a dependency/authority map;
5. a qualification plan;
6. executed evidence where available;
7. limitations and non-claims;
8. identified defects;
9. engineering changes;
10. next falsifiable experiment.

## 16. Standards alignment

This baseline is intentionally compatible with established secure-development and software supply-chain practice rather than replacing it. NIST SSDF provides an external secure-development vocabulary; SLSA provides provenance and build-integrity concepts; GitHub Dependency Graph and Dependency Submission provide repository dependency visibility.

The BRAINK/KEX control layer adds project-specific requirements for semantic identity, owner-first dependency evolution, evidence levels, cross-repository authority and carrier-independent qualification.

## 17. Engineering maxim

```text
CONFIDENCE IS NOT EVIDENCE.

EVIDENCE IS NOT ASSUMPTION.

IMPLEMENTATION IS NOT INTEGRATION.

INTEGRATION IS NOT DEPLOYMENT.

DEPLOYMENT IS NOT EXTERNAL INTEROPERABILITY.

EVERY CLAIM STOPS AT THE HIGHEST LEVEL ACTUALLY PROVEN.
```
