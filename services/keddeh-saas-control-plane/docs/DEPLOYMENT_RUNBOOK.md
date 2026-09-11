# Deployment Runbook

## Preconditions
1. Python 3.11+ or Docker/Compose.
2. Writable persistent volume for `/data`.
3. Long random `KEDDEH_CONTROL_API_KEY` stored in the deployment secret manager, never committed.
4. Reverse proxy/TLS terminator if exposed outside a trusted network.

## Container deployment
```bash
cp .env.example .env
# replace secret in .env or inject from secret manager
docker compose build --pull
docker compose up -d
docker compose exec keddeh-saas python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

## Bare-process deployment
```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export KEDDEH_CONTROL_API_KEY='...'
export KEDDEH_SAAS_DB='/var/lib/keddeh-saas/keddeh_saas.sqlite3'
uvicorn keddeh_saas.app:app --host 127.0.0.1 --port 8000 --workers 1
```

## Verification gates
- `/health`: process and receipt-chain integrity.
- `/ready`: persistence availability and chain validity.
- `pytest -q`: regression suite.
- Mutation without control key must return `401` when the key is configured.
- Replayed provider reference must emit `PAYMENT_EVENT_IDEMPOTENT_REPLAY`.
- DNTG → SaaS mutation probe must remain denied.

## Rollback
Stop the new service, restore the previous container/image, and retain the SQLite volume. Do not delete the database or receipt chain during rollback.
