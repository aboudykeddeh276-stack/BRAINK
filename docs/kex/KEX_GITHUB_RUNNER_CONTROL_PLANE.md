# KEX GitHub Runner Control Plane

This repository layer implements the GitHub execution/control surface defined by the KEX runner-control packet.

## Execution boundary

The control plane and its workflows are not treated as proof that the underlying workbook, HyperK0, IndexedDB, object-runtime, proof-ledger, or deployment mechanics are resident.

Every workflow emits a `reports/kex-ci/<mode>.json` receipt. A receipt may be:

- `PASS`: repository checks for that mode completed.
- `FAIL`: a required control-plane invariant is broken.
- `UNRESOLVED_RUNTIME_SURFACE`: the control-plane path exists, but the implementation surface required for runtime execution was not discovered.

This prevents workflow installation from being promoted into a runtime-execution claim.

## Cascade order

`MOUNT → VERIFY_ALL → HYDRATE_INDEXEDDB → RESOLVE_KEX_URI → PROJECT_UI → DISPATCH_TRIGGER → MUTATE_STATE → WRITEBACK → PROOF_COMMIT → REHYDRATE_ON_FAILURE`

## Warm boot

`VERIFY_SEED → MOUNT_WORKBOOK_SUBSTRATE → OPEN_INDEXEDDB_NAMESPACE → HYDRATE_PULSES → VERIFY_PROOFS → MOUNT_OBJECTS → SUBSCRIBE_UI_COMPONENTS → START_HEARTBEAT → ENTER_REHYDRATE_LOOP`

## Specialist runner labels

The specialist workflows prefer self-hosted runners with KEX labels when explicitly dispatched with `use_self_hosted=true`. Their default validation path uses GitHub-hosted Linux so the repository can expose missing runtime surfaces instead of waiting indefinitely for a runner that is not registered.

A self-hosted runner is still an external machine registration. Workflow files do not create hardware or prove runner registration.
