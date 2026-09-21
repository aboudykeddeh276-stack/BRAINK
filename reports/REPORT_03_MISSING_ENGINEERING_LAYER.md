# REPORT 03 — Missing Engineering Layer

## ToT Safety Kernel, Distributed Coordinate Directory, Layer-2 Reconciler, Falsification, Evidence, and Deficiency Closure

**Authority context:** BRAINK × KEX × IL-LLM × Observer²  
**Date:** 2026-09-21  
**Observed execution receipt root:** `65b449db4287472bec35d539cf9a8f67fc8122edfa3ff8f7f2f092a210dd4d03`

## 1. Executive result

Report 03 was produced after implementation and execution, not before it.

The missing layer that was built contains:

1. a ToT safety kernel for transitive node-to-node proposals;
2. a distributed coordinate directory with versioned roots, ancestry, CAS mutation and fork detection;
3. a Layer-2 desired/observed reconciler that fails immutable identity drift, requires ToT for mutable drift, commits with CAS, and verifies readback;
4. fault-injection and negative tests;
5. evidence receipts and a bounded benchmark;
6. a current standards comparison;
7. an explicit deficiency map separating what advanced from what remains unproven.

Observed result: **24/24 tests passed** after one real defect was found and corrected.

The integration run emitted a **14-packet evidence chain with zero verification failures**. A 32-way collision against one logical coordinate produced exactly **1 committed owner and 31 blocks**. Restart reproduced the directory and ToT heads. Directory tampering was rejected. Invalid ToT attestation failed without changing target directory state.

The first replica-fork test failed against the initial implementation. Two replicas produced different roots at the same sequence from the same parent. The original merge code treated the remote state as stale. That rule was unsafe. It was replaced with:

- same sequence + same root -> identical;
- same sequence + different root -> `CONCURRENT_FORK_SAME_SEQUENCE`;
- lower sequence -> stale;
- higher sequence -> accepted only when ancestry proves succession.

The strongest bounded conclusion is:

> Report 03 proves a single-host executable safety/directory/reconciliation layer with deterministic conflict detection, replay protection, explicit fault states, restart persistence, evidence-chain integration, and local concurrency behavior. It does not prove multi-host consensus, linearizability, Byzantine fault tolerance, production identity infrastructure, secure remote transport, physical power-loss durability, connected-service writer failover, or deployed R40 execution.

## 2. Resident baseline

The accessible runtime estate already contained BRAINK V9 with a transactional SQLite/WAL `PacketService`, semantic hash chaining, logical sequencing and a chain verifier. R40 already separated logical identity from carrier endpoints, kept mutation under BRAINK/KEX and Observer² authority, required capability/authority resolution before side effects, and required readback before promotion.

No resident ToT safety kernel or distributed logical coordinate-directory owner was discovered. Report 03 therefore fills those edges without creating another BRAINK operator, another IL-LLM, another capability registry, another node constructor, or another global ledger.

## 3. ToT safety kernel

The executable ToT semantics are now precise. A transition proposal binds:

- source node;
- target node;
- source state root;
- expected target coordinate-entry root;
- logical source sequence;
- operation;
- payload root;
- authority;
- hop path;
- external attestation.

The kernel verifies source/target directory identity, source-state freshness, target-revision freshness, authority, source `tot.propose`, target operation capability, path origin, bounded hops, cycle absence, target-not-already-visited, source sequence monotonicity, replay absence, and the external verifier result.

Only after all checks pass does the kernel persist replay state and append evidence.

The kernel does not own credentials and does not mutate runtime state. The observed tests used HMAC-SHA256 only as a falsifiable verifier adapter. That is not a production credential architecture.

## 4. Distributed coordinate directory

A coordinate entry contains:

- node ID;
- non-zero logical coordinate;
- generation;
- sequence;
- logical identity;
- state root;
- template root;
- endpoints;
- capabilities;
- authority;
- health;
- parent entry root;
- tombstone state.

The coordinate is logical identity state. Carrier endpoints are mutable.

Every entry has a SHA-256 entry root. Updates require the current root and extend per-node ancestry. Stale CAS cannot overwrite current state.

Replica merge is deliberately conservative:

- identical root -> no-op;
- lower sequence -> stale;
- equal sequence with unequal root -> fork conflict;
- higher sequence with provable ancestry -> apply successor chain;
- higher sequence without ancestry -> conflict.

