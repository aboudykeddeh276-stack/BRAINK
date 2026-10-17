# KEDDEH SaaS Control Plane — Architecture R2.1

## Authority model
This candidate is subordinate to the authority contracts already resident in the estate.

- BRAINK owns resident orchestration/state mechanics, its runtime registry, and BRAINK proof/evidence relations.
- SERVERS-KEDDEHSYSTEMS owns Linux/server process execution, listeners, host binding, and server-side runtime qualification.
- SaaS state owns tenant, identity-binding, entitlement, queue, and local receipt state only.
- CasePath and ClaimPath keep their business/product semantics.
- EPIC does not own SaaS mutation state.
- DNTG has no SaaS mutation authority.

A derived SaaS representation is never promoted above the resident BRAINK or server implementation from which it was derived.

## Resident BRAINK dependencies
The service imports and uses:

- `runtime/illlm_ledger.py` — canonical append-only IL-LLM evidence ledger;
- `runtime/runtime_registry.py` — resident runtime registry.

The service does not carry synthesized replacements of those modules. Linux container packaging copies the repository's resident `runtime/` directory into the image build context.

## Runtime-preservation law
`runtime://braink/saas-control-plane` may be registered only when absent. If a runtime record already exists, the candidate returns it unchanged and reports whether its command/argv are compatible. It does not rewrite the existing record.

## SaaS-owned state
SQLite/WAL currently stores:

- tenants;
- identity bindings;
- payment-derived entitlements;
- queued jobs;
- local append-only receipts;
- explicit BRAINK-evidence synchronization state for each local receipt.

## Evidence relation
A committed local receipt is projected into BRAINK's IL-LLM ledger. The projection is recorded locally as `SYNCED` or `FAILED`. A failed projection is surfaced in evidence/readiness output and is not rewritten as qualification success.

BRAINK evidence projection does not become the business-state authority for CasePath, ClaimPath, tenant state, or entitlements.

## API completion states
The catalogue distinguishes:

- `implemented` — executable paths present in this candidate;
- `descriptor_only` — relation descriptions with no executable domain adapter behind them;
- `declared_unbound` — dependencies/capabilities not established by this candidate.

This distinction is normative. Documentation may not promote a lower state to a higher state without execution/readback evidence.

## Execution carrier
The Linux/systemd carrier is staged in `SERVERS-KEDDEHSYSTEMS` rather than being redefined as BRAINK authority. Server-side promotion requires an authorised host and property-scoped readback.

## Provider boundary
Payment-provider credentials, webhook signature verification, external identity providers, public ingress, DNS/TLS, and production reachability remain separate bindings. Their absence is reported as unbound, not silently synthesized.
