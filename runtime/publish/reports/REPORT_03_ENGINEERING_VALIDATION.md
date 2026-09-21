# REPORT 03 — BRAINK/KEX Missing Engineering Layer: Executed Safety, Directory, Reconciliation, Fault Injection and Evidence

**Date:** 2026-09-21  
**Scope:** ToT safety kernel, distributed coordinate directory, Layer-2 reconciler, durable evidence, executed fault injection, standards comparison, and explicit remaining deficiency architecture.  
**Evidence class:** Local executed engineering qualification. No claim of production deployment or multi-host distributed proof is made where it was not observed.

---

## 1. Executive determination

This report records an engineering advance, not a prose rearrangement.

The pre-existing repository already contained three important components:

1. `tot_safety.py`: a fixed-membership, majority-quorum, non-Byzantine transaction-ordering kernel with receipt hashes and per-voter equivocation locks;
2. `coordinate_directory.py`: a deterministic coordinate directory whose state is driven by committed ToT transitions and whose replicas can replay and compare receipt history;
3. `layer2_reconciler.py`: a desired-versus-observed reconciliation loop with deterministic action planning, idempotency keys, per-action receipts, and convergence checks.

Those components were real, but they still left important engineering gaps. Report 03 therefore added and executed the missing layer rather than replacing the existing design:

- whole-chain ToT receipt verification anchored at the fixed genesis root;
- durable append-only evidence journaling with per-record hash chaining and `fsync`;
- torn-tail detection and bounded truncation recovery for an interrupted journal write;
- coordinate-directory snapshot restoration with root verification;
- explicit validation of actuator responses before reconciliation accepts them as observed state;
- fault injection for ambiguous actuator outcomes where a side effect occurred but the response was lost;
- an expanded falsification suite covering ordering, quorum, replay, tampering, stale generations, zero-address rejection, snapshot corruption, actuator lies, partial failure, and retry convergence.

The observed result is **16 tests passed, 0 failed** in the executed local qualification environment.

That result advances the system materially, but it does not establish production-distributed correctness. The current architecture is still a deterministic single-process implementation of crash/replay/reconciliation mechanics. It does not yet contain a transport protocol, leader election, dynamic membership protocol, replicated durable log across independent hosts, authenticated node identity for quorum voting, linearizable read service, formal model checking, or independent provenance signing. Those absences define the remaining boundary.

---

## 2. What existed before Report 03

### 2.1 ToT safety kernel

The resident `ToTSafetyKernel` already provided:

- deterministic transition serialization and SHA-256 transition digests;
- fixed membership and membership hash;
- majority quorum calculation;
- transition proposal under an epoch;
- per-voter equivocation lock for a specific `(epoch, index, voter)` tuple;
- quorum certificate construction;
- commit-root chaining;
- per-receipt cryptographic integrity checks;
- replay-root calculation;
- fail-closed rejection of unsupported membership change;
- zero-address rejection for members and actors.

The kernel explicitly declared itself crash-fault/non-Byzantine. That is the correct claim boundary. It did not pretend that voter names were cryptographically authenticated identities or that a malicious member could not forge another member's vote.

### 2.2 Distributed coordinate directory

The resident directory already provided:

- coordinate registration;
- manifestation upsert/detach operations;
- positive generation monotonicity;
- stale-generation rejection;
- replay-gap rejection;
- replica history comparison by receipt hash;
- deterministic directory-root hashing;
- zero rejection for coordinate and manifestation addresses;
- zero rejection for manifestation state.

The directory was therefore already more than an in-memory dictionary. Its state was tied to committed ToT transitions and receipt continuity.

### 2.3 Layer-2 reconciler

The resident reconciler already provided:

- desired/observed state comparison;
- deterministic `MATERIALISE`, `REPLACE`, and `DETACH` action planning;
- generation checks;
- idempotency-key generation from reconcile identity and action;
- action receipts;
- partial-failure receipts;
- repeated reconciliation until the desired and observed maps converge.

