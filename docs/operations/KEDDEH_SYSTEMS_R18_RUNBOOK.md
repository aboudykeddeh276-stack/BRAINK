# KEDDEH SYSTEMS R18 Runtime Bindings Runbook

## Release authority
Canonical source: `aboudykeddeh276-stack/BRAINK` on `main`.

## Qualification gate
1. Compile the R18 adapter/runtime modules.
2. Execute `python scripts/kex-ci/test_runtime_bindings_r18.py`.
3. Require every local qualification check to pass.
4. Read `enterprise/adapters/BINDING_REGISTER_R18.json` as the authoritative binding state.
5. Do not promote an external provider beyond observed evidence.

## Start local runtime ingress
`python enterprise/runtime/http_ingress.py`

Default local endpoint: `127.0.0.1:19420`.

Readback endpoints:
- `/health`
- `/metrics`

## Process supervision
Use `enterprise.runtime.process_supervisor.ManagedProcess` for start/alive/stop lifecycle control. Managed subprocesses run in a distinct process group so shutdown can terminate the complete group rather than leaving orphan descendants.

## Provider boundaries
- Gmail: authenticated control plane bound. Live send is not promoted until side-effect/readback qualification is intentionally executed.
- Google Contacts: read-only identity lookup bound.
- Google Calendar: read binding confirmed. Writes require intentional side-effect qualification.
- Google Drive: create/write binding confirmed.
- Payments: provider-neutral contract implemented; provider remains unbound until authenticated authorize/capture/refund/reconcile operations are proven.
- Public HTTP ingress: local HTTP service proven; public routing/TLS remains unbound until an actual external ingress is attached and read back.

## Rollback
1. Stop the R18 managed process group.
2. Restore the predecessor runtime and binding-register commit.
3. Preserve execution receipts, observer/evidence records, and continuation state.
4. Re-run the predecessor qualification before re-promoting it.

Rollback never deletes evidence of the failed or superseded release.

## Replica policy
Satellite BRAINK repositories consume the canonical R18 deployment descriptor and must not independently redefine binding truth. Their role is hydration/entry-point replication, while the canonical repository remains the release authority.
