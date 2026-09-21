# Report 03 — ToT Safety, Distributed Coordinate Directory, Layer‑2 Reconciliation
## R3 observed engineering result — 21 September 2026

**Repository projection:** `aboudykeddeh276-stack/BRAINK`  
**Engineering status:** local independent-process layer `QUALIFIED_WITHIN_SCOPE`; physical/multi-host boundaries remain routed through explicit lifecycle states.

## 1. Ticket and method

This report is written from executed mechanics and receipts, not from a rearrangement of the architecture narrative.

The governing chain used in this pass was:

`research → analyse → derive → plan → architect → design → implement → test → falsify → readback → reconcile → document → qualify → deployment progression`

The predecessor repository already contained:

- `tot_safety.py`: fixed-membership majority/quorum kernel with per-position equivocation lock;
- `coordinate_directory.py`: committed-prefix directory replica and suffix replay;
- `layer2_reconciler.py`: desired/observed reconciliation with actuator receipts;
- Report‑03 unit/fault tests and a prior technical report.

The predecessor report itself identified the next missing architectures: durable consensus storage, real peer transport, independent processes, a safe membership-transition protocol, networked directory read semantics, and a physical L2 actuator boundary. This pass implemented and exercised that boundary rather than reproducing those files.

## 2. What was implemented

### 2.1 Durable ballot-based ToT kernel

The one-shot vote lock was replaced in the new layer by:

`PREPARE → DURABLE PROMISE → ACCEPT → QUORUM CERTIFICATE → COMMIT`

Each node owns:

- fsync-backed JSONL WAL;
- durable ballot promises;
- durable accepted values;
- ordered committed receipts;
- committed-root chain;
- KEX coordinate state machine;
- configuration epoch and optional joint configuration.

The important liveness rule is:

> If a higher-ballot proposer discovers a previously accepted value at the target index, it must complete the highest accepted value before it may place a different caller value at the next index.

That rule was not theoretical. The first multi-process campaign exposed the predecessor-style liveness defect: a minority vote/accept could strand the log position. The new ballot/prepare mechanism was introduced specifically because that execution falsified the one-shot locking design as a sufficient liveness mechanism.

### 2.2 Independent-process peer transport

Each node now runs as a separate OS process with:

- separate TCP listener;
- separate WAL file;
- HMAC-authenticated line-delimited JSON messages;
- `STATE`, `PREPARE`, `ACCEPT`, `COMMIT`, and `RECEIPTS_FROM` operations.

This is materially different from multiple objects in one process.

### 2.3 Distributed coordinate state

Directory transitions are consensus values. The committed state machine currently supports:

- `DIRECTORY_REGISTER`;
- `DIRECTORY_UPSERT`;
- `BARRIER`;
- `BEGIN_RECONFIG`;
- `FINALIZE_RECONFIG`.

A barrier read first commits a barrier through the active quorum and then reads the highest committed directory state from live replicas. Within the exercised single-host/multi-process environment, this supplies a consensus-ordered read point instead of treating a local object lookup as globally current.

### 2.4 Joint membership transition

Membership transition is now explicit:

1. old configuration commits `BEGIN_RECONFIG(new_members)`;
2. the system enters joint configuration `(old,new)`;
3. prepare/accept/commit require a majority of **both** old and new sets;
4. `FINALIZE_RECONFIG` commits under the joint rule;
5. the new set becomes authoritative at the next epoch.

The campaign exercised `A,B,C → A,B,D`, then stopped C and committed under `A,B,D`.

### 2.5 Layer‑2 actuator boundary

A concrete Linux `iproute2` bridge actuator adapter now exists for:

- bridge existence/create/up;
- interface attachment;
- operational command readback boundary.

The current execution container reported `iproute2=true`, `euid=0`, `ready=true`. A destructive host-network mutation was **not** executed because the run did not have a dedicated network namespace/bridge fixture. That mechanic is therefore `AWAITING_ISOLATED_TARGET_TESTING`, not “passed” and not “failed”.

