# REPORT 03 — Integrated Missing Engineering Layer

## ToT Safety Kernel, Distributed Coordinate Directory, Layer-2 Reconciler, Waveform Geometry Boundary, Fault Injection, Evidence and Deficiency Closure

**Authority context:** BRAINK × KEX × IL-LLM × Observer²  
**Date:** 2026-09-21  
**Base Report 03 receipt root:** `65b449db4287472bec35d539cf9a8f67fc8122edfa3ff8f7f2f092a210dd4d03`  
**Geometry source:** `enterprise/waveform_geometry_r40.py`

---

## 1. Executive result

This report is downstream of implementation and execution.

The base Report 03 engineering layer remains intact:

1. ToT safety kernel;
2. distributed coordinate directory;
3. Layer-2 desired/observed reconciler;
4. deterministic conflict/fork detection;
5. fault injection;
6. evidence receipts;
7. bounded performance measurements;
8. explicit deficiency mapping.

Its observed result remains **24/24 passing tests**, a **14-packet verified evidence chain**, **1 committed / 31 blocked** in a 32-way coordinate collision, persistent restart heads, tamper detection and an explicitly surfaced replica fork.

The waveform-geometry delta added a new executable boundary:

`A/B symbolic projection -> toroidal geometry -> computational modulation descriptor -> verified demodulation -> geometry receipt -> Layer-2 observed-state root`.

The isolated geometry falsification suite produced **15/15 passing tests**. A direct exhaustive execution recovered all **256 byte values** and produced a minimum measured radial magnitude of **7.000322698965479** with configured theoretical lower bound **7.0** for `R=10, r=3`.

Three claims from the proposed geometry design did not survive falsification unchanged:

1. **Phase endpoint alias:** `phi=(byte/255)*2π` maps byte 0 to phase 0 and byte 255 to phase `2π`. Those phases are physically equivalent modulo `2π`. The executable codec now uses 256 bin centres: `2π(byte+0.5)/256`.
2. **Zero-crossing claim:** `R>r` guarantees that the toroidal radial magnitude is bounded below by `R-r`; it does **not** guarantee that every Cartesian coordinate is non-zero, does not establish a non-singular execution tensor, and does not prove electrical/RF zero-crossing immunity.
3. **Curvature-only integrity:** the original demodulator reconstructed bytes solely from phase, so arbitrary x/y/z or amplitude distortion was not automatically detectable by “curvature tracking.” The implemented receiver now binds payload, geometry samples and modulation descriptors to commitments and verifies reconstructed amplitude, phase and frequency against expected geometry.

Therefore the strongest current claim is:

> The geometry layer is a deterministic computational codec and integrity representation. It is not evidence of an analog carrier, RF/optical modulation, jitter suppression, a zero-free physical signal, WebAssembly execution, or higher-dimensional manifold stability.

---

## 2. Canonical execution chain

The governing path is now:

```text
SYMBOLIC / A-B CONTENT
        ↓
BYTE BOUNDARY
        ↓
WAVEFORM GEOMETRY PROJECTION
        ↓
GEOMETRY COMMITMENT
        ↓
COMPUTATIONAL MODULATION DESCRIPTOR
        ↓
RECEIVER VERIFY + DEMODULATE
        ↓
PAYLOAD / GEOMETRY RECEIPT
        ↓
MEMORY-IN-MOMENT
        ↓
DATA CLASS / AUTHORITY
        ↓
ToT SAFETY KERNEL
        ↓
LAYER-2 RECONCILER
        ↓
DISTRIBUTED COORDINATE DIRECTORY
        ↓
LEDGER / PROOF
```

Geometry does not receive mutation authority. A valid geometry frame becomes evidence for an observed state. Shared state still requires the existing authority, capability, ToT and Layer-2 gates.

---

## 3. ToT safety kernel

The ToT kernel remains the transitive safety authority for node-to-node proposals.

A proposal binds source node, target node, source state root, expected target entry root, logical sequence, operation, payload root, authority, hop path and attestation.