The important gap was that it trusted the actuator's returned object. An actuator could return the wrong manifestation ID, wrong endpoint, wrong generation, or wrong state and the reconciler would accept that response into its own observed map. That was an integrity hole at the exact boundary where an external or lower-layer executor reports what actually happened.

---

## 3. Engineering added in Report 03

### 3.1 Whole-chain ToT verification

A new `verify_chain()` operation verifies the complete ordered sequence of transitions and receipts from the fixed genesis root.

The verifier rejects:

- transition/receipt count mismatch;
- index gaps;
- unexpected epoch changes inside the verified chain;
- transition or receipt roots that do not match the prior committed root;
- any receipt that fails the existing quorum-certificate, membership-hash, committed-root, or receipt-hash checks.

This closes a meaningful distinction between **a receipt that is internally self-consistent** and **a sequence of receipts that is proven to belong to one continuous history**.

Before this addition, `verify_receipt()` could correctly prove that a given transition/receipt pair was internally coherent, but it did not by itself prove that the pair occupied the correct place in the entire genesis-anchored chain. Recovery already performed some sequential checks, but the new method makes whole-chain verification a first-class invariant used by recovery and replay.

### 3.2 Durable evidence journal

A new `EvidenceJournal` was added as an append-only JSONL ledger.

Each journal record contains:

- monotonically increasing sequence number;
- previous record hash;
- evidence kind;
- evidence payload;
- SHA-256 record hash computed over the canonical record body.

Appending uses:

- `O_APPEND`;
- a single serialized line per record;
- explicit `fsync` before the append returns.

Recovery verifies every record from a journal genesis value. A modified historical payload causes `JOURNAL_HASH_MISMATCH`. A changed previous hash causes `JOURNAL_CHAIN_DIVERGENCE`. A sequence discontinuity causes `SEQUENCE_GAP`.

A final incomplete line is treated separately from historical corruption. Recovery can fail closed with `PARTIAL_TAIL_RECORD`, or, when explicitly authorized with `truncate_partial_tail=True`, truncate only the uncommitted tail bytes and preserve the last complete verified record.

This does **not** prove storage durability across disk-controller failure, filesystem corruption, device loss, or multi-host replication. It proves that this process explicitly flushes completed evidence appends and can distinguish a torn final record from a valid historical chain during local filesystem recovery.

### 3.3 Directory snapshot verification and restore

The coordinate directory now supports `from_snapshot()`.

The restore operation:

- reconstructs typed coordinate and manifestation records;
- reapplies the zeroless address/state checks;
- recalculates the deterministic directory root;
- rejects the snapshot when the calculated root differs from the recorded root.

Fault injection altered a restored coordinate generation value without changing the recorded directory root. Restoration correctly failed with `DIRECTORY_SNAPSHOT_ROOT_MISMATCH`.

The snapshot mechanism is therefore now an integrity-checked acceleration/recovery surface rather than an unverified object dump.

It is still not a replicated snapshot protocol. There is no snapshot transfer transport, quorum-installation protocol, snapshot term/index negotiation, compaction boundary, or concurrent writer exclusion across independent machines.

### 3.4 Layer-2 actuator-result validation

The reconciler now verifies that the actuator's returned observation matches the action it was asked to execute.

For all action kinds it checks:

- manifestation ID equals the requested manifestation ID;
- returned generation equals the action generation;
- state is `DETACHED` for detach and `ATTACHED` for materialise/replace;
- endpoint equals the requested endpoint for materialise/replace.

A mismatched result is turned into a failed action receipt and is not installed into the reconciler's observed-state map.

Fault injection returned a future generation and then, separately, the wrong endpoint. Both cases were rejected and preserved as `PARTIAL_FAILURE` evidence rather than being converted into false convergence.

### 3.5 Ambiguous side-effect retry

A particularly important failure mode was executed:

1. reconciler sends a materialisation action;
2. the actuator applies the effect and stores the idempotency key/result;
3. the response is lost and the caller sees a timeout;
4. reconciler records partial failure without assuming whether the side effect happened;
5. a subsequent reconciliation produces the same action/idempotency key;
6. actuator recognizes the previously applied key and returns the already-observed result;
7. reconciliation converges.