## 3. Execution and falsification results

### 3.1 Focused unit suite

Observed:

`......s                                                                  [100%]
6 passed, 1 skipped in 4.64s`

The skipped test is the destructive Linux bridge mutation boundary.

### 3.2 Independent-process campaign

| Scenario | Observed state |
|---|---|
| multiprocess_initial_commit | `PASS` |
| multiprocess_barrier_read | `PASS` |
| process_crash_quorum_progress | `PASS` |
| process_restart_wal_suffix_catchup | `PASS` |
| quorum_loss_fail_closed | `PASS` |
| higher_ballot_after_quorum_loss | `PASS` |
| orphan_acceptance_recovery | `PASS` |
| joint_membership_transition | `PASS` |
| new_config_progress_without_removed_member | `PASS` |
| hmac_auth_negative_control | `PASS` |
| linux_bridge_actuator | `AWAITING_NONDESTRUCTIVE_TARGET` |

Summary: **10 PASS, 1 awaiting target-bound testing, 0 FAIL.**

### 3.3 Defects actually found during execution

Three important defects were found before the final green campaign:

1. **Receipt validation ordering.** A tampered already-committed receipt was initially reported as prefix divergence before its own receipt hash was validated. The validation order was corrected so malformed evidence is rejected as malformed evidence first.
2. **Process startup deadline.** A five-second child endpoint deadline was too aggressive for this execution environment. The orchestration timeout was corrected after observing actual child startup.
3. **One-shot vote-lock liveness.** A failed quorum attempt could leave a durable minority lock at the next index. Safety remained intact, but progress could deadlock. This directly caused the move to durable prepare/ballot/accept recovery.
4. **Restart replay path.** The first committed-process restart exposed a missing committed-WAL recovery path and the risk of appending configuration records while replaying configuration records. Recovery was separated from mutation and re-tested.

Those failures are retained as engineering evidence because they explain why the final implementation differs from the predecessor.

## 4. Standards / established architecture comparison

### Raft

Raft remains an established crash-fault replicated-log reference with leader election, persistence, log replication and membership-change machinery. The current ToT R3 layer now overlaps more materially with consensus practice: durable promises/accepted values, quorum intersection, committed log ordering, restart recovery, catch-up, and joint membership. It still does **not** implement Raft leader election, AppendEntries, randomized election timeouts, snapshot installation, or Raft's exact safety proof/model. It is therefore a separate crash-fault protocol experiment, not a Raft implementation.

### etcd

Current etcd v3 API documentation distinguishes consensus-backed linearizable reads from lower-latency serializable member-local reads. The R3 barrier read deliberately follows the stronger pattern: it establishes a consensus-ordered barrier before reading. However, BRAINK does not yet provide etcd-equivalent MVCC revisions, gRPC service semantics, leases, watches, compaction, transactional KV semantics, or a production linearizability proof.

### Kubernetes controller pattern

Kubernetes controllers continuously compare desired and current state and act to bring them closer. The BRAINK L2 reconciler already follows that controller separation. R3 adds a concrete Linux actuator boundary, but it still lacks a production watch/event source, controller ownership/finalizers, distributed work queue, and isolated privileged integration fixture.

### RFC 8342 NMDA

NMDA distinguishes intended configuration from applied/operational state. BRAINK's desired/observed reconciler and readback receipts align with that distinction. It still lacks YANG datastore semantics, origin metadata, NETCONF/RESTCONF bindings, and schema validation.

### RFC 8343 / RFC 8345

RFC 8343 provides a YANG model for interface configuration/operational state; RFC 8345 provides generic networks/nodes/links/termination points. BRAINK coordinates and manifestations can now be persisted and reconciled through consensus, but there is still no YANG projection binding a KEX coordinate to RFC 8345 topology identities or a manifestation to RFC 8343 interface objects.

### IEEE 802.1Q

