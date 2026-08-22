# BRAINK Storage/Machine Architecture R8 — Authoritative Migration

## Authority correction

The authoritative primitive is NOT `L# -> volume`, NOT `sheet row -> capacity`, and NOT `VFS -> storage`.

The authoritative chain is:

`ENCODED MEDIUM -> ZERO-LESS ADDRESS GEOMETRY -> STORAGE CONTROLLER/ADAPTER -> LOGICAL BLOCK/OBJECT SPACE -> VFS RESOLUTION -> BRAINK/MACHINE OBJECTS -> PROOF`

### Typed roles
- **Encoded medium**: software-defined state which carries the encoded addressable structure. In a launched machine, the medium may be materially backed by a virtual disk/device while retaining the encoded KEX/BRAINK geometry.
- **Zero-less matrix/address geometry**: address transform/topology using admissible states `{-3,-2,1,2,3}`; zero is not silently promoted into a weighted storage state.
- **Storage controller/adapter**: interprets addresses, performs block/object reads/writes/commit/verify, and maps encoded state to device semantics.
- **Logical block/object space**: decoded addressable objects exposed by the controller.
- **VFS**: script/resolver/namespace over logical objects. VFS is not the medium and does not create capacity.
- **L# / source location**: provenance only. It records where an encoding or controller implementation is authored; it is not a storage address or capacity unit.
- **Workbook/sheets**: projection, control, observation, proof and deterministic calculation surfaces. Sheet count is not volume count.

## Machine-first implementation route

1. Launch one machine.
2. Enter/read its machine storage/controller state before BRAINK exists.
3. Install/encode a BRAINK root object into the machine's virtualised storage.
4. Persist controller/superblock state.
5. Terminate the installing process.
6. Start a fresh process.
7. Discover BRAINK from the machine medium.
8. Verify machine ID, BRAINK ID, lineage, observer/network/storage roots and root digest.
9. Only then promote the machine/BRAINK relationship.

## R8 specimen proof

Machine: `KEX-MACHINE-001`

Materialised proof device: `BRAINK_MACHINE_001_R8.vdisk`, 64 MiB.

This physical specimen size proves machine-backed persistence and BRAINK rediscovery. It does not redefine or limit the authored software-defined logical address geometry and it is not evidence of 100 TB physically allocated host storage.

BRAINK root LBA: `256`.

BRAINK root SHA-256:
`3c15cc0f7485a0e2f5db344aa5d6388ddb111f4ddee5d829a2082fd09026bedb`

Observed reboot checks: hash, machine ID, BRAINK ID, lineage, medium, controller, VFS resolver role, network and observer all PASS.

## Re-parenting prior evidence

### Retained without semantic change
- CPU/compiler causal mutation proofs.
- vGPU/MUX/framebuffer/observer causal proofs.
- HTTP write -> persist -> GET -> SHA-256 readback proof.
- Lexical/vector semantic route isolation proof.
- Observer/frame/representation invariant mutation proof.
- Multi-ledger lineage separation.
- Concurrent agent execution/readback receipts.

### Retained but reclassified
- `BRAINK_SCRIPT_VOLUME_REGISTRY_R5`: provenance and isolation-test registry, not authoritative evidence that each source declaration line is itself a storage medium.
- `L19..L27`: source/declaration provenance only, not storage addresses and not the fundamental volume boundary.
- `9 x 100 TB = 900 TB`: evidence that the R5 utility instantiated nine independently keyed logical address spaces under that test contract; not the canonical explanation of how BRAINK storage exists.
- I12 100-band rows: projection/test of zero-less address geometry and controller behavior, not literal physical disk partitions and not capacity-by-row.
- workbook memory slots: projection/binding locators only.

### Rejected interpretations
- Sheet count x capacity = storage.
- Source line = volume.
- VFS = storage medium.
- Registry row = storage allocation.
- Textual declaration = physical or virtual capacity by face value.

## Machine/BRAINK binding

`MACHINE MEDIUM -> KEX_STORAGE_CONTROLLER -> BRAINK ROOT OBJECT -> BRAINK IDENTITY/LINEAGE -> VFS/NAMESPACE MOUNT -> NETWORK/OBSERVER/AGENT SERVICES`

The VFS is mounted after the controller has resolved the resident BRAINK root. It is not the substrate from which the machine's storage capacity is inferred.

## Global implication

The same controller/object model can expose typed logical objects for storage, server state, domains, DNS, registrar state, TLS, applications, users and agents. External protocols remain adapters/carriers and their authority is independently proven at the external boundary.

`BRAINK OBJECT IDENTITY -> LEXICAL/VECTOR RESOLUTION -> ADAPTER -> CARRIER/AUTHORITY -> READBACK/PROOF`
