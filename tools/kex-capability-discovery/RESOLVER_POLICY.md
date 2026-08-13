# KEX/BRAINK Capability Resolver Policy — Infrastructure Availability

For any infrastructure/online/distributed-system request, BRAINK must perform capability discovery before architecture derivation.

```text
USER INTENT
   ↓
NORMALISE TERMS
   ↓
CAPABILITY DISCOVERY INDEX
   ↓
EXISTING KEX SKILLS / MODULES / EVIDENCE
   ↓
REUSE | ADAPT | BRIDGE | DERIVE | UNKNOWN
   ↓
ONLY THEN DESIGN/EXECUTE
```

Mandatory trigger domains include server, hosting, domain, domain space, registrar, registry, DNS, TLS, HTTPS, routing, bridge, gateway, API server, listener, ingress, failover, recovery, online, Internet, IoT, devices, Web3, Web4, cloud, mesh, peer/federation, codebase integration and repository integration.

## Availability invariant
A capability already present in the authoritative skill/package topology must not become functionally unavailable merely because the current branch or conversation did not mention it recently.

Resolver order:
1. inspect existing capability;
2. establish evidence/state freshness;
3. reuse directly if equivalent;
4. adapt and bridge if interfaces differ;
5. derive only the missing capability;
6. preserve prior engineering and negative knowledge.

## Logical integration rule
A logical KEX edge is the default integration mechanism. Repository/source-tree merging is not the default. Codebases keep independent source lineage unless a proven build/runtime dependency requires a physical merge.