This demonstrates the correct shape of an idempotent retry path for the classic "did it happen or not?" boundary.

It does not prove that a real external service honors the same idempotency contract. The test actuator was specifically engineered to simulate that semantics. Real service adapters must either expose an equivalent idempotency key, a queryable operation identity, or a read-after-write mechanism capable of determining the actual outcome before safe retry.

---

## 4. Executed falsification matrix

| Fault / falsifier | Expected safety response | Observed result |
|---|---|---|
| Reordered ToT receipts | reject history | PASS, rejected |
| Insufficient quorum | no commit | PASS, rejected |
| Voter equivocation at same epoch/index | reject second conflicting vote | PASS, rejected |
| Dynamic membership request | fail closed because protocol absent | PASS, rejected |
| Journal payload modified after append | detect hash mismatch | PASS, detected |
| Torn final journal record | detect partial tail | PASS, detected |
| Authorized torn-tail recovery | retain complete history and truncate only tail | PASS |
| Replica replay gap | reject | PASS, rejected |
| Stale manifestation generation | reject | PASS, rejected |
| Zero used as coordinate address | reject | PASS, rejected |
| Directory snapshot modified without new root | reject restore | PASS, rejected |
| L2 partial actuator failure | receipt partial failure, preserve prior successful actions | PASS |
| L2 retry after partial failure | converge | PASS |
| Side effect applied but response lost | retry same logical action/idempotency key | PASS, converged |
| Actuator reports wrong generation | reject returned observation | PASS, rejected |
| Actuator reports wrong endpoint | reject returned observation | PASS, rejected |

Executed suite result:

```text
................                                                         [100%]
16 passed in 0.04s
```

The important interpretation is not that "16 tests means the system is complete." It means these sixteen specifically named falsifiers did not break the implementation in the executed environment.

---

## 5. Evidence receipts

The Report 03 evidence receipt is stored as `REPORT03_EVIDENCE_RECEIPT.json`.

It records:

- execution environment;
- test count and result;
- SHA-256 digests for the tested source files;
- SHA-256 digest for the test source;
- observed advances;
- falsifiers actually executed;
- explicit non-proven claims.

This is an improvement over prose-only qualification because the evidence object binds the claim to the tested artifacts by digest.

It is not yet independently authenticated provenance. A process with write access to the same environment can rewrite the code and regenerate a new local receipt. There is no external signature, transparent log, hardware-backed attestation, independent builder identity, or verifier-produced attestation.

---

## 6. Standards and reference-architecture comparison

The comparison below uses current public specifications/reference architectures as of 2026-09-21. The purpose is to define capability boundaries, not to claim that BRAINK must clone any one external implementation.

### 6.1 Raft

Reference: <https://raft.github.io/>

Raft is a consensus algorithm with leader election, replicated logs, safety rules, and a defined approach to cluster membership changes. Its published materials include a formal TLA+ specification.

**BRAINK Report 03 now has:** deterministic log entries, majority quorum, receipt chaining, fixed membership, equivocation locks, recovery verification.

**BRAINK does not yet have:** leader election, request routing to leader, AppendEntries-style replication transport, heartbeat/election timeouts, term-based conflict resolution across independent hosts, log backtracking, snapshot installation between hosts, joint-consensus or equivalent safe membership reconfiguration, or formal model-checking evidence.

Therefore the current ToT kernel is correctly described as a local/non-Byzantine quorum safety kernel, not a Raft-equivalent distributed consensus implementation.

### 6.2 etcd v3.7 API guarantees

Reference: <https://etcd.io/docs/v3.7/learning/api_guarantees/>

etcd documents strict serializability and durability for KV operations. Its watch stream is revision ordered, unique, reliable within retained history, atomic by revision, and resumable subject to compaction limits. Revisions act as a logical clock.

**BRAINK Report 03 now has:** monotonic committed indices/generations, replay ordering, deterministic roots, replica divergence detection, restartable local evidence, and snapshot integrity verification.

