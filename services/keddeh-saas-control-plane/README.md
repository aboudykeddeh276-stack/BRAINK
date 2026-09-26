# KEDDEH Quarantined SaaS Control Plane R2.1

This branch is a candidate SaaS dependency implementation inside the BRAINK estate. It does not supersede BRAINK's resident runtime/evidence mechanisms, CasePath or ClaimPath business authority, or the SERVERS-KEDDEHSYSTEMS execution-carrier authority.

## Implemented in this candidate
- durable local SQLite/WAL state for tenants, identity bindings, entitlements, jobs, receipts, and BRAINK-evidence synchronization state;
- mutation authentication hook using `KEDDEH_CONTROL_API_KEY`;
- payment-event idempotency;
- append-only local SHA-256 receipt chain with readback verification;
- direct consumption of BRAINK's resident `runtime/illlm_ledger.py` and `runtime/runtime_registry.py`;
- IL-LLM evidence mirroring for committed local receipts, with persisted `SYNCED` / `FAILED` state;
- runtime-registry admission that refuses to overwrite an existing BRAINK runtime record;
- authority/quarantine probe;
- health/readiness endpoints that separate local readiness, BRAINK-evidence readiness, and qualification readiness;
- Linux container packaging that copies the resident BRAINK `runtime/` implementation from repository context;
- regression tests, including preservation of an existing working runtime definition.

## Descriptor-only surfaces
`/v1/adapters/casepath` and `/v1/adapters/claimpath` are descriptions of allowed SaaS relations. They are **not** executable CasePath/ClaimPath adapters and are marked `DESCRIPTOR_ONLY` in their responses.

## Declared but unbound
The candidate does not currently establish external database providers, external identity providers, payment-provider networks, external job workers, public ingress, or production deployment. The live catalogue exposes these as `declared_unbound`, not implemented services.

## Execution carrier
Linux/systemd carrier mechanics belong to `aboudykeddeh276-stack/SERVERS-KEDDEHSYSTEMS`. A matching carrier candidate is staged on branch `deploy/keddeh-saas-control-plane-r2-carrier`; repository staging is not host execution.

## Qualification command
From `services/keddeh-saas-control-plane` inside the BRAINK repository:

```bash
pytest -q
```

The test configuration includes the BRAINK repository root so the candidate is qualified against the resident runtime modules rather than a copied test double.

## Promotion rule
Do not call this production-deployed until an authorised server host executes the canonical carrier, the service is read back from that host, BRAINK evidence readiness is observed, restart/rehydration is verified, and any claimed public ingress is independently read back from the relevant external vantage.
