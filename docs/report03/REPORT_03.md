# REPORT 03 — ToT Safety Kernel, Distributed Coordinate Directory, and Layer‑2 Reconciliation Engineering

**Date:** 2026-09-21  
**Repository target:** `aboudykeddeh276-stack/BRAINK`  
**Scope:** implementation, execution, falsification, evidence capture, standards comparison, and deficiency analysis.  
**Evidence rule:** this report distinguishes implemented code, locally executed evidence, repository deployment state, and still-unproven claims. No item is promoted beyond the strongest observed evidence.

## 1. Executive result

Report 03 advances three previously weak areas from architectural declaration into executable engineering:

1. **ToT safety kernel:** upgraded from bare majority counting to a fixed-membership, non-Byzantine quorum log with membership hashing, per-voter equivocation locks, quorum certificates, receipt hashes, deterministic root chaining, receipt verification, and crash-recovery replay.
2. **Distributed coordinate directory:** upgraded from a single in-memory table that trusted committed-looking inputs into deterministic replicas that can verify ToT receipts, enforce contiguous committed-prefix replay, reject stale manifestation generations, synchronize from a peer replica, and detect divergent receipt histories.
3. **Layer‑2 reconciler:** upgraded from a pure planner into an executable desired/observed controller with deterministic idempotency keys, actuator calls, action receipts, post-action readback state, partial-failure receipts, and explicit convergence status.

The observed local test result is **10/10 passing tests**. The separate deterministic fault campaign produced **8/8 passing falsification scenarios**. In that campaign, **498/498 conflicting quorum attempts were blocked**, **100/100 transient-fault Layer‑2 runs converged**, and those runs generated **158 partial-failure receipts** before convergence. A persistent actuator failure remained non-converged and generated an explicit failure receipt. The system also deliberately rejects membership reconfiguration because no safe membership-transition protocol has yet been implemented.

These results prove substantially more than the earlier code, but they do **not** prove a production distributed system, Byzantine fault tolerance, physical Layer‑2 switching, autonomous indefinite mesh survival, or linearizable multi-process service under real network faults. Those claims remain unproven for explicit architectural reasons documented below.

## 2. What existed before this pass

The pre-pass repository already contained files named `tot_safety.py`, `coordinate_directory.py`, `layer2_reconciler.py`, and `test_report03_engineering.py`. Naming existed; several engineering guarantees did not.

### 2.1 Pre-pass ToT kernel

The existing kernel provided:

- fixed member list;
- majority quorum calculation;
- sequential transition indexes;
- epoch checking;
- root chaining;
- duplicate voter deduplication;
- commit receipts;
- deterministic replay-root calculation.

It did not provide:

- a per-voter lock preventing one member from voting for two conflicting transitions at the same epoch/index;
- an independently verifiable quorum certificate;
- a membership hash bound into the proposal/vote/receipt;
- receipt-integrity verification independent of the committing kernel object;
- deterministic crash recovery from transition + receipt sequences;
- a safe membership-change protocol;
- durable WAL/fsync semantics;
- transport or leader election;
- cryptographic member signatures.

Therefore it was a useful deterministic majority-log prototype, but not yet a defensible distributed safety kernel.

### 2.2 Pre-pass coordinate directory

The existing directory provided:

- coordinate registration;
- manifestation upsert/detach;
- generation checking;
- sequential apply index;
- deterministic directory root.

It did not independently validate quorum certificates, synchronize replicas, detect a divergent common prefix, or define any network exchange/anti-entropy mechanism. It was deterministic state-machine application, not yet a distributed directory protocol.

### 2.3 Pre-pass Layer‑2 reconciler

The existing reconciler computed `MATERIALISE`, `REPLACE`, and `DETACH` actions and could determine whether desired and observed maps matched. It had no actuator interface, no execution loop, no idempotency token, no readback receipt, no partial-failure state, and no proof that an action changed anything outside Python memory.

That distinction matters. A planner is not an actuator and an intended state is not an observed operational state.

## 3. Engineering layer built in this pass

## 3.1 ToT safety kernel R1

The upgraded kernel retains the existing project invariant that zero is not a live address/state value, while adding a fixed-membership safety envelope.

### 3.1.1 Membership-bound transition identity

Each transition now carries:

- log `index`;
- `epoch`;
- member `actor`;
- `command` and payload;
- `previous_root`;
- `membership_hash`.

