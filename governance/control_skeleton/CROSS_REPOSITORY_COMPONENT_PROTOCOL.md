# Cross-Repository Component Adoption Protocol

## Purpose

Govern components whose implementation and authority live in one repository but are consumed, qualified or orchestrated by another.

The objective is reuse without semantic duplication.

## Core rule

```text
OWNING REPOSITORY
  defines class + state + interface + mutation authority + receipts
        ↓
EXACT REVISION / COMPATIBILITY CONTRACT
        ↓
CONSUMER ADAPTER
        ↓
CONSUMER-SPECIFIC INVARIANTS
        ↓
CROSS-REPO EVIDENCE RECONCILIATION
```

The consumer must not copy the owned mechanic merely to make it local.

## Required records

For every cross-repository component register:
- component ID;
- owning repository;
- owning sector;
- external component spec/control index where available;
- runtime/interface identity;
- consuming repository/module;
- dependency class;
- compatible/pinned revision for qualification;
- producer receipt schema;
- consumer proof conditions;
- failure ownership map;
- promotion state.

## Authority separation

```text
component authorship
≠ repository ownership
≠ runtime mutation authority
≠ consumer orchestration authority
≠ execution carrier
```

A consumer may authorize invocation without becoming the owner of the invoked mechanic.

## Adoption sequence

1. Discover the existing owning mechanic before coding a replacement.
2. Read owning repository inventory/governance/control files.
3. Resolve the producer interface and receipt schema.
4. Register the external component in `GOVERNANCE_TARGET_REGISTRY.json`.
5. Add a dependency fragment linking consumer to owning repo/runtime.
6. Implement the smallest consumer adapter.
7. Keep state-transfer/authority semantics inside the owner unless the owner contract explicitly delegates them.
8. Define consumer-specific postconditions separately.
9. Qualify owner in isolation, then consumer integration, then cross-process/cross-machine lanes as required.
10. Reconcile evidence using the claim's actual evidence level.

## Revision rule

Qualification must resolve exact revisions for both producer and consumer. Branch names can select development lines but are not immutable proof identifiers.

## Evidence composition

Producer receipt proves only producer semantics. Consumer evidence composes that receipt with consumer invariants.

Example:

```text
KEX mirror receipt
proves: verified mirrored/restored bytes + manifest parity

BRAINK logical-computer receipt
proves: logical ID/state/lineage/authority invariants after consuming restored state
```

Neither receipt alone proves the other's semantics.

## Failure ownership

Classify before patching:
- owner implementation defect;
- consumer adapter defect;
- incompatible contract/revision;
- carrier corruption;
- executor unavailable;
- consumer invariant failure;
- governance/dependency admission failure.

Patch the owning layer. Do not build an abstraction around the failure in the wrong repository.

## Promotion

Cross-repo promotion requires:
- owner component specified;
- dependency admitted;
- exact revisions recorded;
- owner qualification observed;
- consumer integration observed;
- required higher-level proof observed;
- unresolved failures assigned to an owner;
- control documents and registries updated.

Triggered or queued workflows are not promotion evidence.

## Cross-platform rule

The cross-repo interface should express required capabilities and schemas, not hard-coded platform paths. Platform-specific carriers/adapters remain replaceable projections.