**BRAINK does not yet have:** a network-accessible linearizable read/write API, revisioned multi-client transactions, lease semantics, resumable watch protocol, compaction protocol, replicated durable backend, quorum read path, or demonstrated strict serializability under concurrent multi-host access.

The directory is therefore a deterministic committed-state directory, not yet an etcd-class distributed coordination service.

### 6.3 Kubernetes controller reconciliation

Reference: <https://kubernetes.io/docs/concepts/architecture/controller/>

Kubernetes controllers repeatedly compare desired state with current state and act to move current state toward desired state. This model explicitly tolerates ongoing change and repeated reconciliation.

**BRAINK Report 03 now has:** desired/current state separation, deterministic plan generation, idempotency keys, action receipts, retry after partial failure, and convergence checks.

**BRAINK does not yet have:** a durable shared API server/resource-version contract, controller work queues, backoff policy, finalizer semantics, ownership references, conflict-aware optimistic concurrency, distributed controller lease/election, or a real adapter matrix proving idempotent behavior across actual external targets.

The L2 reconciler now matches the control-loop shape more closely but remains a core reconciliation engine rather than a production controller platform.

### 6.4 RFC 8785 JSON Canonicalization Scheme

Reference: <https://www.rfc-editor.org/rfc/rfc8785.html>

RFC 8785 defines a canonical JSON representation intended for repeatable hashing/signing and interoperability.

The current BRAINK implementation uses deterministic Python `json.dumps(..., sort_keys=True, separators=(',', ':'))`. That is useful for deterministic hashes **inside the tested Python implementation**, but it has not been proven RFC 8785 conformant. Differences in numeric serialization, Unicode treatment, and implementation-specific JSON behavior matter when multiple languages independently calculate the same digest.

Until a JCS implementation or conformance suite is added, hashes are implementation-profile deterministic, not claimed as cross-language JCS-compatible cryptographic canonicalization.

### 6.5 SLSA 1.2 and in-toto 1.0

References:

- <https://slsa.dev/spec/v1.2/>
- <https://slsa.dev/spec/v1.2/provenance>
- <https://in-toto.io/docs/specs/>

SLSA 1.2 treats provenance as verifiable information about where, when, and how an artifact was produced. in-toto provides stable attestation specifications.

**BRAINK Report 03 now has:** digest-bound local evidence records and a hash-chained local evidence journal.

**BRAINK does not yet have:** authenticated builder identity, standard in-toto statement envelope, SLSA build/source provenance predicates, signature verification, key management, transparent publication, independent verifier output, or a hardened build control plane preventing the tested workload from altering its own provenance.

The Report 03 receipt is therefore local engineering evidence. It is not represented as SLSA L2/L3 provenance or an independently trustworthy attestation.

---

## 7. What materially advanced

### 7.1 Safety moved from pair verification to history verification

The most important ToT advance is the distinction between validating individual commits and validating one continuous committed history. `verify_chain()` now makes the complete genesis-to-head root sequence an executable invariant.

### 7.2 Evidence moved from transient output to crash-aware persisted records

The new evidence journal makes local evidence replayable after restart and detects historical alteration. The torn-tail path is specifically handled rather than treating any damaged final byte sequence as total ledger corruption.

### 7.3 Directory snapshots became verifiable state checkpoints

A snapshot can now be restored only when its recomputed directory root matches the recorded root. This is necessary before snapshots can be trusted as recovery accelerators.

### 7.4 Reconciliation no longer trusts actuator assertions blindly

A lower-layer executor cannot return arbitrary observation data and have the controller silently adopt it. The returned observation must satisfy the contract implied by the action.

### 7.5 Ambiguous execution gained an evidence-preserving retry model

The apply-then-timeout test demonstrates why idempotency identity belongs to the operation contract. The controller neither invents success nor blindly emits a different retry identity.

---

## 8. What remains unproven

The following claims remain unproven and should not be promoted by wording alone:

