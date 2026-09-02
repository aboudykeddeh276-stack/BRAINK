# Keddeh Systems Sector Repository Federation R1

## Purpose

Create a clear operational repository boundary for each major sector while preserving one shared BRAINK execution protocol and one HR authority model.

## Federation roots

- BRAINK orchestration: `aboudykeddeh276-stack/BRAINK`
- HR/governance authority: `aboudykeddeh276-stack/GENERAL-GOVERNANCE-`

## Sector repositories

| Sector | Repository | Shared runtime |
|---|---|---|
| Runtime / Servers | `aboudykeddeh276-stack/KERA_SERVER` | `braink_sector/sector_runtime.py` |
| Storage / Memory | `aboudykeddeh276-stack/virtualized-storage` | `braink_sector/sector_runtime.py` |
| Research / Learning / Evolution | `aboudykeddeh276-stack/KSYSTEMS_LEARNING-` | `braink_sector/sector_runtime.py` |
| Code / Synthesis | `aboudykeddeh276-stack/K-SYSTEMS-CODE-SPACE-` | `braink_sector/sector_runtime.py` |
| Mesh / Software Nodes | `aboudykeddeh276-stack/KEDDEH_SOFTWARE_NODES` | `braink_sector/sector_runtime.py` |
| Mining | `aboudykeddeh276-stack/MINING` | `braink_sector/sector_runtime.py` |
| Console / UI | `aboudykeddeh276-stack/BRAINK-CONSOLE-PLUS` | `braink_sector/sector_runtime.py` |

Each repository also owns `braink_sector/SECTOR_MANIFEST_R1.json`, which declares its capability namespace and its BRAINK/HR parentage.

## Shared ABI

Every sector consumes the same logical task fields:

`task_id, sector, work_module, capability, operation, payload, agent_id`

Every sector emits the same receipt fields:

`task_id, sector, capability, agent_id, status, effect, produced_at_ns, receipt_root`

Unbound capabilities return `DEFERRED_CAPABILITY_HOLE` rather than being silently substituted.

## HR role

`GENERAL-GOVERNANCE-/braink_hr/hr_runtime.py` owns assignment state:

- agent identity
- team identity
- sector
- role set
- capability set
- authority scope
- verifier/promoter role separation
- revocation state

HR authorization is evaluated before BRAINK dispatch.

## BRAINK role

`BRAINK/enterprise/sector_federation_runtime.py` owns cross-sector dispatch and receipt collection. It does not bypass HR authority. It distinguishes:

- `REJECTED_HR_AUTHORITY`
- `DEFERRED_SECTOR_HOLE`
- sector-native execution/rejection states

The federation therefore supports one WorkModule contract being assigned to multiple agents or groups while sector-specific implementations remain local to their repositories.

## Evolution law

1. Discover an executable obligation.
2. Resolve HR agent/team assignment.
3. Resolve sector and required capability.
4. Reuse resident capability if present.
5. If absent, open a capability `HOLE` and route research/specification work.
6. Synthesize only from an explicit requirement/WorkModule contract.
7. Independently verify and qualify generated code.
8. Bind the validated function to the sector runtime.
9. Execute the shared WorkModule across the assigned group.
10. Return content-rooted receipts to BRAINK.
11. Reconcile observer state through BRAINK/IL-LLM.
12. Re-rank the next highest-unlock executable obligation.

This is a federation of sector repositories, not a set of independent architectures.
