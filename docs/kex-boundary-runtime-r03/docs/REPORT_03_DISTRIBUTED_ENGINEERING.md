# REPORT 03 — Distributed Coordinate Engineering Qualification

Date: 2026-09-22
Baseline: `docs/kex-boundary-runtime-r03`

## 1. Work executed

The existing R03 symbolic/binary and waveform baseline was retained and extended with executable distributed mechanics rather than another architecture-only description.

Implemented:

- evidence-required `ToTSafetyKernel` with fail-closed action vocabulary and deterministic receipt root;
- three-or-more replica `DistributedCoordinateDirectory`;
- majority commit rule;
- generation fencing and previous-value hash chaining;
- explicit offline/crash replica behavior;
- fail-closed loss-of-quorum behavior;
- `Layer2Reconciler` that detects stale/missing replicas and replays committed coordinate history;
- fault-injection/falsification tests;
- machine-readable execution receipt.

## 2. Observed execution

The distributed qualification suite executed 12 tests with 12 PASS, 0 failures and 0 errors.

An additional execution scenario committed generation 1, removed replica `n3`, committed generation 2 with the remaining majority, restored `n3`, and reconciled the directory. The observed final state was consistent. `n1` and `n2` required `NOOP`; `n3` was `REPAIRED`.

The observed evidence root was `9fbabea8c6bb3c9e1228df6507c9e6ccb2b8445c45cffac4142e023357574d45`.

## 3. What advanced

### ToT safety kernel

Actions outside the declared vocabulary are rejected. Evidence is mandatory. Accepted actions emit immutable receipt records and contribute to a deterministic receipt root. This advances the earlier action gate into an evidence-bearing execution boundary.

### Distributed coordinate directory

The directory is no longer merely a local coordinate conflict map. A coordinate mutation now requires a majority of the configured replicas. Every accepted mutation carries a monotonically increasing generation and the prior committed value hash. A single unavailable replica does not prevent a three-node directory from committing. Loss of the majority prevents a canonical state from being asserted.

### Layer-2 reconciliation

A stale replica is detected by generation/value mismatch. Reconciliation replays missing committed records and then emits a `RECONCILE` evidence receipt. The executed stale-node fault was repaired successfully.

### Falsification boundary

The test suite deliberately removes one replica, removes a majority, attempts zero-address commits, uses an unknown proposer, creates stale replicas, injects a corrupt high-generation record, and asks for canonical state without a quorum. The implementation fails closed in the tested cases.

## 4. What remains unproven

### Byzantine fault tolerance

Unproven. The directory assumes crash/offline faults. A corrupt replica can be outvoted in the tested three-node case, but records are not signed and there is no Byzantine quorum protocol.

Why it remains unproven: majority replication under a crash-fault model is not a proof against malicious equivocation, forged messages, conflicting signed histories or coordinated faulty replicas.

Why that reason remains unaddressed: the runtime has no cryptographic node identity, signature verification, Byzantine quorum certificate, view-change protocol or adversarial transport harness.

Required missing architecture: authenticated node identities; signed proposals/votes; domain-separated record signatures; Byzantine quorum rules; view/epoch changes; equivocation evidence; adversarial multi-process tests; key rotation/revocation.

### Real network distribution

Unproven. Replicas execute as independent state objects in one Python process.

Why it remains unproven: no socket, QUIC/TCP, RPC or other transport was involved in the qualification run. Therefore latency, reordering, duplication, packet loss and process scheduling were not physically exercised.

Why that reason remains unaddressed: the current layer deliberately establishes state-machine semantics before binding them to a transport. There is no transport adapter or independent process supervisor in this slice.

Required missing architecture: peer transport; serialization framing; connection lifecycle; retry/idempotency contract; message IDs; replay window; packet-loss/reorder injector; independent processes/hosts; network partition controller; measured convergence traces.

### Concurrent proposer linearizability

Unproven. Sequential generations are enforced, but independently concurrent proposers racing on different replicas have not been subjected to a leader/election or equivalent total-order protocol.

