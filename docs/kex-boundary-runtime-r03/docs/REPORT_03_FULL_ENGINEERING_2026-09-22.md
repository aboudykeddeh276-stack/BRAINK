# REPORT 03 — KEX/BRAINK Executed Engineering Baseline

Date: 2026-09-22

## Executive result

Report 03 now spans four executable layers rather than one architectural description: the ToT evidence gate, replicated coordinate directory and Layer-2 reconciler already resident in the R03 baseline; the waveform-geometry boundary and its falsification suite; and a new fsync-backed authenticated peer baseline executed in this tranche.

The new durable-peer suite executed 9/9 PASS. It exercised majority commit, one-peer outage, quorum loss, restart/WAL replay, signed-payload tampering, unknown identity, WAL corruption, entry reordering and duplicate delivery.

The result advances durability and message provenance, but it does not silently relabel a three-object crash-fault prototype as production consensus.

## 1. ToT safety kernel

The existing ToT kernel remains the fail-closed evidence boundary. Actions outside the declared set are rejected; subjects and evidence are mandatory; accepted actions produce immutable evidence receipts and a deterministic receipt root.

What advanced: safety-sensitive mutation has an explicit evidence path instead of being an unreceipted side effect.

What remains unproven: cryptographic append-only ledger persistence across independent machines.

Why: the ToT receipt collection itself remains process-local in the current R03 implementation.

Why the why remains unaddressed: the new WAL work persists peer log entries, not the complete ToT receipt chain as an independently replicated ledger.

Missing architecture required: a durable receipt WAL or content-addressed ledger; independent replicas; checkpoint/root publication; restart replay; corruption proofs; retention/compaction rules; receipt-to-commit causal binding.

## 2. Distributed coordinate directory

The existing directory provides majority-gated coordinate mutation, generation fencing, previous-value hash chaining, crash-fault availability with one of three replicas absent, and fail-closed canonical reads after quorum loss. Layer-2 repair can replay a stale replica to the canonical generation.

What advanced: coordinate state is no longer merely a mutable dictionary. The implementation has a tested quorum boundary and explicit stale-generation behavior.

What remains unproven: linearizable concurrent writes across independent networked hosts.

Why: proposal generation and acknowledgement still occur under a single coordinating Cluster/Directory object. There is no independently elected leader or distributed total-order protocol.

Why the why remains unaddressed: implementing sockets without an ordering protocol would move bytes between processes but would not solve competing-leader histories. The missing object is consensus semantics, not merely transport syntax.

Missing architecture required: independent peer processes; leader election; term/vote persistence; log matching; commit-index propagation; conflicting suffix repair; randomized election timing; membership changes; partitionable transport; concurrency model checking.

## 3. Durable authenticated peer baseline

New implementation: `src/durable_peer_runtime.py`.

Each peer owns an append-only JSONL WAL. Accepted entries are flushed and fsynced before acknowledgement. Restart reconstructs the peer log from the WAL. Messages carry an authenticated envelope. Payload mutation after signing is rejected, as is an unknown sender. Index gaps and duplicate delivery are rejected.

Observed suite: 9/9 PASS.

What advanced:

- fsync-backed peer log persistence;
- restart replay;
- authenticated message envelope baseline;
- crash-fault majority commit;
- duplicate and reorder rejection;
- explicit WAL corruption failure.

### Falsification findings

The authenticated-envelope test falsifies the proposition that an unauthenticated coordinate string is sufficient peer provenance. State identity and peer identity are separate concerns.

The restart test falsifies the earlier deficiency that all replicated state necessarily disappears with the Python object. The peer log now crosses a process-style reconstruction boundary through disk.

The corruption test also prevents an opposite overclaim: the current WAL detects malformed JSON records, but it does not yet prove recovery from torn writes, valid-but-bit-corrupted records, or malicious historical rewriting.

### What remains unproven

**Real independent-host transport.** Unproven because the executed peers remain Python objects and authenticated envelopes are direct method calls.

Why unresolved: no TCP/QUIC/Unix-socket peer service, framing protocol, timeout state machine, retransmission policy, connection identity binding or network namespace harness exists.

Required architecture: independent executables; authenticated transport; framed protocol; request IDs; deadlines; retry/idempotency contract; controllable proxy/netns fault layer; asymmetric partition, loss, duplication, reorder and delay tests.

**Leader election and total ordering.** Unproven because the caller names the leader and the cluster derives the next index from currently visible histories.

Why unresolved: no RequestVote/AppendEntries-equivalent state machine, persistent term/vote, election timeout or leader lease exists.

Required architecture: a specified crash-fault consensus protocol; persistent term/vote; election state; log matching; majority commit rule; old-leader fencing; leadership-transfer tests; concurrent proposal tests.

**Linearizability.** Unproven because concurrent independent clients were not executed against independently scheduled leaders.

Why unresolved: the current harness serializes `commit()` calls.

Required architecture: concurrent client driver; operation history capture; linearizability checker; randomized schedules; repeated partition/heal histories.

**Safe dynamic membership.** Unproven because node IDs are fixed at construction.

Why unresolved: no membership entries are part of the replicated log.

Required architecture: learner/catch-up state; joint or otherwise proven configuration transition; promotion/removal fencing; stale removed-node rejection; rejoin identity rules.

**Byzantine tolerance.** Unproven. HMAC authentication prevents unauthenticated modification but does not stop a legitimate compromised peer from equivocating.

Why unresolved: this is deliberately a crash-fault baseline, not a BFT protocol.

