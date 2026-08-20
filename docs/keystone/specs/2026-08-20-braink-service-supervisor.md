# BRAINK Service Supervisor — Product and Technical Specification

Date: 2026-08-20
Status: APPROVED_FOR_TASK_CREATION
Scope: Product Planning specification only; no runtime implementation is implied by this artifact.

## Goal

Evolve BRAINK from a set of components that can launch or invoke processes into a deterministic, evidence-bearing runtime that knows what is running, why it is running, who owns it, whether it is healthy, what depends on it, and what lifecycle action is permitted next.

Primary invariant:

```text
Observe
→ Identify
→ Classify
→ Decide
→ Act
→ Verify
→ Record
```

A process mutation is never justified solely by process existence, a PID, repository state, or an LLM-generated recommendation.

## Audience / users

- BRAINK operator/owner.
- BRAINK runtime modules that require long-lived services.
- Engineering agents performing bounded implementation, testing, and change review.
- NativeChatBot and future UI surfaces that project service state.

## Modes

- Product planning.
- Technical planning.
- Runtime/process lifecycle planning.
- Alternative evaluation.

## Existing evidence and constraints

The current repository already contains:

- a native macOS SwiftUI BRAINK application;
- a proof-bearing repository/command planner;
- bounded BTC mining jobs;
- Bitcoin Core RPC discovery and health checks;
- optional detached `bitcoind` launch;
- solver/engine subprocess execution with timeouts;
- JSON/JSONL state and evidence outputs.

The current BTC substrate can start `bitcoind` using a detached process session, but the surveyed repository does not provide a complete general service supervisor, durable process ownership registry, PID-identity reconciliation, dependency graph, bounded restart controller, or host-daemon lifecycle contract.

The existing BTC consensus, mining, RPC, and NativeChatBot boundaries are to be preserved unless later execution evidence justifies a change.

## Product behavior

### Service abstraction

BRAINK manages semantic services, not raw PIDs.

A managed service record must contain at minimum:

```text
service_id
process_role
service_type
executable_path
command
pid
pid_start_time
owner_classification
started_by
started_at
desired_state
observed_state
health_state
readiness_state
network_or_scope
data_path
endpoint
restart_policy
shutdown_authority
dependencies
dependents
last_health_check
last_transition_id
```

PID values are evidence beneath a service identity and are never sufficient authority by themselves.

### Service types

`SERVICE` is long-lived and supervisable.

Examples: Bitcoin Core, future BRAINK API, future local inference runtime, future mesh node.

`JOB` is finite and bounded.

Examples: BTC nonce-search windows, repository scans, governance checks, matrix workflows, smoke tests, proof-generation tasks.

The existing BTC miner remains a bounded job. Persistent mining behavior belongs in a mining scheduler service above the existing miner.

### Ownership classifications

Every discovered service/process must be classified as exactly one of:

```text
BRAINK_OWNED
BRAINK_ADOPTED
EXTERNAL_MANAGED
SHARED_DEPENDENCY
UNOWNED
UNKNOWN
```

Rules:

- `BRAINK_OWNED`: BRAINK has durable creation/ownership evidence and may manage lifecycle within policy.
- `BRAINK_ADOPTED`: an existing compatible service has been explicitly adopted under a recorded authority transition.
- `EXTERNAL_MANAGED`: BRAINK may observe/use the service but may not automatically stop, restart, or reconfigure it.
- `SHARED_DEPENDENCY`: lifecycle mutation requires dependent-service reconciliation.
- `UNOWNED`: no authority relationship exists.
- `UNKNOWN`: evidence is insufficient; default action is `DO_NOT_MUTATE`.

### Service lifecycle states

The supervisor must support at minimum:

```text
UNDISCOVERED
DISCOVERING
ABSENT
IDENTIFIED
OWNERSHIP_PENDING
EXTERNAL
ADOPTED
OWNED
STARTING
RUNNING_HEALTHY
RUNNING_DEGRADED
RUNNING_UNHEALTHY
RECOVERING
STOPPING
STOPPED
START_FAILED
CRASHED
IDENTITY_CONFLICT
DEPENDENCY_BLOCKED
RESTART_SUPPRESSED
ORPHAN_DETECTED
```

State changes are evidence-bearing transitions and must not be inferred from UI state.

### Host survey