IEEE 802.1Q-2022 is the active published bridging standard and an active revision PAR exists. The R3 Linux actuator is **not** an 802.1Q bridge implementation. It can invoke host bridge/interface operations; it does not implement MAC learning, FDB aging, VLAN forwarding/tagging semantics, STP/RSTP/MSTP, frame ingress/egress, or conformance behaviour.

## 5. What advanced

### ToT safety / liveness
**Advanced from:** fixed-membership one-shot vote locks in one-process tests.  
**Advanced to:** durable ballot promises/accepted values, higher-ballot orphan recovery, quorum certificates, restart recovery, independent TCP processes, joint membership transition.  
**Evidence state:** `QUALIFIED_WITHIN_SCOPE` for the exercised single-host multi-process crash-fault environment.

### Coordinate directory
**Advanced from:** direct replica method calls and suffix copying.  
**Advanced to:** coordinate transitions as consensus values, process-separated replicas, restart catch-up from committed receipts, consensus barrier before current-state read.  
**Evidence state:** `QUALIFIED_WITHIN_SCOPE` for the exercised environment.

### Layer‑2 reconciliation
**Advanced from:** abstract test actuator only.  
**Advanced to:** concrete Linux `iproute2` actuator adapter and explicit capability/readback boundary.  
**Evidence state:** `AWAITING_ISOLATED_TARGET_TESTING`.

### Membership
**Advanced from:** explicit `MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED`.  
**Advanced to:** tested joint old/new quorum transition and new-epoch progress.  
**Evidence state:** `QUALIFIED_WITHIN_SCOPE` for the exercised 3→3 membership replacement case.

## 6. What remains unproven — and the exact causal chain

### 6.1 Multi-host consensus
**Lifecycle:** `AWAITING_EXTERNAL_VERIFICATION`

**Why it remains unproven:** all independent processes ran on one host and loopback TCP. That proves process separation, socket transport, WAL separation and OS scheduling boundaries, but not LAN/WAN partitions, independent machine clocks, NIC loss, host reboot or cross-host discovery.

**Why that reason remains unaddressed:** this execution environment has no second controllable host attached to the test harness.

**Architecture still absent for closure:** host discovery/bootstrap, authenticated per-host identity rather than one shared HMAC secret, cross-host deployment supervisor, network partition/delay/duplication injector, independent clock/reboot receipts, and restoration/catch-up tests across machines.

### 6.2 Strong client linearizability proof
**Lifecycle:** `IN_DEVELOPMENT`

**Why:** the barrier read has the intended consensus ordering shape, but no formal history checker was run against concurrent independent clients.

**Why the why remains:** a history generator/checker and explicit client request IDs are not yet part of this module.

**Missing architecture:** concurrent client harness, operation histories, linearizability checker, request deduplication/idempotency ledger, timeout/unknown-result semantics.

### 6.3 Snapshot/compaction and bounded recovery
**Lifecycle:** `IN_DEVELOPMENT`

**Why:** catch-up replays the receipt suffix from JSONL WAL.

**Why the why remains:** no snapshot format or compaction boundary has yet been implemented.

**Missing architecture:** signed/checksummed snapshots, install-snapshot protocol, WAL truncation/retention policy, snapshot/WAL consistency proof, large-history recovery benchmark.

### 6.4 Per-member cryptographic identity
**Lifecycle:** `IN_DEVELOPMENT`

**Why:** transport authentication currently uses a cluster-shared HMAC secret.

**Why the why remains:** the target trust model for this pass is explicitly non-Byzantine.

**Missing architecture:** member-specific keys/certificates, key rotation, replay nonce/window, authorization policy, compromise/revocation recovery. Full Byzantine tolerance is `CANNOT_BE_DEVELOPED_WITHIN_CURRENT_NON_BYZANTINE_TRUST_MODEL` unless that trust model is deliberately changed.

### 6.5 Physical L2 mutation
**Lifecycle:** `AWAITING_ISOLATED_TARGET_TESTING`

**Why:** the host reports privileged `iproute2`, but this run did not have a disposable namespace/veth/bridge fixture.

**Why the why remains:** mutating the execution host's live networking would be poor falsification practice because failure could destroy the test/control path.

