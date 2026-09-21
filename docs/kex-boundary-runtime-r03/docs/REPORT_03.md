# Report 03 — Symbolic-to-Binary Boundary Engineering

## Scope
This report records an executable engineering slice for the missing boundary: IL-LLM supplies semantic identity/grammar, KEX carries symbolic state/relations, and an explicit adapter produces bytes only when a target substrate requires them.

## What advanced
The build contains a typed immutable node definition, deterministic definition fingerprint, independent node instances, ToT action gating, coordinate conflict detection, Layer-2 reconciliation, a strict A/B byte codec, HTML projection, and fault-injection tests. The runtime has no GitHub dependency.

## Observed qualification
9 tests passed locally. Tests cover empty/non-empty round trips, truncation, non-canonical encodings, header corruption, coordinate conflict, reconciliation mismatch, undeclared action rejection, instance isolation and HTML projection. The browser concept surface also executes the encoder in native JavaScript.

## What remains unproven and why

### Linux block-device execution
Not proven because this artifact does not run a Linux ublk qualification environment. Linux documents ublk as a generic userspace block-device framework. Required proof is a real Linux run creating a ublk device, formatting it, mounting it, performing I/O, unmounting/remounting, and checking persistence/recovery.

### Persistent sparse-volume semantics
Not proven because the current codec is a representation layer, not a filesystem, allocator, journal or durability mechanism. Required architecture is LBA mapping, backing-store allocation, ordering/barriers, recovery, integrity and concurrent I/O tests.

### Distributed consensus
Not proven because the coordinate directory is a local deterministic conflict gate, not consensus. Required architecture is membership, authority/quorum or equivalent, epochs, partition handling, replay protection and durable log semantics.

### Cryptographic security
Not proven because SHA-256 fingerprints are integrity identifiers, not a cryptographic protocol, and A/B is not a cryptographic primitive. Required architecture is a threat model, key lifecycle, domain separation and authenticated construction with vectors.

### WebAssembly execution
Not proven because the current browser surface is JavaScript. Required proof is compiling the core state machine to Wasm and comparing its outputs against the reference implementation across a conformance corpus.

## Architectures not present
Linux ublk/NBD adapters; filesystem formatter/mounter; crash-consistent journal; distributed consensus service; Byzantine fault model; production key management; authenticated encryption; Wasm production build; multi-host qualification; sustained I/O benchmark suite; hardware-specific NVMe/SATA qualification.

## Why the remaining why remains unaddressed
Each remaining claim requires an executable architecture and an observation trace. A document cannot substitute for the absent kernel adapter, persistence model, distributed authority, cryptographic construction, portable binary runtime or operational instrumentation. Those are explicit missing components, not unexplained hardware bottlenecks.

## Boundary conclusion
IL-LLM semantic meaning -> KEX symbolic representation -> explicit target adapter -> substrate representation, with the reverse path substrate representation -> adapter -> KEX reconstruction -> IL-LLM semantic resolution.

This establishes a reproducible reference boundary. It does not claim that the missing production subsystems already exist.

# Report 03 Extension — Waveform Geometry Manifold Engineering

## Executed result

A waveform-geometry boundary adapter was implemented and executed against an 11-case falsification suite. Observed result: 11/11 PASS after one deliberately useful test-design correction. The run exercised all 256 byte values, torus-constraint distortion, phase corruption, the 0.297 jitter boundary, coordinate generation fencing, Layer-2 reconciliation, and independent-directory divergence.

The geometry layer now uses 256 half-bin phase centres, phi=2*pi*(byte+0.5)/256, rather than phi=2*pi*byte/255. This change is required because the original mapping assigns byte 0 to phase 0 and byte 255 to phase 2*pi; under physical phase equivalence modulo 2*pi those endpoints alias. The original mapping was therefore not injective at the waveform boundary.

## What advanced

The implementation now has an executable toroidal byte embedding, explicit Gaussian curvature calculation for the standard torus, manifold constraint verification, geometric modulation, inverse phase decoding, payload SHA-256/CRC integrity checks, a 0.297 observed-jitter admission bound, generation-fenced coordinate state, and deterministic Layer-2 MATERIALISE/REPLACE/NOOP reconciliation.

For R=10 and r=3, the Euclidean norm floor is R-r=7. The exhaustive 256-byte test confirmed the generated sample norms respect that floor.

Distortion injection now changes an actual coordinate and recomputes the torus equation; deformation is rejected as TORUS_CONSTRAINT_VIOLATION. Phase corruption that changes the recovered byte is rejected by payload integrity.

## What was falsified

**The original 0..255 phase equation is not a lossless physical phase mapping.** Byte 0 and byte 255 occupy phases separated by exactly 2*pi and therefore alias modulo one phase cycle. The half-bin 256-state mapping repairs this local defect.

**A non-zero vector norm does not mean every coordinate is non-zero.** The torus can maintain norm >= 7 while x, y, or z approaches or crosses zero. Therefore the norm floor is a geometric radius invariant, not proof that floating-point zero, zero crossing, or ambiguity has disappeared from every representation.

