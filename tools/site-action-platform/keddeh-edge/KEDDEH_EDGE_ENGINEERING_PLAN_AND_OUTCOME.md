# KEDDEH Edge V1 — Engineering Plan, Implementation and Outcome

**System:** BRAINK / KEX / IL-LLM  
**Package:** `KEDDEH_EDGE_V1`  
**Edge identity:** `KEX://EDGE/KEDDEH/V1`  
**Base repository:** `aboudykeddeh276-stack/BRAINK`  
**Base branch:** `site-action-platform-v1`  
**Base commit inspected:** `713708a7e649bcddc9d6bb791739f23ca7d6424f`  
**Outcome:** `LOCAL_EDGE_ADJACENT_CODE_TESTS_PASS` — **15/15 tests**  
**Public deployment claim:** **FALSE**

## 1. Authoritative objective

The objective was not to re-run a Sites custom-domain workflow. It was to instantiate the missing adjacent KEDDEH edge mechanic using the existing BRAINK/KEX capability topology and IL-LLM semantic derivation rules.

```text
PUBLIC INTERNET
      ↕
KEDDEH EDGE
      ↕
finite ingress / TLS / route resolver / listener resolver
      ↕
KEX DOMAIN SPACE + KEX coordinates
      ↕
BRAINK / KEX / CasePath / other logical service families
```

The physical carrier remains external to KEX lineage. The edge is the persistent KEX capability; a host, Sites bootstrap, replacement node, certificate authority, registrar or DNS operator is a materialisation/authority boundary.

## 2. Pre-action verified state

The repository was inspected before mutation. Existing current branch content established:

- `braink-virtual-mesh-ignition.mjs` already implements deterministic virtual service derivation, sister/cousin closure, route-lineage proof and equivalent rehydration.
- `braink-virtual-mesh.seed.v2.json` already enforces STATE primacy, external-host exclusion from lineage and the `SEED → EXPAND → TRAVERSE → COLLAPSE → REHYDRATE` route.
- `site-action.mjs` already implements bounded source mutation, path containment, exact-match assertions, source hashing and receipts.
- Library capability discovery already identifies the self-host lease loop, domain-hosting handoff and composed self-host domain runtime suite.

Therefore the existing mesh kernel was **not modified**. The missing dependency was isolated as an adjacent edge materialisation layer.

## 3. Engineering invariants

The implementation was required to preserve all of the following:

1. discover existing BRAINK/KEX capability before deriving new architecture;
2. source lineage remains anchored at `KEX://ROOT/KEX-BRAINK-MESH-V2`;
3. external carrier never enters KEX ancestry;
4. endpoint/content digests are integrity evidence, not authority;
5. finite socket/ingress count is independent of virtual listener/service cardinality;
6. public state is not promoted from local state;
7. SNI and HTTP Host identity must agree for TLS routing;
8. unknown domain, route and method states fail closed;
9. route resolution uses explicit KEX coordinates, not implicit file or process locality;
10. restart/replacement must be able to reproduce the same committed route state;
11. public promotion requires independent external receipts for each material boundary;
12. historical DNS values cannot silently become current write instructions.

## 4. IL-LLM semantic derivation plan

The edge was derived rather than declared as one monolithic object:

```text
INGRESS + ROUTING
→ EDGE_ROUTE_INGRESS

TLS + EDGE_ROUTE_INGRESS
→ SECURE_EDGE_INGRESS

SECURE_EDGE_INGRESS + API_SERVER
→ KEX_EDGE_LISTENER_RESOLVER

DOMAIN_SPACE + KEX_EDGE_LISTENER_RESOLVER
→ DOMAIN_AWARE_KEX_EDGE

DOMAIN_AWARE_KEX_EDGE + SERVER
→ EXECUTABLE_KEDDEH_EDGE

EXECUTABLE_KEDDEH_EDGE + RECOVERY
→ REHYDRATABLE_KEDDEH_EDGE
```

