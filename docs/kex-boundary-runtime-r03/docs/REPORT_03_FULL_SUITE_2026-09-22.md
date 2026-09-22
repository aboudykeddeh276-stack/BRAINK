# REPORT 03 — BRAINK/KEX Full Software Suite, Kernel and Layer 1–9 Reconciliation

Date: 2026-09-22

## Observed advancement

The R03 baseline now contains an executable composition root (`BRAINKSoftwareKernel`), the evidence-gated ToT safety kernel, majority-backed distributed coordinate directory, toroidal waveform boundary utilities, the existing Layer-2 reconciler, and a deterministic Layer 1–9 causal reconciliation chain.

The Layer 1–9 implementation assigns explicit executable boundaries: L1 ingress, L2 identity, L3 coordinate, L4 geometry, L5 propagation, L6 consensus, L7 execution, L8 observation and L9 evidence. Every layer output is hash-bound to the preceding layer output. A changed upstream layer invalidates every downstream layer rather than silently preserving stale derived state.

Observed Layer 1–9 qualification: **9/9 PASS**. Executed cases covered complete-chain construction, deterministic replay, payload sensitivity, skipped-layer rejection, incorrect upstream-root rejection, stale-generation rejection, downstream invalidation, incomplete-pipeline rejection and zero-generation rejection.

The repository also retains the earlier executed R03 surfaces: distributed coordinate majority/failure tests, durable peer WAL/authentication tests, waveform geometry falsification tests, and ToT/evidence machinery. These are separate evidence classes and are not silently promoted into stronger claims.

## What advanced

1. **Full software composition root.** The current R03 components are callable through one kernel object rather than existing only as adjacent modules.
2. **Layer 1–9 causal chain.** Layer outputs are deterministic and predecessor-bound. Skipping a layer or presenting the wrong predecessor root fails closed.
3. **Downstream invalidation.** Replacing an upstream generation removes all downstream derived states. This closes the stale-derived-state defect inside the local model.
4. **Evidence boundary.** Layer 9 is explicitly evidence state, not an informal log label.
5. **Directory/Layer integration.** Coordinate identity and quorum state feed the higher reconciliation chain rather than being treated as interchangeable with it.

## What was falsified or constrained

The nine-layer abstraction is **not proof that OSI Layers 1–7, hardware Layer 1, or a physical network were executed**. The names are KEX/BRAINK reconciliation boundaries implemented in Python. Physical/link/network/transport behavior requires actual corresponding adapters and independent observations.

A deterministic hash chain does **not** make distributed agreement automatic. It detects causal mismatch; it does not elect a leader, serialize concurrent writers across independent machines, repair arbitrary partitions, or establish Byzantine agreement.

Layer 4 geometry remains a representation/error-detection mechanism. It does not replace transport or consensus. Layer 5 currently records the propagation boundary but is not an SDR/DAC/ADC or independently networked waveform channel. Layer 7 records Python execution; it is not yet evidence of Wasm/native equivalence.

## Remaining unproven concepts and causal deficiencies

### Independent-process consensus

**Unproven:** multiple independently scheduled processes/hosts maintain one linearizable committed history under concurrent proposals, delay, loss, duplication, partition, crash and restart.

**Why:** current majority-directory tests and durable-peer tests do not implement a complete leader-election/log-replication protocol across independent processes.

**Why the why remains unaddressed:** there is no persistent term/vote state, election timer, leader lease/authority rule, AppendEntries-equivalent log matching, commit-index propagation, snapshot installation or joint membership transition.

**Absent architecture required:** independent peer services; fault-injectable transport; persistent term/vote/log state; election and leadership protocol; log conflict truncation/repair; committed-index rules; snapshot/install-snapshot; safe membership transition; partition/heal and concurrent-writer harness.

### Physical Layer-1 / real propagation

**Unproven:** toroidal symbols survive an actual physical or sampled communication channel and reconstruct with measured error characteristics.

**Why:** geometry and modulation are currently software parameter models.

**Why the why remains unaddressed:** no DAC/ADC, SDR, audio/RF channel, sampled channel simulator, symbol clock, carrier recovery, FEC, BER/FER measurement or hardware loopback is connected.

**Absent architecture required:** transmitter/receiver adapter; sample representation; clock/pilot design; noise/jitter injection; channel coding; synchronization; measured BER/FER/latency; physical or reference simulated loopback.

### Layer-2 through Layer-5 external protocol realization

**Unproven:** the reconciliation layers interoperate with Ethernet/Wi-Fi/IP/TCP/QUIC or another declared real protocol stack.

**Why:** current layers are internal deterministic state boundaries, not packet/frame implementations.

**Why the why remains unaddressed:** no NIC/TUN/TAP adapter, frame codec, routing table, socket transport or packet capture verification is present in this R03 execution path.

**Absent architecture required:** explicit protocol choice; adapter per boundary; packet/frame reference vectors; namespace/network sandbox; packet capture; loss/reorder/MTU/fragmentation tests; independent endpoint interoperability.