**Non-zero toroidal magnitude does not make distributed desynchronization mathematically impossible.** The executed falsifier created two independent coordinate directories with valid non-zero geometry but different payload generations. Without communication/consensus they diverged. Geometry can provide deterministic state identity and error-detection structure; it does not by itself solve asynchronous distributed agreement.

**0.297 is presently an enforced engineering bound, not a derived synchronization theorem.** The adapter accepts observations at or below the configured limit and rejects 0.298. No executed derivation currently proves that 0.297 is a universal physical jitter threshold or that values below it guarantee distributed convergence.

**The supplied scalar expression is not a curvature tensor.** The implementation records Gaussian curvature of the standard torus. A tensor claim would require an explicit metric, connection/second fundamental form, tensor components, coordinate convention, and validation of the chosen geometric quantity.

## Why the remaining claims remain unproven

### Absolute spatial state across independent nodes

Unproven because a coordinate is only absolute relative to a shared coordinate definition, epoch, payload identity and committed authority. Two isolated nodes can hold internally valid but mutually different states.

Why the why remains unaddressed: the waveform layer has no independent peer transport, replicated commit log, clock/epoch authority, authenticated node identity, or partition-recovery protocol.

Required architecture: independently failing peer processes; authenticated transport; durable ordered log; quorum/consensus protocol; generation/epoch fencing; replay protection; partition injection; restart/rejoin; state-root comparison and repair.

### Instant curvature realignment

Unproven because the implemented verifier detects off-manifold coordinates but does not infer the unique intended source coordinate from arbitrary deformation and does not actuate a remote repair.

Why the why remains unaddressed: error detection and error correction are different mechanisms. No geometric error-correcting code, nearest-valid-codeword rule, confidence radius, remote actuator, or post-repair observer exists.

Required architecture: defined error model; redundant geometric code; correction radius; ambiguity handling; correction receipt; Layer-2 actuator; independent re-observation.

### Continuous transmission eliminating packet boundaries

Unproven because the current Python objects model waveform parameters; they do not drive or sample an analog channel. The binary/Wasm boundary still serializes finite representations.

Why the why remains unaddressed: there is no DAC/ADC, SDR, audio/RF transport, sampled channel model, symbol clock, carrier recovery, channel coding, or measured BER/FER path.

Required architecture: physical or simulated channel; sample rate; pulse shaping; synchronization/pilot design; noise/jitter model; receiver estimator; BER/FER and latency measurements.

### Floating-point ambiguity elimination

Unproven because transcendental torus coordinates are evaluated with finite floating-point arithmetic. The radius offset avoids the origin for the complete vector but does not remove rounding, cancellation, quantization, NaN/Inf behavior, or platform-dependent numerical edges.

Why the why remains unaddressed: no fixed-point representation, interval arithmetic, error budget, cross-runtime conformance corpus, or numerical proof exists.

Required architecture: canonical numeric format; bounded-error analysis; quantization specification; deterministic rounding rules; cross-Python/Wasm/native vectors; adversarial boundary tests.

### Higher-dimensional hyper-toroidal scaling

Unproven because only a 3D standard torus embedding was executed.

Why the why remains unaddressed: no n-dimensional coordinate/metric definition, decoder, conditioning analysis, phase-allocation rule, or dimensional-noise model exists.

Required architecture: explicit T^n representation; injective symbol mapping; metric and invariants; dimensional decoder; complexity bounds; conditioning/noise analysis; exhaustive and randomized high-dimensional conformance tests.

## Standards comparison

Raft remains the relevant comparison for distributed state agreement: consensus requires independent servers to agree on an ordered replicated log, and practical Raft includes leader election, log replication, safety and membership-change machinery. A toroidal coordinate representation can be payload/state carried by such a protocol, but it does not replace those agreement mechanics.

WebAssembly remains the binary execution boundary comparison. Its current core specification defines a safe, portable low-level code format with validation and execution semantics. The waveform adapter must therefore be compiled and checked against reference vectors before Wasm equivalence can be claimed.

NIST SP 800-207/207A remains relevant to peer identity: no location or geometric coordinate should itself grant trust. Production peer votes and reconciliation actions require authenticated service/device identities and authorization.

## Evidence boundary

Executed locally: 11/11 waveform geometry/falsification tests PASS.

Published into the BRAINK R03 runtime: waveform geometry engine, modulator, demodulator, integrity-bearing boundary frame, waveform coordinate directory, waveform Layer-2 reconciler, and regression/falsification tests.

Not established by this run: physical analog transmission, multi-host consensus, mathematical impossibility of desynchronization, universal 0.297 synchronization law, floating-point ambiguity elimination, automatic arbitrary-deformation correction, or hyper-toroidal >3D stability.

This distinction is intentional: the geometry layer is now stronger because the claims that survived execution are separated from the claims the execution actually disproved.
