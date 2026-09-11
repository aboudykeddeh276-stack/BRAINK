# KEDDEH SaaS Control Plane — Architecture

## Purpose
This service is the SaaS dependency node for KEDDEH product runtimes. It is **not** the CasePath business runtime, ClaimPath product runtime, BRAINK/KEX execution core, EPIC claim engine, or DNTG research model.

## Authority boundaries
- CasePath/ClaimPath may **require** SaaS services.
- SaaS may dispatch only explicitly admitted BRAINK/KEX capabilities.
- EPIC may govern claim promotion but does not own SaaS state.
- DNTG has no SaaS mutation authority.
- Public HCI is a projection, never canonical state by appearance.

## Owned state
Tenants, identity bindings, payment-derived entitlements, jobs, and append-only evidence receipts.

## Persistence
SQLite WAL is the current durable local store. A future database adapter may replace it only behind the same state contracts and receipt semantics.

## Security model
Mutation endpoints can require `X-Keddeh-Control-Key` via `KEDDEH_CONTROL_API_KEY`. Payment-provider credentials and secrets are deliberately absent from this service. Provider webhook verification belongs in provider-specific adapters.
