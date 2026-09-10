# Window Signal Runtime Skill

## Purpose
Transform any operational surface into a bounded window that owns semantic interpretation, compilation, runtime validation, state transition, persistence and evidence before emitting one canonical machine propagation request.

## Required separation
Do not collapse BRAINK, KEX, CasePath, ClaimPath, workbook, site, carrier, projection or host identities into one application. Their common boundary is the propagation ABI, not their domain semantics.

## Window contract
Every operational window SHALL expose:

1. identity and authoritative state reference;
2. permitted operations and authority requirements;
3. local semantic compiler from domain intent to `kex.signal/1`;
4. pre-transition state hash and invariants;
5. one outbound `SignalRequest` only after local validation;
6. one returned `SignalReceipt` before advancing visible authoritative state;
7. durable evidence linking before-state, request, execution and after-state.

## Canonical machine grammar

`VERIFY -> ADDRESS -> PROPAGATE -> EXECUTE -> COMMIT -> RECEIPT`

The machine runtime SHALL NOT be required to understand domain-language intent. Domain windows compile that intent into the canonical request.

## Signal schema

Required fields:

- `abi`
- `signal_id`
- `source`
- `target`
- `operation`
- `state_hash_before`
- `compiled_payload`
- `invariants`
- `authority`
- `sequence`
- `proof_root`

## State rule
A projection is not authoritative merely because it is visible. A window advances its displayed authoritative revision only after a valid receipt confirms commit.

## Evidence rule
Hash chaining is consistency evidence, not immutable-history proof by itself. Do not claim external immutability unless the chain is anchored to an independently controlled witness or equivalent trust boundary.

## Execution rule
Prefer an existing runtime handler, adapter, service, workbook mechanic or sector bridge. Do not create a parallel abstraction where an actual implementation already exists. Wrap the existing implementation behind the canonical propagation ABI.