BRAINK boot begins with observation, not automatic mutation.

Survey inputs must include, where supported by the host platform:

- process table;
- process executable and start time;
- process parent identity;
- listening sockets/ports;
- host service-manager state;
- persisted BRAINK service records;
- configured runtime endpoints;
- Bitcoin Core RPC state;
- application instances;
- bounded job/worker processes.

Survey mode must not start, stop, signal, adopt, or reconfigure any service.

### Identity verification

Before BRAINK mutates a persisted process identity, it must verify at minimum:

```text
PID exists
AND process start time matches
AND executable identity matches
AND expected command/service identity matches
AND ownership policy authorizes the transition
```

Service-specific contracts may add stronger checks, such as datadir, network, RPC endpoint, or application bundle identity.

PID reuse must be detected and must result in a non-mutating stale/identity-conflict classification.

### Health hierarchy

BRAINK must distinguish:

```text
PROCESS_HEALTH
SERVICE_HEALTH
DEPENDENCY_HEALTH
PRODUCT_READINESS
```

Example for Bitcoin Core:

- process health: executable is running and identity matches;
- service health: RPC is reachable and returns valid service state;
- dependency health: expected chain and required dependencies are available;
- product readiness: node is outside IBD, verification progress meets the configured gate, and a valid template can be obtained.

A healthy but syncing Bitcoin Core node is not a failed service; it is not yet mining-ready.

### Dependency graph

Services and jobs must declare dependencies.

Initial BTC graph:

```text
BTC mining job
    requires
Mining Scheduler
    requires
Bitcoin Template Provider
    requires
Bitcoin Core RPC
    backed by
Bitcoin Core process/service
```

Dependency failure should propagate `BLOCKED`/`QUIESCED` state downward instead of causing uncontrolled restart loops.

### Desired/observed reconciliation

The central supervisor operation is reconciliation:

```text
Desired state
+
Observed state
+
Ownership policy
+
Health/dependency state
+
Governance constraints
→ permitted action
```

Only a justified difference between desired and observed state produces a mutation.

Examples:

- desired `RUNNING`, observed `ABSENT`, owner authority valid → `START_REQUIRED`;
- desired `RUNNING`, compatible external service healthy → `USE_EXTERNAL`, no mutation;
- desired `RUNNING`, process present with conflicting network/datadir/identity → `IDENTITY_CONFLICT`, no mutation.

The decision function must be deterministic for the same canonical inputs. An LLM may explain or propose a lifecycle action but must not be the policy authority that decides whether a process is killed or restarted.

### Start / ensure

`ensure(service_id)` must be idempotent.

It must:

1. inspect current state;
2. verify identity/ownership;
3. derive the minimum permitted action;
4. start only when required and authorized;
5. verify service health after transition;
6. record the evidence transition.

Repeated `ensure` calls against an already healthy compatible service must not create duplicate service processes.

### Stop

Normal stop is ownership-gated.

Rules:

- `EXTERNAL_MANAGED`, `UNOWNED`, or `UNKNOWN` services are never automatically stopped.
- shared dependencies require dependent-state reconciliation before stop.
- graceful service-native shutdown is preferred where available.
- forced process termination is a separate recovery operation and requires stronger authority/evidence.

For Bitcoin Core, ordinary shutdown should use the service's control/RPC mechanism where available rather than unconditional process signaling.

### Restart

Restart policy is explicit per service.

Initial policy classes:

```text
NEVER
ON_FAILURE
ALWAYS_WHILE_DESIRED
OPERATOR_ONLY
```

Restart must support bounded attempts, backoff, stable-health reset, and `RESTART_SUPPRESSED` when limits are exceeded.

A finite mining job is not restarted as the same stale job. It is replaced by new work when the scheduler determines that current network/template state warrants a new job.

### Crash recovery

Persisted state is evidence, not truth.

On supervisor restart, every persisted active-service record must be reconciled against current host state and classified as one of:

```text
REATTACHED
ORPHANED
STALE_RECORD
IDENTITY_CONFLICT
ABSENT
```

BRAINK must never assume that a persisted PID still identifies the same process.

## BTC mining scheduler

Persistent mining behavior is owned by a scheduler service above the current bounded miner.

Core flow:

