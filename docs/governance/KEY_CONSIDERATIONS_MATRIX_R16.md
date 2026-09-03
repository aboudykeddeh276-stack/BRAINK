# Key Considerations Matrix R16

Every governed unit must explicitly consider the following before promotion:

1. Identity and lineage: stable unit ID, parentage, canonical semantic identity.
2. Purpose and scope: exact service/function and explicit non-goals.
3. Authority: who may create, mutate, approve, deploy, rollback and retire.
4. Runtime boundary: what actually executes and what remains conceptual/external.
5. Storage/data boundary: source of truth, persistence, retention, backup, recovery and confidentiality.
6. Network boundary: listeners, routes, carriers, external dependencies, WAN assumptions and failover.
7. Security/privacy: authentication, authorisation, secrets, least privilege, logging, data handling and incident response.
8. Legal/compliance: jurisdiction, licences, records, customer obligations and sector-specific controls where applicable.
9. Reliability: failure states, retries, idempotency, rollback, redundancy, reconciliation and disaster recovery.
10. Observability/proof: metrics, logs, receipts, hashes, causal tests and independent readback.
11. Human operations: runbook, help, escalation, administration, maintenance and training.
12. Cross-platform adaptation: semantic invariants, adapter APIs/ABIs, capability differences and unsupported functions.
13. Versioning/compatibility: schema version, migration, backward compatibility and deprecation.
14. Performance/capacity: measured limits, resource assumptions and benchmark scope without invented capacity claims.
15. Accountability: author, owner, operator, verifier, approver and evidence chain.
16. Filing/records: canonical location, naming, metadata, digest, retention and supersession.
17. External authority: distinguish internal canonical state from registrar, DNS, CA, financial, government or other third-party authority.
18. Customer/service impact: availability, support, accessibility, change communication and rollback impact.
19. Evolution: a claimed capability evolution requires contract, implementation, behavior and proof deltas.
20. Retirement: archive, migration, revocation, data disposition and tombstone/lineage record.

A unit may add sector-specific considerations, but none of these may be silently omitted when relevant.
