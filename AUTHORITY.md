# BRAINK Authority Contract

## Sector class
Persistent runtime / state authority.

## Owns
- BRAINK persistent state and memory-in-time;
- Observer² framing and readback relations;
- local orchestration and resident capability resolution;
- VFS / continuation / checkpoint / rehydration mechanics;
- state/proof relation mechanics that belong to BRAINK itself.

## Executes
BRAINK runtime mechanics and orchestration paths resident in this repository or declared as imported dependencies.

## Depends on
- `KEX`: coordinate/addressing and data/definition evolution semantics;
- `IL-LLM`: recurrent traversal mathematics;
- `EVIDENCE-LEDGER`: cross-sector durable qualification receipts;
- infrastructure sector repositories for server/network/cloud execution.

## May mutate
BRAINK-owned state, continuation, orchestration, VFS and proof-relation objects. It may not silently mutate another sector's authority state.

## Proof condition
A BRAINK mechanic is qualified only when it is implemented in the declared runtime, invoked through the resident mechanism, produces property-scoped readback/evidence, and preserves lineage. A repository write, package, hash or UI projection is not functional proof.

## Does not own
CasePath/ClaimPath business semantics, registrar authority, network route authority, public host allocation, or evidence merely because those relations are displayed by BRAINK.