1. **Multi-host ToT consensus safety.**
2. **Network-partition behavior and recovery.**
3. **Liveness under node loss, latency, duplication, and reordering.**
4. **Safe dynamic membership.**
5. **Byzantine or malicious-node resistance.**
6. **Cryptographically authenticated voter identity.**
7. **Linearizable distributed coordinate reads and writes.**
8. **Durability after independent host/disk loss.**
9. **Snapshot transfer/install across replicas while writes continue.**
10. **Real service actuator idempotency across external providers.**
11. **Cross-language canonical digest equivalence.**
12. **Formal consensus safety proof/model checking.**
13. **Authenticated, independently verifiable build/runtime provenance.**
14. **Production performance characteristics under concurrent load.**
15. **Long-duration operation with compaction, retained history, repair, and version migration.**

---

## 9. Why each item remains unproven, why that cause remains unaddressed, and what architecture is absent

| Unproven property | Why it remains unproven | Why the cause remains unaddressed | Why the unaddressed condition remains | Missing architecture required to close it |
|---|---|---|---|---|
| Multi-host consensus | All executed tests ran inside one process/environment | There is no peer transport or independent node process in this qualification layer | A quorum object can simulate vote sets without exercising real message delivery/failure timing | Peer RPC/transport, independent node runtimes, persistent replicated log, term/view protocol, integration harness across processes/hosts |
| Partition safety/liveness | No packets were dropped between real peers because there were no real peers | No network fault harness is wired to a cluster runtime | Local method calls cannot represent asymmetric partition, delay, reorder, reconnect, or split brain | Multi-node testbed plus deterministic network proxy/fault injector and partition test matrix |
| Leader election | ToT kernel commits using caller-supplied votes; it has no leader role | Leader/election was deliberately outside the existing fixed-membership kernel | Adding an election algorithm without transport/term persistence would be decorative architecture | Election/term state, heartbeat protocol, timeout rules, stable term/vote storage, leader fencing |
| Safe membership change | `reconfigure_membership()` explicitly fails closed | There is no joint-old/new quorum transition protocol | Changing the member list naively can produce disjoint quorums and violate safety | Joint-consensus/equivalent reconfiguration state machine, persisted configuration index, old/new quorum rules, recovery tests |
| Byzantine resistance | Votes are typed records, not signatures | Threat model is non-Byzantine and there is no key registry/signature layer | Cryptographic identity was never part of the crash-fault kernel | Node key identity, signed votes/receipts, replay protection, trust registry, Byzantine protocol if malicious consensus participants are in scope |
| Linearizable directory API | Directory replay is deterministic but no concurrent network API was exercised | No distributed read/write serving layer exists | In-memory/root equality is weaker than real-time operation ordering observed by multiple clients | Consensus-backed API, leader/quorum read path, revision tokens, concurrent client tests, serializability checker |
| Durable replicated state | `fsync` proves local flush intent only | No independent durable replicas were written | One filesystem can be lost despite a valid hash chain | WAL per node, replicated commit acknowledgment policy, snapshots, fsync policy, storage corruption/replacement recovery |
| Snapshot installation | Local snapshot root verification exists | No snapshot transport/install protocol exists | Restore from a local object does not exercise concurrent replication boundaries | snapshot metadata, included index/root, transfer/chunk verification, atomic install, log truncation/compaction rules |
| External actuator exactly-once-equivalent behavior | Fake actuator honors idempotency key | Real providers have not been bound and fault-injected here | Idempotency semantics are provider-specific and cannot be inferred | Target adapters with operation IDs/idempotency tokens, readback APIs, reconciliation-specific recovery contracts, live sandbox fault tests |
| Cross-language hash interoperability | Python canonical JSON is deterministic locally | RFC 8785/JCS was not implemented | `sort_keys` is not proof of JCS numeric/string semantics | RFC 8785 implementation/conformance corpus or a binary canonical format with published schema and cross-language vectors |
| Formal safety proof | Unit/fault tests cover finite scenarios | No TLA+/PlusCal/Coq/Isabelle model is tied to current code semantics | Tests cannot quantify all schedules/interleavings | formal state-machine model, invariant definitions, exhaustive model checking over bounded cluster/fault states, model-code traceability |
| Authenticated provenance | Receipt is hash-bound locally | Same environment can generate code and receipt | Hash integrity is not origin authenticity | in-toto/SLSA statement, trusted builder identity, signing keys/identity federation, external verifier, transparency/distribution path |
| Production performance | No benchmark workload in Report 03 | Correctness work was isolated from performance claims | Performance without realistic concurrency/network/storage is meaningless | benchmark plan, multi-client load generator, p50/p95/p99 latency, throughput, CPU/memory/disk/network telemetry, fault-under-load tests |
| Long-run lifecycle | Tests complete in milliseconds | No compaction/version migration/retention service exists | Short deterministic tests do not expose operational aging | compaction policy, schema migration, retained-history rules, rolling upgrades, soak tests, repair automation |

