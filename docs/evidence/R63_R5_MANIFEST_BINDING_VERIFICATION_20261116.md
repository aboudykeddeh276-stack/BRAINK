# R63.1 — corrected R5 standalone manifest binding verification

**Architect/source authority:** A. Keddeh  
**Canonical architecture:** KS-BRAINK-IL-LLM  
**Result:** PASS — source/manifest verification only; correction to the initial R63 artifact transfer

## Correction retained

The first R63 GitHub commit (`fe9be09038efcc9e96fa1a64c051573d7f89d794`) contained an incomplete ZIP blob. GitHub readback reported 7,646 bytes, not the 16,929-byte local archive. The initial R63 comment's ZIP-size/hash claim therefore did not describe the committed blob. The invalid ZIP path is deleted in this correction. The Git history is not rewritten.

The replacement stores the exact standalone R5 manifest as a normal JSON file and a separately labelled, derived cross-work binding excerpt. The full cross-work source remains identified by its independently materialized byte count and SHA-256. The derived excerpt is not presented as the full source.

## Exact source readback

| Identity | Bytes | SHA-256 |
|---|---:|---|
| `braink://volume/r4` | 13,050,075 | `5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592` |
| `braink://volume/r5/system-orchestrator` | 13,086,990 | `9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede` |
| Standalone `BRAINK_R5_SYSTEM_MANIFEST.json` | 32,546 | `a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc` |
| Full cross-work manifest `...CROSS_WORK_R1.json` | 39,430 | `5d867ae7d7f517d6cdde14c138e67e90571062521e5d912fd8812165da1ce985` |
| Derived cross-work binding excerpt | 658 | `54f535a659ac9cd9c38602975e72f0ce08a3062f3732664cb140870fe5f929c3` |
| Embedded `script#r5-system-manifest` | 25,831 | `b64565d56f7172bb4db1206ca4cc8857f42dbcb1f76ae99635c629f16791ceb2` |

The apparent hash mismatch is resolved: `parent_system_orchestrator.manifest_sha256` in the full cross-work manifest points to the **standalone 32,546-byte manifest**, not the embedded 25,831-byte script body. The two are distinct hash targets. The cross-work object remains `braink://volume/r5/system-orchestrator/cross-work-r1`, not the R5 parent.

## Fresh corrected local test

Command: `python3 -c` invoking `unittest.defaultTestLoader.discover('tests', pattern='test_r63_r5_manifest_binding.py')`.

- PID: `749`
- Result: **6 passed, 0 failed**
- Exit: `0`
- Duration: `0.001 s`
- Test source SHA-256: `351837144e2510a566213ebf9202c1b57a18d0cb9a8e187906f8046896efd3ff`
- Stdout SHA-256: `c54642417874ab90ba52428df913ae3e2b0f6c60b2334bcb50fb8db573926ad3`

The test reads the exact standalone manifest file and the explicitly labelled `derived_excerpt_not_full_source` binding excerpt. It verifies the standalone byte count/hash/identity, the full cross-work source hash and identity, the parent manifest binding, the R4 parent identity/hash, manifest surface counts, and the separation of the cross-work descendant.

## Boundary

The R4/R5 source files and manifests were read from the ChatGPT Files Library and materialized locally. This is **not** a Google Drive read. It does not establish the PR #107 full current-head suite, owner-host admission, boot, heartbeat, independent quorum, trained production weights, DNS/TLS activation or Sites publication. No original source was overwritten, no candidate promoted and no PR merged.
