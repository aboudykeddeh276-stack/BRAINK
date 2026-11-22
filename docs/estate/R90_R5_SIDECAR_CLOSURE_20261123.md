# R90 — R5 sidecar byte/hash closure

**Architect:** A. Keddeh  
**Architecture:** KS-BRAINK-IL-LLM  
**Disposition:** additive, read-only materialization and verification. No original source, manifest, workbook or historical identity was changed. No promotion or deployment.

## Result

**Byte/hash coverage: 29/29.** R69 recorded 18/29 exact Library matches. R90 independently materialized and verified the remaining 11/11 tool, runtime and unified surfaces. This is a cumulative R69/R90 evidence chain, not a claim that all 29 were re-read in one process.

**Semantic naming review: 6 HTML title mismatches remain.** All 11 newly materialized files match the R5 manifest byte length and SHA-256. Four tool volumes and both unified surfaces expose internal HTML titles that differ from the manifest title. These identities remain unpromoted pending architect review.

## Parent and manifest bindings

| Object | Bytes | SHA-256 |
|---|---:|---|
| R5 parent `braink://volume/r5/system-orchestrator` | 13,086,990 | `9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede` |
| R5 standalone manifest | 32,546 | `a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc` |
| Embedded `r5-system-manifest` | 25,831 | `b64565d56f7172bb4db1206ca4cc8857f42dbcb1f76ae99635c629f16791ceb2` |
| Cross-work R1 manifest | 39,430 | `5d867ae7d7f517d6cdde14c138e67e90571062521e5d912fd8812165da1ce985` |

The standalone manifest declares 29 surfaces: 15 system volumes, four tool volumes, five runtime resources, three workbooks and two unified surfaces. It has 23 base relations. The cross-work child has 32 relations and binds to the exact R5 parent and standalone-manifest hashes. The embedded and standalone manifests are distinct; neither is substituted for the other.

R89 stated that the standalone JSON had not been materialized. R90 supersedes that retrieval status with a fresh exact Library materialization. R89 remains unchanged.

## Newly materialized 11/11

| Class | Logical identity | File | Bytes | SHA-256 |
|---|---|---|---:|---|
| tool_volumes | `tool://server-runtime` | `KEDDEH_LINUX_COMPUTER_v71_AUTOSTART_LINUX_SERVERS.html` | 5,093,904 | `a9b8cba41499dd95a4a8bb0c735e408c592517eccd1514b683d372b52325e3e4` |
| tool_volumes | `tool://research-fabric` | `KEDDEH_LINUX_COMPUTER_v71_RESEARCH_SECTOR_FABRIC_S26_S29.html` | 5,103,217 | `9aaf61466c123acc0554ce0a1514b40bd57b824b9bfeea0ac2b3313e150d294b` |
| tool_volumes | `tool://il-llm-hci` | `BRAINK_IL_LLM_UNIFIED_HCI_v2.html` | 54,952 | `9aeece2e7ee166420a2da45337c952beee7d1b2c1811bf52c36afb6e76d39bad` |
| tool_volumes | `tool://library-dna-governance` | `KEDDEH_BRAINK_LIBRARY_DNA_EVOLUTION_R1.html` | 766,963 | `3dbd9009b34c41f88e1349e9faec3d786f93f6ce79e974da07f3c2036b4c650e` |
| runtime_resources | `runtime://abi` | `runtime-abi.json` | 772 | `358dc830620480130f3a421bd01ff006d9ce8247923eed5ee036b0a85686ad2f` |
| runtime_resources | `runtime://registry` | `runtime-registry.json` | 1,441 | `7dbd586e68475449a435b62c0eeb0362aaa7b8d102557ffafce6dbc6799ccd96` |
| runtime_resources | `runtime://contract` | `runtime-contract.v2.json` | 1,917 | `ae2108098838e97416174d48099b8e329f660bc273ccb59892c846eca1abd0fa` |
| runtime_resources | `service://braink-sdos` | `braink-sdos.service` | 309 | `a6118a759afefab1dbb0795117116a5b02991cdafee55df432c4a01ae7b935da` |
| runtime_resources | `runtime://mesh-ignition` | `braink-infrastructure-mesh-ignition.mjs` | 12,890 | `4e02d1e09fd484844387a12c699a8d564f0cc86c301b6e334f59f64051670af7` |
| unified_surfaces | `projection://keddeh/resident-engineering-corpus/v3` | `KEDDEH_RESIDENT_ENGINEERING_CORPUS_PROJECTION_v3_SERVICE_LAYERS.html` | 4,023,659 | `254f466c559c29b8814bb434724abbebd20bfcdf54c7af143ee74fe9c098a09b` |
| unified_surfaces | `control://braink/illlm-kex/v11` | `BRAINK_IL_LLM_KEX_V11_ENGINEERING_CONTROL_PLANE.html` | 6,337,343 | `484f05f39c487b7573404c21a7f024c764e41812781e80c2929304e76deb2965` |

## Internal HTML title differences retained

| Identity | Manifest title | Actual HTML title |
|---|---|---|
| `tool://server-runtime` | KEDDEH v71 Autostart Linux Servers | KEX Linux Computer v71 |
| `tool://research-fabric` | KEDDEH v71 Research Sector Fabric S26-S29 | KEX Linux Computer v70 |
| `tool://il-llm-hci` | BRAINK IL-LLM Unified HCI v2 | BRAINK / IL-LLM — Unified Sovereign HCI |
| `tool://library-dna-governance` | BRAINK Library DNA Evolution R1 | KEDDEH BRAINK Library DNA Evolution R1 |
| `projection://keddeh/resident-engineering-corpus/v3` | KEDDEH Resident Engineering Corpus Projection v3 | KEDDEH — Recursive Self-Hosting Referential Volume v24 · P18 + A18 Integration / Closure Gate |
| `control://braink/illlm-kex/v11` | BRAINK IL-LLM KEX V11 Engineering Control Plane | BRAINK / KEX User Space v9 |

The research tool is especially sensitive: the manifest says v71 while the actual HTML title says v70. No lineage is inferred from the number alone. These are review items, not permission to rename files or rewrite history.

## Runtime checks and boundaries

- Three runtime JSON resources parsed.
- Server-runtime HTML: 24/24 embedded JSON script blocks parsed; 21/21 inline JavaScript blocks passed `node --check`.
- `braink-infrastructure-mesh-ignition.mjs`: `node --check` passed.
- `braink-sdos.service` is a descriptor only. It was not started; its `ExecStart` points to a host path not present in the 29-surface materialization.
- Runtime registry references `runtime-browser-v4.js` and `runtime-reference-v4.py`, not materialized here.
- The cross-work relation remains `ADMITTED_RELATION_ROUTE_NOT_TARGET_EXECUTION`; it is not target execution or independent quorum.
- Source scope is ChatGPT Files Library materialization, not a live Google Drive read or upload. No Google Drive connector was exposed.
- The historical root-v16 carrier remains unrecovered. No candidate was substituted.
- No external host PID, heartbeat, restart receipt, independent quorum, trained weights or subjective-consciousness proof is established.