This is distributed replica reconciliation, **not consensus**.

Persistence uses temp write, flush, file fsync, atomic replace and parent-directory fsync. Injected persistence failure rolled back the candidate. Restart readback restored the prior committed state.

## 5. Layer-2 reconciler

Layer-2 compares desired identity with observed execution state.

Immutable fields:

- node ID;
- coordinate;
- logical identity;
- template root;
- authority.

Any immutable drift is `FAILED:IDENTITY_DRIFT`.

Mutable fields:

- state root;
- endpoints;
- capabilities;
- health.

Outcomes:

- `REGISTERED`: locally verified new node admitted through bootstrap authority;
- `FIXED_POINT`: observed and directory state agree; quiesce;
- `RECONCILED`: exact drift is bound to a ToT proposal, authorized, CAS-committed and read back.

Mutable drift without ToT is `BLOCKED:TOT_PROOF_REQUIRED`. A proposal not bound to the observed payload/current target root is `FAILED:TOT_PROPOSAL_BINDING`.

The executed reconciler changes coordinate control state from observed execution evidence. It does not bypass R40 Observer²/capability gates to actuate arbitrary processes.

## 6. Tests and fault injection

Final result: **24 passed**.

Coverage includes:

- deterministic canonical hashing;
- directory registration/restart;
- zero-coordinate rejection;
- coordinate collision;
- coordinate immutability;
- stale CAS rejection;
- persistence-failure rollback;
- corruption detection;
- concurrent coordinate claims;
- successor merge;
- fork detection;
- valid ToT authorization;
- bad attestation;
- stale source state;
- replay/stale sequence;
- cycles;
- hop limits;
- ToT state tamper detection;
- Layer-2 bootstrap;
- fixed point;
- immutable identity drift;
- missing observation;
- ToT requirement for mutable drift;
- authorized drift reconciliation;
- bad ToT proposal binding;
- evidence-ledger tamper detection.

### Observed integration events

| Case | Result |
|---|---|
| bootstrap proposer | COMMITTED |
| Layer-2 bootstrap | REGISTERED |
| repeat reconciliation | FIXED_POINT |
| authorized mutable drift | RECONCILED |
| invalid attestation | FAILED:TOT_ATTESTATION_INVALID; state unchanged |
| initial replica merge | MERGED |
| concurrent replica fork | CONFLICT / CONCURRENT_FORK_SAME_SEQUENCE |
| 32-way coordinate contention | 1 committed / 31 blocked |
| restart readback | directory head equal; ToT head equal |
| directory tamper | detected / DIRECTORY_HEAD_MISMATCH |

Evidence ledger: 14 packets, chain verified, zero failures.

Primary directory end state: version 5, 3 entries, head `c9012940a53ba86d1860b757c114e83980827fde57ae4478d86c07eef7dc3f83`.

ToT kernel end state: one accepted transition, head `bb6681084e21989f22c4728f482b9e960d4b50368c7750d1db2de746fa5bd135`.

## 7. Measured local performance

No arbitrary latency gate was imposed.

100 persisted coordinate updates:

- median 3.102 ms;
- p95 6.415 ms;
- p99 8.011 ms;
- max 8.612 ms.

100 persisted ToT authorizations:

- median 0.777 ms;
- p95 1.322 ms;
- p99 1.931 ms;
- max 3.838 ms.

Error rate: 0.0.

These are local warm-run numbers with local fsync/SQLite. They are not network, quorum, cloud or production SLO evidence.

## 8. What advanced

### 8.1 ToT

ToT advanced from a continuity/topology concept to an executable safety decision procedure. Stale state, replay, invalid attestation, capability failure, cycle and excessive hops now have deterministic outcomes.

### 8.2 Coordinates

Logical coordinate identity is now persisted independently of carrier endpoint state. Endpoint changes need not redefine node identity.

### 8.3 Replica semantics

The directory now distinguishes ordering from divergence. Equal sequence is not enough to establish equality. Root/ancestry evidence is required.

### 8.4 Layer-2

Layer-2 now has a concrete state machine:

`DESIRED -> OBSERVED -> IDENTITY VERIFY -> DIRECTORY -> FIXED POINT or ToT -> CAS COMMIT -> READBACK`.