```text
ensure Bitcoin service ready
→ request live block template
→ assign execution/work ID
→ partition search domain
→ launch bounded jobs/workers
→ monitor chain/template invalidation
→ cancel superseded work
→ refresh template
→ schedule replacement work
→ validate candidate independently
→ submit through existing Core boundary when authorized
→ record evidence
```

### Job states

```text
JOB_CREATED
JOB_ASSIGNED
JOB_RUNNING
JOB_CANCEL_REQUESTED
JOB_CANCELLED
JOB_COMPLETED
JOB_FAILED
JOB_TIMED_OUT
```

Cancellation reasons must include at minimum:

```text
CHAIN_TIP_CHANGED
NEW_TEMPLATE
OPERATOR_STOP
SERVICE_UNHEALTHY
SHUTDOWN
SUPERSEDED_WORK
```

A changed chain tip or superseding template must not cause stale work to be silently continued.

### Work allocation

Concurrent worker lanes must receive non-overlapping work partitions. Allocation identity must include enough information to prove the intended uniqueness boundary, including template/work identity and nonce/extranonce or equivalent search-domain allocation.

## Evidence model

Every lifecycle and mining execution path must have a correlation identity.

At minimum:

```text
execution_id
transition_id
service_id
job_id where relevant
work_id where relevant
timestamp
observed_before
requested_action
policy_decision
action_result
observed_after
evidence_classification
```

Artifacts and external responses should be hashed when integrity/lineage materially matters. Hashing must not be used as decorative proof of claims the hash itself cannot establish.

The evidence vocabulary should remain compatible with the existing BRAINK proof-bearing model, including `OBSERVED`, `SOURCE_VERIFIED`, `IMPLEMENTED`, `TESTED`, `VALIDATED`, `FAILED`, `BLOCKED`, `DEPLOYED`, and `OPERATIONALLY_PROVEN`.

## Native UI / API projection

NativeChatBot and future interfaces consume supervisor state; they do not own it.

The product-facing runtime projection should support at minimum:

- service identity and role;
- observed state;
- ownership classification;
- health/readiness state;
- dependency blockers;
- uptime where verified;
- relevant network/scope;
- current jobs;
- last transition/result;
- evidence/drill-down reference.

UI actions such as Start, Stop, Restart, Adopt, or Reconcile invoke supervisor operations and display the resulting verified state. UI success must never be inferred solely from button activation or request dispatch.

## UX states

### Happy

Supervisor state is available; services show ownership, health, readiness, dependencies, and last verified transition. Permitted actions are enabled according to policy.

### Empty

No managed services are configured. Show an explicit `No BRAINK-managed services are configured` state rather than an empty process table suggesting failure.

### Loading / pending

While surveying or reconciling, retain last-known state as historical context and mark the current state as pending. Do not temporarily label services healthy or stopped without observation.

### Error / failure

Failures identify the failed operation, service, evidence boundary, and available recovery action. Example: `Bitcoin Core could not be verified after start. Process remains running; RPC did not become available before the health deadline.`

### Edge / constraint

Identity conflict, unknown ownership, shared dependency, stale PID record, restart suppression, and external-managed services must have distinct states and must disable unsafe mutation actions.

## Control API shape

Caller-facing operations should express intent rather than raw process mechanics.

Recommended semantic commands:

```text
braink service list
braink service inspect <service-id>
braink service ensure <service-id>
braink service start <service-id>
braink service stop <service-id>
braink service restart <service-id>
braink service adopt <service-id>
braink service reconcile
braink service evidence <service-id>

braink mining status
braink mining start
braink mining stop
braink mining jobs
braink mining evidence <execution-id>
```

Raw PID kill is not a normal product operation. Any emergency force-termination command must be explicitly separated, authority-gated, and evidence-bearing.

## Platform boundary

Preferred architecture is hybrid:

```text
BRAINK Service Supervisor
    semantic state / ownership / dependencies / evidence / policy

Host service/process adapter
    mechanical process discovery and lifecycle operations
```

Initial platform: macOS.

The semantic service model must not depend on macOS-only concepts. Future adapters may map onto `launchd`, `systemd`, Windows Service Control Manager, or direct child-process supervision while preserving the same BRAINK contract.

## Boot behavior

BRAINK boot sequence:

