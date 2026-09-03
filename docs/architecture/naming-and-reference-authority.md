# BRAINK Naming and Reference Authority

## Governing correction

Numeric suffixes such as `R8`, `R9`, `R10`, `R15`, `V73`, or similar are historical receipt/build identifiers only. They MUST NOT define architectural identity, capability boundaries, progression, or the next action.

A new observation, packet, test, or agent contribution does not create a new BRAINK architecture version by implication.

## Stable architecture identities

The runtime is addressed by stable roles:

- `MACHINE`
- `ENCODED_MEDIUM`
- `STORAGE_CONTROLLER`
- `BRAINK_ROOT`
- `VFS_RESOLVER`
- `OBSERVER`
- `NETWORK_BRIDGE`
- `SERVICE_FABRIC`
- `DOMAIN`
- `DNS`
- `REGISTRAR`
- `TLS`
- `CLOUD`
- `PROOF`

Historical filenames may retain revision suffixes for traceability, but callers MUST resolve the stable role through the runtime manifest rather than infer semantics from a filename suffix.

## Evidence authority

Every incoming data packet from another agent is classified as `REFERENCE_ONLY` by default.

A reference packet may contain:

- observations,
- proposed architecture,
- code,
- test results,
- claims,
- terminology,
- suggested actions.

None of those are promoted merely because the packet labels them `implemented`, `verified`, `deployed`, `complete`, `Rxx`, `Vxx`, `final`, or equivalent.

Promotion requires local reconciliation against the active BRAINK state:

`REFERENCE -> PARSE -> MAP_TO_STABLE_ROLE -> COMPARE_ACTIVE_STATE -> EXECUTE_IF_NEEDED -> READBACK -> PROMOTE`

The packet's own version labels remain packet metadata only.

## No forced progression

Forbidden control pattern:

`R8 -> therefore build R9 -> therefore build R10`

Required control pattern:

`current verified predicates -> missing mandatory predicate -> smallest executable change -> readback -> updated verified predicates`

Progress is measured by verified capability delta, not number increment.

## Source/provenance separation

Names, line numbers, sheet indices, packet IDs, revision labels, and agent names are provenance coordinates. They do not become runtime addresses, storage capacity, authority, or architecture classes unless an explicit mapping contract proves that role.

## Conflict handling

When a reference packet conflicts with active observed state:

1. preserve the packet unchanged as evidence;
2. preserve active observed state;
3. record the contradiction;
4. execute a resolving test if possible;
5. promote only the result supported by readback.

No fluent reconciliation is permitted in place of execution evidence.
