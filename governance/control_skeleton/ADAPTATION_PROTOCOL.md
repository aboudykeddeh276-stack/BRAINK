# Governance Skeleton Adaptation Protocol

## Objective

Apply one consistent control grammar across sectors, repositories, modules, runtimes, adapters, actuators, workflows and consequential functions while preserving each component's actual semantic and substrate boundary.

## Adaptation algorithm

For each target component:

```text
IDENTIFY COMPONENT
→ RESOLVE CANONICAL CLASS
→ IDENTIFY OWNING REPOSITORY/SECTOR
→ CLASSIFY SUBSTRATE + STATE
→ ENUMERATE PRODUCER/CONSUMER INTERFACES
→ ENUMERATE DEPENDENCIES + AUTHORITIES
→ DEFINE PROOF + ROLLBACK
→ DEFINE EVIDENCE/FILING
→ DEFINE PROMOTION STATES
→ DEFINE CROSS-PLATFORM CAPABILITIES
→ GENERATE CONTROL PACKAGE
→ QUALIFY PACKAGE
→ BIND TO CI/DEPENDENCY GRAPH
→ EXECUTE/READ BACK
```

## Level-specific adaptation

### Sector
Add business/system ownership, sector authority, repository boundaries, shared services and sector-level evidence/accountability.

### Repository
Add repository authority, dependency graph, branch/pull promotion path, CI controls, filing hierarchy and external repository dependencies.

### Module/runtime
Add imports/runtime dependencies, state/persistence, producer/consumer interfaces, process lifecycle, recovery and readback.

### Adapter/actuator
Add exact representation boundary, mutation authority, target substrate, pre/post-state, idempotency, rollback and external proof.

### Function
Use the skeleton only for consequential functions that cross authority/state boundaries. Pure internal helpers normally inherit their module controls rather than receiving eleven documents each, because bureaucracy should not achieve sentience.

## Inheritance

A child component inherits controls from its parent unless it changes:

- authority;
- substrate boundary;
- persistence class;
- external interface;
- dependency class;
- proof condition;
- rollback requirement;
- evidence schema;
- cross-platform adapter.

Only differing controls need specialised child material, but the child governance manifest must reference its parent controls.

## Cross-sector reuse

The skeleton is applicable to:

- DOMAIN/DNS/REGISTRAR/TLS;
- SERVER/CLOUD/NETWORK;
- BRAINK orchestration;
- KEX runtime/addressing;
- IL-LLM semantic resolution;
- VFS/K-DRIVE storage/controller paths;
- WORKBOOK-OS;
- CASEPATH/CLAIMPATH service runtimes;
- AGENTS/ORCHESTRATION;
- SECURITY/AUTHORITY;
- EVIDENCE/LEDGER.

The generated files are structurally consistent; the component specification supplies the differing semantics.

## Anti-patterns

Do not use the skeleton to invent missing mechanics. Do not copy one sector's authority into another. Do not call generated governance runtime proof. Do not make every helper its own repository. Do not allow an adaptation to weaken inherited proof without an explicit schema/control change.
