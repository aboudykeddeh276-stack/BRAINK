# Window Signal Runtime Skill

## Purpose
Transform an operational surface into a bounded window that owns semantic interpretation, compilation, runtime validation, state transition, persistence and evidence before emitting one canonical machine propagation request.

## Required separation
Do not collapse BRAINK, KEX, CasePath, ClaimPath, workbook, site, carrier, projection or host identities into one application. Their common boundary is the propagation ABI, not their domain semantics.

## Window contract
Every operational window SHALL:

1. identify its own source identity and exact target identity;
2. read the target's authoritative state, receipt head and sequence head before compilation;
3. resolve domain intent locally using its own logic, compiler and runtime rules;
4. select only a machine operation that is explicitly bound by the target runtime;
5. compile one `kex.signal/1` request against the observed state hash and receipt head;
6. declare only invariants the machine runtime knows how to enforce;
7. emit exactly one propagation request for the resolved transition;
8. treat the returned `COMMITTED` receipt as the authority to advance visible state;
9. recover a lost response by looking up the same `signal_id`, never by silently constructing a replacement mutation;
10. preserve the domain's identity and evidence even though execution converges on the shared ABI.

## Canonical machine grammar

`VERIFY -> ADDRESS -> PROPAGATE -> EXECUTE -> COMMIT -> RECEIPT`

The machine runtime SHALL NOT be required to understand domain-language intent. Domain windows compile that intent into the canonical request.

## Signal schema
Required request fields are `abi`, `signal_id`, `source`, `target`, `operation`, `state_hash_before`, `compiled_payload`, `invariants`, `authority`, `sequence`, and `proof_root`.

## Address and state rule
Machine state and receipt chains are partitioned by exact target identity. A commit to one target SHALL NOT advance the state hash, sequence, or receipt head of another target.

A projection is not authoritative merely because it is visible. A window advances its displayed authoritative revision only after a valid receipt confirms commit.

## Sequence rule
For a target with `head_sequence = n`, the next accepted request is `n + 1`. Sequence gaps and stale requests are rejected. The next request uses the prior committed `receipt_hash` as its `previous_receipt`.

## Transaction rule
State and the receipt-chain head form one persistence transaction. They SHALL be serialized and durably replaced as one journal unit so a process failure cannot legitimately expose advanced authoritative state without its corresponding committed receipt.

## Concurrency rule
The verify/state-precondition/execute/commit sequence SHALL be serialized per target, or implemented with an equivalent compare-and-swap transaction. Two requests derived from the same target revision may not both commit distinct next states.

## Recovery and idempotency rule
A committed `signal_id` may be replayed only to recover the original committed receipt. The stored request proof root must match the replayed request. Reusing a signal identifier for different proof material is an integrity failure.

## Authority rule
An unkeyed request hash proves consistency, not authority. Mutating ingress SHALL authenticate the caller and bind that authenticated channel to the permitted `authority` identity before execution. Do not infer authority merely because the request names one.

## Invariant rule
Unknown invariants are rejected. Never return a committed receipt that can be read as evidence for an invariant the runtime did not actually evaluate.

## Evidence rule
Hash chaining is consistency and lineage evidence, not immutable-history proof by itself. Do not claim external immutability unless the chain is anchored to an independently controlled witness or equivalent trust boundary.

## Execution rule
Prefer an existing runtime handler, adapter, service, workbook mechanic or sector bridge. Do not create a parallel abstraction where an actual implementation already exists. Wrap the existing implementation behind the canonical propagation ABI.

Current resident bindings include `STATE_PATCH`, `KEX_ACTION`, `CASEPATH_DISPATCH`, `WORKBOOK_READ`, `RUNTIME_REGISTER`, and `RUNTIME_DESIRED_STATE`. A bound operation proves routing to that resident mechanic; the receipt's claim boundary still governs what downstream effects are proven.