The kernel checks:

- source/target existence;
- source-state freshness;
- target-entry freshness;
- authority equality;
- source `tot.propose` capability;
- target operation capability;
- source-origin path;
- bounded hop count;
- cycle absence;
- target-not-already-visited;
- monotonically increasing source sequence;
- replay absence;
- external attestation result.

Only after those checks pass is replay state persisted and ledger evidence appended.

Observed base result: valid proposals authorize; invalid attestation, stale state, replay, cycles and hop violations fail closed.

Geometry integration does not bypass this kernel.

---

## 4. Distributed coordinate directory

The coordinate directory stores logical identity independently of carrier endpoints.

Each entry includes:

- node ID;
- non-zero logical coordinate;
- generation;
- sequence;
- logical identity;
- state root;
- template root;
- mutable endpoints;
- capabilities;
- authority;
- health;
- parent entry root;
- tombstone state.

Every mutation is compare-and-swap against the current entry root.

Replica merge semantics remain:

```text
same root                         -> identical
remote lower sequence             -> stale
same sequence + different root    -> CONFLICT
higher sequence + proven ancestry -> apply
higher sequence + ancestry gap    -> CONFLICT
```

The base falsification run discovered and corrected the equal-sequence fork bug. Fork detection remains evidence of divergence, not consensus.

---

## 5. Layer-2 reconciler

Layer-2 compares desired control identity with observed runtime state.

Immutable fields remain node ID, logical coordinate, logical identity, template root and authority. Drift in an immutable field is failed rather than repaired.

Mutable state includes state root, endpoints, capabilities and health.

Outcomes remain:

- `REGISTERED` for a locally verified bootstrap admitted by explicit bootstrap authority;
- `FIXED_POINT` when observed and directory state agree;
- `RECONCILED` when exact mutable drift is ToT-authorized, CAS committed and read back.

The geometry module produces a verified observation state root. That root is not itself a directory mutation command.

---

## 6. Waveform geometry engineering layer

### 6.1 A/B codec boundary

The A/B adapter is lossless and intentionally simple:

- `A = bit 0`;
- `B = bit 1`;
- exactly eight A/B symbols per byte.

It is a symbolic projection. It is not claimed as compression, physical line coding or a replacement for the binary substrate.

Observed exhaustive test: all 256 possible byte values encode and decode without loss.

### 6.2 Toroidal projection

Configured defaults:

```text
major radius R = 10
minor radius r = 3
R > r > 0
```

For payload byte `b`, the corrected phase is:

```text
phi = 2π (b + 0.5) / 256
```

For sample index `i` in `n` samples:

```text
theta = 2π (i + 0.5) / n
```

Coordinates:

```text
x = (R + r cos(phi)) cos(theta)
y = (R + r cos(phi)) sin(theta)
z = r sin(phi)
```

The implementation also records standard torus Gaussian and mean surface curvatures.

The radial distance from origin is bounded below by `R-r`. With the default parameters that is 7.0.

This is the exact valid result behind the “zero” discussion. The code does not claim that x, y or z cannot cross zero.

### 6.3 Modulation descriptor

Each geometry sample is projected into a computational descriptor containing:

- amplitude = radial magnitude;
- phase = corrected byte phase;
- frequency = base frequency adjusted by a bounded dimensionless curvature term;
- Gaussian curvature;
- source geometry-sample commitment.

This descriptor is metadata inside software. No DAC, RF transmitter, optical carrier, SDR chain or analog channel was used.

### 6.4 Receiver verification

The receiver:

1. checks sample ordering and finite numeric values;
2. decodes phase bins back to bytes;
3. verifies payload SHA-256;
4. verifies A/B-token SHA-256;
5. regenerates expected toroidal geometry;
6. checks geometry root;
7. checks modulation root;
8. checks per-sample geometry commitments;
9. compares phase, amplitude and frequency against reconstructed expected values;
10. emits a geometry receipt root.

