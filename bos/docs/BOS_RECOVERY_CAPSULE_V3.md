# BOS-RECOVERY-CAPSULE-v3

## Authority chain

```text
CapTable
  -> generation-pinned ExtentLease
  -> trusted hardware ReadReceipt
  -> complete geometry-bound Merkle root
  -> signed Capsule v3
  -> membership-bound quorum certificate
  -> freshness / parent / state-root checks
  -> private VerifiedCapsule
  -> inactive A/B root slot
  -> durability boundary
  -> Hardgate anti-rollback advance
  -> redundant selector publication
  -> atomic in-memory active-slot release store
```

No safe public method accepts a raw capsule for root publication.

## Canonical capsule encoding

All integers are unsigned big-endian values. Raw Rust structure layout is never
used as wire or disk encoding.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 8 | `BOSCAPS\x03` |
| 8 | 4 | fixed encoded length: 912 |
| 12 | 2 | format version: 3 |
| 14 | 2 | SHA-256 algorithm identifier |
| 16 | 2 | Ed25519 algorithm identifier |
| 18 | 2 | zero reserved field |
| 20 | 16 | cluster identifier |
| 36 | 16 | volume identifier |
| 52 | 8 | membership epoch |
| 60 | 8 | consensus view/term |
| 68 | 8 | capsule sequence |
| 76 | 32 | parent capsule hash |
| 108 | 32 | parent state root |
| 140 | 32 | data Merkle root |
| 172 | 32 | state-manifest root |
| 204 | 32 | authenticated extent-map root |
| 236 | 32 | derived authoritative state root |
| 268 | 8 | starting LBA |
| 276 | 8 | logical block count |
| 284 | 4 | logical block size |
| 288 | 8 | total state bytes |
| 296 | 32 | membership root |
| 328 | 2 | signer bitmap |
| 330 | 6 | zero reserved bytes |
| 336 | 576 | nine fixed Ed25519 signature slots |

The proposal digest covers bytes `0..328` under the domain
`BOS/CAPSULE-PROPOSAL/v3`. The full capsule hash covers all 912 bytes under the
domain `BOS/CAPSULE-FULL/v3`.

## Recovery invariants

| Code | Enforced rule |
|---|---|
| `INV-REC-01` | Capability lease exists before the backend read is called |
| `INV-REC-02` | Handle generation and exact LBA geometry remain pinned through completion |
| `INV-REC-03` | Read data is accepted only with a trusted exact-completion receipt |
| `INV-REC-04` | Every requested byte is committed to a domain-separated Merkle root |
| `INV-REC-05` | Every counted vote belongs to a distinct authorized public key |
| `INV-REC-06` | Quorum policy has the required intersection for its declared fault model |
| `INV-REC-07` | Capsule epoch, sequence, parent hash, and parent root match Hardgate state |
| `INV-REC-08` | State root is recomputed from all signed structural roots and geometry |
| `INV-REC-09` | Only the private `VerifiedCapsule` type enters the root-store path |
| `INV-REC-10` | Inactive root data is flushed before Hardgate authority advances |
| `INV-REC-11` | Selector publication is last and represented by one atomic slot value |
| `INV-REC-12` | Any pre-publication failure leaves the previous selector active |

## Quorum rules

Crash-fault policy requires:

```text
2k > n
```

Byzantine policy with declared maximum `f` requires:

```text
n >= 3f + 1
2k - n > f
```

The implementation verifies signatures independently with each manifest key.
It does not use a shared mesh secret and does not count duplicate signer slots.

## Linux-hosted ring seal

The Linux adapter performs:

```text
IORING_SETUP_R_DISABLED
-> register 32 aligned fixed buffers
-> register one pre-opened fixed file
-> permanently allow READ_FIXED only
-> allow IOSQE_FIXED_FILE only
-> allow IORING_REGISTER_ENABLE_RINGS only
-> enable ring
```

This is the Linux transition backend. Native BOS still requires a separate
`BOS-NATIVE-NVME-01` implementation over controller submission/completion
queues, MSI-X, DMA pages, IOMMU mappings, and reset authority.
