# Governance Profile Matrix

The same control skeleton applies at different levels with different required depth.

| Level | Separate control package | Must define authority | Must define dependency graph | Must define rollback | Must define cross-platform contract | Evidence scope |
|---|---|---|---|---|---|---|
| Sector | Yes | Yes | Yes | For consequential sector transitions | Yes | Sector/service receipts and repository lineage |
| Repository | Yes | Yes | Yes | For deployment/config mutations | Yes | CI, release, dependency and deployment evidence |
| Runtime/service | Yes | Yes | Yes | Yes | Yes | Runtime state, interface, restart/recovery and readback |
| Module | Usually | Yes when state/authority crossing occurs | Yes | When module mutates persisted/external state | Inherit + specialise | Module/interface evidence |
| Adapter/actuator | Yes | Yes | Yes | Yes | Yes | Pre/post state, authority and external readback |
| Workflow/process | Yes | Yes | Yes | Yes when mutation is coordinated | Runner/platform contract | Workflow run, job, admission and rollback evidence |
| Consequential function | Inherit module + function manifest | Yes | Inherit/declare delta | Yes when mutation crosses state boundary | Inherit unless platform-specific | Function receipt/readback |
| Pure helper function | No separate document set | Inherit | Inherit | Not normally | Inherit | Unit-level evidence only |

## Minimum component specification by level

### Sector
- canonical sector identifier;
- legal/operating owner where relevant;
- repository authorities;
- shared runtime dependencies;
- interfaces to other sectors;
- promotion/evidence policy.

### Repository
- canonical repository role;
- upstream/downstream repositories;
- branch/pull/release controls;
- dependency fragments;
- filing standard;
- CI and deployment workflow controls.

### Runtime/service
- resident identity;
- state and persistence;
- start/stop/restart lifecycle;
- exposed interfaces;
- consumers/producers;
- recovery and readback.

### Adapter/actuator
- source class;
- target substrate;
- mutation authority;
- preconditions;
- exact mutation;
- post-condition/readback;
- rollback;
- proof class.

### Consequential function
A function needs explicit governance only when it can mutate persistent, remote, authoritative, financial, security-sensitive or externally visible state. Otherwise it inherits its module controls.

## Inheritance rule

A child manifest references the nearest governed parent and records only deltas in authority, substrate, interface, dependency, proof, rollback, filing or portability semantics.

## Repository organisation rule

Governance packages belong beside the owning component or in the central `governance/specs` registry. Do not duplicate control packages into unrelated repositories. Cross-repository dependencies are referenced through the dependency graph and authority documents.
