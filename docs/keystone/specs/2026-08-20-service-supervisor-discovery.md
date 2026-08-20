# BRAINK Service Supervisor — Read-Only Discovery and Reconciliation Specification

Date: 2026-08-20
Status: APPROVED PLANNING HANDOFF / IMPLEMENTATION NOT CLAIMED
Scope: First vertical slice only

## Goal

Establish a proof-bearing, read-only service discovery and reconciliation boundary for BRAINK long-lived processes before any start, stop, restart, adoption, or termination behavior is introduced.

The governing invariant is:

`ProcessObservation -> IdentityVerification -> OwnershipClassification -> HealthClassification -> EvidenceReceipt`

Discovery is not ownership. Visibility is not shutdown authority. A process being healthy is independent of whether BRAINK started it.

## Audience

BRAINK/KEX runtime architect, operator, verifier, and implementation engineer.

## Established repository evidence

The repository contains heterogeneous execution surfaces rather than one monolithic runtime. The native application, proof-bearing engineering CLI, finite BTC workload jobs, finite solver/engine child commands, and Bitcoin Core daemon have different lifecycle semantics.

`runtime/btc_workload_substrate.py` currently:

- checks Bitcoin Core RPC before attempting launch;
- leaves an already reachable node running rather than starting a duplicate;
- can resolve and launch local `bitcoind` using `subprocess.Popen(..., start_new_session=True)`;
- redirects daemon stdout/stderr to ledger files;
- polls RPC after launch and returns a PID;
- executes configured engine/solver commands with bounded `subprocess.run(..., timeout=...)` semantics;
- performs a finite workload orchestration and returns a next-route value rather than owning a demonstrated persistent mining loop.

The current source therefore establishes daemon-start capability but does not, by itself, establish complete durable daemon lifecycle ownership.

## Product behavior

### Actor

BRAINK runtime/operator or another authorized BRAINK component requesting service state.

### Trigger

A read-only discovery, status, or reconciliation request for a registered service.

### Preconditions

- A service definition identifies the expected process/service role.
- Discovery may inspect host-visible process and service metadata when the active runtime exposes it.
- No mutation authority is required for this slice.

### Result

For each discovered service, return independently represented:

1. process identity;
2. BRAINK ownership classification;
3. service health;
4. evidence supporting each classification;
5. contradictions or unresolved fields.

The result MUST NOT start, stop, restart, signal, adopt, or otherwise mutate a process.

## State model

Lifecycle states relevant to the wider supervisor are:

- `ABSENT`
- `DISCOVERED_EXTERNAL`
- `DISCOVERED_BRAINK_OWNED`
- `STARTING`
- `RUNNING_HEALTHY`
- `RUNNING_SYNCING`
- `RUNNING_UNHEALTHY`
- `STOPPING`
- `STOPPED`
- `CRASHED`
- `IDENTITY_CONFLICT`

Slice 1 may observe/classify existing states but may not initiate lifecycle transitions.

`DISCOVERED_EXTERNAL` is a valid stable state. It is not an error and does not imply adoption.

## Orthogonal state dimensions

The implementation MUST NOT flatten these into a single `running` boolean:

### Identity

Whether the observed host process can be bound to the expected service instance.

### Ownership

Whether BRAINK has evidence that it owns lifecycle authority for that exact instance.

### Health

Whether the service satisfies its service-specific health predicate.

Therefore:

`Healthy(P) != OwnedByBRAINK(P)`

and:

`PID_recorded == PID_current` is insufficient to establish process identity because PIDs can be reused.

## Minimum service record

A discovered/managed service record should support at least:

- `service_id`
- `process_role`
- `pid`
- `pid_start_time`
- `executable_path`
- `command`
- `owner`
- `started_by`
- `started_at`
- `network`
- `datadir`
- `rpc_endpoint`
- `health_state`
- `last_health_check`
- `restart_policy`
- `shutdown_authority`
- `classification`
- `evidence`
- `contradictions`

Fields that cannot be observed MUST remain explicitly unknown/unobserved rather than synthesized.

## Evidence semantics

Each reconciliation attempt produces an append-only receipt. At minimum:

- `run_id`
- `sequence`
- `timestamp`
- `service_id`
- `observation_type`
- `source_id`
- `source_class`
- `classification`
- observed identity fields
- ownership result
- health result
- contradictions
- `previous_record_digest`
- `record_digest`

Recommended evidence classifications remain compatible with BRAINK evidence governance, including `OBSERVED`, `INFERRED`, `FAILED`, and `UNOBSERVED` where applicable.

A timeout of a child task is evidence about that task attempt. It MUST NOT automatically be promoted into evidence that the supervisor itself is unavailable.

## Bitcoin Core service adapter planning contract

Bitcoin Core is the first concrete service to characterize because current source can launch it as a detached process.

Read-only discovery should combine available host/process observations with service-specific RPC health where available.

Required distinctions include:

- executable/process discovered but RPC unavailable;
- RPC available and node healthy;
- RPC available and node syncing;
- RPC available but unhealthy/contradictory;
- externally started healthy node;
- BRAINK-owned node supported by matching durable identity evidence;
- identity conflict between stored and observed process metadata.

No `stop` behavior belongs in Slice 1.

## API granularity

The intended supervisor contract should eventually expose caller-intent operations:

- `discover(service)`
- `status(service)`
- `start(service)`
- `adopt(service, authority)`
- `stop(service)`
- `restart(service)`
- `reconcile()`