This closes the error in the original proposed design where coordinate distortion could be described as detectable even though the demodulator ignored coordinates.

---

## 7. Geometry falsification results

### WG-00 — Phase endpoint alias

**Original hypothesis:** byte-to-phase mapping using `byte/255 * 2π` provides 256 unique physical phases.

**Observed:** false. Byte 0 gives 0 and byte 255 gives `2π`, which are identical modulo `2π`.

**Correction:** use 256 bin centres.

**State:** `FALSIFIED_AND_PATCHED`.

### WG-01 — Geometry/modulation distortion

Coordinate distortion and modulation-amplitude/frequency distortion are rejected by the commitment-and-reconstruction path.

**State:** `PASS_BOUNDED`.

This proves local software integrity detection for the encoded descriptor. It does not prove channel equalization or physical error correction.

### WG-02 — Zero-byte boundary

A payload containing byte 0 remains fully decodable. With `R=10,r=3`, radial magnitude remains above 7.

**State:** `PASS_BOUNDED`.

What is proven is:

```text
radial_magnitude >= R-r > 0
```

What is not proven is:

```text
x != 0
y != 0
z != 0
physical_signal_amplitude != 0
metric_tensor has no singularity under arbitrary transforms
```

### WG-03 — Exhaustive byte recovery

All 256 byte values were passed through geometry/modulation/demodulation and recovered exactly.

Observed direct execution:

```text
recovered bytes = 256
status          = VERIFIED
minimum radius  = 7.000322698965479
lower bound     = 7.0
```

### WG-04 — Random payload

A seeded 4096-byte random payload round-tripped in the isolated falsification suite.

### WG-05 — Tamper/non-finite/reordering

The test suite rejects:

- metadata hash mismatch;
- sample reordering;
- NaN/non-finite modulation values;
- phase distortion large enough to alter the decoded payload;
- amplitude distortion;
- frequency distortion.

---

## 8. Execution evidence

### Base Report 03

```text
tests                              24/24 PASS
evidence ledger                    14 packets / chain verified
coordinate contention              1 commit / 31 blocked
replica fork                       explicit conflict
restart heads                      preserved
directory tamper                   detected
invalid ToT attestation            state unchanged
```

### Waveform geometry isolated execution

```text
tests                              15/15 PASS
all-byte roundtrip                 PASS
seeded random roundtrip            PASS
phase alias falsifier              PASS / corrected
coordinate distortion              rejected
amplitude distortion               rejected
frequency distortion               rejected
sample reorder                     rejected
non-finite values                  rejected
metadata tamper                    rejected
Layer-2 observation bridge         PASS
```

The artifact host later began returning tool-level runtime failures when the combined suite was re-invoked. That failure is not counted as test evidence either way.

A clean repository-hosted verifier has therefore been added at:

`scripts/kex-ci/verify_waveform_geometry_report03.py`

and a dedicated hosted workflow at:

`.github/workflows/report03-waveform-geometry.yml`.

The clean hosted run was attempted as GitHub Actions run `35590761525`, but the job completed with failure before executing any steps. GitHub returned `steps=[]`, and the job log blob was unavailable (404). That is classified as an infrastructure pre-step failure, not as geometry source/test failure. Therefore source-level geometry→ToT→Layer-2 integration remains implemented but not promoted as clean-run evidence.

---

## 9. Current standards comparison

This is a comparison, not a certification statement.

### W3C WebAssembly Core Specification 3.0

The current W3C publication describes WebAssembly 3.0 as a safe, portable low-level code format. Report 03 currently stops before that boundary.

**Aligned:** verified payload bytes can be handed to a future explicit Wasm ABI.

**Absent:** Wasm module validation, linear-memory schema, host-import capability policy, module signature, execution receipt and Wasm fault tests.

**Conclusion:** the phrase “binary-constrained substrate (WASM / Buffer)” is architectural intent, not observed Report 03 execution.

### IEEE 754-2019