```text
1. establish runtime identity
2. open state/evidence store
3. load service definitions
4. inspect host process/service state
5. inspect endpoints/sockets as required
6. validate persisted identities
7. classify ownership/orphans/conflicts
8. build observed-state graph
9. compare desired vs observed state
10. generate reconciliation plan
11. apply only permitted transitions
12. verify each transition
13. publish runtime state
14. enter health/reconciliation loop
```

Boot does not mean start every service.

## Shutdown behavior

BRAINK shutdown sequence:

```text
1. stop accepting new bounded jobs
2. cancel/reconcile active jobs
3. persist final job state
4. stop BRAINK-owned transient services according to policy
5. leave externally managed services unchanged
6. apply explicit persistence policy to long-lived owned services
7. flush evidence/state
8. terminate supervisor
```

Closing NativeChatBot does not automatically imply shutdown of independently persistent services.

## Scope and tradeoffs

### In scope

- service schema and registry;
- host/process survey;
- ownership model;
- identity verification;
- health/readiness contracts;
- dependency graph;
- desired/observed reconciler;
- lifecycle transitions;
- bounded restart policy;
- crash recovery;
- evidence ledger integration;
- BTC Core migration to supervisor ownership semantics;
- mining scheduler and cancellable bounded jobs;
- NativeChatBot state projection;
- macOS process/service adapter.

### Out of scope for this initiative

- changing Bitcoin consensus rules;
- rewriting existing BTC consensus construction without evidence;
- GPU/ASIC optimization;
- profitability claims;
- modifying Bitcoin Core itself;
- distributed cluster scheduling;
- automatic mutation of arbitrary external processes;
- LLM authority over stop/kill/restart policy;
- claiming production readiness from specification or repository commits.

### Tradeoffs

The design deliberately prefers explicit blocked/degraded/conflict states over optimistic auto-recovery. This increases state-model complexity but reduces false success, unintended process mutation, duplicated daemons, restart storms, and unverifiable product claims.

## Alternatives considered

### A. Lifecycle logic inside each module

Rejected. It creates competing authorities, inconsistent ownership semantics, and divergent process-state models.

### B. Host OS supervisor only

Insufficient by itself. Host supervisors handle process mechanics but do not express BRAINK semantic ownership, dependency readiness, mining work invalidation, or evidence classification.

### C. BRAINK-only process supervisor

Viable but would unnecessarily recreate host-level supervision mechanics and complicate portability.

### D. Hybrid semantic supervisor + host adapter

Preferred. BRAINK owns semantic policy/evidence while the host adapter owns platform-specific mechanics.

## Implementation slices

### S1 — Host/process survey

Read-only inventory of processes, executable identity, start time, parent, listening endpoints, host service-manager state, and known BRAINK state. No mutation operations.

Promotion criterion: deterministic tests plus host-level evidence proving survey accuracy for known fixture/test processes without mutating them.

### S2 — Service schema + registry

Canonical service/job definitions, desired/observed state, ownership, policies, dependencies, identity material, and durable serialization.

Promotion criterion: round-trip persistence and invalid-record rejection tests.

### S3 — Identity and ownership verification

PID-reuse detection, executable/start-time verification, ownership classifications, adoption boundary, stale-record handling.

Promotion criterion: tests demonstrate that an unrelated process reusing a PID cannot be mutated.

### S4 — Health contracts

Layered process/service/dependency/readiness health model, including Bitcoin Core RPC readiness.

Promotion criterion: healthy, degraded, syncing, unavailable, wrong-network, and invalid-identity cases classify correctly.

### S5 — Desired/observed reconciler

Pure deterministic decision engine producing actions from canonical observed state + policy.

Promotion criterion: decision table coverage for all lifecycle/ownership combinations; no side effects in decision layer.

### S6 — Safe start/stop/adopt lifecycle

Mechanically apply permitted transitions through host adapter and verify read-back.

Promotion criterion: idempotent ensure/start; ownership-gated stop; external service protection; graceful shutdown path.

### S7 — Evidence ledger

Execution/transition IDs, before/action/result/after records, classification, and required hashes.

Promotion criterion: every lifecycle mutation produces a reconstructable evidence chain.

### S8 — BTC Core migration

Replace direct lifecycle ownership inside BTC substrate with service-supervisor dependency while preserving RPC/template/submission boundaries.

Promotion criterion: existing BTC tests remain satisfied and Core can be discovered, externally used, BRAINK-started, and safely stopped according to ownership classification.

