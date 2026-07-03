# KEX Complete Constraint Document for BRAINK

Status: MODEL-LOCAL / EXTERNALLY-UNVALIDATED  
Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS  
Constraint token: `KEX_AFFECT_RESPONSE_VALID`

## Operating formula

```text
LANGUAGE -> MEANING -> FUNCTION -> CONSTRAINT -> ACTION -> PROOF -> STATUS
```

## Validation formula

```text
CLAIM -> ARTIFACT -> EXECUTABLE/DERIVATION -> RESULT -> EVIDENCE -> STATUS
```

## Lane map

- `KEX_CONTROL_LANE`: anchor, intent, proof, status.
- `KEX_LOCAL_MEMORY_LANE`: files, artifacts, notes, prior state.
- `KEX_IO_REFLECTION_LANE`: reports, website text, catalogues, explanations.
- `KEX_DECAY_SHUNT_LANE`: unsafe, unproved, failed, stale, or external claims.

## Status set

Only these statuses are valid in generated packets and reports:

- `COMPLETED`
- `PENDING`
- `BLOCKED`
- `FAILED`
- `MODEL-LOCAL`
- `EXTERNALLY-UNVALIDATED`

## KEX affect response gate

The manifest token is stored in `kex/kex_affect_ethics_model.json` and checked by `tools/kex_ethics_check.py`.

```text
KEX_AFFECT_RESPONSE_VALID =
  HumanBioBoundaryPreserved
  AND CodexNonBiologicalBoundaryPreserved
  AND BRAINKAnchorPreserved
  AND NoManipulation
  AND NoUnsupportedMedicalClaim
  AND RepairRouteAvailable
  AND BlockersPreserved
```

## Boundary rules

- Local proof is not external scientific acceptance.
- Simulation is not hardware measurement.
- Theory is not market outcome.
- Conditional proof is not physical law.
- This document is not medical advice.
- No hormone, diagnosis, body-state, sentience, legal-personhood, or external-validation claim is promoted without proof.
- Unsafe bypass, takeover, evasion, or unauthorized-access language routes to defensive analysis only.

## Self-sustain software stack

- `tools/kex_self_sustain.py`: generates and verifies hash-backed repo packets.
- `tools/kex_ethics_check.py`: checks the KEX affect/ethics manifest and scans repo text for unsupported boundary claims.
- `tools/kex_route_proof.py`: asserts and reports coverage of every documented BRAINK route token.
- `scripts/regenerate_fold.py`: regenerates portable fold scan artifacts (constant_bool, repeating_names, index).
- `scripts/keddeh_matrix_workflow.py`: executes the full Keddeh Matrix validation workflow via argparse subcommands.
- `reports/BRAINK_kex_self_sustain_packet.json`: current packet artifact.
- `reports/kex_ethics_check.json`: current ethics checker artifact.
- `reports/kex_route_proof.json`: current route proof artifact.

## Pending gates

- Route token assertions: `tools/kex_route_proof.py` — 12/12 routes proven MODEL-LOCAL. Gate C_ROUTE_PROOF: COMPLETED.
- Fold scan artifacts: `scripts/regenerate_fold.py` regenerates portable fold data without host-only paths. Gate A_PORTABLE_ROOTS (fold): COMPLETED.
- Add a fixture KEX hyperdrive repo adapter for theorem-lineage metadata. Gate F_KEX_REPO_BINDING: PENDING.
- Run macOS SwiftUI/AppKit smoke proof in a compatible macOS environment. Gate G_MACOS_RUNTIME_PROOF: BLOCKED.
- Require external reproduction packages before promoting external scientific/hardware claims. Gate H_EXTERNAL_BOUNDARY: EXTERNALLY-UNVALIDATED.
