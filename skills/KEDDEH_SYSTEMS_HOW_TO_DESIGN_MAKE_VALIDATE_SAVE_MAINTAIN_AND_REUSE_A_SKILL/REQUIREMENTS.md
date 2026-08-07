# Requirements

## Skill identity and purpose

- The authoritative skill name must state what the skill enables a user or engineer to do.
- Machine-stable identifiers must contain only `A-Z`, `0-9`, and `_`.
- Machine-stable identifiers must be semantically reconstructable without a private legend.
- Scope and excluded scope must be explicit in SKILL.md.

## Mechanics and reproducibility

- Core causal mechanics must be understood and documented before workflow design.
- Every material input, output, state, invariant, transformation, failure path, and
  completion condition must be represented where applicable.
- Another competent engineer must be able to reproduce the method using only this package.

## Assumptions

- All assumptions the skill depends on must be listed explicitly in SKILL.md.
- Runtime environment requirements (OS, language version, APIs) are assumptions.

## Reuse and derivation

- Existing components must be materialised and tested against their responsibilities
  before a new implementation is derived.
- Reuse must be justified by semantic-equivalence tests, not source presence alone.
- Missing behaviour must be derived only when not already correctly implemented.
- Bounded defects must be repaired at the smallest responsible layer.

## Execution and validation

- Source existence does not satisfy an execution claim.
- Build/import/compile must succeed without errors.
- Isolated primitive tests must exist and pass.
- Completed-module contract tests must exist and pass.
- Negative and recovery tests must exist and pass where failure modes are defined.

## Evidence and claims

- Every material claim must trace to a requirement, mechanism, test, evidence artifact,
  and verdict.
- Evidence references must resolve to retained artifacts or authoritative external results.
- Unknowns must remain marked unknown.
- Limitations must be classified and evidenced, not asserted generically.

## Packaging

- `VERSION` file must exist and contain a semantic version string.
- `manifest.json` must exist and contain `canonical_identifier`, `version`, `purpose`,
  `claim_boundary`.
- `claim_boundary` values must be boolean — no placeholders, no nulls.

## Maintenance

- Any change to mechanics, interfaces, protocols, tests, evidence requirements, or
  standards must trigger impact analysis and regression before the version is updated.