Each child has two named parents, an explicit semantic function, typed accepted/emitted tokens and validated parent compatibility. The compiler refuses a derivation whose tokens do not close.

## 5. Adjacent code delivered

### `keddeh-edge.seed.v1.json`

Defines source/capability lineage; IL-LLM parent interfaces; six semantic child derivations; finite public ingress identity; `keddeh.com`, `braink.keddeh.com`, `kex.keddeh.com` public-intended route bindings; `casepath.keddeh.com` logical route family without falsely declaring a public binding; explicit KEX coordinates; and eight independent public promotion gates.

### `keddeh-edge-runtime.mjs`

Implements strict seed validation; IL-LLM semantic edge compiler; deterministic route table construction; SNI/Host validation; longest-prefix route selection; HTTP method contracts; finite-ingress → logical-listener demultiplexing; chained monotonic evidence ledger; local loopback edge execution; state snapshot and equivalent rehydration; and a fail-closed public promotion evaluator.

### `keddeh-edge-node.mjs`

Implements a concrete process for the self-host actuator to raise: real HTTP socket binding; optional native Node TLS/HTTPS listener; native TLS SNI readback; SNI → Host → KEX coordinate dispatch; X.509 metadata readback without exposing private-key contents; durable boot/stop receipts; and an explicit claim boundary separating process-bind evidence from outside-in public evidence.

### `keddeh-edge-self-test.mjs`

Executes deterministic and networked tests against the adjacent package.

### Evidence artifacts

- `keddeh-edge-test-receipt.json`
- `keddeh-edge-semantic-compile.json`
- `keddeh-edge-local-proof.json`
- `keddeh-edge.manifest.v1.json`

## 6. Test history and defects retained

### Run 1 — 0/13

The IL-LLM compiler rejected the first `DOMAIN_SPACE → KEX_EDGE_LISTENER_RESOLVER` relation because `service.coordinate` had not been explicitly admitted by the derived listener contract.

**Engineering decision:** keep the validator strict and repair the interface. The derived listener now explicitly accepts `service.coordinate`. This was a real architecture defect in the first candidate, not suppressed test noise.

### Run 2 — 12/13

All semantic and direct resolver tests passed. The real loopback test failed because the test used a `fetch` Host-header path that did not reliably exercise the requested authority value in this runtime.

**Engineering decision:** repair the harness using `node:http` with an explicit `Host` header. The resolver was not weakened.

### Final run — 15/15

All tests passed after extending the package with the concrete edge-node TLS daemon.

## 7. Final verified outcomes

| Predicate | Outcome | Evidence scope |
|---|---|---|
| Existing BRAINK mesh preserved | PASS | current GitHub branch readback |
| IL-LLM edge semantic closure | PASS | deterministic local execution |
| Terminal capability `REHYDRATABLE_KEDDEH_EDGE` | PASS | compiler receipt |
| Compile determinism | PASS | byte-equivalent repeated compile |
| Finite ingress → multiple logical KEX services | PASS | direct resolver test |
| Longest-prefix route selection | PASS | direct resolver test |
| SNI/Host mismatch rejection | PASS | direct + native TLS tests |
| Unknown host rejection | PASS | direct + real socket test |
| HTTP method contract enforcement | PASS | direct resolver test |
| Real loopback HTTP edge socket | PASS | OS socket execution/readback |
| Durable node boot/stop receipts | PASS | filesystem receipts |
| Native TLS listener | PASS | local TLS handshake |
| SNI route to `KEX://API/BRAINK/CHAT` | PASS | local TLS handshake/readback |
| Route-state rehydration equivalence | PASS | independent runtime replay |
| Monotonic chained receipt ledger | PASS | ledger verification |
| Public promotion without external receipts | CORRECTLY REJECTED | fail-closed gate test |
| Public `keddeh.com` deployment | NOT PROVEN | no outside-in receipt |