`membership_hash` is the SHA-256 hash of the sorted fixed member set and epoch. A transition from another membership/epoch therefore cannot silently enter the current log.

### 3.1.2 Per-voter equivocation lock

For each `(epoch, index, voter)` the kernel records the digest that member voted for. A second vote by the same member for another digest at the same position raises:

`VOTER_EQUIVOCATION`

This is the critical new safety mechanism behind the conflicting-quorum falsification result. In a majority quorum, two majorities intersect. Under the non-Byzantine assumption that a member cannot successfully vote twice at the same log position, two conflicting majority certificates cannot both be constructed through this API.

This is **not** Byzantine tolerance. A compromised process able to fabricate voter identities or bypass the kernel can violate the assumption because votes are not cryptographically signed by independently held member keys.

### 3.1.3 Quorum certificate

A commit now materializes a `QuorumCertificate` containing:

- epoch;
- index;
- transition digest;
- membership hash;
- sorted voter list;
- certificate hash.

The certificate can be verified independently against a member list.

### 3.1.4 Commit receipt

The commit receipt now binds:

- transition digest;
- previous committed root;
- new committed root;
- membership hash;
- quorum certificate;
- receipt hash.

The committed root is chained from:

`previous_root + transition_digest + quorum_certificate_hash`

Tampering with the receipt hash or certificate is therefore detected by the verifier.

### 3.1.5 Recovery

`recover()` reconstructs the kernel from a transition/receipt sequence while checking:

- equal sequence lengths;
- contiguous indices;
- previous-root continuity;
- receipt/certificate validity;
- membership hash.

This provides deterministic logical crash recovery from already-durable records. It does **not** itself make those records durable on disk.

### 3.1.6 Explicit unsupported operation

`reconfigure_membership()` fails closed with:

`MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED`

This is intentional evidence, not an omission hidden by an architecture diagram. Safe membership transition requires a separate protocol.

## 3.2 Distributed Coordinate Directory R1

The directory is now a replicated deterministic state machine over committed ToT entries.

### 3.2.1 Receipt admission

When configured with the membership list, each applied transition must pass `ToTSafetyKernel.verify_receipt()` before changing directory state.

The directory therefore no longer assumes that a `CommitReceipt` object is trustworthy merely because it has the right fields.

### 3.2.2 Prefix safety

A replica only applies `applied_index + 1`. Gaps fail with:

`DIRECTORY_REPLAY_GAP`

Receipt roots must also form a continuous commit chain. Divergent commit ancestry fails with:

`DIRECTORY_COMMIT_CHAIN_DIVERGENCE`

### 3.2.3 Generation safety

Manifestation generations must strictly increase. Replaying or overwriting the same manifestation at an equal or older generation fails with:

`STALE_GENERATION`

This is stricter than the previous `< old_generation` test and prevents same-generation conflicting overwrite.

### 3.2.4 Replica synchronization

`sync_from()` compares all common receipt hashes before accepting the missing suffix. If a supposedly common prefix differs, synchronization fails with:

`DIRECTORY_REPLICA_DIVERGENCE`

A clean suffix can be replayed and both replicas converge on the same deterministic directory root.

This advances the directory from a local map toward a distributed directory model, but the sync mechanism is currently an in-process API. There is no transport, persistent replicated log, peer discovery, rate control, or network partition recovery service yet.

## 3.3 Layer‑2 Reconciler R1

The reconciler now implements a complete local control-loop transaction rather than only a plan.

### 3.3.1 Desired / observed split

The reconciler consumes distinct maps for:

- desired manifestation state;
- observed manifestation state.

This prevents intended configuration from being treated as proof of applied operational state.

### 3.3.2 Deterministic plan

The planner still emits:

- `MATERIALISE` when desired state is absent;
- `REPLACE` when endpoint/generation/state differs;
- `DETACH` when observed state has no desired object.

An observed generation ahead of desired fails closed because blindly replacing newer observed state with an older intent would be unsafe.

### 3.3.3 Actuator interface

`reconcile_once()` now calls an actuator for each action. The reconciler itself remains transport/device agnostic.

### 3.3.4 Idempotency key

Every action receives a deterministic idempotency key derived from:

- reconcile identity;
- desired root;
- pre-action observed root;
- canonical action content.

An actuator can therefore deduplicate retries.

### 3.3.5 Readback and receipts

