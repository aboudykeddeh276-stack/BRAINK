# Deployment

This directory contains deployment actuators and deployment-scope logic. Deployment classes are deliberately separated so private runtime operation is not misclassified as public publication.

## Deployment classes

### `TL2_LIVE`

Means the current KEX/WBOS service generation is launched and reachable through the TL VPN/TL2 transport scope.

Required evidence:

- TL2/tunnel identity resolved;
- runtime bind succeeds on the tunnel address;
- a newly spawned supervisor owns the observed supervisor state;
- the new child process is running;
- authenticated inside-tunnel health/service/route/proof readbacks succeed;
- deployment receipt records `TL2_LIVE`;
- proof ledger records the participant result.

Does not require or imply:

- public DNS;
- public TLS;
- public router/firewall publication;
- website publication;
- Drive persistence;
- Bitcoin IBD state.

### `PUBLIC_LIVE`

A separate publication class requiring public naming, TLS/ingress and outside-in readback. `TL2_LIVE` never promotes to this state implicitly.

## `tl2_deploy.py`

The TL2 deployer:

1. detects an explicit/observed tunnel address;
2. requires runtime auth for non-loopback binding;
3. verifies the address can be bound;
4. launches the supervised action server;
5. reads supervisor state;
6. verifies ownership of the newly spawned supervisor generation;
7. runs authenticated tunnel readback;
8. emits a hashed deployment report/proof event;
9. leaves the service resident when daemon mode is requested.

A service already listening on the target port must not be allowed to impersonate the new deployment generation.

## Capability-fabric integration

When `capability_fabric.py` engages TL2, the intended participant flow is:

```text
local capability fabric
→ durable outbox intent
→ TL2 participant deploy
→ participant readback
→ current-generation verification
→ participant receipt
→ outbox reconciliation
```

A pending outbox record is not deployment evidence.

## Security boundary

Runtime bearer/capability credentials are scoped to trusted runtime origins. Public/outside-in readback must not inherit internal mutation credentials. Redirects must not be used to escape readback policy.

## Promotion rule

No deployment status is promoted from configuration, process launch, source presence or workflow status. Promotion requires the receipt for the deployment class being claimed.
