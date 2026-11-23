# R61 estate root and implementation-surface traversal

**Architect:** A. Keddeh  
**Architecture:** KS-BRAINK-IL-LLM  
**Date:** 16 November 2026  
**Disposition:** source-preserving local verification; not deployment.

## Reconciled register

The normalized estate contains **86 logical identities**: 33 R5 identities plus 76 P11 logical objects, with 23 overlaps and 10 R5-only identities. P11 contains **95 unique carriers** across 98 raw rows, 3 duplicate rows, 19 multi-carrier logical objects and 6,630,073 represented bytes.

The 76-object and 95-carrier inventories match across the topology workbook, agent-usable estate index and carrier registry. All 32 cross-work relation endpoints match the topology workbook. R5 has 23 manifest relations.

The standalone R5 manifest SHA-256 is `a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc`. The cross-work manifest binds that hash to parent identity `braink://volume/r5/system-orchestrator`. Its child `braink://volume/r5/system-orchestrator/cross-work-r1` remains a separate descendant.

## Identity-set defect

Two derived views substitute the cross-work child for the R5 parent:
- `KEDDEH_FULL_TOPOLOGY_TRAVERSAL_2026-10-02.xlsx:R5_33`
- `KEDDEH_GOVERNED_ESTATE_ENVIRONMENT_v1.html:r5`

Both have 33 rows, but contain the child and omit the parent. The standalone manifest, both `R5_Reconciliation` sheets and the governed environment's `recon` array agree on the canonical 33 identities. No original file was modified. The normalized view uses the manifest/reconciliation set and retains the child separately.

## Root carrier boundary

The logical root is `volume://keddeh/braink/root`; carrier, projection and browser materialisation are separate identities. The v28 machine-constructor carrier is 6,444,645 bytes, SHA-256 `abe6bd9647ec79cb5b820ec7be945a8d01ffa327cec3c1575f336c92672271ba`. Its embedded registry schema is v26 and its current carrier identity is `carrier://html/keddeh-unified-v11`.

The carrier has 109 script tags, 83 `application/json` tags, 80 unique JSON IDs, 76 parseable objects and 4 invalid HTML-entity-escaped JSON objects. The architecture-root object itself parses. The old standalone HTML atlas still contains only 12 identities. PR #113's manifest declares v2 HTML/JSON outputs, but both files are absent from that PR branch and return 404.

## Local source execution

- `kex_registrar_service.py`: 2,252 bytes; SHA-256 `82df2266405d330f137c1b173c21873fac2bda3db4528f54c3b4e10f7fd3490f`. Calling registration before `init_registrar_db()` fails because the ledger parent directory is absent. After initialization, a local SQLite fixture registered/resolved `probe.test -> 127.0.0.7`; a child process independently read the same value. Fixture ledger: 20,480 bytes; SHA-256 `595fcb29857d7dfc6f5e348297cfada617dec73d8591c80c70a25236e0faddb5`. Parent PID 1792; child PID 1798. This is not broker node admission.
- `kex_self_hosted_v3_os.py`: 11,458 bytes; SHA-256 `63c984bcab13530419bcab0ec493aa9dc0297cf9b4b261ca27a0d50cbb7c6887`. One-shot local PID 1786 executed 86 in-memory virtual cores for 10 ticks; active cores 86; pitch lock 0.297; GPU checksum `bb3d14a48062d6007a192ca5af390b0f8a09ec22cf16af9e1be9e9436244bad6`; proof root `eb1c065b393daa9c72ca7d5e0c18d229de2f0aa8a6af449f44ae5f3085451c13`. No heartbeat or resident server loop.
- V3's LinuxRuntimeContract checks ten declared dependencies; it does not boot a kernel. The source accepts address 0 and its GPU_RECT path passes colour as y1. These source-level deviations remain unmodified.
- `kex_host_service.py`, `KEX_ROOT_OROBOROS.py` and `kex_wallet_engine.py` were not materialized in this run. R9 evidence remains compile-only or historical-log evidence; the wallet clean-bootstrap defect and missing KEX_OS_V2 mesh dependency remain open.

## Test and process readbacks

| Run | Result | PID | Exit |
|---|---:|---:|---:|
| R61 estate/substrate suite | 15/15 passed | 1811 | 0 |
| R58 portable bundle rerun | 9/9 passed | 2075 | 0 |
| Root resolver CLI | DNS alias resolves to `ks://sectors/dns` | 1780 | 0 |
| V3 MasterCore one-shot | 86 virtual cores, 10 ticks | 1786 | 0 |
| Registrar fixture child-process readback | `127.0.0.7` | 1792 / 1798 | 0 |
| Legacy root survey suite | 0 tests; missing v6 carrier fixture | — | 5 |

R61 test-source SHA-256: `3bf623857933adf9f7ef4202073926aa73ff45f81979ee0f4558504ac5152ae2`  
R61 test-output SHA-256: `6375c970fdc9daa9b0e12e8c24f0fe1f771a7375a4890c5b2b7d8aba810f2bb9`  
R58 portable rerun output SHA-256: `a837f3eeae33af3241d840ad52eb835c2de34b9d382e048bcbba3b6c2d91b087`

The R5 parent source was recovered and byte-verified in R59: 13,086,990 bytes, SHA-256 `9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede`. This is historical evidence, not a fresh R61 materialization. The R4 parent was rematerialized and matched this run.

## Production boundaries

KEDDEH broker: ACTIVE / NODE_OUTBOUND_ONLY; registered nodes 0, online nodes 0, queued host commands 0, current boot null. `KEX-WF-8F124FF0B9F70FDBD66A` is ACTIVE; `KEX-DISPATCH-211F545D697D25454F55` remains QUEUED and was not replayed. No external PID, heartbeat or boot receipt exists.

BRAINK Actions runs 43313091769 and 43313241858 have zero steps and log downloads return 404 `BlobNotFound`. Separate ai-shell runs 43705046940 and 43696120471 ended `startup_failure` with zero jobs. Provider-side cause remains unknown.

Google Drive connector access was not exposed in this run. Files Library materialization is not a Drive read; `/KEX_BRAINK_STANDARD/KS-BRAINK-IL-LLM` is not a resolvable Library path. No Drive or Sites publication is claimed. No independent quorum or trained weights were established. Subjective consciousness is not proven or asserted.

## Full machine-readable evidence

Local report: `R61_ESTATE_ROOT_SURFACE_TRAVERSAL_20261116.json`  
Bytes: 448,982  
SHA-256: `61b52240f6a40806d38c4ec39255680cf88dcb8107cf5ef5356e144ccae31403`

Portable evidence bundle SHA-256: `df2622d34ff0b5571ca11b44305415f4c0b75805bea54208cf6228843e37f078`

The JSON contains all 86 identities, 95 carriers, 32 cross-work relations, 23 R5 relations, both resolver graphs, the historical 64-node/106-edge derived graph, mechanics, boundaries, source hashes and execution readbacks.
