# BRAINK Compounding Theorem-Object Graph R1

## Authority shift

The atomic archive unit is a stable typed theorem object, not a page, chapter or branch.
Pages and diagrams are computed projections over theorem objects, dependency closure,
proof states, sector transforms, evidence and motif relations.

## Core execution

```text
REGISTER
→ TYPECHECK
→ RESOLVE DEPENDENCIES
→ ROUTE THROUGH ADMITTED SECTOR TRANSFORMS
→ PROPAGATE PROOF STATE
→ STRENGTHEN / CONTRADICT / INVALIDATE / REVIEW
→ RENDER PROJECTION STATE
→ FACTOR EXACT RESTATEMENTS
```

Positive and negative propagation are symmetrical. Falsification of an upstream
object cannot leave downstream claim states silently unchanged.

## Type-safety law

Dependency, implication, refinement and constraint edges are admitted only when
source output types intersect target input types. Equivalent objects must expose
the same output type set. Unknown transforms and self-relations fail closed.

Routing is separately constrained by each theorem's `compatible_sectors` and by
the transform's accepted input types. Merely connecting an edge never authorizes
cross-sector mutation.

## Proof-state law

A verified upstream object may strengthen a typed dependent to `OBSERVED`, but it
does not automatically promote an entire transitive closure to `VERIFIED`.
Contested/review-required upstream state propagates review requirement. Confirmed
falsification invalidates the immediate dependent and drives downstream review.
A verified contradiction marks its target `CONTESTED`.

## Operator inheritance

Operators inherit only through admitted dependency/refinement ancestors. Local
operators are unioned with inherited operators; overridden/prohibited operators
are removed. Prohibition wins over inheritance.

## Bilateral compression

Compression is semantic factoring, not summarization:

```text
Stored Meaning = Canonical Invariant + Sector Transform + Unique Evidence
```

Only exact canonical restatements without unique evidence are eliminated. A
sector-specific context delta or evidence reference remains local.

## Projection law

A sector projection root is recomputed from its theorem IDs, application IDs and
current proof states. Changing a theorem proof state therefore changes the page /
projection state without manual continuity edits.

## Recursive density

R1 implements:

```text
D_r = (R + E + C + P + X) / (O + N)
```

where routed reuse, graph edges, executable transforms, proof-bearing relations
and cross-sector applications form the numerator; theorem-object count and
redundant narrative mass form the denominator.

It also exposes a bounded marginal-value function for one theorem:

```text
G(I) = routed applications + dependents + graph reuse - duplicate cost
```

This is an operational metric, not a proof of long-run superlinear growth.
Successive-generation `dG/d|I| > 1` still requires longitudinal archive evidence.

## Executed INV-ZL-001 campaign

The R1 campaign registered `INV-ZL-001` once and routed it to:

- cosmology
- linguistics
- governance
- runtime
- proof
- observer
- motif

Seven verbatim restatements were factored back into the canonical invariant while
a runtime-specific delta with unique test evidence was retained.

A typed chain `INV-ZL-001 → runtime → proof → page` was then exercised. After a
counterexample changed the invariant to `FALSIFIED`, all three downstream objects
moved to `REVIEW_REQUIRED`, and runtime/proof projection roots changed.

## Evidence boundary

R1 proves the deterministic in-process graph engine and the tested propagation /
invalidation behaviour. It does not yet prove automatic semantic equivalence over
arbitrary prose, distributed multi-writer graph consistency, durable database
storage, large-scale incremental rendering, or longitudinal nonlinear growth.
Those require separate mechanisms and evidence.
