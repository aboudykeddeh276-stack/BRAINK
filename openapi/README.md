# OpenAPI Contracts

This directory defines external interface contracts for KEX/WBOS and the unified action/data surfaces. OpenAPI describes callable interfaces; it is not an execution authority and it does not prove a deployment exists.

## Contract classes

The current repository carries API descriptions for two related concerns:

1. **Workbook/data and WBOS cascade surfaces** such as workbook datasets, health, services, routes, KEX URI resolution, mesh/cascade state and proof-ledger readback.
2. **Action/runtime surfaces** such as typed mutations, runtime launch/readback, deployment operations, Casepath dispatch, workbook mutation, proof writes and participant integrations.

## Source of truth

When contract text and runtime behavior diverge, the divergence is a defect to be reconciled. Neither side should be silently treated as authoritative without readback.

Important examples:

- a declared bearer security scheme requires runtime enforcement;
- a `200` schema must match the actual response shape;
- scoped capabilities used by the runtime should appear in the contract when exposed to clients;
- residency/error states should be represented explicitly rather than replaced by fabricated rows;
- deployment states must distinguish `TL2_LIVE` from `PUBLIC_LIVE`.

## Execution boundary

```text
OpenAPI operation
→ client request
→ runtime route
→ authorization / IL-LLM translation where applicable
→ mutation or read
→ receipt/readback
```

Only the latter stages establish execution.

## IL-LLM relationship

IL-LLM can act as a translation layer before an action reaches an API actuator:

```text
local IL-LLM intent
→ global IL-LLM context
→ typed ACTION::TARGET residual
→ narrow capability
→ OpenAPI/runtime operation
→ receipt
→ context re-entry
```

This permits API operations to remain concrete machine contracts while IL-LLM supplies contextual resolution and authority narrowing.

## Validation

Validate syntax/schema separately from runtime behavior. A contract parser passing proves contract structure, not endpoint availability. Runtime tests should additionally verify:

- positive/negative authentication;
- request/response schema agreement;
- idempotency behavior;
- source-not-resident behavior;
- readback policy;
- proof receipt fields;
- current service-generation identity for live promotion.

## Publication

Placeholder or local servers must not be presented as public deployment evidence. Public host URLs are promoted only after public DNS/TLS/ingress/outside-in readback has been independently observed.
