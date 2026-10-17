# REPORT 03 R2 — IL-LLM → KEX Symbolic/Binary Boundary Integration

**Date:** 2026-09-21  
**Repository:** aboudykeddeh276-stack/BRAINK  
**Base:** `441475dfa351c5e4116497868114384825435b78`  
**Branch:** `engineering/report03-kex-boundary-r2`  
**PR:** #95

## 1. Result

The missing symbolic/binary boundary is now implemented in two executed layers.

R1, already merged through PR #94, binds IL-LLM semantic entries to deterministic KEX symbolic envelopes, projects them into HTML without invoking packed carrier bytes, and materialises/restores KAB1 bytes only through an explicit `BinaryBoundaryAdapter`. R1 executed 8/8 tests and falsified a weak integrity assumption: a padding-bit mutation initially survived semantic-root validation, so packed-payload SHA-256 was added and the same mutation was then rejected.

R2 binds that already-implemented boundary to the existing Report 03 ToT safety kernel, distributed coordinate directory, and Layer-2 reconciler. The new `KEXBoundaryIntegration` commits semantic/envelope/wire identities through ToT, registers the logical KEX coordinate, attaches the KAB1 manifestation, emits a chained boundary receipt, and converts that receipt into desired Layer-2 state.

## 2. Implemented execution path

```text
IL-LLM semantic entry
  → semantic_root + dictionary_root
  → KEX SymbolicEnvelope
  → A/B symbolic token stream
  → deterministic HTML concept projection
  → BinaryBoundaryAdapter.emit()
  → KAB1 bytes + packed payload SHA-256
  → ToT quorum commit
  → DistributedCoordinateDirectory
  → Layer-2 desired manifestation
  → actuator
  → observed manifestation
  → reconciliation receipt
```

The boundary is explicit: HTML is still ultimately encoded by ordinary computing infrastructure when transported or stored, but this architecture does not invoke the KAB1 packed carrier until the declared binary-boundary adapter is called.

## 3. Observed R1 evidence

Merged R1 evidence records:

- symbolic bridge tests: **8/8 PASS**;
- all-zero 4096-bit A/B packed ratio: **0.557×**;
- all-one 4096-bit ratio: **0.557×**;
- alternating 4096-bit ratio: **5.000×**;
- deterministic random seed 297 ratio: **2.504×**;
- semantic fixture: 496 canonical semantic bytes → 1382 KAB1 wire bytes, **2.786× expansion** including header;
- padding-bit tamper initially escaped semantic-root checking;
- repair: exact packed-payload SHA-256;
- post-repair tamper: rejected.

This falsifies any universal-compression claim for the present A/B codec. Its demonstrated property is deterministic run-domain representation with data-dependent compression/expansion and a controlled symbolic→binary boundary.

## 4. R2 engineering additions

### 4.1 ToT safety integration

`KEXBoundaryIntegration.commit_envelope()` does not bypass Report 03. It creates normal quorum-governed directory transitions. The existing ToT kernel therefore continues to enforce fixed membership, majority quorum, contiguous indexes, previous-root chaining, voter equivocation locks, receipt verification, and fail-closed unsupported membership changes.

### 4.2 Distributed coordinate directory integration

The KEX concept receives a logical coordinate independent of its carrier manifestation. The KAB1 manifestation is attached by generation and endpoint. Stale generations, zero addresses, replay gaps, divergent replica history, and invalid receipts remain governed by the existing directory rules.

### 4.3 Layer-2 reconciliation

The committed boundary receipt becomes a `DesiredManifestation`. The existing reconciler then materialises/replaces/detaches physical or hosted manifestations through an actuator and produces an idempotent reconciliation receipt.

This separates symbolic identity from carrier state instead of pretending the HTML projection, KAB1 bytes, endpoint, and logical KEX concept are interchangeable objects.

## 5. R2 fault campaign encoded in tests

The new integration suite explicitly tests:

1. successful semantic envelope → KAB1 → ToT → directory → L2 convergence;
2. tampered ToT receipt rejection;
3. zero coordinate rejection;
4. insufficient quorum rejection;
5. stale manifestation generation rejection.

A GitHub clean-VM workflow was added. Its first run (`35587619062`) terminated before any job steps were emitted. That run is therefore **not application-test evidence** and is not counted as a pass or a falsification of the runtime. It exposes a CI execution-environment deficiency that must be resolved independently.

## 6. Current standards comparison

### W3C EXI

EXI is the closest mature standards analogue to the proposed boundary in one important respect: it uses grammar-informed representation to produce compact binary encodings of an information model. EXI is a W3C Recommendation and explicitly supports schema-informed and schema-less operation.

Difference: current KEX R1 binds an IL-LLM semantic dictionary/grammar to a symbolic A/B representation and only later invokes KAB1. It does not yet have EXI's standardized grammar machinery, interoperability profile, conformance corpus, or mature entropy encoding.

### CBOR / RFC 8949

CBOR is an IETF Standards Track binary serialization designed for small code size, small message size, and extensibility.

Difference: CBOR begins as a defined binary object representation. KEX R1's research question is whether semantic/symbolic identity can remain the authoritative representation above an explicit carrier boundary. KAB1 currently does not demonstrate superior size, speed, or interoperability versus CBOR.

### Protocol Buffers

Protocol Buffers use schema-defined field numbers and binary wire types; strings become UTF-8 bytes and messages become wire records.

Difference: Protobuf has a mature schema/wire ecosystem and efficient field encoding. KEX currently provides a semantic-root/dictionary-root/envelope-root continuity chain absent from ordinary protobuf messages by default, but has not demonstrated that this produces a practical performance advantage.

