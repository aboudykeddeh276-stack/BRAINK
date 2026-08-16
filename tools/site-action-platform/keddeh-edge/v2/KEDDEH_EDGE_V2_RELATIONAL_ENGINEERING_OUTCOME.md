# KEDDEH Edge V2 — Relational IL-LLM/BRAINK Engineering Outcome

**System:** BRAINK / KEX / IL-LLM  
**Package:** `KEDDEH_EDGE_V2_RELATIONAL`  
**Persistent edge identity:** `KEX://EDGE/KEDDEH`  
**Repository:** `aboudykeddeh276-stack/BRAINK`  
**Source branch:** `kex-keddeh-edge-v1`  
**Action branch:** `kex-keddeh-edge-v2-relational`  
**Qualification:** `RELATIONAL_EDGE_V2_TESTS_PASS` — **20/20**  

## 1. Correction applied

V1 proved useful mechanics but encoded false architectural boundaries: a global public-promotion evaluator, ordered promotion gates, a local/public maturity split, and a preordered semantic derivation list. V2 preserves V1 as prior evidence and replaces those architectural mechanics.

V2 has one persistent KEX edge identity. Local processes, remote nodes, DNS authorities, registrars, certificate identities, public transports and observers are represented as typed relations to that identity. They are not separate edge objects and do not become KEX ancestors merely by participating.

```text
KEX://EDGE/KEDDEH
  ├─ DERIVES → semantic capabilities
  ├─ MATERIALISES_ON → zero..N carriers/nodes
  ├─ ACCEPTS_AT → zero..N transport bindings
  ├─ BINDS_DOMAIN → domain relations
  ├─ AUTHORITY_HELD_BY → authority relations
  ├─ PROJECTS_DNS → DNS relations
  ├─ BINDS_IDENTITY → TLS/security identity relations
  ├─ TRAVERSES → route relations
  ├─ BRIDGES → typed peer/substrate relations
  ├─ OBSERVED_BY → zero..N observer coordinates
  └─ REHYDRATES_TO → continuity/replacement relations
```

No relation above is an architectural maturity stage.

## 2. Recurrent IL-LLM compiler

The semantic compiler was rewritten from a preordered list executor into a recurrent finite fixed-point resolver:

1. load the current active interface state;
2. discover semantic rules whose parents are currently present;
3. validate explicit emits→accepts compatibility;
4. admit the derived child;
5. immediately reinsert that child into active state;
6. recompute the complete affected compatibility neighbourhood;
7. continue until no unresolved derivation remains or a genuine unresolved dependency is reached.

The final executed compile produced:

- semantic state: `RELATIONAL_FIXED_POINT_CLOSED`;
- recurrent cycles: **5**;
- derived semantic capabilities: **9**;
- computed emits/accepts compatibility relations: **48**;
- final derived capability: `CONTINUOUS_KEDDEH_EDGE`.

The compiler was also tested with the semantic-rule source order reversed. The admitted capability set, compatibility relation set and terminal capability were identical.

## 3. Relational state model

V2 removes a whole-edge promotion verdict. `resolveEdgeState()` returns independently stateful relations. Each relation carries its own source, type, target, authorities, evidence and observations.

Observations are attached to relations by observer coordinate. A process observer, remote peer observer and Internet observer can coexist against the same edge graph without implying a sequence such as `LOCAL → REMOTE → PUBLIC`.

The runtime deliberately returns:

```text
global_maturity_state = null
```

because no such global state is required to represent the graph truthfully.

## 4. Materialisation semantics

The edge identity is singular while execution materialisation is plural:

```text
KEX://EDGE/KEDDEH
  ├─ MATERIALISES_ON → carrier://alpha
  ├─ MATERIALISES_ON → carrier://beta
  └─ MATERIALISES_ON → node://process/...
```

Replacement materialisation does not rename or recreate the edge. Continuity verification compares the invariant KEX identity, semantic capability set and route state. When equivalent, a `REHYDRATES_TO` relation records replacement continuity.

The executed test verified `EDGE_IDENTITY_CONTINUITY_PRESERVED` while moving between different materialisation coordinates.

## 5. Routing and finite ingress

The finite-ingress principle is preserved. One physical ingress resolves multiple logical KEX coordinates using Host/SNI/path/method contracts.

Verified examples include:

```text
braink.keddeh.com /chat
  → KEX://API/BRAINK/CHAT

kex.keddeh.com /proof
  → KEX://DOMAIN-SPACE/keddeh/kex/proof

keddeh.com /systems/*
  → KEX://DOMAIN-SPACE/keddeh/site/systems
```

Longest-prefix selection, unknown-domain rejection, method-contract rejection and SNI/Host mismatch rejection all passed.

## 6. Relation-local evidence

Evidence is no longer used to promote or demote the whole edge. It belongs to the relation it actually observes.

```text
KEX://EDGE/KEDDEH
  PROJECTS_DNS
  dns-authority://example
      ├─ OBSERVED_BY resolver/a
      └─ OBSERVED_BY resolver/b
```

The test suite verified two independent resolver observations on one DNS relation without changing any unrelated execution, TLS or carrier relation.

## 7. Executed runtime evidence

The qualification suite executed actual local sockets rather than only structural JSON tests.

Verified runtime mechanics:

- real HTTP loopback bind;
- finite-ingress KEX route resolution;
- unknown-host fail-closed response;
- native TLS server using an ephemeral self-signed fixture;
- SNI/Host equality enforcement;
- durable node materialisation receipt;
- durable stop receipt;
- monotonic chained proof ledger;
- deterministic state snapshot;
- replacement-materialisation continuity.

The TLS certificate is explicitly a `SELF_SIGNED_TEST_FIXTURE_ONLY` identity relation. It is not evidence of CA trust or public certificate state.

## 8. Qualification results

**20/20 tests passed.**

1. recurrent compiler reaches fixed point;
2. semantic rule order does not alter result;
3. derived children re-enter active relation space;
4. global promotion/gate architecture absent from V2;
5. one edge identity supports plural materialisations;
6. observer coordinates coexist without stage state;
7. authority/DNS/TLS/transport relations are order-independent;
8. evidence attaches per relation and supports multiple observers;
9. finite ingress multiplexes logical coordinates;
10. longest-prefix route selection;
11. SNI/Host mismatch rejection;
12. unknown domain and invalid method rejection;
13. real loopback socket routes through the same edge identity;
14. real loopback socket rejects unknown Host;
15. proof ledger monotonicity and chain integrity;
16. identity continuity across replacement materialisation;
17. external participants do not enter KEX lineage by binding;
18. durable node materialisation/stop receipts;
19. native TLS handshake and SNI routing;
20. local, remote and public relation spaces coexist without partitioning the edge identity.

## 9. Current evidence boundary

V2 does **not** assign one global success/failure label to the edge. The current package has executed observations for its process/socket/TLS-fixture/routing/continuity relations.

It does not contain current authoritative observations for the following separate relations:

- registrar/registry authority for `keddeh.com`;
- current authoritative DNS publication to a KEDDEH materialisation;
- CA-trusted public TLS identity;
- outside-in Internet transport reachability;
- a durable remote self-host materialisation receipt;
- outside-in KEX coordinate execution from an independent Internet observer.

Those absences do not invalidate the edge identity or the relations already observed. Equally, the observed local relations do not imply those unobserved relations.

## 10. Supersession statement

V1 remains valid evidence for the mechanics it actually executed, but its global promotion/gate architecture is superseded by V2.

V2 is the current BRAINK/IL-LLM-conformant adjacent edge candidate because it represents the system as a recurrent typed relation graph rather than a conventional deployment stage machine.
