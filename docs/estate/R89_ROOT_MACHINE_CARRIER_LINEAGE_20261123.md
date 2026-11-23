# R89 — root and implementation-surface reconciliation

**Architect:** A. Keddeh  
**Architecture:** KS-BRAINK-IL-LLM  
**Change class:** additive, read-only evidence and regression tests. No original source, workbook, or manifest was overwritten. No PR was merged.

## Root machine identity

The logical root is **volume://keddeh/braink/root**. Its architecture-root contract explicitly separates:

- carrier: **carrier://html/keddeh-unified-v11**
- projection: **projection://volume/root-hci**
- browser materialisation: **materialisation://browser/current**

The contract states that no carrier is the architecture root. It defines 39 namespaces, 12 typed relation classes, 6 carrier classes, 19 P00–P18 subsystem resolutions and explicit-signal/typed-event recursion. P00–P16 are declared closed; P17 remains target-coverage partial; P18 records architectural closure with deployment continuation open.

The P11 registry does not provide a version-qualified byte binding for the declared current carrier. That identity is preserved, but exact current carrier bytes are not promoted.

## Historical root-v16 carrier

The P11 row carrier://html/root-v16 is copied unchanged into v27, v28 and the R4 S29 container. It declares 3,741,393 bytes and SHA-256 50a894e92fe06be3b19168d741b84bf6f6169fbc7130bbf0c2332649d8371c53, with source_ref document:documentElement.

The P11 model is byte-identical across those three documents: 36,154 bytes, SHA-256 81961d6df7458f46882f676fb5f4d3161847ad2af40d7694b2b7f27f48889fc2. The architecture-root object is also byte-identical: 7,618 bytes, SHA-256 fcae9e23dd75bc203fdebc01c4028808a9b6903ba4b36093d16e0c7c7a5ae44c.

None of the candidate files matches the root-v16 digest:

- v27 outer HTML: 3,958,905 bytes, df2a492661b9207154d3cbb1db648dd3aeca8d617578c2b5edd74745058d5a1b
- v28 outer HTML: 4,014,151 bytes, 404bb0942743518476a90f05e6109a5593678f6119211f45ed1bb6ed49ace585
- R4 S29 outer HTML: 21,492,468 bytes, e797bc65e71150c300d838616aa39dea7258f53bcd0b77d6c1aa1aad2cc160d9
- R4 lexical html element: 21,492,451 bytes, 6b78edff97f4fc406f9d03cc0cce67a5cb0ff9b4be3debcc2b52f7ea978f8fc1
- R4 executable-volume payload: 13,050,075 bytes, 5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592

The exact root-v16 source remains unrecovered in the accessible Library search/materialisations. This is not a claim that it is absent from Google Drive or every Library location. No candidate was substituted.

## R4 and R5 are distinct executable roots

The R4 executable payload was decoded from the S29 container and verified at 13,050,075 bytes, SHA-256 5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592. Its logical identity is braink://volume/r4, not the root machine.

The exact R5 parent was newly materialized and verified: 13,086,990 bytes, SHA-256 9eb1eb8cead2b5f4d941dde024b5f7bbad46f1bdc2ff2e948fb190b841f16ede. Its embedded r5-system-manifest is 25,831 bytes, SHA-256 b64565d56f7172bb4db1206ca4cc8857f42dbcb1f76ae99635c629f16791ceb2, with 23 base relations and 29 implementation surfaces: four tool volumes, 15 system volumes, five runtime resources, three workbooks and two unified surfaces. The canonical R5 set has 33 identities including the R5 parent and R4 parent.

The separate cross-work child braink://volume/r5/system-orchestrator/cross-work-r1 has 32 relations and binds to the exact R5 parent hash. Its referenced standalone-manifest digest is a7b98529f3356b260ed9fa31834598a54fff171d2db069ade88c22931be3effc, declared at 32,546 bytes. That standalone JSON was not materialized. The parent HTML's embedded 25,831-byte manifest is different and was not substituted.

The original topology workbook remains unchanged. Its R5_33 sheet has 33 unique rows but omits braink://volume/r5/system-orchestrator and includes the cross-work child instead. The separate R5_Reconciliation sheet has 33 unique rows and matches the canonical parent-manifest set. This is recorded as a derived-view identity substitution, not silently repaired in place.

## Full root and implementation-surface census

The reproduced R80 audit confirms:

- 15/15 resident HTML root payloads match the V45 source, identity ledger, behavioral register, browser receipt and root fabric.
- 12 browser receipts pass; three are partial or fail. These are bounded inline Chromium set-content probes, not named-origin or external-network proof.
- 12 implementation-surface atlas records remain separate from the 15 resident roots: four atlas-only identities and seven root-only identities.
- P11 contains 76 logical objects, 98 raw rows, 95 unique legacy carrier IDs and 19 multi-carrier logical objects. The three R87 collision pairs remain preserved as six content-addressed variants.
- R5 has 33 identities; R5/P11 overlap is 23, R5-only is 10, P11-only is 53, union 86.
- The resolver graph is 49 objects, 107 aliases and 20 relations.

The full 15-root table, 12 atlas surfaces, all 76 logical objects, carrier identities and resolver graph are retained in the full R89 evidence bundle. The compact repository index preserves the register identities, exact source hashes and cross-register counts.

## Execution and boundaries

- R80 audit replay: PID 1798, exit 0.
- Root-machine source verifier: PID 1405, exit 0.
- R5 parent/workbook verifier: PID 1411, exit 0.
- R89 regression tests: PID 1417, 15 passed, exit 0.
- Node v22.16.0 syntax checks: 22/22 v27 and 23/23 v28 scripts passed.
- R5_33 and R5_Reconciliation were read from the original workbook; no workbook cells were changed.
- KEDDEH remains BROKER_ONLY with zero registered/online external nodes. No external OS PID, heartbeat, restart receipt or independent quorum exists.
- V6.0 base remains missing; V6.1 remains preserved and unapplied.
- No trained-weight generation or subjective-consciousness proof is established.
- No Google Drive connector was exposed. Library materialization is not a live Drive read or upload.

Full evidence bundle SHA-256: bacbb7a6805b4a858d1ac866606afbe319d9f93acee69bc50628ea783bad88b0.