Why it remains unproven: choosing the highest locally observed generation before broadcast is insufficient to establish one global operation order during genuine concurrent races.

Why that reason remains unaddressed: there is no elected leader, term number, prepare/accept phase, quorum certificate or comparable serialization mechanism.

Required missing architecture: explicit consensus/ordering algorithm; terms/epochs; election or quorum phases; conflict resolution; linearizability history checker; concurrent multi-process workload generator.

### Durable recovery

Unproven. Replica logs are memory-resident.

Why it remains unproven: process termination destroys the log, so crash/restart persistence and torn-write behavior cannot be observed.

Why that reason remains unaddressed: no WAL, fsync/barrier contract, snapshot store or recovery scanner is present.

Required missing architecture: durable append-only WAL; checksummed records; atomic commit marker; fsync policy; snapshots/compaction; crash injection between writes; restart/replay qualification.

### Cryptographic peer identity and authorization

Unproven. Proposer IDs are strings checked for membership, not authenticated principals.

Why it remains unproven: possession of a node ID is not proof of identity.

Why that reason remains unaddressed: no key material, certificate/workload identity, verifier or authorization policy engine exists in this layer.

Required missing architecture: workload/service identities; authenticated transport; key lifecycle; authorization policy; revocation; audit linkage from identity to vote and receipt.

### WebAssembly equivalence

Unproven. The new distributed state machine executed in Python only.

Why it remains unproven: no Wasm binary implementing the same state transitions was compiled or executed.

Why that reason remains unaddressed: there is no Wasm build target or cross-runtime conformance runner for this module.

Required missing architecture: Wasm implementation/build; canonical serialization shared with Python; reference-vector corpus; differential runner; deterministic numeric/byte rules; browser and non-browser Wasm qualification.

## 5. Current standards comparison

### WebAssembly

The W3C WebAssembly Core Specification published as a Candidate Recommendation Draft on 11 September 2026 describes WebAssembly as a safe, portable low-level code format and specifies binary encoding, validation and execution semantics. R03 has an explicit binary boundary, but the distributed implementation is not yet a Wasm implementation. Conformance therefore remains a missing execution layer rather than a documentation task.

### NIST zero trust

NIST SP 800-207 states that physical or network location must not itself confer implicit trust and that authentication and authorization are discrete functions before access. SP 800-207A further emphasizes application/service identities in cloud-native environments. R03 coordinate identity therefore cannot substitute for authenticated peer identity. The present proposer string is intentionally classified as insufficient for that role.

### Consensus comparison

The present majority directory implements only a bounded crash-fault replication experiment. It does not claim Raft, Paxos or Byzantine consensus semantics. A production agreement claim requires a specified ordering/consensus protocol plus independent-process execution and history verification.

## 6. Architectures not present

The remaining deficiencies map to concrete absent components rather than vague 'future work':

1. authenticated peer transport;
2. independent process/host runtime;
3. leader/election or other total-order consensus mechanism;
4. Byzantine quorum/signature layer;
5. durable WAL and restart recovery;
6. concurrent history/linearizability checker;
7. network partition/reorder/duplication fault harness;
8. service/workload identity and authorization layer;
9. key rotation/revocation machinery;
10. Wasm build and differential conformance runner;
11. physical waveform channel/DAC-ADC or SDR qualification path;
12. hyper-toroidal >3D conformance and conditioning harness.

## 7. Qualification conclusion

R03 has advanced from a local coordinate conflict gate to an executable three-replica majority-commit directory with evidence-gated transitions, generation fencing, stale-replica repair and fail-closed quorum loss. Those statements are supported by the executed 12-test suite and execution receipt.

The run does not establish that desynchronization is mathematically impossible. It establishes a narrower and defensible result: within the implemented crash-fault model, a majority can establish one tested canonical coordinate record, one unavailable replica can later be repaired, and loss of a majority prevents the runtime from claiming canonical state.

Everything beyond that boundary remains explicitly classified by the architecture required to test it.