# Deployment Runbook R2.1

## Preconditions

1. BRAINK repository checkout containing the candidate service plus resident `runtime/illlm_ledger.py` and `runtime/runtime_registry.py`.
2. Persistent state for both SaaS SQLite and BRAINK evidence/runtime state.
3. `KEDDEH_CONTROL_API_KEY` bound outside source control.
4. For canonical Linux deployment: `SERVERS-KEDDEHSYSTEMS` carrier PR #3 (or its promoted successor) available on the authorised host.
5. Public ingress/TLS is a separate binding and must not be inferred from local process activation.

## Local qualification

From `BRAINK/services/keddeh-saas-control-plane`:

```bash
PYTHONPATH=src:../.. pytest -q
PYTHONPATH=src:../.. python -m compileall -q \
  src tests ../../runtime/illlm_ledger.py ../../runtime/runtime_registry.py
```

Expected current qualified result: `5 passed` and compileall `PASS` for the R2.1 code path. Re-run; do not inherit the historical result as current evidence.

## Container candidate

The Compose file intentionally builds from the BRAINK repository root so the image copies the resident `runtime/` implementation rather than a synthesized duplicate.

From `BRAINK/services/keddeh-saas-control-plane`:

```bash
cp .env.example .env
# bind the control key outside source control
docker compose build --pull
docker compose up -d
```

Then read back:

```bash
python - <<'PY'
import json, urllib.request
for path in ('/health','/ready','/v1/braink/status'):
    with urllib.request.urlopen('http://127.0.0.1:8000'+path, timeout=5) as r:
        print(path, json.loads(r.read()))
PY
```

A successful image build is `SOURCE/IMAGE_EXECUTION` evidence only. It is not canonical Linux-host or public deployment evidence.

## Canonical Linux/server carrier

Server process execution belongs to `SERVERS-KEDDEHSYSTEMS`.

On an authorised Linux host with the BRAINK source tree at `/opt/keddeh/BRAINK`:

```bash
sudo ./deploy/install_keddeh_saas_control_plane.sh alpha-production
```

On first invocation the installer creates `/etc/keddeh/saas/alpha-production.env` and exits without starting the service until `KEDDEH_CONTROL_API_KEY` is bound. This is intentional.

After configuration, rerun the installer. It must perform resident BRAINK imports, compile qualification, `systemd` activation, and local HTTP/BRAINK readback via `validate_keddeh_saas_control_plane.py`.

## Verification gates

- `/health.local_evidence_chain == true` qualifies the local receipt chain only.
- `/ready.service_ready == true` qualifies local SaaS persistence/chain readiness.
- `/ready.braink_evidence_ready == true` requires BRAINK ledger health and no unsynchronized local evidence.
- `/ready.qualification_ready == true` requires both local and BRAINK evidence conditions.
- `/v1/braink/status.status == PASS` verifies the resident BRAINK evidence/runtime dependencies can be read.
- existing BRAINK runtime records must remain unchanged by candidate admission.
- public ingress requires separate external readback.

## Rollback

Stop/disable the new carrier while retaining `/var/lib/keddeh/saas/<instance>` state. Do not delete SaaS SQLite, BRAINK evidence state, or runtime registry state during rollback. Restoring code does not authorize rewriting an existing BRAINK runtime record.