## 7. What advanced

**Advanced from architecture to executed evidence:**

- bounded IL-LLM semantic dictionary/grammar binding;
- deterministic semantic and dictionary roots;
- symbolic KEX envelope;
- existing A/B codec integrated as symbolic payload representation;
- deterministic HTML concept projection that does not call the packed carrier adapter;
- explicit KAB1 binary boundary;
- exact packed-byte integrity verification;
- round-trip symbolic restoration;
- compression claim falsified and narrowed;
- R2 code binding the boundary to ToT, distributed coordinate state, and Layer-2 desired state;
- explicit integration fault tests committed in PR #95.

## 8. What remains unproven, why, why the cause remains, and missing architecture

### 8.1 Complete IL-LLM semantic grammar — UNPROVEN

**Why:** R1 uses a bounded registered dictionary and typed grammar role, not a complete natural-language grammar.

**Why that remains:** the repository contains semantic/linguistic components, but no executed grammar authority covering ambiguity, morphology, syntax, multilingual equivalence, context precedence, and versioned conflict resolution as one conformance surface.

**Missing architecture:** canonical grammar registry; ambiguity resolver; multilingual equivalence ledger; grammar-version migration; semantic conformance corpus; property-based semantic round-trip tests.

### 8.2 Universal compression advantage — FALSIFIED for current codec

**Why:** alternating and random inputs expand substantially.

**Why the earlier claim fails:** run-length coding benefits long homogeneous runs and penalizes frequent transitions.

**Missing architecture for a renewed efficiency claim:** corpus classifier; adaptive codec selection; entropy baseline; comparison harness against raw UTF-8, gzip/Brotli, CBOR, Protobuf and EXI; CPU, memory and latency instrumentation.

### 8.3 HTML as non-binary substrate — NOT A SUPPORTED PHYSICAL CLAIM

**Why:** HTML is a symbolic/textual model at the application layer but conventional machines still encode and transport it as bytes.

**What is demonstrated instead:** KEX can keep its *authoritative model* symbolic until an explicit KAB1 adapter is requested.

**Missing architecture for stronger substrate claims:** non-byte-native execution substrate or hardware representation, plus instrumentation demonstrating operation without conventional byte materialisation.

### 8.4 Dynamic distributed membership — UNPROVEN

**Why:** the ToT kernel intentionally fails closed with `MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED`.

**Why it remains:** safe reconfiguration changes quorum intersection assumptions and requires a protocol, not a setter.

**Missing architecture:** joint-consensus or equivalent reconfiguration protocol; durable term/vote state across membership epochs; membership certificates; restart/recovery tests; partition tests during reconfiguration.

### 8.5 Byzantine resistance — UNPROVEN

**Why:** current ToT is explicitly crash-fault/non-Byzantine.

**Why it remains:** hashes and majority quorums do not establish Byzantine consensus.

**Missing architecture:** authenticated member identities/keys; Byzantine quorum rules; view-change protocol; equivocation evidence propagation; adversarial replica tests; formal safety/liveness model.

### 8.6 Multi-host WAN convergence — UNPROVEN

**Why:** prior evidence is local process/loopback and R2's clean-VM workflow has not produced application steps.

**Why it remains:** no independently controlled multi-host deployment with latency, loss, reordering, partitions and restart has been evidenced for this boundary.

**Missing architecture:** transport protocol; peer discovery; durable replica state; retransmission/backpressure; partition healing; clock-independent ordering; WAN fault harness.

### 8.7 Browser execution of symbolic A/B concepts — UNPROVEN

**Why:** deterministic HTML projection exists, but no browser runtime has been shown consuming arbitrary A/B concepts and driving the full semantic→KEX→carrier lifecycle.

**Missing architecture:** browser parser/runtime; content security policy; capability sandbox; lifecycle/state machine; conformance tests across browser engines.

### 8.8 Carrier interoperability — UNPROVEN beyond KAB1

**Why:** KAB1 is currently a project-specific wire contract.

**Missing architecture:** version negotiation; media type/content negotiation; streaming framing; canonicalization rules; independent decoder implementation; compatibility vectors; protocol registry.

### 8.9 Performance superiority — UNPROVEN

**Why:** current evidence measures representation size, not end-to-end CPU, latency, memory, energy or throughput superiority.

**Missing architecture:** reproducible benchmark runner; representative corpora; hardware counters; cold/warm runs; competing encoders; statistical treatment; published raw results.

### 8.10 Production provenance/security — PARTIAL

**Why:** SHA-256 roots prove integrity relationships inside the tested model, not signer identity, key lifecycle, supply-chain provenance or production authorization.

**Missing architecture:** signed provenance, SBOM, release attestations, key rotation/revocation, trusted build identity, dependency verification, security threat model and penetration/fuzz campaign.

## 9. Engineering conclusion

The missing boundary is no longer merely prose. R1 executed the IL-LLM → KEX symbolic envelope → HTML projection → KAB1 binary boundary and falsified the universal-compression interpretation. R2 now connects that boundary to the existing Report 03 ToT/directory/reconciler architecture.

The strongest supported statement is therefore:

> KEX now has an executable, integrity-checked translation boundary that can preserve IL-LLM-bound semantic identity in a symbolic envelope and defer project-specific packed-byte materialisation until an explicit binary adapter is invoked. The current A/B codec is data-dependent and is not a universal compressor.

Everything beyond that statement remains classified above by the architecture actually missing to prove it.
