# BRAINK Encoded-Medium Storage Architecture — Authoritative Reconciliation v1

## Authoritative primitive

`Encoded Script Runtime Structure = Software-Defined Storage Medium`

The source text is the authoring/manufacturing representation. Source-line identifiers are provenance only. They are not storage addresses.

## Canonical hierarchy

`EncodedScript -> SoftwareStorageMedium -> ZerolessMatrixAddressGeometry -> BRAINK/KEXStorageController -> VirtualBlock/ObjectSpace -> VFSInterpretation -> LogicalObjects`

The machine boot invariant is:

`BRAINKRoot_i ∈ EncodedMedium_i`

BRAINK is not attached after construction. The BRAINK root is already encoded as a resolvable object/state inside the medium.

## Typed roles

- `L#`: source provenance.
- Matrix/vector coordinates: encoded address geometry.
- Adapter/controller: translation, allocation, read/write, reconstruction, lineage and integrity.
- Logical block/object space: decoded controller-level objects.
- VFS: filesystem/resolver interpretation over logical objects.
- Sheets/workbook rows: observer/readback projection where used.
- Network/IP/HTTP: carrier projection.
- Registry: instrumentation/proof unless separately demonstrated to be an encoded-medium primitive.

## Rejected architecture

`SourceLine -> Volume -> VFS -> BRAINK`

## Machine model

`M_i = (EncodedMedium_i, Controller_i, BRAINKRoot_i, Compute_i, Memory_i, GPU_i, Network_i, Observer_i, Proof_i)`

with `BRAINKRoot_i ∈ EncodedMedium_i`.

## Evidence reconciliation

Preserve observed execution/readback, zero-less geometry behaviour, lineage/address separation, network-carrier distinction, persistence/integrity receipts, concurrency and observer evidence where directly demonstrated.

Demote or reject interpretations that depended on `line -> volume -> VFS`, including `L#` as storage address, rows as literal volumes, VFS as substrate, and the 900 TB logical-address-space experiment as proof that the fundamental encoded medium had already been reconstructed.
