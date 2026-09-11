# BRAINK/KEX Runtime Publish Bundle

This bundle turns the recovered architecture into a typed, evidence-bearing runtime instead of treating schedules, projections and implementation as interchangeable.

## Implemented now
- Typed object registry and evidence states
- Deterministic 7-stage cascade: MOUNT → VERIFY → HYDRATE → RESOLVE → MUTATE → WRITE_BACK → PROOF
- Idempotent action execution with optimistic version checks
- SHA-256 mutation receipts
- Append-only JSONL proof ledger
- Durable SQLite runtime/object/request registry
- FastAPI health/services/cascade/runtime/ledger/object APIs
- OpenPyXL workbook service
- Cross-system SaaS node for systems, tenants, entitlements and provisioning intents
- Verified-payment ingestion that grants entitlement and creates one deterministic provisioning intent per provider event
- Replay protection for payment events and provisioning requests
- Fail-closed separation between provider webhook verification and SaaS state mutation
- Estate bindings for host control, public ingress, payment rail and identity rail
- Optional Google OAuth adapter with token persistence for Sheets/Calendar/Gmail/Drive
- Docker, Compose and Kubernetes packaging
- Tests for health, cascade, mutation idempotency, version conflicts, SaaS routing, payment activation and replay safety

## Address model
`1` is the sole singularity and is not a grid coordinate. `X2/Y2` is a logical address. `B2` is only the spreadsheet carrier projection of that address.

## Payment → entitlement → provisioning path
The production boundary is deliberately split into distinct implementation surfaces:

1. `runtime/public_gateway.py` accepts `/payments/stripe/webhook` and forwards the raw signed body to the local Stripe rail.
2. `runtime/stripe_payment_rail.py` asks the KEX capability runner to verify the Stripe signature. Provider secrets remain behind that capability boundary.
3. For supported Checkout events, the verified event metadata is normalized into `{tenant_id, system_id, service_id, plan}` and sent to `/saas/payments/verified-event`.
4. `braink_runtime.saas.SaaSNode` records the provider event, grants the entitlement only for a paid state, and creates a deterministic `PENDING_ACTUATION` provisioning intent.
5. Replayed provider events return the existing result and cannot create a second provisioning intent.
6. Host execution remains a separate fail-closed stage. Payment success does not claim that a service has been physically deployed.

Checkout creation must carry `tenant_id`, `system_id`, `service_id` and `plan` so the verified provider event can be mapped back to the exact logical service relation.

Required rail/runtime environment:

```bash
export BRAINK_AUTH_TOKEN='replace-this'
export BRAINK_SAAS_AUTH_TOKEN="$BRAINK_AUTH_TOKEN"
export BRAINK_SAAS_ENDPOINT='http://127.0.0.1:8000'
export BRAINK_STRIPE_SOCKET='/tmp/braink-stripe.sock'
export KEX_RUNNER_SOCKET='/run/keddeh/kex-runner.sock'
```

`BRAINK_SAAS_AUTH_TOKEN` is never sent to Stripe. It authenticates the local verified-event handoff from the secret-bearing payment rail to the SaaS runtime.

## Run locally
```bash
python -m pip install -e .
export BRAINK_AUTH_TOKEN='replace-this'
PYTHONPATH=src python scripts/seed_registry.py
PYTHONPATH=src uvicorn braink_runtime.app:app --host 127.0.0.1 --port 8000
```

## Test
```bash
PYTHONPATH=src pytest -q
```

## Google write integration
Install `.[google]`, provide your own OAuth Desktop credentials, and point `BRAINK_GOOGLE_CREDENTIALS` / `BRAINK_GOOGLE_TOKEN` at local secret files. Credentials are deliberately not included in the publishable bundle.

## Deployment truth
The repository contains deployable manifests and the payment-to-entitlement-to-provisioning control path. Actual public deployment additionally requires a live execution carrier, container runtime/registry, credentials/secrets, target infrastructure and DNS/TLS authority.

A source commit, a queued workflow, a verified payment, an entitlement and a `PENDING_ACTUATION` provisioning intent are all different evidence states. None is silently promoted into proof that the final customer service is physically running. External runtime state must be read back and evidenced separately.