Every action returns an `ObservedManifestation` or raises an error. The reconciler records `ActionReceipt` objects and returns a `ReconcileReceipt` containing:

- reconcile ID;
- desired root;
- observed-before root;
- observed-after root;
- action receipts;
- convergence flag;
- status;
- receipt hash.

A failed actuator produces `PARTIAL_FAILURE`; it does not produce a synthetic converged state.

## 4. Execution evidence

### 4.1 Deterministic unit suite

Command executed locally against the exact files later prepared for repository deployment:

`PYTHONPATH=/mnt/data/report03_work pytest -q /mnt/data/report03_work/tests/test_report03_engineering.py`

Observed result:

`10 passed in 0.14s`

### 4.2 Fault campaign

The fault harness used deterministic random seed `297`.

Observed summary:

- scenarios: 8;
- passed: 8;
- failed: 0.

Detailed observations:

| Scenario | Observed result |
|---|---|
| Conflicting quorum attempts | 498/498 blocked by voter equivocation detection |
| Tampered receipt hash | rejected with `RECEIPT_HASH_MISMATCH` |
| Recovery sequence truncation | rejected with `RECOVERY_LENGTH_MISMATCH` |
| Coordinate replica divergent prefix | rejected with `DIRECTORY_REPLICA_DIVERGENCE` |
| Stale coordinate manifestation generation | rejected with `STALE_GENERATION` |
| Transient L2 actuator faults | 100/100 runs converged within 12 rounds |
| Transient-fault failure evidence | 158 `PARTIAL_FAILURE` receipts observed before eventual convergence |
| Persistent L2 actuator failure | remained non-converged with explicit failed action receipt |
| Membership reconfiguration | rejected with `MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED` |

The campaign does not prove absence of all defects. It demonstrates that the listed fault classes were exercised and the observed result matched the specified failure/convergence policy.

## 5. Evidence receipts and code fingerprints

SHA-256 fingerprints of the locally executed engineering files:

- `tot_safety.py`: `6b4ca578ea8598bf494a5adb7aecb109f395901b7f35700b75f574ee1de1965b`
- `coordinate_directory.py`: `ecaf5a6e2462dd82a53f4e3dd64076741b7fd91b977d2cf29888f3d5a7d6647d`
- `layer2_reconciler.py`: `b39201bcdcd62c88fd8d626cf7ecae6249a18e2f809865f4e565a4e55ebd22de`
- `test_report03_engineering.py`: `d4d91590f4d13837fe03c6ab0e618931ab8f80d09071e71bd67bfafc080cc811`
- `run_report03_fault_campaign.py`: `bbdca6e90a27ec862a3d4e456e1577991a37bd3af830a5adbf6c45b299fbc087`
- fault receipt file: `96fd065d84b58aaa9302c9b79a942d07cd28a8adc26882c2a2dd499a455eb937`

The machine-readable fault receipt is deployed with the code so the report is not the only surviving evidence.

## 6. Current standards / established architecture comparison

This section compares behaviour, not branding.

### 6.1 Raft and etcd

Raft is an established crash-fault consensus design using leader election, replicated logs, safety constraints, and explicit membership-change algorithms. Its published reference material includes a formal TLA+ specification and membership-change work. etcd uses Raft and documents linearizable operations that pass through consensus.

The ToT kernel now shares several **safety primitives** with crash-fault replicated logs: epochs, majority quorum, ordered log positions, previous-root chaining, conflicting-vote rejection, and replay validation. It does **not** yet provide Raft-equivalent service semantics because it lacks leader election, AppendEntries-style transport, commit-index dissemination, follower catch-up over a network, persistent term/vote WAL, snapshot installation, and safe membership transition. It therefore must not be labelled a Raft replacement or a linearizable distributed database.

### 6.2 Kubernetes controller pattern

Kubernetes describes controllers as control loops that observe current state and move it toward desired state. The new L2 reconciler now follows this established control-loop separation materially: desired and observed state are distinct, actions are generated from drift, action failure is recorded, and reconciliation can repeat until convergence.

What is not yet present is a watch/event source, persistent resource versioning, controller ownership/finalizers, distributed work queue, lease/leader election, or production actuator bindings.

### 6.3 IETF NMDA (RFC 8342)

RFC 8342 distinguishes intended configuration from operational state and specifically allows clients to determine how much intended configuration is actually in use by comparing against operational state. This directly supports the decision in Report 03 not to treat desired manifestation state as proof of applied state.

