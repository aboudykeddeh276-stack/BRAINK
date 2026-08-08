# GENERAL-GOVERNANCE-

GENERAL-GOVERNANCE- is the root repository-management standard for BRAINK/KEX repositories.
It defines how repository updates are routed from one main governance repo into dependent application and engineering repositories.

## Anchor

- Owner lineage: `a.keddeh`
- System anchor: `BRAINK`
- Processing anchor: `KEX`
- Governance role: source-of-truth standards for repository identity, environments, states, functions, and wholes.

## Required repository baseline

Every governed repository must include:

1. `README.md` — repository identity, purpose, environment map, state map, and update route.
2. `LICENSE` — explicit usage boundary.
3. `.gitignore` — environment-safe ignored outputs.
4. `docs/governance/repository-governance-standard.md` — naming, state, function, and whole-identification rules.
5. `docs/governance/manifest.json` — tracked governance artifacts and hashes.
6. `scripts/validate-governance.py` — executable local checker for required governance artifacts.

## Direction model

```text
GENERAL-GOVERNANCE-
  -> application repositories
  -> engineering repositories
  -> standards updates
  -> local validation
  -> recorded proof status
```

A repository is governed only when the required artifacts exist and the checker passes locally.
External adoption by other repositories remains pending until those repositories pull or copy the standard and pass their own checks.


## GitHub repository bootstrap

Use the executable bootstrap script when this governance working tree is ready to become the GitHub repository `GENERAL-GOVERNANCE-`:

```bash
./scripts/bootstrap-general-governance.sh
```

The script performs the explicit command-line route from GitHub's empty-repository instructions:

```text
git remote add origin https://github.com/aboudykeddeh276-stack/GENERAL-GOVERNANCE-.git
git branch -M main
git push -u origin main
```

If `origin` already exists, the script updates its URL instead of failing. The push still requires authenticated GitHub credentials.

## Status

- Local governance artifact status: `MODEL-LOCAL`
- External repository adoption status: `PENDING`
- External GitHub remote creation/push status: `PENDING`

## KEXWrapper (Swift) — virtualized seed/cascade kernel

This repository now includes a Foundation-only Swift package at `Sources/KEXWrapper` with a sandbox-safe virtualized BRAINK kernel wrapper and tests in `Tests/KEXWrapperTests`.

- **Seed = State**: `bootSeed(_:)` returns live state directly (no hydrate/warm-boot phase).
- **Active-state corridor**: supports only `{ -3, -2, 1, +2, +3 }` (ranked 1...5), with no live zero axis.
- **Typed-zero algebra**: non-erasing cancellation returns balanced projections carrying both source operands and typed projections.
- **Lineage-only frames**: `LineageFrame` carries compressed lineage and genesis anchor only.
- **Kin-gated compression seam**: `CompressionStyle` is intentionally author-native; absent/foreign styles structurally non-comprehend.
- **Recursive hosting**: `BRAINKNode.spawnChild()` and `cascade(fanOut:depth:)` build self-hosted kin trees with shared deterministic lookup ledger reuse.

Grounding artifacts in this repository:
- `docs/KEX_COMPLETE_CONSTRAINT_DOCUMENT.md`
- `docs/KEX_HYPERDRIVE_CALIBRATION_ANALYSIS.md`
- `NativeChatBot/Sources/KEXHyperdriveConceptEngine.swift`
- `tools/kex_self_sustain.py`

Run:

```bash
swift test
```