Only read-only `discover`, `status`, and `reconcile` behavior is authorized by this first slice.

Service-specific protocol semantics remain in adapters. The generic supervisor must not become a Bitcoin-specific god object.

## UX / projection states

### Happy

Identity, ownership, and health are each established from evidence. The projection shows them independently.

### Empty

No matching process/service instance was observed. This does not claim the executable, service definition, resident volume, or capability does not exist.

### Pending

A discovery/reconciliation operation is active. The exact current observation boundary is shown.

### Failure

The failed observation or health predicate is named. Previously obtained evidence is retained.

### Edge / constraint

A healthy external Bitcoin Core instance may be shown as:

`DISCOVERED_EXTERNAL / RUNNING_HEALTHY`

without granting BRAINK shutdown authority.

## Scope

### In

- read-only process/service discovery;
- identity evidence;
- ownership classification;
- service-specific health classification;
- contradiction reporting;
- append-only reconciliation receipts;
- Bitcoin Core as the first characterized daemon adapter;
- explicit unknown/unobserved fields.

### Out

- process termination;
- process signaling;
- process adoption;
- automatic restart;
- changing BTC consensus/candidate construction;
- redesigning NativeChatBot;
- turning one-shot utilities into daemons;
- claiming current host process state from repository data alone;
- treating a timeout as automatic supervisor death.

## Tradeoffs

Centralizing lifecycle evidence and authority adds state and reconciliation complexity, but removes the more serious ambiguity where process visibility or launch capability can be mistaken for ownership.

Service adapters increase the number of components but preserve protocol-specific health and shutdown semantics outside the generic controller.

Read-only first implementation delays lifecycle mutation, but creates the evidence boundary required to make later mutation safe and reviewable.

## Alternatives considered

### Distributed lifecycle ownership

Each subsystem manages its own daemon lifecycle. Rejected as the preferred direction because identity, ownership, evidence, restart, and shutdown rules would be duplicated and could diverge.

### Keep current behavior unchanged

Legitimate as a temporary state, but leaves detached `bitcoind` lifecycle ownership incomplete.

### Preferred

One evidence-bearing BRAINK Service Supervisor with service-specific adapters and a read-only discovery/reconciliation slice implemented before lifecycle mutation.

## Acceptance criteria — Slice 1

1. Discovery performs no process mutation.
2. Identity, ownership, and health are independently represented.
3. Discovery never implies ownership.
4. A healthy external Bitcoin Core node can be classified without adoption.
5. No shutdown authority is inferred merely from process visibility or RPC accessibility.
6. PID equality alone cannot establish process identity.
7. Missing observations remain `UNOBSERVED`/unknown rather than fabricated.
8. Contradictory identity evidence produces `IDENTITY_CONFLICT` or an equivalent fail-closed classification.
9. Bitcoin Core health is evaluated through a service-specific adapter boundary.
10. A task timeout marks the task attempt failed and does not automatically mark the supervisor unavailable.
11. Reconciliation emits an evidence receipt for every attempted classification.
12. Evidence from prior successful observation stages survives later observation failure.
13. The implementation can represent `DISCOVERED_EXTERNAL / RUNNING_HEALTHY` without enabling stop authority.
14. Repository-only inspection cannot claim actual current host PIDs.
15. Existing BTC workload behavior remains unchanged by this slice.
16. Existing native and engineering CLI behavior remains unchanged by this slice.
17. No persistent mining loop is claimed merely because a returned next-route requests more work.
18. Tests include PID-reuse/identity-conflict fixtures, external healthy Core fixtures, unavailable RPC fixtures, partial-observation fixtures, and timeout-with-supervisor-still-healthy fixtures.

## Implementation slicing

### Slice 1A — data contract and pure classification

Implement service observation types and pure identity/ownership/health classification with fixtures. No host process calls required to prove classification semantics.

### Slice 1B — read-only host observation adapter

Bind the classification layer to the host observations available in the target runtime. No mutation calls.

### Slice 1C — Bitcoin Core health adapter

Bind existing RPC health semantics to the generic observation record without moving Bitcoin-specific behavior into the supervisor core.

### Slice 1D — evidence reconciliation

Emit append-only, hash-linked receipts and prove that retries do not rewrite previous observations.

Each sub-slice must preserve the overall read-only invariant.

## Promotion gate

Slice 1 may be promoted only when tests establish:

`ObservedHostState + ServiceSpecificHealth -> DeterministicClassification + EvidenceReceipt`

without any process mutation.

Only after Change Review should lifecycle mutation (`start/adopt/stop/restart`) be planned or implemented.

## Recommended next module

`implementation` for Slice 1A only, followed by proof and `change-review` before proceeding to host binding.

## Checkpoint

Current skill: task-creation / approved Product Planning handoff
Goal: establish truthful BRAINK service discovery and lifecycle authority boundaries
Completed gates: repository survey -> product planning -> approved specification -> task decomposition
Protected behavior: current NativeChatBot, BTC workload, Bitcoin Core interaction, solver/engine execution, governance CLI, historical artifacts
Authorized mutation: Slice 1A only after implementation isolation check
Proof status: specification only; no supervisor implementation or host-runtime state claim
Next required skill: implementation
Next check: isolation, existing contract search, characterization fixtures, then minimum pure-classification implementation
Action: proceed to implementation Slice 1A