### Authenticated identity and Hardgate claims

**Unproven:** node identity is cryptographically bound to a hardware root and remains secure through enrollment, rotation, compromise and revocation.

**Why:** HMAC/authenticated-envelope work proves possession of configured shared secret material, not silicon identity.

**Why the why remains unaddressed:** no TPM/Secure Enclave attestation, certificate chain, workload identity, revocation service or key lifecycle is connected.

**Absent architecture required:** hardware-backed key generation where available; attestation evidence; certificate/workload identity; authorization policy; rotation/revocation; replay protection; compromised-node tests.

### Durable crash consistency

**Unproven:** acknowledged commits survive arbitrary process/power failure at every write boundary without torn or partially durable state.

**Why:** fsync-backed WAL execution is stronger than memory-only state but does not by itself prove atomic multi-record recovery.

**Why the why remains unaddressed:** no checksummed segment framing, atomic metadata protocol, snapshot/WAL coordination or kill-at-every-write-position harness has been executed.

**Absent architecture required:** framed/checksummed WAL; atomic commit metadata; snapshot format; recovery algorithm; truncated/torn-write corpus; process-kill injection at every persistence boundary; backup/restore verification.

### Byzantine safety

**Unproven:** safety with malicious/equivocating peers.

**Why:** the present directory is explicitly a crash-fault majority model.

**Why the why remains unaddressed:** no Byzantine protocol, quorum certificates, view-change mechanism or equivocation proof exists.

**Absent architecture required:** first define the Byzantine threat model and fault bound. If required, implement an appropriate authenticated BFT protocol, certificates, view changes and adversarial peer harness. Crash-fault majority code must not be renamed BFT.

### Wasm/native equivalence

**Unproven:** the same KEX reference vectors produce identical state roots and rejection behavior in Python/native and WebAssembly implementations.

**Why:** the current execution engine is Python.

**Why the why remains unaddressed:** no Wasm implementation of the kernel/reconciler and no differential conformance runner exist in this R03 slice.

**Absent architecture required:** Wasm module implementing canonical serialization/hash/reconciliation; explicit imports/exports; reference vectors; Wasm runtime harness; differential outputs; malformed-input tests; deterministic numeric policy.

### Layer 8 independent observation

**Unproven:** observation is independent of the component that performed the mutation.

**Why:** local directory state is currently used as the observed state.

**Why the why remains unaddressed:** no separate observer process, external actuator, telemetry channel or postcondition probe is wired.

**Absent architecture required:** actuator adapter; independent observer; correlation/operation IDs; timeout/retry/idempotency rules; pre/post state receipts; disagreement escalation.

### Layer 9 tamper-evident external evidence custody

**Unproven:** evidence remains independently verifiable after compromise of the running process or repository.

**Why:** hashes/receipts are generated by the same software authority and stored with the project.

**Why the why remains unaddressed:** no external transparency log, independently held signing key, timestamp authority or replicated evidence custodian is connected.

**Absent architecture required:** signed receipt envelope; independent key custody; append-only transparency store; timestamping; inclusion/consistency proofs; external verification utility.

## Current standards comparison

**Raft:** the present majority and causal-root mechanics overlap with some replicated-state safety concerns, but Raft additionally defines leader election, replicated log behavior and safety rules. Until those mechanics are implemented and exercised across independent peers, the R03 directory is not labelled a complete Raft implementation.

**WebAssembly:** the W3C WebAssembly Core specification defines a portable low-level code format with decoding, validation and execution semantics. R03 therefore treats Wasm as a separate executable conformance target; Python success is not evidence of Wasm equivalence.

**NIST SP 800-207 / 800-207A:** coordinates and network position are not authentication. Production peer admission and Layer 2–9 actions require authenticated identities and authorization policy; service identity is a separate concern from the coordinate manifold.

## Evidence summary

New in this tranche:
- Layer 1–9 reconciler implementation.
- Full software composition kernel.
- Layer 1–9 fault/causality tests.
- Full-kernel integration tests committed for repository/CI execution.
- Layer 1–9 observed receipt: 9/9 PASS.

Observed locally in this tranche: **9/9 Layer 1–9 tests PASS**.

The full-kernel integration test file has been committed but is **not represented here as locally executed evidence**, because the available execution environment could not directly materialize the complete repository dependency set from GitHub. It must therefore remain pending repository CI or a complete checkout execution rather than being invented as a passing result.

## Conclusion

R03 now has an executable nine-layer causal reconciliation model and an integrated software-kernel composition surface. The important unresolved boundary has moved outward: independent process/host execution, complete consensus ordering, real protocol/physical transport, hardware-backed identity, crash-consistent persistence, independent observation, external evidence custody and Wasm differential execution.

Those are not renamed as future architecture. They are the exact missing substrates preventing the corresponding claims from being proven today.
