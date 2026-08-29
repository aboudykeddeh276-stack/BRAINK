# KEDDEH Software Topology and Design Iteration Standard

## Identity

```text
standard://keddeh/software-topology
version: 1.0.0
owner: skill://keddeh/engineering-orchestrator
status: ACTIVE_ARCHITECTURE_STANDARD
```

## Purpose

This standard defines how KEDDEH software is decomposed, named, connected, versioned, reviewed, iterated, and evidenced. It preserves the existing KEDDEH/BRAINK/KEX architecture while providing a consistent topology that can be read by humans, validators, agents, repositories, workbooks, and deployment runtimes.

## Architecture-description law

Every software entity must be represented through distinct but linked descriptions:

```text
entity of interest
→ context
→ bounded domain
→ runtime container
→ component
→ code unit
→ execution transition
→ deployment projection
→ evidence receipt
```

No single diagram, file, manifest, or runtime state may silently collapse these levels.

## Canonical topology levels

### L0 — Ecosystem

Scope: the complete KEDDEH/BRAINK/KEX environment and external authorities.

Required content:

```text
actors
external systems
legal or operational authorities
provider classes
trust boundaries
major data exchanges
```

### L1 — System

Scope: one independently governed software system.

Examples:

```text
system://braink/workstation
system://kex/legal-process
system://keddeh/k-cloud
system://keddeh/bare-metal-os
```

Required content:

```text
system responsibility
owned capabilities
external interfaces
quality goals
forbidden responsibilities
```

### L2 — Domain

Scope: one bounded semantic and operational responsibility.

Examples:

```text
domain://runtime/provider-resolution
domain://storage/prime-tensor-volume
domain://governance/active-story
domain://evidence/artifact-preservation
```

A domain owns its vocabulary, state model, invariants, services, and evidence rules.

### L3 — Runtime container

Scope: one independently executable or deployable unit.

Allowed kinds:

```text
APPLICATION
APPLET
SERVICE
AGENT_RUNTIME
WORKER
MICROVM
KERNEL_SUBSYSTEM
WEB_CLIENT
DATABASE
WORKBOOK_RUNTIME
CI_WORKFLOW
```

A runtime container declares startup dependencies, runtime dependencies, capabilities, failure policy, health contract, and deployment target.

### L4 — Component

Scope: one cohesive implementation unit inside a runtime container.

A component must expose a narrow interface and may not mutate another component's private state.

### L5 — Code unit

Scope: source-level structures such as packages, modules, translation units, classes, functions, schemas, and tests.

Code-level diagrams are generated or maintained only where they add engineering value; topology authority remains at L0-L4.

### L6 — Execution transition

Scope: a validated runtime state transition.

```text
prior state
→ expression or command
→ executing service/component
→ observed result
→ next state
→ receipt
```

### L7 — Deployment projection

Scope: where the runtime container executes.

Examples:

```text
provider://github-hosted/ubuntu-x64
provider://local/m3
provider://kubernetes/arc
node://k-cloud/worker-001
volume://prime-tensor/8x8x8
```

Deployment identity does not redefine software identity.

## Dependency-direction law

The default dependency direction is:

```text
interface/contracts
← domain logic
← application orchestration
← adapters
← providers and deployment
```

Equivalent rule:

```text
higher policy must not depend on lower implementation detail
```

Permitted dependency classes:

```text
COMPILE_TIME
STARTUP_REQUIRED
RUNTIME_REQUIRED
OPTIONAL
REPLACEABLE
DEFERRED_COMMIT
OBSERVATION_ONLY
AUTHORITY_GATE
```

Every dependency edge must declare:

```text
source identity
target identity
capability consumed
data consumed
criticality
selected failover path
failure impact radius
re-entry condition
```

Cycles are prohibited unless explicitly modelled as a controlled protocol with termination, ownership, and deadlock proofs.

## Interface contract

Every interface must declare:

```text
interface identity
owner
consumer set
input schema
output schema
preconditions
postconditions
failure states
idempotency rule
ordering rule
version
compatibility policy
evidence produced
```

Interfaces use explicit contracts rather than implementation discovery.

## Naming grammar

Canonical addresses use lowercase kebab-case segments:

```text
<kind>://<authority>/<domain>/<entity>
```

Allowed kinds include:

```text
system
domain
service
component
interface
schema
workflow
agent
worker
provider
volume
adapter
receipt
evidence
story
expression
word
```

Examples:

```text
service://k-cloud/admission
component://k-cloud/admission/integrity-readback
interface://volume/backing-adapter/v1
workflow://artifact/preservation-audit
receipt://volume/binding/<receipt-id>
```

Repository names and directories use `kebab-case`.

Language-specific symbols follow language convention:

```text
C/C++ types: PascalCase
C/C++ functions and variables: snake_case
Python modules/functions: snake_case
Python classes: PascalCase
TypeScript types/classes: PascalCase
TypeScript variables/functions: camelCase
JSON/YAML keys: snake_case unless an external protocol requires otherwise
Environment variables: UPPER_SNAKE_CASE
```