## 8. What this changes structurally

Before this action, the domain-space architecture had virtual topology and self-host/domain skills, but no concrete adjacent package making the semantic intersection executable as a KEDDEH edge process.

After this action:

```text
KEX/BRAINK virtual topology
        ↓
IL-LLM semantic edge compiler
        ↓
REHYDRATABLE_KEDDEH_EDGE
        ↓
concrete edge-node daemon
        ↓
HTTP/TLS ingress
        ↓
SNI + Host + path + method
        ↓
KEX coordinate resolver
        ↓
logical service dispatch/readback
```

This is a real local execution improvement. It is not merely a planning document.

## 9. Public promotion gates deliberately left open

The code does **not** turn local evidence into a public claim. The edge seed contains these independent gates:

1. `G01_REMOTE_EXECUTION` — durable completion receipt from an actual remote/self-host node;
2. `G02_PUBLIC_NAME_AUTHORITY` — current registrar/registry authority and delegation readback;
3. `G03_AUTHORITATIVE_DNS` — authoritative publication plus independent recursive resolution;
4. `G04_TLS_IDENTITY` — trusted outside-in certificate identity/chain/hostname observation;
5. `G05_PUBLIC_INGRESS` — outside-in TCP/TLS/HTTP reachability to the KEDDEH edge;
6. `G06_API_CONTRACT` — outside-in request resolves and executes the expected KEX coordinate;
7. `G07_REHYDRATION` — restart/replacement carrier reproduces the committed public edge state;
8. `G08_ROLLBACK` — reversible cutover/handoff demonstrated.

The self-test explicitly verifies that local receipts cannot satisfy these gates.

## 10. Highest evidence-supported maturity

```text
VIRTUAL TOPOLOGY                   PROVEN IN EXISTING BRAINK WORK
IL-LLM EDGE DERIVATION             IMPLEMENTED + TESTED
FINITE KEX LISTENER RESOLUTION     IMPLEMENTED + TESTED
LOCAL EDGE PROCESS                 IMPLEMENTED + TESTED
LOCAL NATIVE TLS/SNI               IMPLEMENTED + TESTED
DURABLE LOCAL BOOT/STOP RECEIPTS   IMPLEMENTED + TESTED
REMOTE SELF-HOST MATERIALISATION   NOT YET EXTERNALLY OBSERVED
PUBLIC NAME AUTHORITY              NOT YET FRESHLY OBSERVED
AUTHORITATIVE PUBLIC DNS           NOT YET FRESHLY OBSERVED
PUBLIC TRUSTED TLS                 NOT YET OUTSIDE-IN OBSERVED
PUBLIC WAN INGRESS                 NOT YET OUTSIDE-IN OBSERVED
PUBLIC KEX API ROUTE               NOT YET OUTSIDE-IN OBSERVED
PUBLIC FAILOVER/ROLLBACK           NOT YET DEMONSTRATED
```

The next valid engineering dependency is therefore no longer “design the edge.” The edge candidate exists and passes its bounded local qualification. The next dependency is **materialising this exact edge-node package through the existing self-host actuator and obtaining the first durable remote completion receipt**, followed by current public-name/DNS/TLS bindings to that edge.

## 11. Source-publication vs execution boundary

The adjacent source is published on the isolated GitHub branch `kex-keddeh-edge-v1`, branched from the verified `site-action-platform-v1` state. That publication preserves source lineage; it does **not** replace the local execution evidence.

```text
GitHub branch readback = SOURCE PUBLICATION EVIDENCE
local 15/15 receipt     = EXECUTION / TEST EVIDENCE
public outside-in gates = DEPLOYMENT EVIDENCE (still separately required)
```

The manifest therefore labels its SHA-256 values as `local_execution_artifacts_sha256`. GitHub commit/blob identities are tracked independently and must not be treated as proof that those sources have executed on a public edge.