### 8.5 Recursive convergence

Unchanged state reaches `FIXED_POINT`; recursive operation therefore has a quiescent state instead of recomputing indefinitely.

## 9. Standards comparison

Report 03 is compared against current formal and industry references without claiming certification.

### NIST SP 800-207 / SP 800-207A

Alignment: partial.

Report 03 does not trust a network coordinate or endpoint merely because it is local. Explicit authority and capabilities are required. However, there is no deployed production workload identity provider, credential rotation/revocation service or policy decision point.

### NIST SP 800-53 Rev.5 current release line

Alignment: partial.

Separate source/target capability checks reflect least-privilege concerns and evidence packets record privileged reconciliation decisions. This is not a complete 800-53 implementation or assessment.

### RFC 8785 JCS

Alignment: conceptual only.

Report 03 uses deterministic Python JSON serialization for tested data. It does not enforce I-JSON or exact JCS number/string rules and therefore must not claim RFC 8785 conformance.

### RFC 8949 deterministic CBOR

Not implemented.

### RFC 9846 TLS 1.3

Not implemented in Report 03.

No remote TLS session was exercised, so secure multi-host transport is unproven.

### POSIX.1-2024 / The Open Group Issue 8

Partial alignment.

The persistence path uses file fsync, atomic replacement and parent-directory fsync. Physical power-loss invariance remains unproven and storage semantics remain implementation dependent.

### Kubernetes controller/resourceVersion pattern

Strong pattern alignment.

Report 03 compares desired/current state, quiesces at a fixed point, and rejects stale mutation using expected roots analogous to optimistic resource-version checks. It does not implement a Kubernetes API server, watch system, leader election or HA control plane.

### etcd/Raft consistency

Report 03 is explicitly below this level.

The directory detects forks; it does not run quorum consensus and therefore does not provide linearizability or one globally committed order.

### RFC 9562 UUID

Report 03 uses system node IDs plus SHA-256 state/content roots. UUID interoperability is not provided and would require an adapter where external schemas require UUIDs.

## 10. Epistemic classification

### Reproducibly tested

- ToT validation/rejection;
- replay persistence;
- cycle/hop rejection;
- coordinate uniqueness;
- CAS rejection;
- rollback on injected persistence error;
- restart recovery;
- directory tamper detection;
- evidence-ledger tamper detection;
- fixed point;
- ToT-gated mutable drift;
- successor merge;
- fork detection.

### Source or architectural evidence only

- live R40 CanonicalRuntimeHost binding;
- deployment to self-hosted BRAINK nodes;
- connected-service failover;
- GCS/Drive remote replication in this run;
- remote TLS;
- production credential lifecycle.

### Unsupported if claimed completed

- global linearizability;
- consensus;
- Byzantine fault tolerance;
- indefinite self-sustaining availability;
- production RPO/RTO;
- physical power-loss invariance;
- internet-scale performance;
- RFC 8785 compliance;
- zero-trust certification.

## 11. Why forks are not auto-resolved

Automatic deterministic choice is not the same as authorized finality.

A partition can produce two valid local successors. Choosing the highest hash, newest timestamp or lowest node ID would hide the conflict without proving authority.

Current rule:

`provable successor -> merge`  
`stale ancestor -> ignore`  
`identical state -> no-op`  
`fork or ancestry gap -> CONFLICT`

Consensus, finality, or an explicitly chosen CRDT policy must exist before conflict can legitimately become automatic selection.

## 12. Deficiency analysis

### D01 — Multi-host coordinate consistency

**Advanced:** CAS, ancestry, snapshot merge, same-sequence fork detection.

**Unproven:** linearizable/single-copy global coordinate truth.

**Why unproven:** no quorum/consensus commit exists.

**Why the why remains unaddressed:** resident mesh/proof/fanout mechanics do not contain proposal terms, votes, quorum commit, replicated WAL or equivalent finality.

**Why it remains:** fork detection proves divergence but cannot choose an authoritative global branch.

**Architecture absent:** consensus or explicitly chosen CRDT semantics; membership/failure detector; quorum/finality authority; replicated persistence; snapshot/compaction; partition test harness.

### D02 — Production ToT authentication

**Advanced:** external verifier plus replay, capability, state-root, cycle and hop checks.