The current reconciler has an intended/observed distinction but does not implement NETCONF/RESTCONF/NMDA datastores, origin metadata, candidate/running/intended stores, or YANG validation.

### 6.4 IETF interface and topology models (RFC 8343, RFC 8345)

RFC 8343 defines common configuration and operational state for interfaces. RFC 8345 defines a generic topology model with networks, nodes, links, termination points, and supporting-layer relationships.

BRAINK's coordinate directory and node/edge work overlaps conceptually with inventory/topology representation, but no YANG mapping currently exists. A KEX coordinate or manifestation is therefore not yet interoperable as an RFC 8345 topology node/termination point, and a Layer‑2 manifestation endpoint is not yet exposed as an RFC 8343 interface object.

### 6.5 IEEE 802.1Q

IEEE 802.1Q-2022 remains the active published standard for bridges and bridged networks, while a revision project is active. It covers MAC/VLAN bridging behaviour, management, protocols, and algorithms.

The component named `Layer2Reconciler` in Report 03 is **not an IEEE 802.1Q bridge implementation**. It reconciles abstract manifestations. It does not perform MAC learning, frame forwarding, VLAN tagging, spanning-tree behaviour, forwarding database aging, Ethernet frame ingress/egress, or line-rate switching. Those remain separate dataplane architectures.

## 7. What advanced

### 7.1 ToT

Advanced from “majority votes were counted” to “conflicting per-position votes are locked, certified, independently verifiable, chain-bound and recoverable.”

Evidence level: **EXECUTED LOCALLY / FAULT-INJECTED**.

### 7.2 Coordinate directory

Advanced from “one deterministic in-memory directory” to “replicas can verify committed input, compare common history, replay a committed suffix, detect divergence, and converge to the same root.”

Evidence level: **EXECUTED LOCALLY across independent Python directory objects**.

### 7.3 Layer‑2 reconciler

Advanced from “planner” to “controller transaction with actuator invocation, deterministic retry identity, readback, partial failure and convergence receipt.”

Evidence level: **EXECUTED LOCALLY with fault-injected fake actuators**.

### 7.4 Evidence discipline

Advanced because failure is now an explicit state in the receipts. A failed actuator or unsupported membership transition cannot be linguistically promoted into success by the report.

## 8. What remains unproven

The following claims remain unproven after this pass.

### 8.1 Multi-host distributed consensus

**Unproven:** that independent hosts can safely commit under process crashes, delay, duplication, reordering, network partitions, restart, and concurrent proposals.

**Why unproven:** tests executed multiple kernel/directory objects in one local process and did not exercise a real transport, disk recovery boundary, scheduler, socket loss, machine reboot, or independent clocks.

**Why that reason remains unaddressed:** the repository still lacks a ToT peer transport and durable consensus service joining the kernel to host processes.

**Missing architecture:** peer RPC/message transport, persistent WAL, durable vote/term storage, leader/proposer selection or equivalent serialization mechanism, catch-up/snapshot protocol, process supervisor, network fault harness across real processes.

### 8.2 Safe dynamic membership

**Unproven and currently unsupported:** changing the voting membership while preserving safety.

**Why unproven:** the code deliberately raises `MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED`.

**Why the underlying problem remains:** a majority rule over one member set cannot simply switch to another set without defining the transition overlap and commit rules. Naive reconfiguration can create two valid majorities on different configurations.

**Missing architecture:** joint membership/joint consensus or an equivalent configuration-epoch protocol, configuration certificates, admission/removal proof, recovery rules, and tests across overlapping/non-overlapping sets.

### 8.3 Byzantine fault tolerance

**Unproven:** tolerance of malicious members, forged votes, equivocation outside the kernel API, corrupted messages, or compromised keys.

**Why unproven:** votes are logical Python objects, not independently signed statements. The safety result assumes members use the kernel and do not forge another member.

**Why still unaddressed:** the project directive for this layer is non-Byzantine, so implementing PBFT/HotStuff-style machinery would be a different trust model rather than “finishing” this one.

**Missing architecture if Byzantine tolerance is later required:** per-member cryptographic identity, signed votes, replay protection/nonces, authenticated transport, Byzantine quorum thresholds, view change, evidence/slashing or quarantine semantics, key rotation and compromise recovery.

### 8.4 Linearizable distributed coordinate service

