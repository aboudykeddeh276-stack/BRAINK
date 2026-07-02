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
- `KEX_THOUGHT_LANE`: per-interaction thought log; `BRAINKInnerRuntime.evolve()` fires on every route, recording user input and response quality into `BRAINKInnerRuntimeState.thoughts`.
- `KEX_THINKING_LANE`: active reasoning state (logic, highIq, kexTheorem, cosmology); updated per wrapper domain via `updateReasoningState` and per specialised route via `updateRouteReasoningState`.
- `KEX_LEARNING_LANE`: file learning snapshots (`BRAINKRuntimeLearning.buildSnapshot`), IL-LLM knowledge growth, skill/action accumulation; `reasoningState.learning` is boosted each time the `learn_all_files` route runs.
- `KEX_UPDATE_LANE`: runtime path mutations (`illlm_update`), line registry changes (`line_registry_add`/`line_registry_list`), inner state write-back; all update operations evolve the THOUGHT lane so mutations are recorded as thoughts.

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
- `reports/BRAINK_kex_self_sustain_packet.json`: current packet artifact.
- `reports/kex_ethics_check.json`: current ethics checker artifact.

## Pending gates

- Replace host-only `/Users/ak/Documents/...` output paths with configurable roots.
- Add route-level runtime assertions for every documented BRAINK route.
- Add a fixture KEX hyperdrive repo adapter for theorem-lineage metadata.
- Run macOS SwiftUI/AppKit smoke proof in a compatible macOS environment.
- Require external reproduction packages before promoting external scientific/hardware claims.