The active IEEE floating-point standard covers binary/decimal floating-point formats and arithmetic.

**Aligned:** the geometry layer rejects non-finite values and uses bounded finite float operations.

**Absent:** a cross-platform deterministic transcendental profile. Python/libm sine and cosine results have not been proven bit-identical across target runtimes.

**Conclusion:** local geometry roots are runtime-bounded evidence. Cross-language/cross-architecture deterministic geometry requires stronger numeric rules.

### RFC 8785 JCS

Report 03 uses sorted compact Python JSON for internal hashes.

**Absent:** I-JSON enforcement and exact JCS numeric/string serialization.

**Conclusion:** not RFC 8785 conformant.

### RFC 8949 deterministic CBOR

No deterministic CBOR geometry/waveform frame exists.

**Conclusion:** not implemented.

### NIST SP 800-207

The geometry channel does not receive trust because of network location or because a frame validates geometrically. Shared mutation still requires authority/capability and ToT/Layer-2 gates.

**Gap:** production workload identity and credential lifecycle remain absent.

### POSIX.1-2024

The geometry layer does not change the Report 03 durability boundary. Existing local persistence uses fsync/atomic replacement patterns, but physical power-loss behavior remains unproven.

---

## 10. What advanced

1. Byte-to-geometry mapping is now executable and reversible.
2. The 0/255 phase endpoint collision was identified and removed.
3. The valid zero-related invariant is now precise: non-zero radial magnitude under `R>r`.
4. Geometry samples have independent commitments.
5. Modulation descriptors have a deterministic root.
6. Receiver reconstruction verifies amplitude, phase and frequency against expected geometry.
7. Corrupted geometry cannot be promoted merely because phase still decodes.
8. A verified geometry result can be represented as a Layer-2 observed-state root.
9. Geometry remains below ToT/capability authority instead of becoming an alternative mutation path.
10. The report now distinguishes computational waveform metadata from physical signal transmission.

---

## 11. What remains unproven

The following claims are not supported by current evidence:

- continuous analog transmission;
- RF/optical carrier generation;
- elimination of electrical zero-crossing dead zones;
- jitter mitigation;
- clock recovery;
- phase-noise tolerance under a physical channel;
- BER improvement;
- forward error correction;
- multi-host geometry transport;
- higher-dimensional hyper-toroidal stability;
- cross-language bit-identical floating geometry;
- WebAssembly execution;
- deterministic binary geometry wire format;
- production-scale performance;
- physical hardware acceleration;
- automatic correction of corrupted geometry;
- consensus or finality derived from geometry.

---

## 12. Why the remaining geometry claims are unproven

### D13 — Cross-platform deterministic geometry

**What advanced:** one deterministic Python implementation generates and verifies toroidal samples and local roots.

**What remains unproven:** identical geometry roots across Python versions, operating systems, CPU architectures, JavaScript, Swift, Rust, Wasm and GPU implementations.

**Why:** geometry roots currently include floating values derived from transcendental functions.

**Why the why remains unaddressed:** no system-wide deterministic transcendental/fixed-point numerical profile was resident or required by the original Report 03 coordinate algorithms.

**Why it remains:** a cryptographic commitment is useful only if independent implementations can reproduce the exact committed representation.

**Architecture not present:**

- fixed-point or specified deterministic numeric representation;
- correctly-rounded/specified trig implementation;
- float canonicalization rule;
- cross-language test vectors;
- architecture/runtime conformance suite.

### D14 — Physical waveform transmission

**What advanced:** software computes amplitude/phase/frequency descriptors.

**What remains unproven:** those descriptors produce a useful real physical waveform.

**Why:** no waveform was emitted or sampled.

**Why the why remains unaddressed:** Report 03 operates at the symbolic/control plane; no SDR/DAC/ADC/radio/optical hardware path is attached.

**Why it remains:** software numbers are not measurements of an electromagnetic channel.

**Architecture not present:**