**Unproven:** production per-node credential authenticity, rotation and revocation.

**Why:** executed tests used one local HMAC secret.

**Why the why remains unaddressed:** no deployed workload-identity/PKI service was available to Report 03.

**Why it remains:** a safety kernel can consume identity evidence but cannot create trustworthy distributed identity from a test key.

**Architecture absent:** identity issuer, per-node keys/credentials, secure key storage, rotation, revocation, authority binding.

### D03 — Byzantine tolerance

**Advanced:** integrity checks and deterministic fork evidence.

**Unproven:** safety/liveness under malicious quorum members.

**Why:** no BFT consensus exists.

**Why the why remains unaddressed:** adding BFT changes the fault model; no resident BFT proposal/vote/commit architecture was discovered.

**Why it remains:** hashes/HMAC do not create honest quorum behavior.

**Architecture absent:** formal Byzantine fault model; quorum certificates; equivocation handling; BFT state machine if actually required; adversarial multi-node harness.

### D04 — Directory distribution/liveness

**Advanced:** replicas converge through provable ancestry where no fork exists.

**Unproven:** automatic anti-entropy, discovery and availability under host/network loss.

**Why:** snapshots were exchanged locally.

**Why the why remains unaddressed:** no live remote transport or multi-host scheduler was active.

**Why it remains:** merge logic does not move state between machines.

**Architecture absent:** authenticated peer transport; anti-entropy scheduler; membership/discovery; retries/backoff; remote readback.

### D05 — Layer-2 runtime actuation

**Advanced:** desired/observed comparison, immutable drift failure, ToT-authorized mutable reconcile.

**Unproven:** mutation of an actual R40 runtime/service with external-effect proof.

**Why:** the executed reconciler updates coordinate control state from observed state rather than owning R40 actuation.

**Why the why remains unaddressed:** no active R40 CanonicalRuntimeHost target was present in the artifact container.

**Why it remains:** bypassing Observer²/capability gates would create a competing execution authority.

**Architecture absent:** Report03-to-CanonicalRuntimeHost adapter; Observer²-governed actuator; capability/resource handoff; rollback/readback; process/service integration test.

### D06 — Physical power-loss durability

**Advanced:** fsync-backed replacement, injected persistence failure rollback, restart recovery.

**Unproven:** physical power-loss invariance.

**Why:** no real power cut occurred.

**Why the why remains unaddressed:** the environment cannot destructively power-cycle target hardware/storage.

**Why it remains:** exception injection and process restart do not reproduce device caches/journaling/power removal.

**Architecture absent:** destructive power/crash harness; filesystem/storage matrix; post-boot inspection; timing injection around durability barriers.

### D07 — Secure remote transport

**Advanced:** endpoints are mutable carrier fields, not identity.

**Unproven:** remote confidentiality, authentication and channel integrity.

**Why:** no network transport exists inside Report 03.

**Why the why remains unaddressed:** transport was deliberately left to resident networking rather than creating another networking authority.

**Why it remains:** in-process exchange cannot produce TLS evidence.

**Architecture absent:** RFC 9846 TLS 1.3 or equivalent; certificate/workload identity; connection lifecycle; channel binding; remote fault tests.

### D08 — Canonical serialization interoperability

**Advanced:** deterministic serialization for tested Python values.

**Unproven:** RFC 8785 or deterministic-CBOR conformance.

**Why:** implementation is Python `json.dumps` sorting/compact separators only.

**Why the why remains unaddressed:** local algorithms required internal consistency, not standards-wire conformance.

**Why it remains:** deterministic output in one implementation is not cross-language canonicalization.

**Architecture absent:** JCS/CBOR codec; cross-language vectors; Unicode/number edge suite; wire-format versioning.

### D09 — Scale/performance

**Advanced:** 32-way collision stress and 200 persisted benchmark operations completed without error.

**Unproven:** sustained multi-host 40-node+ cascades, large directories, high churn and production contention.

**Why:** benchmark was local and bounded.

**Why the why remains unaddressed:** no distributed load-generator fleet or production-size corpus was active.

**Why it remains:** local latency cannot model network RTT, quorum, remote disk or long-history growth.

**Architecture absent:** distributed load generator; representative corpus; long-duration churn; resource telemetry; compaction/finality.

### D10 — Directory compaction

