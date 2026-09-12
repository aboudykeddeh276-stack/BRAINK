# Operations and SLO R2.1

## Qualification signals

Do not collapse the service's independent signals:

- `/health.status` — local SaaS process/receipt-chain result.
- `/ready.service_ready` — local SaaS state readiness.
- `/ready.braink_evidence_ready` — resident BRAINK IL-LLM/runtime dependency health plus zero unsynchronized local receipts.
- `/ready.qualification_ready` — conjunction of the local and BRAINK evidence conditions.
- public reachability — not represented by the above and requires independent external readback.

## Initial objectives after authorised host deployment

These are objectives, not currently achieved SLO evidence:

- local health/readiness checks: target 99.9% successful checks over the measured deployment window;
- mutation durability: an acknowledged local mutation remains present after process restart;
- local evidence integrity: receipt-chain verification remains true;
- BRAINK evidence synchronization: committed local receipts reach `SYNCED` or expose a visible `FAILED` state; no silent drop;
- runtime preservation: candidate admission never rewrites a pre-existing BRAINK runtime definition;
- idempotency: duplicate provider references do not create duplicate entitlements.

## Alert conditions

- `/health.status != PASS`;
- `/ready.service_ready == false`;
- `/ready.braink_evidence_ready == false`;
- any `braink_evidence_sync` row in `FAILED`;
- local `chain_valid == false`;
- SQLite I/O/constraint failure;
- unexpected mutation-auth failures or repeated unauthorized attempts;
- any change to an existing BRAINK runtime record caused by candidate admission.

## Backup and restore

Back up the SaaS SQLite/WAL state and the configured `BRAINK_SAAS_STATE_DIR` together. Restore into a disposable instance and independently verify:

1. `/health`;
2. `/ready`;
3. local receipt chain;
4. BRAINK IL-LLM ledger verification;
5. runtime-registry readback;
6. pending/failed BRAINK-evidence synchronization state.

A copied database is not a qualified backup until restore/readback has been observed.
