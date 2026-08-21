# Requirements

## Skill identity and purpose
- The authoritative skill name must state what the skill enables a user or engineer to do.
- Machine-stable identifiers must remain semantically reconstructable without a private legend.
- Scope and excluded scope must be explicit.

## Mechanics and reproducibility
- Core causal mechanics must be understood before workflow design.
- Every material input, output, state, invariant, transformation, failure path, and completion condition must be represented where applicable.
- Another competent engineer must be able to reproduce the method without hidden conversational context.

## Reuse and derivation
- Existing components must be materialised locally where practical before repeated inspection.
- Reuse must be justified by semantic-equivalence tests.
- Missing behaviour must be derived only when not already implemented correctly.
- Bounded defects should be repaired at the smallest responsible layer.

## Execution and validation
- Source existence cannot satisfy an execution claim.
- Build/import/compile must succeed where applicable.
- Primitive, module, composition, negative, recovery, target, and performance tests must be defined only where relevant.
- Test oracles must be independent or authoritative enough to justify the claim.

## Evidence and claims
- Every material claim must trace to a requirement, mechanism, test, evidence artifact, and verdict.
- Evidence references must resolve to actual retained artifacts or authoritative external results where claimed.
- Unknowns must remain unknown.
- Hardware/performance limitations must be classified and evidenced rather than asserted generically.

## Packaging and maintenance
- The skill must be versioned.
- The package must include integrity hashes.
- Changes to mechanics, interfaces, protocols, tests, evidence requirements, or standards must trigger impact analysis and regression.
