# R58: R5 source rehydration

**Architect:** A. Keddeh  
**Architecture:** KS-BRAINK-IL-LLM  
**Date:** 15 November 2026

## Result

The seven surfaces previously listed as unlocated were recovered and each was compared with the standalone R5 manifest. All seven byte lengths and SHA-256 values match. The cumulative R5 file-backed inventory is now **30/30 verified** (15 prior + 8 R57 + 7 R58).

The two payloads below were decoded from the exact `payloads` JSON in `KEDDEH_UNIFIED_REFERENTIAL_VOLUME_v28_MACHINE_CONSTRUCTOR_V8.html`, then compared byte-for-byte and by SHA-256 with the R5 manifest:

- `ClaimPath_Shippable_Contents_v1.html` → `app://claimpath`, 18,614 bytes, `6dbbee10334838c85d0f56ad10a0ff859fd5a35fce433cbb42cc4af0eda86a45`.
- `index(1).html` → `os://keddeh/hybrid`, 5,410 bytes, `5bcda013f14a47330e963b232167e1a3fc237e8668e17aa1e379d33e645b7c9d`. The manifest explicitly marks this OS shell `DEPENDENCY_INCOMPLETE`; its companion styles.css/app.js are not resident.

## Seven exact source matches

| Surface | Identity | Bytes | SHA-256 |
|---|---|---:|---|
| ClaimPath Shippable Contents v1 | `app://claimpath` | 18,614 | `6dbbee10334838c85d0f56ad10a0ff859fd5a35fce433cbb42cc4af0eda86a45` |
| BRAINK IL-LLM Sovereign Volume | `volume://braink/il-llm/sovereign-v1` | 31,873 | `8630d974d8705729107ea5cd232e243fe4b6d990088ea2e7440fa6a223d511a8` |
| Hybrid OS shell | `os://keddeh/hybrid` | 5,410 | `5bcda013f14a47330e963b232167e1a3fc237e8668e17aa1e379d33e645b7c9d` |
| Self-hosted workbook OS V7.4 | `workbook://workbook_os_v7_4` | 444,892 | `190feb0c5fdca49120a711ad3b77aa7eaf96ffcf9c9ab41dbe048c1aeacbd387` |
| Boolean graph workbook V7 | `workbook://boolean_graph_v7` | 271,865 | `2b7ef7e659dfd7fd416a060fe840c5a1cae8223add66e610a8e951507730f28e` |
| IL-LLM KEX V11 engineering control plane | `control://braink/illlm-kex/v11` | 6,337,343 | `484f05f39c487b7573404c21a7f024c764e41812781e80c2929304e76deb2965` |
| Resident engineering corpus projection V3 | `projection://keddeh/resident-engineering-corpus/v3` | 4,023,659 | `254f466c559c29b8814bb434724abbebd20bfcdf54c7af143ee74fe9c098a09b` |

Workbook readbacks: Boolean graph workbook 76 sheets; V7.4 self-hosted workbook 134 sheets.

## Manifest and root distinction

- Standalone R5 manifest: 32,546 bytes, SHA-256 `a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc`.
- Cross-work manifest: 39,430 bytes, SHA-256 `5d867ae7d7f517d6cdde14c138e67e90571062521e5d912fd8812165da1ce985`.
- The standalone R5 manifest hash matches the `parent_system_orchestrator.manifest_sha256` value in the cross-work manifest.
- The v28 carrier is `volume://keddeh/braink/root`, 6,444,645 bytes, SHA-256 `abe6bd9647ec79cb5b820ec7be945a8d01ffa327cec3c1575f336c92672271ba`. It is not the R5 system-orchestrator parent.

## Tests and retained failure

Command: `python3 -m unittest -v test_r58_source_rehydration`

- Local execution: 9/9 passed, exit 0, PID 650.
- Extracted-bundle execution: 9/9 passed, exit 0, PID 718.
- Test source SHA-256: `0cc051c1a79e22672fb0109274e0ef1758d5b2b0d7ef9f838e6a40f0c63710b0`.
- Bundle: 6,873,378 bytes, SHA-256 `5866eee9f0cbb02b0e6ce9c801a0bcdc962631ee2e9748960ab77e56621751c0`.

A separate attempt to rerun the R57 suite stopped before test collection (0 tests, exit 5) because its historical fixture path `/mnt/data/ks-braink-source-recovery/BRAINK_R5_SYSTEM_MANIFEST.json` was absent. The manifest was subsequently materialized, but the other R57 fixture dependencies were not all restored. The prior 15/15 result is therefore retained as historical evidence, not promoted to a fresh pass.

## Still unresolved

The R5 parent `braink://volume/r5/system-orchestrator` remains unmaterialized at expected SHA-256 `9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede`.

The v6.0 base archive remains unrecovered. The current session exposes Files Library materialization but no direct Google Drive connector. The source recovery does not establish Chromium/v86 boot, external-node execution, independent quorum, trained weights or production deployment.
