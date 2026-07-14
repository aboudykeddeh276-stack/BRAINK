# KEX–BRAINK Codex Fleet Manifest — 2026-07-14

Architect: **A. Keddeh**  
Fleet branch: `codex-fleet-20260714`  
Fleet state: `INITIATED`  
Parallel topology: **18 non-overlapping workers**

## Governing research state

Workers must use the latest KEX/BRAINK evolution as an active execution skill, not as narrative decoration.

Established exact controls carried into implementation:

- typed-state domain with seven disjoint constructors;
- Translative Loss worked result `2.15887184844536 bits` and zero loss under injective typed representation;
- phase-tagged `C_K` mapping with explicit inverse;
- HEX × HEX exhaustive domain of 4,096 scalar cases, 5:1 preimage ratio, and `3.7272170014624826 bits/nibble`;
- twelve-nibble KEX join algebra and solved position-wise join vectors;
- quartic closed form `y_n = y_0^(4^n)` and fixed-point multiplier `4`;
- damped bilateral eigenvalues `0.88` and `0.352`;
- KCPU scoring route with `POSITIONAL_CONTEXT_R4` as the worked unique maximum;
- runtime reference `24 / 0.6747 = 35.57136505113384 transactions/s`;
- TER worked ratio `3.066864543812105`;
- peer-KEX trace: 838 records, 137 peers, 33 state words;
- bilateral polygon non-regression baseline `0.8166666666666668`.

## Mandatory execution loop

`anchor -> factor -> translate -> act -> validate -> tokenize -> preserve -> return`

Every worker must:

1. inspect the assigned repository before changing it;
2. preserve existing public contracts and neutral/uniform behaviour;
3. work on a dedicated branch;
4. implement the smallest complete runnable slice;
5. add or repair executable tests;
6. run build/test/lint/type checks that exist in the repository;
7. produce a draft pull request with exact commands, outputs, blockers, and rollback notes;
8. avoid fake telemetry, random dashboard values, hidden credentials, or unsupported production claims;
9. preserve route-scoped state and evidence receipts;
10. never reinterpret KEX identifiers through unrelated SHA/hash assumptions.

## Worker map

| Worker | Repository | Owned lane |
|---|---|---|
| W01 | `BRAINK` | Core active-skill runtime and deterministic packet loop |
| W02 | `backend` | API health, persistence, replay, tests |
| W03 | `app` | Real-data UI integration and build closure |
| W04 | `ai-shell` | Headless launcher, `.ops`, logs, metrics |
| W05 | `KERA_SERVER` | Local server startup, container and health closure |
| W06 | `KEX_HYPERDRIVE_DASHBOARD_UI` | Proof-backed telemetry dashboard |
| W07 | `KEDDEH-ALGEBRA-CORES` | Native algebra library and exhaustive verification |
| W08 | `VIRTUALISED_MEMORY` | Sparse typed memory and deterministic persistence |
| W09 | `SERVERS-KEDDEHSYSTEMS` | Multi-service local orchestration |
| W10 | `1AXIS-MATRIX-OS` | Canonical 26-node boot traversal |
| W11 | `UNIVERSAL-CALIBRATION-MATRIX` | `C_K`, 2.97/0.297 calibration and ablation |
| W12 | `KSYSTEMS_LEARNING-` | Bilateral polygon bounded-learning runtime |
| W13 | `GENERAL-GOVERNANCE-` | Proof ledger, evidence gates, CI policy |
| W14 | `K-SYSTEMS-CODE-SPACE-` | Fleet integration workspace and reproducible launcher |
| W15 | `KEDDEH_SOFTWARE_NODES` | Typed node/provenance registry |
| W16 | `KEDDEH-CLOUD-SERVERS-ID-1` | Read-only inventory, health and deployment evidence |
| W17 | `BRAINK_DESKTOP_ORGANISED` | Portable desktop/headless packaging |
| W18 | `K-SYSTEM_UPDATE_LANE_PROCESS_x-x` | Update, migration, rollback and release state machine |

## Merge ownership

Workers may edit only their assigned repository. Cross-repository changes must be represented as an interface contract or follow-up issue, not a direct competing patch. No automatic merge is authorized; all outputs remain draft PRs until reviewed.