Required architecture if BFT is in scope: explicit fault bound; public/verifiable node signatures or equivalent authenticated identities; quorum certificates; view changes; equivocation evidence; adversarial double-sign tests. Do not label a majority crash-fault protocol BFT-safe.

**Hardware-rooted/Hardgate identity.** Unproven because the current keys are deterministic software keys derived for the test cluster.

Why unresolved: no Secure Enclave/TPM/attestation provider is wired into peer enrollment.

Required architecture: hardware-backed key generation/storage where supported; attestation verification; enrollment authority; rotation; revocation; recovery; explicit fallback policy for platforms without that hardware.

**Torn-write-safe durability.** Unproven because fsync proves an attempted durability boundary, not atomic record recovery under every crash point.

Why unresolved: JSONL has no record checksum, length framing, commit marker or snapshot/WAL truncation protocol.

Required architecture: framed records with checksum; atomic metadata; crash-at-every-write-boundary harness; valid-prefix recovery; snapshot creation/install; compaction; backup/restore; corruption repair policy.

## 4. Waveform geometry boundary

The R03 baseline includes deterministic toroidal byte embedding, modulation/demodulation, geometry verification, payload integrity, generation fencing and Layer-2 waveform reconciliation.

The earlier falsification remains binding: `phi = 2*pi*byte/255` aliases byte 0 and byte 255 under phase periodicity. The corrected half-bin 256-state mapping avoids that endpoint alias locally.

The norm floor `R-r=7` is a vector-magnitude property for R=10,r=3. It is not proof that every component is nonzero and is not proof that distributed desynchronization is impossible. Two isolated nodes can still possess valid nonzero geometry while holding different generations.

The 0.297 value is therefore retained as an enforced engineering admission bound where configured, not promoted into a universal synchronization law without a derivation and channel evidence.

Missing architecture for physical waveform claims: DAC/ADC or SDR/simulated sampled channel; symbol clock; carrier/phase recovery; pulse shaping; channel coding; measured BER/FER; jitter/noise sweep; independent transmitter and receiver; calibration and clock-drift experiments.

## 5. Layer-2 reconciler

Layer 2 now has two demonstrated roles: deterministic desired/current reconciliation in the baseline directory and stale-replica repair in the replicated state model.

What remains unproven: actuation against an external VM/container/device followed by independent observation of the changed target.

Why unresolved: current reconciliation mutates/repairs runtime-owned replica state, not a separately administered substrate.

Required architecture: actuator interface; target authentication; idempotency key; generation/fencing token; timeout/retry semantics; observer interface; postcondition verification; compensating action; receipts binding requested action, target, before-state, after-state and evidence hash.

## 6. Current standards comparison

Raft is the comparison boundary for the next consensus tranche. Raft separates leader election, log replication, safety and membership changes; the current KEX peer baseline has persistence and authenticated delivery but does not yet implement those consensus mechanics.

etcd is the operational durability comparison. Production recovery includes WAL/snapshot behavior, quorum-loss semantics and cluster restore. The current KEX WAL has fsync/replay and malformed-record detection but lacks snapshots, revision management, compaction and full disaster recovery.

NIST SP 800-207/207A is the identity boundary: network location, ownership or a coordinate must not itself confer trust. The HMAC envelope advances explicit peer authentication locally, while service/device authorization, enrollment and hardware attestation remain separate work.

WebAssembly Core is the binary execution comparison. The current W3C candidate specification defines validation and execution semantics for the portable low-level format. KEX/Wasm equivalence therefore requires reference vectors executed through both the Python/native model and a Wasm implementation, comparing byte outputs, error behavior and deterministic state roots.

## 7. Deficiency closure matrix

| Surface | Executed evidence | Remaining deficiency | Architecture absent | Closure evidence required |
|---|---|---|---|---|
| ToT safety | evidence-required receipts | durable replicated receipt ledger | receipt WAL/replicas/checkpoints | restart/corruption/replica tests |
| Coordinate directory | quorum + generation fencing | networked linearizable ordering | independent consensus peers | concurrent partition histories |
| Peer durability | fsync + restart replay | torn-write/snapshot recovery | framed WAL + snapshots | crash-at-write-boundary suite |
| Peer identity | HMAC tamper rejection | hardware/service identity lifecycle | attestation/enrollment/revocation | forgery/rotation/revocation suite |
| Layer 2 | replica repair | external substrate actuation | actuator + independent observer | real target convergence receipt |
| Waveform | local geometry round trip | physical channel claims | sampled/physical channel | BER/FER/jitter measurements |
| Wasm boundary | specification baseline only | execution equivalence | Wasm implementation + runner | differential conformance corpus |
| BFT | none claimed | malicious-member safety | BFT protocol | equivocation/view-change suite |

## 8. Observed conclusion

Report 03 has advanced beyond the prior in-memory boundary. The new tranche adds durable fsync-backed peer logs, restart recovery and authenticated message envelopes, with 9/9 executed fault tests passing. Combined with the existing ToT, replicated directory, Layer-2 and waveform work, this creates a materially stronger executable baseline.

The remaining deficiencies are not being renamed into completion. The decisive missing architecture is now: independently executing peers over a fault-injectable authenticated transport; a fully specified total-order consensus state machine; torn-write-safe WAL/snapshot recovery; dynamic membership; external Layer-2 actuation/observation; hardware/service identity lifecycle; and differential Wasm execution.

Those are the structures required before claims of production multi-host consensus, mathematically impossible desynchronization, hardware-rooted provenance, BFT safety, physical waveform synchronization or cross-runtime equivalence can be supported by observed evidence.
