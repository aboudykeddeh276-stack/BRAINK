# Operations and SLO

## Initial service objectives
- Health/readiness probes: 99.9% successful checks over the deployment window.
- Mutation durability: acknowledged mutation must be present after process restart.
- Evidence integrity: receipt-chain verification must always pass; failure is a release blocker.
- Idempotency: duplicate payment-provider references must not activate duplicate entitlements.

## Alert conditions
- `/health` or `/ready` non-200.
- `chain_valid=false`.
- SQLite I/O or constraint failures.
- repeated unauthorized mutation attempts.

## Backup
Snapshot the SQLite database and WAL consistently. Validate restore into a disposable instance and rerun `/health`, `/ready`, and evidence-chain verification before declaring backup qualification.
