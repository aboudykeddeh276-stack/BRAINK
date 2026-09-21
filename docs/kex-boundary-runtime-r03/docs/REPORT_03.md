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