- DAC/modulator or SDR transmitter;
- carrier/sampling specification;
- channel model or physical test channel;
- receiver/ADC;
- synchronization and carrier recovery;
- calibrated measurement instrumentation.

### D15 — Jitter and phase-noise mitigation

**What advanced:** exact local descriptor distortion can be detected.

**What remains unproven:** reduced network jitter, clock jitter, phase noise or packet-delay variation.

**Why:** none of those phenomena were injected or measured.

**Why the why remains unaddressed:** the modulation descriptor has no physical clock-domain or packet-timing control loop.

**Why it remains:** error detection and jitter control are different mechanisms.

**Architecture not present:**

- monotonic cross-event measurement model;
- receiver jitter buffer or CDR/PLL equivalent;
- phase-noise model;
- delay-variation test harness;
- correction/controller law with stability evidence.

### D16 — Higher-dimensional manifold scaling

**What advanced:** 3D toroidal projection is executable.

**What remains unproven:** 4D+ hyper-toroidal projection with stable invertibility and useful transmission semantics.

**Why:** no higher-dimensional transform is implemented.

**Why the why remains unaddressed:** dimensional extension changes the projection, conditioning, serialization and inverse mapping rather than merely adding coordinates.

**Why it remains:** a 3D success does not prove numerical or topological stability in higher dimensions.

**Architecture not present:**

- n-dimensional manifold contract;
- dimension-aware inverse;
- conditioning/error bounds;
- dimensional projection to transport symbols;
- high-dimensional falsification vectors.

### D17 — Wasm execution boundary

**What advanced:** verified bytes exist at the receiver boundary.

**What remains unproven:** validated Wasm execution driven by those bytes.

**Why:** there is no Wasm module or runtime adapter in this path.

**Why the why remains unaddressed:** execution authority was deliberately kept separate from transport/geometry authority.

**Why it remains:** accepting arbitrary verified bytes as executable code would collapse validation and execution into an unsafe remote-code path.

**Architecture not present:**

- explicit Wasm module/data distinction;
- versioned ABI;
- linear-memory frame schema;
- module validator;
- signature/provenance binding;
- capability-scoped host imports;
- execution/readback receipt.

### D18 — Error correction

**What advanced:** many classes of distortion are detected.

**What remains unproven:** corrupted frames can be corrected without retransmission.

**Why:** commitments detect errors; they do not reconstruct lost information.

**Why the why remains unaddressed:** no redundancy/error-code design was included in the proposed geometry codec.

**Why it remains:** integrity and error correction are separate information-theoretic functions.

**Architecture not present:**

- FEC/erasure coding or retransmission policy;
- symbol-loss model;
- correction capability bounds;
- corrupted-block recovery tests;
- residual error-rate evidence.

### D19 — Compact wire representation

**What advanced:** the logical frame has deterministic semantics.

**What remains unproven:** efficient wire density.

**Why:** the current in-memory descriptor carries Python floating-point structures per byte.

**Why the why remains unaddressed:** this pass targeted correctness/falsification before packing.

**Why it remains:** an unpacked software object can cost far more than the original payload.

**Architecture not present:**

- fixed-width or variable deterministic binary schema;
- quantization contract;
- deterministic CBOR/custom frame decision;
- endianness/version rules;
- compression and overhead benchmark.

### D20 — Symbol error margin

**What advanced:** corrected phase bins are unique in the ideal numerical model.

**What remains unproven:** reliable byte recovery under phase noise, frequency offset and sampling error.

**Why:** the tested receiver uses exact software values except deliberate fault injections.

**Why the why remains unaddressed:** there is no channel probability/noise model or calibrated physical link.

**Why it remains:** 256 phase bins imply finite decision margins; real noise can cross bin boundaries.

**Architecture not present:**

- symbol/noise probability model;
- phase/frequency offset estimator;
- decision-threshold analysis;
- BER/SER measurement;
- coding/interleaving strategy;
- synchronization preamble.

---

## 13. Original Report 03 deficiencies still open

