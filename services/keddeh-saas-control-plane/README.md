# KEDDEH Quarantined SaaS Control Plane R2

Production-oriented FastAPI service implementing the recovered KEDDEH SaaS dependency node while preserving strict authority boundaries between SaaS, CasePath, ClaimPath, BRAINK/KEX, EPIC, DNTG, evidence, and public projections.

## Implemented
- durable SQLite/WAL state for tenants, identities, entitlements, jobs, and receipts;
- mutation authentication hook using `KEDDEH_CONTROL_API_KEY`;
- payment-event idempotency;
- append-only SHA-256 receipt chain with readback verification;
- explicit CasePath/ClaimPath SaaS adapters;
- authority/quarantine probes;
- health/readiness endpoints;
- Docker/Compose deployment;
- GitHub Actions CI;
- regression and restart-persistence tests.

## Non-claims
No provider-network execution is inferred. Stripe, PayPal, Afterpay, Google Pay, Supabase, public DNS, and TLS require separately authenticated provider adapters and receipts.

## Local qualification
```bash
PYTHONPATH=src pytest -q
```

See `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT_RUNBOOK.md`, `docs/OPERATIONS_AND_SLO.md`, and `docs/PROVIDER_INTEGRATION_BOUNDARIES.md`.