**Missing architecture:** isolated Linux network namespace or disposable VM, veth fixture, before/after link/FDB/VLAN readback, rollback, failure injection and repeated reconciliation.

### 6.6 IEEE 802.1Q semantics
**Lifecycle:** `IN_DEVELOPMENT`

**Why:** the current actuator controls bridge objects; it does not implement an Ethernet bridge dataplane.

**Why the why remains:** a controller/actuator and an 802.1Q forwarding implementation are different architectures.

**Missing architecture:** frame model, ingress/egress dataplane, MAC learning/FDB, VLAN membership/tagging, loop prevention/STP family selection, multicast/broadcast semantics, counters, conformance vectors.

### 6.7 Formal safety verification
**Lifecycle:** `IN_DEVELOPMENT`

**Why:** execution/fault campaigns test sampled traces.

**Why the why remains:** no executable formal model has been bound to the R3 ballot/joint-membership state machine.

**Missing architecture:** TLA+/PlusCal (or equivalent) state model, invariants, liveness properties, model-check bounds, counterexample preservation and trace-to-code conformance mapping.

### 6.8 Scale/SLO qualification
**Lifecycle:** `AWAITING_WORKLOAD_AND_SLO_BINDING`

**Why:** this pass targeted correctness/fault boundaries, not estate-scale performance.

**Why the why remains:** no accepted target workload, latency objective, recovery-time objective or directory cardinality target was supplied to this component.

**Missing architecture:** workload generator, benchmark corpus, metrics, profiling, batching/backpressure policy, large-directory persistence strategy, error budgets and repeatable scale environment.

## 7. Why the remaining deficiencies cannot be closed by prose

| Deficiency | Architecture that must exist |
|---|---|
| Multi-host qualification | cross-host deployment + network chaos + host identity |
| Client linearizability | concurrent history generator/checker + idempotency |
| Bounded recovery | snapshots + compaction + install protocol |
| Strong peer identity | per-member cryptographic credentials/rotation |
| Physical L2 qualification | isolated namespace/VM actuator fixture |
| 802.1Q claim | actual Ethernet/VLAN bridge dataplane |
| Exhaustive safety claim | executable formal specification/model checker |
| Production scale claim | workload/SLO/benchmark/telemetry infrastructure |

These are implementation classes, not missing paragraphs.

## 8. Evidence fingerprints

- `report03_mesh.py`: `7f9cc97ad16e874fe26c8ba0507c42b30f2c5d2f496ba0a8f1b919d1ac091a63`
- `test_report03_mesh.py`: `a1c15852503dcd58dfd04f65f57ced4560a9795e527c8aa80b769c54ce2e4b53`
- `run_multiprocess_fault_campaign.py`: `ef1d124caa283994fff793dbdce0e55214735edd014a26aca591762731152e5a`
- `node_runner.py`: `4235e79c4ce86b37af91d2dd1f322a1ca325e39ac29983d3ac02e1523f04fb78`

Machine-readable receipt: `REPORT03_ENGINEERING_FAULT_RECEIPTS_R3.json`.

## 9. Qualification verdict

The R3 layer is qualified **only** for the properties directly exercised:

- durable promise/accept/commit state on fsync-backed WAL;
- independent local OS-process TCP peers;
- crash-fault quorum progress;
- fail-closed quorum loss;
- restart/catch-up to identical committed root;
- orphan accepted-value recovery by higher ballot;
- joint old/new membership transition;
- new-configuration progress after member removal;
- HMAC authentication rejection;
- consensus-ordered coordinate barrier read.

The following remain routed rather than collapsed into a negative verdict:

- physical L2 mutation → `AWAITING_ISOLATED_TARGET_TESTING`;
- cross-host execution → `AWAITING_EXTERNAL_VERIFICATION`;
- formal verification → `IN_DEVELOPMENT`;
- production scale → `AWAITING_WORKLOAD_AND_SLO_BINDING`.

That is the actual observed boundary of this pass.