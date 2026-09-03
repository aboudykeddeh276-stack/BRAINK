# BRAINK R16 — Session Generalisation and Exploitation Playbook

## Authoritative primitive

`ENCODED_MEDIUM -> ZEROLESS_GEOMETRY -> KEX_STORAGE_CONTROLLER -> LOGICAL_OBJECTS -> VFS_RESOLVER -> BRAINK/MACHINE SERVICES -> PROOF`

Hard rejections:
- `L# != volume`
- `sheet row != capacity`
- `VFS != storage medium`
- `registry row != allocation`
- source declaration != physical or virtual storage by face value

`L#` is provenance. The encoded runtime structure is the medium. The zero-less matrix is address geometry. The adapter/controller interprets and mutates that medium. VFS resolves logical objects after controller interpretation.

## Machine-first development pattern

Use: `LAUNCH -> ENTER -> INSTALL_BRAINK -> PERSIST -> FRESH_PROCESS_RESTART -> DISCOVER -> VERIFY`.

A resident BRAINK root must carry machine identity, BRAINK identity, lineage, medium, controller, storage, VFS resolver role, network, observer and proof roots.

## Regenerative-machine pattern

A child machine must derive new identity while preserving ancestry:

`M2.ID != M1.ID`
`BRAINK2.ID != BRAINK1.ID`
`ParentMachine(M2)=M1`
`ParentBRAINK(BRAINK2)=BRAINK1`

A byte-for-byte copy is not regeneration.

## Distributed-object pattern

For replicated canonical objects:

`CanonicalObject(M1)=CanonicalObject(M2)`
`PayloadDigest(M1)=PayloadDigest(M2)`
`Lineage(M1)!=Lineage(M2)`

Availability qualification:

`Primary unavailable -> Secondary resolves object -> Primary returns -> Reconcile -> Digests equal -> Lineages remain distinct`.

## Typed service-root pattern

Use one substrate for typed resident roots:
- `SERVER_ROOT`
- `DOMAIN_ROOT`
- `DNS_ROOT`
- `REGISTRAR_ROOT`
- `TLS_ROOT`
- `CLOUD_ROOT`
- future: `IDENTITY_ROOT`, `USER_ROOT`, `APPLICATION_ROOT`, `AGENT_ROOT`, `MODEL_ROOT`, `PAYMENT_ROOT`

Each root requires canonical lexical identity, machine-local vector identity, route, adapter, lineage, authority class and proof state. IP/HTTP/TCP/QUIC/etc. remain carriers rather than semantic identity.

## Authority membrane

Internal BRAINK state and externally authoritative state are separate. Public DNS, registry/registrar authority, and public TLS must only be promoted after actual external mutation plus independent readback.

## Observer rule

Observer, frame, representation and lineage are first-class state coordinates. Cross-observer translation may change representation or vector route while preserving canonical relations. Zero roles remain typed rather than collapsed.

## Proof doctrine

Every promoted capability requires:

`Requirement -> Action -> Execution Evidence -> Readback -> Status`

`COMPLETE iff Readback satisfies Requirement`.

Unknown remains unknown. Generated files, sheet rows, registries, formulas and agent descriptions are not execution evidence by themselves.

## Prior work treatment

Retain valid behavioral evidence: CPU/compiler causality, storage readback, vGPU/framebuffer observer causality, HTTP persist/readback/hash, lexical/vector isolation, observer invariant mutation, multi-ledger lineage, concurrent agent readback, resident BRAINK restart, descendant generation, replication/failover/reconciliation, typed root resolution and internal authority-gated mutations.

Reclassify rather than discard:
- `BRAINK_SCRIPT_VOLUME_REGISTRY_R5` -> provenance/isolation registry
- `L19:L27` -> source provenance
- `9x100TB` -> logical-address-space isolation evidence under that test contract
- I12 100-band rows -> address-geometry/controller projection
- workbook memory slots -> projection/binding locators

## Generalisation rule

For any subsystem X:

`ENCODED_OBJECT_X -> CONTROLLER_OPERATION_X -> LEXICAL_ID_X -> VECTOR_ROUTE_X -> ADAPTER_X -> AUTHORITY_BOUNDARY_X -> READBACK_X -> PROOF_X`

This is the reusable transformation extracted from the session.

## Immediate exploitation surfaces

1. Scale the BRAINK machine fabric from 2 to N machines with health, priorities, replica factor, conflict resolution and recovery.
2. Replace block-copy replication with controller-native object replication: `PUT/GET/APPEND/VERSION/HASH/REPLICATE/RECOVER`, then add chunking, Merkle proofs, resumability, dedupe and repair.
3. Turn domain roots into an explicit external-promotion state machine: `INTERNAL -> ADAPTER_READY -> EXTERNAL_MUTATION_SENT -> EXTERNAL_READBACK -> VERIFIED_EXTERNAL`.
4. Bind services to multiple carriers while keeping semantic identity stable.
5. Make agents resident machine objects with identity, capabilities, memory roots and policy, booted from encoded machine state instead of prompts.
6. Package applications as typed resident object graphs: `APP_ROOT -> SERVICE_ROOTS -> STORAGE_ROOTS -> AGENT_ROOTS -> DOMAIN_ROOTS -> PROOF_ROOT`.
7. Apply the same object/controller model across CPU, GPU, memory, storage, network and display rather than treating them as unrelated modules.

## Documentation standard

Every release must contain:
1. Architecture contract
2. Executable implementation
3. Qualification test
4. Execution receipt
5. Reclassification/migration ledger
6. External-boundary ledger
7. Exact hashes and commit IDs
8. Deployment/readback state
9. Known unknowns
10. Next capability delta

No release should depend on conversational memory as its sole architecture authority.

## Capability ladder

R8: machine-backed resident BRAINK restart
R9: descendant machine derivation
R10: replicated canonical object with lineage-safe availability/reconciliation
R11: resident global service roots
R12: live semantic service carrier failover
R13: typed service operations and authority gates
R14: external-authority adapter
R15: external network-path classifier
R16: reusable architecture and qualification doctrine

The next release must add a capability delta, not another description of R8-R16.