### S9 — Mining scheduler + cancellable jobs

Persistent scheduler above bounded miner, work partitioning, chain/template invalidation, cancellation, replacement work, job evidence.

Promotion criterion: stale work is cancelled; concurrent allocations do not overlap under the specified allocation contract; scheduler survives worker failure without restart storm.

### S10 — NativeChatBot runtime projection

Read-only service state and policy-governed lifecycle actions exposed through existing deterministic routing/UI patterns.

Promotion criterion: UI renders happy/empty/pending/failure/constraint states and never becomes source of truth.

### S11 — Crash/restart recovery

Reconcile persisted records against host reality after supervisor restart.

Promotion criterion: reattach, orphan, stale record, identity conflict, and absent cases are all demonstrated.

### S12 — macOS launchd adapter

Optional host integration beneath the semantic supervisor for appropriate long-lived BRAINK-owned services.

Promotion criterion: semantic contract remains unchanged whether direct process or launchd-backed mechanism is used.

## Acceptance criteria

The initiative is accepted only when all of the following are demonstrated:

1. BRAINK enumerates service definitions without starting them.
2. Host survey is read-only.
3. Every discovered process/service receives an ownership classification.
4. Unknown/unowned/external processes default to non-mutation.
5. Persisted PIDs are identity-verified before mutation.
6. PID reuse cannot authorize a lifecycle action.
7. Service health is distinct from process existence.
8. Product readiness is distinct from service health.
9. Dependencies are explicit and blockers propagate without restart storms.
10. Services and jobs are distinct runtime types.
11. The BTC miner remains a bounded job.
12. A persistent scheduler can cancel superseded BTC work.
13. Bitcoin Core can be used externally without implicit adoption.
14. BRAINK-owned Bitcoin Core can be gracefully stopped under policy.
15. External Bitcoin Core cannot be automatically killed.
16. `ensure` and `start` are idempotent.
17. Restart attempts are bounded and suppressible.
18. Crash recovery reconciles persisted state against actual host state.
19. Lifecycle transitions carry immutable correlation IDs.
20. Lifecycle mutations generate evidence with before/action/result/after state.
21. Native UI state derives from supervisor state.
22. Native UI cannot confer process authority.
23. Shutdown respects ownership and persistence policy.
24. One service cannot acquire contradictory simultaneous BRAINK ownership records.
25. The same canonical observed state and policy produce the same lifecycle decision.
26. No implementation, test, commit, hash, or generated report is promoted to operational proof without execution evidence matching the claim.

## Non-goals

- Do not rewrite working BTC consensus code merely to conform to the new architecture.
- Do not make all BRAINK utilities daemons.
- Do not use an LLM as the lifecycle policy engine.
- Do not kill processes based on name matching alone.
- Do not equate a commit with completion.
- Do not treat a successful start syscall as proof of service health.
- Do not treat a running Bitcoin Core process as proof of mining readiness.

## Recommended next module

`task-creation`.

Create implementation tasks for S1 through S12, but implementation must begin with S1 and promotion must remain evidence-gated. S8 and S9 must not begin until the supervisor primitives they depend upon are tested.

## Checkpoint

- **Goal:** introduce a deterministic BRAINK service-control plane without destroying current runtime boundaries.
- **Current evidence:** BTC runtime and substrate exist; detached Bitcoin Core launch exists; bounded mining jobs exist; NativeChatBot and proof-bearing CLI exist; no surveyed general service supervisor exists.
- **Decision:** use a hybrid BRAINK semantic supervisor above platform-specific process/service adapters.
- **Preserved invariants:** working BTC consensus/RPC/mining code remains intact until evidence justifies change; repository mutation is not product proof; external processes are non-mutable without authority.
- **Risks:** process identity ambiguity, PID reuse, external-service interference, restart loops, duplicated daemons, stale mining jobs, UI/source-of-truth inversion.
- **Evidence required for promotion:** deterministic tests plus host-level read-back for each slice; lifecycle mutations require before/action/result/after evidence.
- **Blockers:** implementation has not yet been executed; host process state is not established by GitHub repository inspection alone.
- **Non-goals:** consensus rewrite, performance/profitability claims, arbitrary process control, production-readiness claims.
- **Next module:** task-creation, then bounded implementation beginning at S1.