This table is the key architectural boundary of Report 03. The remaining deficiencies are not missing because nobody wrote enough explanatory prose. They remain because the execution substrates needed to test them do not yet exist.

---

## 10. Why the "why" remains unaddressed

The repeated root cause is **layer absence**, not unexplained intent.

For example, saying "multi-host consensus is unproven because no multi-host test was run" is only the first-order reason. The deeper reason is that there is no production peer-transport/election/replicated-WAL architecture to deploy into multiple independently failing processes. Without that layer, a multi-host test would either test mocks or test ad-hoc glue that is not the system.

Likewise, "external actuator idempotency is unproven because no provider was tested" is incomplete. The deeper reason is that the reconciler has a generic actuator protocol but no target-specific execution contract defining how an operation identity maps to the provider's retry/readback semantics. Without that contract, simply calling a provider API is not evidence of safe reconciliation.

And "provenance authenticity is unproven because the receipt is unsigned" is not solved by dropping a signature field into JSON. The missing architecture includes a trustworthy signer identity, key custody or identity-backed signing service, separation between workload and provenance authority, verification policy, and distribution channel.

This is why the unproven items remain. Their closure requires new executable layers, not labels.

---

## 11. Required architecture, separated explicitly from existing architecture

### Existing and executed in Report 03

- fixed-member crash-fault quorum kernel;
- transition digest and commit-root chain;
- quorum certificate integrity checking;
- genesis-anchored whole-chain verification;
- zeroless address/state rejection;
- deterministic coordinate state and generation checks;
- replica replay/divergence detection;
- snapshot root validation;
- desired/observed L2 plan generation;
- deterministic reconciliation identity and action idempotency keys;
- actuator-result validation;
- partial-failure receipts;
- local evidence journal with hash chain and `fsync`;
- torn-tail local recovery;
- executed local falsification suite.

### Architecture not presently present, therefore not claimed

#### A. Distributed consensus runtime

Required components:

- peer identity and connection management;
- authenticated peer-to-peer RPC or messaging;
- leader/primary election or another protocol providing one safe ordering authority;
- term/view/ballot persistence;
- replicated WAL;
- majority replication acknowledgment;
- follower catch-up/log conflict repair;
- snapshot transfer/install;
- safe configuration/membership transitions;
- restart/rejoin protocol;
- network partition handling;
- formalized liveness assumptions.

#### B. Distributed coordinate service layer

Required components:

- externally callable read/write API;
- revision/index returned to clients;
- defined read consistency modes;
- transaction/compare-and-swap semantics where needed;
- watch/subscription stream;
- watch resume and compaction handling;
- leases/TTL if ephemeral membership is needed;
- concurrency and serializability verification.

#### C. Production L2 controller platform

Required components:

- durable work queue;
- exponential/backoff scheduling policy;
- per-target rate limits;
- target adapter contracts;
- operation identity/idempotency persistence;
- read-after-action observation;
- conflict version/resource version;
- ownership/finalization semantics;
- dead-letter/quarantine path;
- controller lease/election when multiple controllers run;
- provider sandbox fault injection.

#### D. Cryptographic identity and provenance plane

Required components:

