# Key Considerations

## Classification

Do not collapse computation, storage, addressing, communication, transport, virtualisation or authority into one runtime label.

## Security

- never commit private keys;
- fail closed on authority drift;
- validate key/certificate correspondence;
- validate SAN coverage and issuer chain;
- require external hostname/system-trust verification for public promotion;
- serialize production mutation and preserve rollback.

## Reliability

- distinguish source presence from runtime consumption;
- use readback after every consequential mutation;
- preserve pre-state sufficient for rollback;
- treat runner allocation as a carrier boundary, not code failure;
- reject ambiguous host bindings.

## Dependency integrity

Dependency Graph submission is part of admission. Architectural/runtime dependencies not visible to package managers must remain explicitly represented.

## Interoperability

The public CA adapter, registrar/DNS actuator and SERVER_ROOT actuator are replaceable at representation boundaries only when the replacement preserves the interface and proof contract.

## Portability

Portable means semantic and interface compatibility across substrates, not identical path names or process managers.

## Accountability

Every promoted claim must resolve to source SHA, authority, proof class and receipt lineage.

## Invalid overclaims

Do not claim:
- public issuance from a local CA test;
- public TLS from localhost HTTPS;
- deployment from certificate file creation alone;
- dependency admission from graph generation without accepted submission;
- external machine execution from queued/pending workflow state;
- DNS authority from a TXT row that is not served through the authoritative path.

## Evolution

New sector/module adaptations should reuse the governance skeleton, then specialise only the interfaces, authorities, evidence classes, cross-platform adapters and promotion conditions that differ.