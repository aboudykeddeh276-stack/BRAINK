# REPORT 03 — Deficiency / Missing-Architecture Matrix

Date: 2026-09-22

This matrix distinguishes five questions for each remaining deficiency:

1. What remains unproven?
2. Why is it unproven?
3. Why does that reason remain unaddressed?
4. Why does the unaddressed condition continue to exist?
5. What executable architecture is required to close it?

| Unproven property | Why unproven | Why the cause remains unaddressed | Why it continues to remain | Architecture not present | Explicit closure requirement |
|---|---|---|---|---|---|
| Multi-host ToT consensus | Tests do not schedule independent networked peers | current ToT is a fixed-membership kernel/API, not a peer service | adding sockets alone would not create total-order/election safety | authenticated peer transport, leader/view/ballot mechanism, replicated WAL, catch-up | run >=3 independent processes under loss/delay/reorder/partition; verify one committed history |
| Dynamic membership | `reconfigure_membership` fails closed | no old/new quorum transition protocol exists | naive member replacement can create disjoint quorums | joint-consensus/equivalent configuration state machine | execute add/promote/remove/restart under partitions with persisted configuration index |
| Byzantine safety | logical votes are not independent cryptographic signatures | threat model remains crash-fault | a compromised member can bypass an in-process equivocation lock | node key identities, signed votes, BFT quorum/view-change protocol | adversarial double-sign/forgery/view-change test suite and formal fault bound |
| Linearizable coordinate service | no concurrent network clients | directory is a deterministic state machine, not a served consensus API | root equality does not prove real-time operation ordering | consensus-backed API, revision/read-index semantics, concurrency history checker | Jepsen-style or equivalent concurrent histories under partitions and leader changes |
| Independent durable replicas | local journal/WAL boundaries are single-filesystem | no per-node durable storage process exists | one host/disk loss can remove all local evidence | replicated WAL, snapshots, backup/restore, disk-failure model | crash at every write boundary + host/disk replacement recovery |
| Layer 1–9 distributed transaction | nine-stage receipts run in one process | no cross-process transaction coordinator exists | local causal hashes do not solve distributed partial commit | durable transaction journal, stage ownership, distributed fencing, recovery coordinator | kill processes between every stage and recover without double-apply or false seal |
| Physical/external Layer 7 actuation | qualification actuator is controlled/in-memory | no production carrier adapter is included | external APIs/devices have provider-specific ambiguity/idempotency | real target adapter, auth, timeout/retry, idempotency, independent observer | execute in isolated Linux bridge/container/VM/provider sandbox and verify post-state externally |
| Independent Layer 8 observation | local observer reads adapter-owned state | no separate observation authority | executor and observer can share one bug/failure domain | independent observer process/data source and evidence identity | compare executor receipt with independently acquired state under corrupted executor results |
| IEEE 802.1Q bridge behavior | no Ethernet dataplane executed | R2 reconciles manifestations, not frames | control-plane state cannot prove MAC/VLAN forwarding | NIC/namespace/OVS/eBPF bridge dataplane, FDB, VLAN, loop prevention | packet-level conformance/fault tests |
| RFC 8785 cross-language hashes | Python sort-key JSON only | JCS not implemented | deterministic Python output is not interoperable canonicalization proof | RFC 8785 canonicalizer + cross-language vectors | Python/JS/Swift/Rust produce identical canonical bytes and digests |
| Authenticated provenance | local evidence is hash chained but self-issued | no trusted signer/verifier separation | same workload can manufacture its own unsigned receipt | in-toto/SLSA envelope, builder identity, signing, verifier, publication | external verifier validates provenance over exact artifact digests |
| Formal consensus safety | finite tests only | no formal state model tied to implementation | tests cannot enumerate all asynchronous schedules | TLA+/PlusCal/other model, invariants and code mapping | model-check election/log/membership/fault states and retain counterexample corpus |
| Long-run lifecycle | tests last milliseconds | no compaction/migration/soak layer | aging faults require time/history | retention, compaction, schema migration, rolling upgrade, repair automation | multi-day soak with version migration, journal growth, restart and repair |
| Production performance | no representative distributed workload | performance target/SLO not bound to architecture | local microtests would give misleading numbers | workload model, telemetry, multi-client load, network/storage realism | publish p50/p95/p99, throughput and resource use under healthy/faulted load |

## Architecture classes still absent

### A. Distributed consensus runtime
Peer transport, persistent terms/votes, leader/equivalent ordering authority, replicated log, conflict repair, safe membership transition, snapshot transfer and network partition handling.

### B. Distributed transaction/recovery plane
Durable run identity, per-stage ownership, stage fencing, recovery coordinator, replay semantics, compensation policy and cross-process evidence sealing.

### C. Production actuator/observer plane
Real target adapters, independent observers, credentials/authority, idempotency contracts, timeout ambiguity handling, provider-specific readback and rollback/compensation.

### D. Identity/trust plane
Service/node identities, enrollment, authentication, authorization policy, key lifecycle, rotation/revocation and optional hardware-backed attestation.

### E. Interoperability plane
RFC 8785 or another standard canonical encoding, YANG/RFC 8342/8345 projection if management interoperability is required, cross-language schemas and compatibility tests.

### F. Provenance plane
Standard attestation envelope, trusted builder identity, signing/verifying separation, artifact subject digests and external verifier output.

### G. Formal verification plane
Machine-readable protocol model, declared safety/liveness properties, bounded fault model, model checking and traceability to runtime operations.

The remaining deficiencies therefore do not persist because the report needs more prose. They persist because these mechanisms are not present to execute.
