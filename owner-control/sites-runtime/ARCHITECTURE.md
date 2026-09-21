# BRAINK Sites Runtime contract

This is an executable owner control plane, not a decorative Site generator.

## State model
SITE_REGISTERED -> VERSIONED -> DEPLOYING -> DEPLOYED -> PUBLIC_READBACK_PASS.

The runtime refuses to collapse these states. A domain binding is metadata until DNS/TLS/readback proves serving. A source version is immutable after creation. A deployment receipt records the adapter, exact version, target and adapter readback. Public readback is a separate event.

## Persistence
SQLite runs WAL + FULL synchronous mode. Source snapshots are content-addressed by SHA-256 and written atomically with file and parent-directory fsync. The event ledger is hash chained. The recovered estate index remains separate evidence and is imported explicitly with bootstrap_estate.py.

## Provider boundary
Core deployment adapter `local` publishes an immutable version to the configured publication root. Adapter `command` executes the owner-configured `KEX_SITES_DEPLOY_CMD`, sending the complete deployment request on stdin and recording exit code/stdout/stderr. A provider can therefore be replaced without changing Site identity, versions or ledger history.

## Authority
Mutation routes can be protected by `KEX_SITES_TOKEN`. Secrets are environment references, never persisted in the Site database or source manifest. Provider credentials belong in the adapter environment.

## Recovery
The database, object store and publication root are independent paths. Restore the database plus object store, run ledger verification, then republish a chosen immutable version. Provider outage does not destroy Site identity or source history.

## Estate bootstrap
`./kex-sites bootstrap` imports every native Site and domain environment represented in `../COMPLETE_SITE_ESTATE_INDEX.json`. Historical states stay historical. Import does not pretend those endpoints are currently healthy.

## Missing provider-specific mechanics
Native ChatGPT Sites read/write/publish is not implemented because this execution has no exposed native Sites actuator. It belongs behind the provider boundary when available, rather than being faked.
