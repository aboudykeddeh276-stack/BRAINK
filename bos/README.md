# BOS Authenticated Cold-Recovery Substrate

Architect: **A. Keddeh**  
Repository sector: `BRAINK/bos`  
Protocol: `BOS-RECOVERY-CAPSULE-v3`

This workspace implements the authority-bearing part of BOS cold recovery as an
additive Rust sector. It does not replace the existing BRAINK Swift, Python, or
runtime surfaces.

## What is implemented

- fixed-capacity `no_std` capability table with generation-tagged handles;
- immutable extent leases established before any raw read;
- fixed 4 KiB recovery blocks with complete-range validation;
- domain-separated, geometry-bound SHA-256 Merkle roots;
- canonical 912-byte Capsule v3 encoding and strict decoding;
- distinct Ed25519 voting keys and strict signature verification;
- crash-fault and Byzantine quorum-intersection policy validation;
- membership-root, state-root, extent-root, parent-root, and anti-rollback checks;
- private `VerifiedCapsule` authority token;
- ordered inactive-slot → flush → Hardgate advance → selector → flush commit path;
- deterministic in-memory executable proof harness;
- Linux `io_uring` adapter using registered files, registered aligned buffers,
  disabled-ring setup, and a permanent opcode/register allowlist;
- Linux file-backed A/B root-store adapter with redundant selector records.

## Explicitly not claimed complete

- physical TPM 2.0 signing, quoting, NV-counter advancement, and event-log replay;
- direct native NVMe SQ/CQ ownership outside Linux;
- IOMMU/VFIO binding receipts;
- device reset, timeout, and abort completion under a failed controller;
- end-to-end no-bounce-buffer proof on target hardware;
- power-cut testing against a dedicated physical disk;
- live multi-node networking and durable no-double-vote ledgers.

Those remain target-hardware E4/E5 gates. The present workspace is an E2/E3
compilable and testable substrate, subject to CI evidence.

## Run

```bash
cd bos
cargo fmt --check
cargo test --workspace --all-targets
cargo clippy --workspace --all-targets -- -D warnings
cargo run -p bos-recovery-demo
cargo check -p bos-cap --target x86_64-unknown-none
cargo check -p bos-recovery --no-default-features --target x86_64-unknown-none
```

The demo emits one JSON receipt only after the full safe verification path has
produced a private `VerifiedCapsule` and committed the inactive root slot.

## Crates

| Crate | Boundary |
|---|---|
| `bos-cap` | Authoritative generation-tagged capabilities and extent leases |
| `bos-recovery` | Capsule v3, Merkle, quorum, Hardgate/root-store contracts, recovery gate |
| `bos-linux-hosted` | Restricted `io_uring` read backend and file A/B store |
| `bos-recovery-demo` | Deterministic executable proof harness; not production authority |