- authenticated node identities;
- cryptographic vote/receipt signatures if adversarial identity spoofing is in scope;
- key lifecycle/rotation/revocation;
- provenance statement schema;
- trusted builder/verifier separation;
- SLSA/in-toto compatible attestations if interoperability is desired;
- publication/distribution and independent verification.

#### E. Canonical data interoperability layer

Required components:

- RFC 8785 JCS or another explicitly standardized canonical format;
- cross-language test vectors;
- schema versioning;
- parser rejection policy;
- numeric precision rules;
- Unicode rules.

#### F. Formal verification layer

Required components:

- executable/formal specification of kernel state machine;
- safety invariants;
- membership transition invariants;
- partition/failure model;
- model checker runs;
- traceability from model operations to runtime methods;
- regression process keeping model and code synchronized.

---

## 12. Failure interpretation

Report 03 deliberately distinguishes four failure meanings.

### 12.1 Falsifier rejected as designed

Examples: insufficient quorum, equivocation, stale generation, zero address, snapshot tampering. These are **PASS** outcomes because the safety boundary rejected an invalid condition.

### 12.2 Recoverable failure with preserved evidence

Examples: actuator fails once; final journal record is torn. The system preserves a valid prefix, records failure, and can retry/recover under an explicit rule.

### 12.3 Architecture absent

Examples: dynamic membership and Byzantine consensus. These are not failed implementations. They are explicitly unimplemented architecture and must remain unproven until built.

### 12.4 External/physical property not exercised

Examples: storage-device loss, real provider timeout-after-side-effect, independent host partition. Local simulation can validate the control logic shape but cannot substitute for the actual external failure domain.

---

## 13. Zero-assessment invariant

The current runtime preserves the governing KEX rule:

> Zero is a computed assessment value arising from opposing polarities; it is not a standalone address, node identity, routable coordinate, or stored state baseline.

Report 03 fault injection explicitly verifies rejection of `0` as a coordinate address. Existing node identity mechanics separately reject zero as address/state.

This invariant is orthogonal to ordinary numeric computation: an assessment function may validly produce numeric zero when opposing values cancel. What is prohibited is promoting that computed assessment result into an ontological address/state token.

---

## 14. Evidence classification

### QUALIFIED by this execution

- code imports and executes in the local test environment;
- 16 specified fault/behavior tests pass;
- complete ToT chain validation catches ordering/root faults;
- local evidence journal detects tampering and incomplete tail writes;
- local torn-tail recovery truncates only the unverified tail;
- directory snapshot tampering is detected by root verification;
- directory replay/stale/zero constraints execute as specified;
- L2 reconciler rejects invalid actuator observations;
- repeated L2 reconciliation converges after injected partial failure;
- ambiguous apply-then-timeout converges under a persistent idempotency-key actuator contract.

### NOT QUALIFIED by this execution

- any live multi-host deployment claim;
- any claim of linearizability across networked clients;
- any Byzantine-fault claim;
- any dynamic-membership safety claim;
- any external-provider exactly-once claim;
- any production SLO or performance claim;
- any RFC 8785 conformance claim;
- any SLSA level claim;
- any formal-proof claim.

---

## 15. Conclusion

Report 03 closes several real engineering gaps.

The ToT layer now verifies continuous genesis-anchored history rather than only isolated receipt integrity. Evidence is persisted in a hash-chained `fsync` journal with torn-tail recovery. Coordinate snapshots have verifiable restore semantics. Layer-2 reconciliation now distrusts and validates executor readback, and it has been exercised against partial failures, false observations, and ambiguous side-effect outcomes.

The executed result was 16/16 passing tests.

The remaining work is no longer honestly describable as "finish the same code." The unproven properties depend on architectures that are simply not present: a real distributed consensus runtime, a networked consistency API, production controller scheduling/adapters, an authenticated identity/provenance plane, standardized cross-language canonicalization, and formal verification infrastructure.

Until those layers exist and are executed under their relevant failure domains, they must remain explicitly unproven. That is not a rhetorical limitation. It is the actual engineering state observed in this qualification run.
