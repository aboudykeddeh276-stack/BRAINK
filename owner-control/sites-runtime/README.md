# BRAINK × KEX Sites Control Plane

Owner-controlled website runtime and estate manager. It is deliberately independent of any single hosted Sites product.

## What it does
- Persistent site identities and domain bindings in SQLite.
- Immutable multi-file source versions with SHA-256 manifests.
- Atomic local publication and an external command-adapter boundary.
- Public HTTP readback receipts.
- Hash-chained event ledger with verification endpoint.
- Browser control panel plus JSON API.
- Optional bearer-token protection for all mutations.
- No inferred GitHub-to-Site relationship and no fake provider success.

## Run
```bash
cd owner-control/sites-runtime
export KEX_SITES_TOKEN='replace-with-a-secret'
python3 app.py --host 127.0.0.1 --port 8787
```
Open http://127.0.0.1:8787. If a token is configured, set `localStorage.kex_sites_token` in the browser or send `Authorization: Bearer …`.

## API
`GET /api/health`, `GET/POST /api/sites`, `GET /api/sites/{id}`, `POST /api/sites/{id}/domains`, `POST /api/sites/{id}/versions`, `POST /api/sites/{id}/deploy`, `POST /api/sites/{id}/readback`, `GET /api/events`, `GET /api/ledger/verify`.

A version request is `{"message":"…","files":{"index.html":"…","assets/app.js":"…"}}`.

Local deployment publishes to `KEX_SITES_PUBLISH_ROOT/<slug>`. For a real provider, set `KEX_SITES_DEPLOY_CMD`; the adapter receives a JSON request on stdin and its exit status/stdout/stderr become deployment evidence. This keeps provider-specific credentials and mechanics outside the core while preserving proof.

## Truth boundary
A domain record is not a deployment. A deployment is not public availability. A provider command returning zero is not public readback. Those are separate states and separate receipts.

Historical estate data remains in `../COMPLETE_SITE_ESTATE_INDEX.json`; this runtime is the executable control plane, not a replacement for that evidence.