Acronyms are normalized as words:

```text
KCloudAdapter, not KCLOUDAdapter
IlLlmRuntime only where source-language convention requires type casing;
il_llm_runtime for files and modules
```

## Repository topology

Canonical project layout:

```text
<system>/
├── architecture/
│   ├── context/
│   ├── topology/
│   ├── decisions/
│   ├── runtime-views/
│   ├── deployment-views/
│   └── risks/
├── contracts/
│   ├── interfaces/
│   ├── schemas/
│   └── policies/
├── src/
│   └── <bounded-domain>/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── failover/
│   └── acceptance/
├── deploy/
├── evidence/
├── runtime_volume/
├── tools/
└── SYSTEM_STATE.md
```

Existing repositories do not require destructive relocation. They require a topology map that binds current paths to this logical structure.

## Architecture viewpoints

Every material system must provide the following views:

```text
CONTEXT_VIEW
BUILDING_BLOCK_VIEW
RUNTIME_VIEW
DEPLOYMENT_VIEW
DATA_LINEAGE_VIEW
FAILURE_AND_RECOVERY_VIEW
SECURITY_AND_TRUST_VIEW
EVIDENCE_AND_PROMOTION_VIEW
```

Each view must identify audience, concern, model kind, source data, update owner, and validation rule.

## Architecture decision records

A material decision receives an immutable ADR identity:

```text
ADR-<four-digit-sequence>-<kebab-case-title>.md
```

Required fields:

```text
status
context
decision
decision drivers
considered alternatives
consequences
invariants introduced
affected topology identities
migration plan
verification evidence
supersedes/superseded-by
```

Allowed states:

```text
PROPOSED
ACCEPTED
ACTIVE
SUPERSEDED
REJECTED
DEPRECATED
```

## Iteration structure

Every engineering iteration is a bounded transition:

```text
I0 OBSERVE
I1 DEFINE
I2 DESIGN
I3 IMPLEMENT
I4 STATIC_VALIDATE
I5 EXECUTE
I6 INTEGRATE
I7 PROMOTE
I8 PRESERVE
I9 REVIEW
```

An iteration may not skip from design to promotion.

Required iteration identity:

```text
iteration://<system>/<domain>/<yyyy-mm-dd>/<sequence>
```

Required outputs:

```text
source baseline
objective
scope
non-goals
affected topology nodes
ADRs
implementation changes
tests
failover tests
evidence receipts
artifact states
promotion result
remaining gates
next iteration
```

## Versioning

Software versions use semantic versioning where the release surface has a stable public contract:

```text
MAJOR.MINOR.PATCH
```

KEDDEH research/build labels such as V98, V109, or V110 remain lineage identifiers and must be mapped to a semantic software version where a deployable product exists.

Version changes:

```text
MAJOR: incompatible interface or state-model change
MINOR: backward-compatible capability addition
PATCH: backward-compatible correction
```

Schemas and interfaces carry independent versions.

## Topology mutation law

A topology mutation must identify:

```text
nodes added
nodes changed
nodes retired
edges added
edges changed
edges removed
compatibility effect
migration sequence
rollback sequence
```

Deletion never erases lineage. Retired identities remain addressable with status `RETIRED` or `SUPERSEDED`.

## Design-quality gates

```text
GATE_TOPOLOGY_01_IDENTITIES_UNIQUE
GATE_TOPOLOGY_02_LEVELS_NOT_MIXED
GATE_TOPOLOGY_03_RELATIONSHIPS_LABELLED
GATE_TOPOLOGY_04_DEPENDENCY_DIRECTION_VALID
GATE_TOPOLOGY_05_INTERFACES_VERSIONED
GATE_TOPOLOGY_06_FAILURE_RADIUS_DECLARED
GATE_TOPOLOGY_07_RUNTIME_VIEW_PRESENT
GATE_TOPOLOGY_08_DEPLOYMENT_VIEW_PRESENT
GATE_TOPOLOGY_09_ADRS_LINKED
GATE_TOPOLOGY_10_ITERATION_RECEIPT_COMPLETE
GATE_TOPOLOGY_11_ARTIFACTS_DURABLY_PRESERVED
GATE_TOPOLOGY_12_BILATERAL_READBACK
```

## Minimum topology receipt

```json
{
  "topology_id": "topology://system/domain/version",
  "system_id": "system://...",
  "nodes": [],
  "edges": [],
  "views": [],
  "adrs": [],
  "iteration_id": "iteration://...",
  "validation_gates": {},
  "artifact_state": "DURABLE_BYTES",
  "promotion_state": "STATICALLY_VALIDATED",
  "global_stop": false
}
```

## Governing principle

```text
software topology is not a decorative diagram
```

It is the authoritative graph connecting identity, responsibility, code, runtime, deployment, evidence, and iteration lineage.
