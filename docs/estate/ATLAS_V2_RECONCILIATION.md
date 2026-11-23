# Estate atlas v2 reconciliation

Architect: A. Keddeh  
Canonical identity: KS-BRAINK-IL-LLM  
Disposition: derived, reviewable inventory; not deployment or mechanics qualification.

The prior HTML atlas embedded 12 identities. The source workbook reconciles 33 R5 identities with 76 P11 logical objects. Their union is 86 identities: 23 overlaps and 10 R5-only logical identities. P11 contains 95 unique carrier IDs, 3 duplicate raw rows (98 total rows), and 19 genuine multi-carrier objects. Represented carrier bytes total 6,630,073.

The ten R5-only identities are preserved as logical-only:
- `app://casepath/analytical-matter-mesh/v18`
- `braink://volume/r4`
- `braink://volume/r5/system-orchestrator`
- `candidate://app/kos-bos/json-manifest-fixed`
- `control://braink/illlm-kex/v11`
- `projection://keddeh/resident-engineering-corpus/v3`
- `tool://IL-LLM-HCI`
- `tool://library-dna-governance`
- `tool://research-fabric`
- `tool://server-runtime`

The source workbook column is named `Integrity`. Its algorithm is unspecified; values are preserved verbatim and are not relabelled SHA-256. Missing values remain missing.

The full derived HTML and JSON artifacts are generated separately and their exact byte sizes and SHA-256 values are recorded in `ATLAS_V2_SOURCE_MANIFEST.json`. The 12 enriched prior entries are preserved. The atlas labels each entry's inspection boundary and does not claim that every carrier's bytes/mechanics were executed.

Original source files were not modified. No site publication or Google Drive write was performed by this build.