**Unproven:** that arbitrary clients receive linearizable reads/writes from a live multi-host coordinate service.

**Why unproven:** replicas currently replay committed entries through direct method calls. There is no client-serving consistency protocol, read-index/barrier, lease, or quorum read path.

**Why still unaddressed:** the directory is presently a state machine, not a distributed database service.

**Missing architecture:** network-facing directory service, authoritative commit-index propagation, consistent-read protocol, durable persistence, snapshot/compaction, backpressure, authentication/authorization, client request idempotency and stale-read policy.

### 8.5 Long-term coordinate retention when every manifestation disappears

**Unproven:** the stronger project proposition that a virtual coordinate/node can never disappear once sufficiently replicated.

**Why unproven:** Report 03 preserves coordinate identity when a manifestation is detached, but all directory replicas are still ordinary process memory. If all copies disappear, there is no surviving state.

**Why the reason remains unaddressed:** logical persistence and physical persistence were previously conflated. A logical identifier can outlive a manifestation only while at least one durable authoritative record survives or can be reconstructed from another durable proof source.

**Missing architecture:** durable multi-failure-domain storage, erasure/replication policy, peer rehydration protocol, discovery/bootstrap anchors, archival proof chain, disaster recovery, independent restoration tests and quantified durability assumptions.

### 8.6 Physical Layer‑2 actuation

**Unproven:** that reconciliation changes a real Ethernet bridge, VLAN, host interface, virtual switch, or NIC.

**Why unproven:** the executed actuator was a fault-injected in-memory test actuator.

**Why still unaddressed:** there is no production adapter connecting `Action` to Linux rtnetlink/bridge, Open vSwitch, eBPF, macOS networking APIs, hardware switch API, or another actual carrier.

**Missing architecture:** concrete actuator driver, privilege/authority boundary, interface discovery, before/after operational readback, rollback semantics, bridge/VLAN/FDB model, driver-specific error taxonomy and isolated integration test environment.

### 8.7 IEEE 802.1Q bridge semantics

**Unproven:** MAC/VLAN bridge conformance.

**Why unproven:** the reconciler models manifestation attachment, not frames, forwarding databases, VLANs or spanning trees.

**Why still unaddressed:** control-plane convergence and bridge dataplane behaviour are distinct architectures and the latter has not been built in this module.

**Missing architecture:** frame model, MAC learning/FDB, VLAN membership/tagging, STP/RSTP/MSTP or chosen loop-prevention method, port state machine, multicast/broadcast behaviour, MTU/frame validation, actual packet I/O and conformance testing.

### 8.8 Formal safety proof

**Unproven:** mathematical proof that every reachable implementation state satisfies the intended safety invariants.

**Why unproven:** randomized and unit tests establish sampled behaviours, not exhaustive state-space proof.

**Why still unaddressed:** there is no TLA+/PlusCal, Alloy, Coq/Lean or equivalent executable formal specification of ToT + directory + reconfiguration.

**Missing architecture:** formal state model, invariants, temporal properties, model checker configuration, counterexample corpus and trace-to-implementation conformance discipline.

### 8.9 Performance and scale

**Unproven:** latency, throughput, memory growth, directory size limits, reconciliation storm behaviour and recovery time at intended estate scale.

**Why unproven:** Report 03 is a correctness/falsification pass, not a benchmark on production-scale nodes.

**Why still unaddressed:** no workload model or target SLO has been bound to these components.

**Missing architecture:** benchmark harness, realistic workload generator, profiling, persistence compaction, batching, flow control, metrics, SLO/error budgets and scale test environments.

## 9. Why the unaddressed unproven concepts remain

The remaining deficiencies are not one undifferentiated bucket called “more testing.” They persist because entire architecture classes are absent:

| Remaining claim | Architecture class absent |
|---|---|
| Safe live multi-host ToT | distributed transport + durable consensus runtime |
| Dynamic voting membership | membership-transition protocol |
| Byzantine safety | cryptographic BFT identity/consensus |
| Linearizable directory API | distributed database/service consistency layer |
| Survive total local node loss | durable cross-failure-domain persistence + bootstrap/rehydration |
| Real L2 mutation | privileged network actuator/driver layer |
| 802.1Q bridge behaviour | Ethernet/VLAN/STP dataplane |
| Exhaustive correctness | formal specification/model checking |
| Production-scale suitability | performance/SLO/chaos infrastructure |

