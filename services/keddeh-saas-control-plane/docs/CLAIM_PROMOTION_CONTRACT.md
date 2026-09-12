# SaaS Claim Promotion Contract

This contract governs claims made about `service://keddeh/saas-control-plane`. It does not redefine BRAINK, CasePath, ClaimPath, KEX, or server-sector authority.

## State ladder

A property may occupy only the highest state independently evidenced for that property:

1. `SOURCE_PRESENT`
2. `IMPLEMENTED`
3. `LOCALLY_EXECUTED`
4. `INTEGRATION_EXECUTED`
5. `HOST_EXECUTED`
6. `READBACK_VERIFIED`
7. `EXTERNAL_READBACK_VERIFIED`
8. `PRODUCTION_PROMOTED`

No state implies the next state.

## Representation classes

- `DESCRIPTOR_ONLY` — relation/contract description exists; no executable adapter is claimed.
- `DECLARED_UNBOUND` — dependency is known but no binding is established.
- `CANDIDATE` — executable implementation exists but is not authoritative over a pre-existing working implementation.
- `PRESERVED_EXISTING` — an existing authoritative/working implementation was detected and left unchanged.

## Prohibited promotions

The following promotions are invalid without additional evidence:

- repository commit -> executed;
- package/container definition -> deployed;
- local process -> public service;
- unit/local test -> integration qualification;
- descriptor -> adapter implementation;
- declared dependency -> bound dependency;
- model/abstraction -> authoritative implementation;
- candidate replacement -> behavioral parity;
- absence in current search -> non-existence;
- GitHub Actions job creation -> CI execution.

## Existing-function preservation

A derived or synthesized candidate may not overwrite, bypass, or retire a pre-existing runtime definition merely because it matches an inferred contract. The original record remains authoritative unless an explicit migration/cutover operation is separately authorized and qualified against the original execution path.

## Completion denominator

`fully populated` or `complete` may be used only when an expected inventory is explicitly enumerated and every member is independently closed. Otherwise report a numerator/denominator or `UNKNOWN_TOTAL`.

## Evidence rule

Every promoted claim must identify the property, execution surface, observation, and readback. Evidence for one property does not transitively qualify adjacent properties.