Waveform geometry does not close the existing D01-D12 boundaries:

- D01 multi-host coordinate finality;
- D02 production ToT credentials;
- D03 Byzantine tolerance;
- D04 remote anti-entropy/liveness;
- D05 R40 physical/runtime actuation;
- D06 destructive power-loss durability;
- D07 secure remote transport;
- D08 standards canonical serialization;
- D09 distributed scale/performance;
- D10 safe directory-history compaction;
- D11 connected-service writer failover;
- D12 target R40 deployment/readback.

None of those become solved because geometry is present.

---

## 14. Architecture present versus absent

### Present and executed

- base ToT safety kernel;
- base distributed coordinate directory;
- base Layer-2 reconciler;
- replay/cycle/hop checks;
- coordinate CAS and fork detection;
- fixed-point convergence;
- restart/tamper tests;
- A/B byte projection;
- toroidal 3D projection;
- corrected 256-bin phase map;
- radial lower-bound enforcement;
- Gaussian/mean torus curvature calculation;
- geometry commitments;
- modulation commitments;
- exhaustive byte roundtrip;
- distortion/non-finite/reorder rejection;
- geometry-to-Layer-2 observation bridge.

### Source implemented, clean hosted verification attempted but externally blocked

- geometry observation → ToT → Layer-2 directory reconciliation in the repository verifier;
- combined original Report 03 regression plus geometry tests.

Hosted verification attempt: run `35590761525`; job `106304374178`; no steps executed; logs unavailable. This does not falsify the source and does not prove it either.

### Absent

- physical carrier;
- jitter controller;
- FEC;
- channel synchronization;
- binary geometry wire standard;
- deterministic cross-platform trig;
- higher-dimensional manifold engine;
- Wasm ABI/executor binding;
- multi-host geometry transport;
- consensus/finality;
- production identity/PKI;
- R40 deployed runtime proof.

---

## 15. Final evidence classification

```text
BASE_REPORT03_TESTS                  = 24/24 PASS
BASE_EVIDENCE_LEDGER                 = 14 PACKETS / VERIFIED
BASE_FORK_FALSIFIER                  = DEFECT FOUND + PATCHED

WAVEFORM_GEOMETRY_SOURCE             = IMPLEMENTED
WAVEFORM_GEOMETRY_ISOLATED_TESTS     = 15/15 PASS
ALL_256_BYTES_ROUNDTRIP              = PASS
MIN_RADIAL_MAGNITUDE_OBSERVED        = 7.000322698965479
THEORETICAL_RADIAL_BOUND             = 7.0
ORIGINAL_0_255_PHASE_MAPPING         = FALSIFIED
CORRECTED_PHASE_BIN_MAPPING          = IMPLEMENTED
COORDINATE_DISTORTION_DETECTION      = PASS
AMPLITUDE_DISTORTION_DETECTION       = PASS
FREQUENCY_DISTORTION_DETECTION       = PASS
NONFINITE/ORDER/TAMPER_REJECTION     = PASS
GEOMETRY_LAYER2_OBSERVATION_BRIDGE   = PASS

GEOMETRY_TO_TOT_LAYER2_RECONCILE     = IMPLEMENTED / HOSTED CI PRE-STEP FAILURE
ANALOG_TRANSMISSION                  = NOT PROVEN
ZERO_FREE_PHYSICAL_SIGNAL            = NOT PROVEN
JITTER_MITIGATION                    = NOT PROVEN
HIGHER_DIMENSIONAL_SCALING           = NOT PROVEN
WASM_EXECUTION                       = NOT IMPLEMENTED
FEC                                  = NOT IMPLEMENTED
MULTI_HOST_GEOMETRY_TRANSPORT        = NOT EXECUTED
PRODUCTION_DEPLOYMENT                = NOT PROVEN
```

**Bounded engineering intent:** achieved for the executable software geometry layer and its local falsification.

**Global distributed/physical-waveform intent:** not achieved; the missing supporting architectures are listed explicitly above.
