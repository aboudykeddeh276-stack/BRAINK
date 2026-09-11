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
- Optional Google OAuth adapter with token persistence for Sheets/Calendar/Gmail/Drive
- Docker, Compose and Kubernetes packaging
- Tests for health, cascade, mutation idempotency and version conflicts

## Address model
`1` is the sole singularity and is not a grid coordinate. `X2/Y2` is a logical address. `B2` is only the spreadsheet carrier projection of that address.

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
The repository contains deployable manifests. Actual public deployment additionally requires a container runtime/registry, credentials/secrets, target infrastructure and DNS/TLS authority. Those external states must be evidenced separately rather than inferred from source files.
