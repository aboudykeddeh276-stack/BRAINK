# K-SYSTEMS Google API Router

This runtime implements the provider-neutral routing control plane backed by the Google Sheet:

- Spreadsheet ID: `1fntX9Rb1Sy6rkxuyVKfBUywkcEHqIjYNIvesIJABOcA`
- Control-plane mode: `CACHED_CONTROL_PLANE`
- The spreadsheet is a policy source, not a synchronous dependency for every request.

## Authority boundary

BRAINK owns local orchestration and resident capability resolution. Google Cloud project authority,
service identities, quota limits, network placement and provider-side resource creation remain external
runtime bindings. This module therefore fails closed when a route has an unbound project or credential.

No secret material belongs in the spreadsheet. `CREDENTIAL_REFS` contains only references and state.

## Control-plane tabs

- `ROUTES`: provider route definitions, priority, weight, capability, health/quota references.
- `CAPABILITIES`: canonical provider-neutral operations and semantics.
- `QUOTA_POLICY`: quota metric, hard/soft limits, observed usage, reserve and safety margins.
- `HEALTH`: operational health and circuit state.
- `CREDENTIAL_REFS`: credential references only, never tokens/private keys/client secrets.
- `CONTROL`: locked invariants, refresh policy, circuit parameters and version.
- `AUDIT_LOG`: administrative and implementation receipts.

The runtime validates these locked invariants before accepting a snapshot:

```text
spreadsheet_role     = POLICY_SOURCE_NOT_REQUEST_PATH
fallback_invariant   = SAME_CAPABILITY_SEMANTICS_ONLY
credential_invariant = NO_SECRET_MATERIAL_IN_SHEET
execution_gate       = BLOCK_UNBOUND_PROJECT_OR_CREDENTIAL
```

## Runtime flow

```text
Google Sheet
    |
    v
GoogleSheetsValuesSource
    |
    v
RouterConfigLoader ---- last-valid cached snapshot
    |
    v
ApiRouter
    |-- capability + semantic filter
    |-- admin/enabled filter
    |-- credential/project binding gate
    |-- circuit filter
    |-- quota pressure ranking
    `-- deterministic priority/weight tie-break
    |
    v
Google provider adapter
```

`RouterConfigLoader.refresh()` preserves the last valid snapshot during a transient control-plane
failure while it remains within the configured stale window. Configuration version rollback is rejected.

## Quota behavior

`QuotaTracker` combines spreadsheet-observed usage with local request accounting. The effective
selection pressure is computed against the route's hard limit when a real limit is bound.

No default Google quotas are invented. A `DISCOVERY_REQUIRED` quota metric or blank hard limit remains
unknown until the target Google project supplies an authoritative value.

## Circuit behavior

- Repeated `429`, `408`, or `5xx` failures count toward the circuit threshold.
- `401` and `403` are authority failures and open the route immediately.
- Authorization failures do not trigger provider hopping.
- After cooldown, an open circuit becomes half-open and may be probed.
- Successful execution closes/reset the local circuit state.

## Semantic fallback rule

Fallback is limited to routes satisfying the same canonical capability and explicit semantics.
Drive file management is therefore not silently substituted with Cloud Storage object persistence,
and BigQuery is not treated as a transactional API fallback.

A cross-service transformation must be modeled as a separate explicit capability/contract.

## Runtime binding

The included REST adapters require an injected bearer-token provider:

```python
from runtime.google_api_router import (
    ApiRouter,
    GoogleSheetsValuesSource,
    RouterConfigLoader,
    build_google_adapters,
)

token_provider = obtain_token_from_runtime_secret_or_workload_identity
source = GoogleSheetsValuesSource(token_provider)

loader = RouterConfigLoader()
loader.refresh(source)

router = ApiRouter(loader)
adapters = build_google_adapters(token_provider)
```

The token provider is intentionally not implemented as a static credential in this repository. Bind it
to the resident workload identity, service account exchange, OAuth token broker, or other approved
secret/runtime authority.

## Current execution state

The spreadsheet control plane exists and is writable through the connected Google workspace surface.
The following provider execution bindings remain deliberately `UNBOUND` until discovered and verified:

- Google Cloud project identifiers for each route.
- Runtime service-account / workload-identity / OAuth token-provider bindings.
- Real project-specific quota metric names and hard limits for Drive, GCS, Sheets, Monitoring,
  BigQuery and Pub/Sub.

Until those are bound, `ApiRouter.select(..., require_bound=True)` returns an execution block instead of
pretending the provider call is live.
