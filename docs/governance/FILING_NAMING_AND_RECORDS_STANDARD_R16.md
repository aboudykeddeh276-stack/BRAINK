# Filing, Naming and Records Standard R16

Canonical root: `KEX://GOVERNANCE/<sector>/<kind>/<unit>/`.

Repository projection: `governance/<sector>/<kind>/<unit>/`.

Drive projection mirrors the same hierarchy.

Artifact name: `<sector>__<kind>__<unit>__<artifact>__r<revision>.<ext>`.

Receipt name: `<unit-id>__<process-id>__<receipt-id>__<UTC timestamp>__<digest-prefix>.json`.

Required metadata: unit ID, parent, sector, artifact class, author, owner, authority, revision, timestamps, lineage, digest, status, supersession, retention, access classification and proof/readback reference.

Control documents are versioned. Execution receipts are append-only. Generated projections may be replaced only when linked to the prior revision and reverified.

A file without governed unit, owner, purpose or filing root is `ORPHANED`. Orphans are classified, migrated, archived or retired and never silently acquire authority.
