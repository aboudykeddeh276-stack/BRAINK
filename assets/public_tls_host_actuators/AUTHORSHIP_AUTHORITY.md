# Authorship and Authority

## Distinct identities

Do not collapse these roles:

```text
AUTHORSHIP ≠ REPOSITORY OWNERSHIP ≠ RUNTIME AUTHORITY ≠ OPERATOR ≠ EXTERNAL AUTHORITY
```

## Repository ownership

Canonical repository: `aboudykeddeh276-stack/BRAINK`.

The actuator asset is maintained under:

```text
assets/public_tls_host_actuators/
```

Changes are proposed through the asset branch/PR lineage and must preserve the pull order documented in `WORKFLOW_CONTROL.md`.

## Authorship record

Every consequential change must be attributable through Git commit identity and pull-request history. Generated runtime receipts should also record the executing commit SHA and, where available, workflow run/job or operator identity.

## Runtime authority classes

- `BRAINK` — orchestration and admission authority.
- `KEX` — canonical state/address/transition interpretation.
- `SERVERS-KEDDEHSYSTEMS` — registrar/DNS implementation authority.
- `PUBLIC_DOMAIN_AUTHORITY` — authority to publish/withdraw DNS-01 challenge state.
- `BRAINK_LOCAL_TLS_AUTHORITY` — resident TLS root/controller.
- `PUBLIC_CA_AUTHORITY` — external certificate issuer reached through ACME.
- `SERVER_ROOT` — authority to install/activate service certificate material.
- `HOST_OS/HOST_FILESYSTEM/HOST_TLS_RUNTIME` — substrate authorities for process, filesystem and TLS primitives.

## Mutation authority

A component may mutate only the substrate it owns or an explicitly delegated interface.

Examples:

- DNS-01 actuator may modify resident registrar TXT state, not arbitrary registrar internals.
- public CA adapter may request issuance; it may not redefine DOMAIN_ROOT.
- SERVER_ROOT actuator may install/rollback certificate material; it may not modify registrar ownership.
- workflow may orchestrate operations; it is not the underlying domain or CA authority.

## Approval and accountability

Consequential production mutation requires:

1. exact source SHA;
2. complete dependency graph cut;
3. successful dependency submission;
4. resolved authority/bindings;
5. passing pre-mutation tests;
6. mutation receipt;
7. independent readback;
8. rollback capability.

A person, agent or workflow that bypasses those gates owns the resulting non-conformance and must record it as such rather than relabeling it successful.

## Authorship versus legal ownership

Source authorship, repository control and legal/business ownership are separate concepts. Runtime records should identify technical authorship/actor and authority without making unsupported legal ownership claims.

## No anonymous promotion

A deployment cannot be promoted when the executing source SHA, authority path or receipt lineage is unknown.