**Advanced:** retained history enables successor/fork proof.

**Unproven:** bounded history while preserving replay and fork evidence.

**Why:** history is retained indefinitely.

**Why the why remains unaddressed:** safe compaction requires finality/checkpoint authority.

**Why it remains:** deleting ancestry before finality destroys proof needed to distinguish successor from fork.

**Architecture absent:** checkpoint/finality rule; signed snapshot root; compaction horizon; retention policy; replay-from-checkpoint tests.

### D11 — Connected-service failover

**Advanced:** local restart is proven; prior GCS work correctly treats remote object storage as replica carrier.

**Unproven:** automatic Drive/GCS/service failover with one writable canonical history.

**Why:** Report 03 did not execute remote credentials or writer promotion.

**Why the why remains unaddressed:** replica availability and writer finality are different problems.

**Why it remains:** multiple copies without fencing permit split brain.

**Architecture absent:** replica promotion policy; fencing/lease or consensus; remote health/readback; RPO/RTO evidence; rejoin protocol.

### D12 — End-to-end R40 deployment

**Advanced:** the layer is executable against the V9 transactional evidence ledger and consumes authority callbacks rather than inventing authority.

**Unproven:** R40 inherited regression, service deployment and runtime readback with Report 03 active.

**Why:** the artifact container is not the resident R40 execution host.

**Why the why remains unaddressed:** prior R40 jobs remained dependent on the self-hosted KEX runner/target environment.

**Why it remains:** local source/test success cannot prove another host's running process identity.

**Architecture/external capability absent:** available R40 runner; canonical adapter binding; CI execution; service start/restart; deployed commit/readback receipt.

## 13. Architecture present versus absent

### Present and executed

- ToT proposal/replay model;
- state-root freshness;
- capability checks;
- cycle/hop protection;
- non-zero logical coordinates;
- single-owner coordinate rule;
- ancestry/CAS;
- atomic local persistence;
- replica merge;
- fork detection;
- Layer-2 desired/observed comparison;
- immutable identity drift failure;
- ToT-gated mutable reconciliation;
- fixed-point quiescence;
- readback verification;
- V9 evidence-ledger integration;
- fault injection;
- restart verification;
- local benchmark.

### Absent and therefore unable to support stronger claims

- multi-host consensus;
- linearizable replicated log;
- finality/quorum;
- production node identity/PKI;
- credential rotation/revocation;
- remote TLS binding;
- anti-entropy scheduler;
- membership/failure detection tied to finality;
- R40 runtime actuator adapter;
- multi-host rollback/readback;
- physical power-loss harness;
- JCS canonicalizer;
- deterministic CBOR codec;
- history compaction/finality;
- distributed load generator;
- connected-service writer fencing;
- executed R40 deployment for this layer.

## 14. Final state

```text
TOT_SAFETY_KERNEL                 = IMPLEMENTED / TESTED
DISTRIBUTED_COORDINATE_DIRECTORY = IMPLEMENTED / FORK DEFECT FOUND + PATCHED
LAYER2_RECONCILER                 = IMPLEMENTED / TESTED
FAULT_INJECTION                   = EXECUTED
UNIT/NEGATIVE TESTS               = 24/24 PASS
EVIDENCE_LEDGER                   = 14 PACKETS / CHAIN VERIFIED
RESTART_RECOVERY                  = PASS
TAMPER_DETECTION                  = PASS
CONCURRENT_COORDINATE_COLLISION   = 1 COMMIT / 31 BLOCKED
REPLICA_FORK                      = EXPLICIT CONFLICT
LOCAL_BENCHMARK                   = RECORDED / NO ARBITRARY GATE
STANDARDS_COMPARISON              = COMPLETE
DEFICIENCY ARCHITECTURE MAP       = COMPLETE
MULTI-HOST CONSENSUS              = NOT PRESENT
PRODUCTION IDENTITY               = NOT PRESENT
REMOTE TLS TRANSPORT              = NOT PRESENT IN REPORT03
PHYSICAL POWER-LOSS PROOF         = NOT PRESENT
R40 TARGET DEPLOYMENT             = NOT PROVEN
```

**Bounded Report 03 intent:** `INTENT_MET = TRUE`.

**Global production-distributed closure:** `INTENT_MET = FALSE` until the explicitly absent architectures are implemented and executed.