These cannot be completed by adding more fields to JSON, more workbook tabs, or more prose. Each requires a running mechanism with its own evidence boundary.

## 10. Exact next engineering requirements

The next defensible engineering sequence, derived from the failed/unproven boundaries, is:

1. Persist ToT transitions, vote locks and receipts in an fsync-backed WAL and prove restart recovery after kill -9 at every write boundary.
2. Add a real peer transport using authenticated local/multi-host channels and run three independent OS processes under packet loss, delay, duplication and partition.
3. Design and implement membership transition before allowing runtime host admission/removal to alter voting membership.
4. Expose the coordinate directory as a service with explicit linearizable/stale-read modes, durable snapshots and client idempotency.
5. Bind the L2 actuator to one real carrier first, preferably an isolated Linux network namespace/bridge or equivalent controlled target, then read operational state back independently.
6. Add YANG/RFC 8343/8345 projection if external management interoperability is a requirement.
7. Implement an actual bridging dataplane only if the intended product claim is “network bridge,” rather than “L2 manifestation reconciler.”
8. Write a formal model of fixed-membership ToT before enlarging the consensus feature set; then model membership transition separately.
9. Build a multi-process chaos harness and collect durability, recovery, convergence and split-brain receipts under real scheduler/network faults.
10. Define production scale/SLO targets before making performance claims.

## 11. Current evidence classification

| Component / claim | Current evidence |
|---|---|
| Fixed-membership ToT deterministic commit | EXECUTED / VERIFIED LOCALLY |
| Per-voter equivocation rejection | EXECUTED / FAULT-INJECTED |
| Quorum certificate tamper detection | EXECUTED / FAULT-INJECTED |
| Crash replay from already-present records | EXECUTED LOCALLY |
| Dynamic membership safety | UNIMPLEMENTED / FAIL-CLOSED |
| Byzantine safety | NOT CLAIMED / UNPROVEN |
| Directory committed-prefix replay | EXECUTED / VERIFIED LOCALLY |
| Directory replica suffix sync | EXECUTED / VERIFIED LOCALLY |
| Directory network anti-entropy | ABSENT |
| Directory linearizable network service | ABSENT |
| L2 desired/observed planning | EXECUTED |
| L2 actuator/readback receipts | EXECUTED WITH TEST ACTUATOR |
| L2 transient failure recovery | FAULT-INJECTED: 100/100 CONVERGED |
| L2 persistent failure handling | FAULT-INJECTED: FAIL-CLOSED |
| Physical bridge/NIC mutation | UNPROVEN |
| IEEE 802.1Q conformance | NOT IMPLEMENTED |
| Multi-host process/network chaos | NOT YET EXECUTED |
| Formal verification | ABSENT |

## 12. Standards/reference sources used for comparison

- Raft consensus project and paper index: https://raft.github.io/
- etcd API guarantees / linearizability: https://etcd.io/docs/v3.4/learning/api_guarantees/
- Kubernetes controller pattern: https://kubernetes.io/docs/concepts/architecture/controller/
- RFC 8342, Network Management Datastore Architecture: https://www.rfc-editor.org/info/rfc8342/
- RFC 8343, YANG Data Model for Interface Management: https://www.rfc-editor.org/info/rfc8343/
- RFC 8345, YANG Data Model for Network Topologies: https://www.rfc-editor.org/info/rfc8345/
- IEEE 802.1Q-2022, Bridges and Bridged Networks, active published standard: https://standards.ieee.org/ieee/802.1Q/10323/
- IEEE P802.1Q revision project: https://standards.ieee.org/ieee/802.1Q/11285/

## 13. Conclusion

Report 03 does not conclude that the larger mesh thesis is proven. It concludes something narrower and more useful: the ToT/directory/reconciler layer has moved from mostly declarative or single-process logic to an executable fixed-membership safety kernel, verifiable replicated directory state machine, and receipted reconciliation loop with demonstrated fail-closed behaviour under the tested fault classes.

The falsification pass also identified a hard line. The remaining claims are blocked by missing mechanisms, not by missing descriptions. Dynamic membership, independent-host consensus, durable cross-host recovery, a linearizable directory service, physical Layer‑2 actuation, IEEE bridging semantics, formal verification, and scale evidence are still absent. Those absences are now explicit enough to engineer instead of being buried under architectural vocabulary.