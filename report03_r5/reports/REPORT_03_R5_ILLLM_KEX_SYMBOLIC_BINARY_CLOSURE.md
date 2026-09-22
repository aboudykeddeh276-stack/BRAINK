# KEDDEH REPORT 03 R5 — IL‑LLM Semantic Authority → KEX Translation → ToT Accepted State → Distributed Coordinate Directory → Layer‑2 Reconciliation → Explicit Binary Boundary

**Report identity:** `KEDDEH-REPORT-03-R5-SEMANTIC-BINARY-CLOSURE`  
**Evidence state:** `IMPLEMENTED / EXECUTED / FALSIFIED / LOCALLY MULTI-PROCESS / NOT MULTI-HOST PRODUCTION`  
**Evidence root:** `9b0b4d9299c3ba5355b49d2de12a93828ac14d413b8a7fd19b74402f6d9ff765`  
**Qualification root:** `264c85c12939f3a6ceed23ec976e567e564ece1c08ef6d3d30f6a7326aba2706`  
**Executed test surface:** `64/64 PASS across three independently exiting suites`  
**Observed evidence run:** `11 positive effect events + 8 fault/negative-control events`  
**Current standards comparison date:** `2026-09-21`

## 1. Executive technical determination

This report closes a specific missing engineering boundary rather than rearranging earlier architecture prose.

The resident IL‑LLM recovery surface is now an actual upstream semantic source. The integrated adapter loads **1084 recovered lexicon entries**, **71 recovered router entries**, **7 translator domains**, and **11 runtime registers**. The executed concept `Information` resolves from `02 - Words (English Lexicon)!row:13`, produces semantic digest `4c45218c93ceae1fd57b88d6f4a80866643096cbd383e7a1eb180472422338fe`, and routes through the resident `KEX-L-TRANS` translator path.

KEX now carries that semantic identity through accepted distributed state rather than treating rendered HTML or encoded bytes as the identity itself. The concept is committed through the nine-process ToT layer as coordinate `KEX://ILLLM/CONCEPT/INFORMATION/ROW/13`. Three independent directory processes replay that committed state and converge. Layer‑2 then materialises the HTML concept projection as a real filesystem effect, detects external visual drift, repairs the file, and returns to a NOOP/converged state without changing the accepted semantic digest. Finally, no binary boundary artifact exists when the request is symbolic-only; only an explicit `requires_binary=true` call creates a `KXBD` substrate packet and verifies byte-for-byte readback.

That is the implemented boundary:

```text
resident IL-LLM semantic record
        ↓ meaning + source provenance
KEX semantic translation (KEX-L-TRANS)
        ↓ semantic_digest remains authoritative
ToT accepted-state commit
        ↓
distributed KEX coordinate directory
        ↓
Layer-2 desired / observed / effect / readback
        ├─ symbolic projection: HTML manifestation
        └─ explicit binary boundary only when requested
              ↓
         RAW_BINARY or KEX_AB
              ↓
         byte-constrained substrate
```

The important qualification is literal: a digital implementation necessarily uses machine bytes internally. “Symbolic until the binary boundary” therefore does **not** mean the host CPU stops using bits. It means the **semantic protocol and identity model do not make a binary wire representation authoritative** until a concrete substrate adapter requires one. Before that boundary, meaning is represented as typed semantic objects, coordinates, digests, desired state and projections; the byte encoding of their carrier is incidental rather than identity-defining.

The work also falsified and repaired a distributed-state defect that was absent from the earlier 51-test surface. A failed minority prepare could leave uncommitted conflicting entries that blocked a later valid proposal at the same log index. R5 now allows an uncommitted entry to be superseded only by a proposal from a **strictly higher elected term** that still extends the current committed head. Committed entries remain immutable and same-term conflicting retries remain fenced. The new regression test passes.

The architecture has therefore advanced materially, but it has not crossed several production boundaries. The report does not claim multi-host consensus, autonomous peer consensus, dynamic membership, mTLS/workload identity, RFC 8785 canonicalization, standardized binary interchange, full IL‑LLM corpus completeness, Byzantine tolerance, hardware power-loss durability, or production external actuators. Each open property is causally decomposed later in this report into: what remains unproven, why, why that reason remains unaddressed, why the unresolved condition remains, the architecture that is actually missing, and the evidence required for promotion.

## 2. What was inherited, what was recovered, and what is new in R5

### 2.1 Inherited accepted-state baseline

Report 03 V3 already contained a stronger accepted-state layer than the earlier in-process model:

- nine independent ToT voter processes;
- TCP loopback RPC between client/orchestrator and each voter;
- one SQLite database per voter using WAL and synchronous FULL;
- term and vote persistence;
- append/commit separation;
- committed-prefix validation;
- process kill, restart and catch-up;
- indeterminate commit recovery after dropped responses;
- three independent directory processes with their own SQLite state;
- deterministic directory replay from the committed ToT prefix;
- a concrete Layer‑2 filesystem actuator using atomic replacement and durable idempotency receipts;
- drift detection, repair and accepted-state fencing.

R5 does not relabel those mechanics as new work. Their 36-test local semantic baseline and 15-test V3 distributed mechanics suite were rerun as part of the final qualification surface.

### 2.2 Recovered symbolic/binary work

A separate resident Report 03 package already contained an earlier IL‑LLM/KEX boundary implementation: a recovered IL‑LLM adapter, semantic translator, HTML projector, A/B codec and adaptive binary envelope. That work established useful mechanics, but its integration boundary was weaker than the current V3 distributed stack. It also existed as a parallel package rather than a single causal chain through the nine-process accepted-state and Layer‑2 effect model.

R5 therefore treats it as recovered source material, not as a new achievement. The substantive new work is the closure between that semantic layer and the stronger distributed/control-plane layer.

### 2.3 New R5 engineering

R5 adds:

1. `src/resident_il_llm.py` — executable read-only adapter over the recovered resident IL‑LLM surfaces.
2. `src/semantic_boundary_integration.py` — the cross-layer semantic authority and explicit binary-boundary controller.
3. A `KXBD` v2 boundary packet with adaptive RAW/A-B payload selection, payload integrity and semantic-digest-prefix binding.
4. `BinarySubstrateActuator` — an actual atomic byte sink, not a displayed packet or status label.
5. 12 new semantic/binary closure tests.
6. A new failed-minority-prepare regression test plus a repair to `tot_process_cluster.py`.
7. A new end-to-end observed evidence run that traverses resident semantics, ToT, directory, Layer‑2 and the binary substrate.
8. New current-standards probes and an explicit 15-item architecture-deficiency matrix.

## 3. Resident IL‑LLM semantics are now upstream of KEX translation

The integrated `ResidentILLMAdapter` loads recovered source cells and preserves source location and degradation state rather than fabricating complete semantics.

Observed adapter state:

```json
{
  "claim_boundary": "read-only adapter over recovered workbook surfaces; not the full IL-LLM runtime",
  "degraded_lexicon_entries": 2,
  "lexicon_entries": 1084,
  "recovered_router_entries": 71,
  "runtime_registers": 11,
  "schema": "il-llm.recovered-adapter.v1",
  "source_path": "/mnt/data/report03_r5/source/il_llm_recovered_cells.json",
  "source_sha256": "25b59aa77b58d3445f08bee2db2a7f72b60705bf87e306db4ac2354a0fe0eed3",
  "translator_domains": 7
}
```

For the executed concept `Information`:

- source locator: `02 - Words (English Lexicon)!row:13`;
- semantic digest: `4c45218c93ceae1fd57b88d6f4a80866643096cbd383e7a1eb180472422338fe`;
- resident semantic coordinate: `semantic://il-llm/information/4c45218c93ceae1f`;
- KEX translator route: `KEX-L-TRANS`.

The semantic digest is computed from the complete recovered semantic record, including source provenance. That makes a change in meaning observable. A negative test mutates the dictionary meaning while retaining the old digest; `SemanticBoundaryController.validate_concept()` rejects it with `SEMANTIC_DIGEST_MISMATCH`.

This closes an important prior weakness. A four-entry boundary dictionary can define what A and B mean, but it does not prove the resident IL‑LLM dictionary is governing translation. In R5, the source record is retrieved from the recovered IL‑LLM corpus, its route is resolved through the recovered translator table, and KEX consumes the resulting typed semantic concept. The semantics therefore precede the codec.

Two corpus defects are deliberately preserved: the adapter reports two `DEGRADED_SOURCE` lexicon entries. The executed negative control requests `One` with `require_clean=True`; it is rejected rather than silently promoted. An unknown symbol is also rejected rather than synthesized.

The exact boundary remains narrow: this is a read-only adapter over recovered workbook surfaces. It is evidence that resident IL‑LLM semantics can drive KEX translation; it is not evidence that the entire IL‑LLM runtime, grammar corpus, multilingual dictionary estate or mutation/governance plane has been reconstructed.

## 4. Observer-theorem application to the semantic/binary sector

The sector implementation follows the same recursive attribution structure already used in the broader node/HCI work:

```text
definition
  → defined semantic attribute
  → attribution of that attribute to a source/observer
  → definition of the attribution relationship
  → node/integration edge
  → observed effect
```

Applied here:

```text
IL-LLM source record
  → semantic fields / meaning
  → source locator + source status + semantic owner
  → semantic_digest and KEX route definition
  → accepted KEX coordinate + directory integration
  → HTML or byte manifestation
  → readback / observer evidence
```

The key engineering constraint is that the observer does not retroactively become the definition. A rendered HTML file can be deleted or visually corrupted without changing the accepted semantic digest. A binary packet can choose RAW or A/B without changing the IL‑LLM meaning. A directory replica can be stale without creating a new semantic identity. These distinctions are now executable rather than merely textual.

## 5. KEX semantic coordinate and accepted-state integration

R5 does not derive the accepted KEX coordinate from an arbitrary modulo or invented numeric counter. The accepted coordinate is grounded in the resident source record:

`KEX://ILLLM/CONCEPT/INFORMATION/ROW/13`

The `ROW/13` component is inherited from the recovered IL‑LLM source locator. The resident semantic coordinate (`semantic://il-llm/information/4c45218c93ceae1f`) is retained in accepted metadata instead of being conflated with the directory coordinate.

The ToT layer committed the concept at log index `1` with entry root:

`ba6682556f6cc68055d08f08fc8bd3d19e6a14e92c25f0104f4f11c59f1102a9`

The accepted directory record contains:

- `semantic_owner = IL-LLM`;
- `translation_owner = KEX`;
- `boundary_policy = SYMBOLIC_UNTIL_BINARY_REQUIRED`;
- resident semantic coordinate and coordinate kind;
- source locator/status;
- `KEX-L-TRANS` route;
- semantic digest;
- desired HTML manifestation;
- HTML hash as representation metadata.

The directory does not independently mutate that authority. It is a projection of the committed ToT log. In the evidence run, all three directory processes converged and returned directory root `0e9ab07657e16f0fa665aa250c6b0c7481b587dcd7b38b3a45ac86c4ef6e7b6d` against accepted-state root `ba6682556f6cc68055d08f08fc8bd3d19e6a14e92c25f0104f4f11c59f1102a9`.

## 6. ToT safety kernel and the R5 failed-minority-prepare repair

### 6.1 Existing safety model

The ToT layer remains explicitly non-Byzantine. It models a 3×3 topology with structural global quorum rules, persistent terms/votes/logs, committed-prefix checks and crash/partition faults. Nine voter identities run in separate OS processes and persist independent SQLite journals.

### 6.2 Newly discovered liveness defect

The R5 evidence runner deliberately attempted a write through only one triad after a prior committed semantic entry. The write could not obtain global quorum, which is correct. However, some replicas had already persisted the uncommitted proposal at the next log index.

The next legitimate metadata transition used the same index. Those replicas returned `CONFLICTING_ENTRY_AT_INDEX`. This preserved safety but harmed liveness: a failed minority prepare could poison the next index indefinitely.

That result was not deleted from the fault history. It caused a source change.

### 6.3 Repair law

Replica append behavior now distinguishes committed and uncommitted conflict:

```text
existing same proposal root
    → idempotent accept

existing committed different proposal
    → reject forever

existing uncommitted different proposal, same/older term
    → reject

existing uncommitted different proposal, strictly higher elected term
    AND proposal index = committed_index + 1
    AND proposal previous_root = committed_root
    → delete conflicting uncommitted suffix
    → accept higher-term proposal
```

The new regression test proves both sides: a same-term replacement remains fenced, while a higher-term elected leader can supersede the uncommitted minority entry and commit the next index through a valid global quorum.

This is a concrete architectural advance derived from falsification, not a report amendment pretending the defect never existed.

## 7. Distributed KEX coordinate directory

Three independent directory processes persist their own SQLite state. The final evidence run records a stale-replica sequence:

1. all directory replicas converge;
2. `DIR_GAMMA` is terminated;
3. a new accepted metadata transition is committed;
4. `DIR_ALPHA` and `DIR_BETA` sync to the new committed prefix;
5. `DIR_GAMMA` restarts behind at an older applied commit index;
6. its stale condition is observed rather than hidden;
7. it receives the canonical committed log and rejoins;
8. all three roots converge again.

Observed stale/current indices: `1` / `2`.

This proves deterministic rehydration of a known directory replica in the local process model. It still does not prove autonomous subscription, multi-host directory replication, linearizable remote reads or arbitrary membership changes. Those omissions are listed as separate missing architectures rather than collapsed into “distributed directory complete.”

## 8. Layer‑2 reconciler: actual effect, drift, repair, and semantic separation

The Layer‑2 path uses a concrete `SandboxActuator`, not an executor placeholder. It writes managed files atomically with file `fsync`, `os.replace`, directory `fsync`, durable SQLite idempotency receipts and readback hashes.

For the accepted `Information` coordinate, Layer‑2 materialised `concept.html` with:

- size: `1669` bytes;
- SHA-256: `80991dd3a6132ce4321768c905e4c02477921438e566c3b873d36a098e42d1f2`;
- semantic digest visibly embedded as projection metadata: `True`.

The evidence harness then overwrote the file with `<h1>visual drift</h1>`. Planning returned action `REPLACE`. Apply restored the accepted HTML hash `80991dd3a6132ce4321768c905e4c02477921438e566c3b873d36a098e42d1f2`. The accepted semantic digest remained unchanged.

That result directly falsifies any architecture that treats the visual projection as semantic authority. The projection may drift; the accepted semantic identity remains the source against which drift is diagnosed.

## 9. Explicit binary boundary and A/B codec

### 9.1 Boundary activation rule

The evidence run first invoked binary materialization with `requires_binary=false`. Result:

```json
{
  "binary_exists": false,
  "event": "symbolic_path_preserved",
  "state": "SYMBOLIC_PATH_NO_BINARY_MATERIALIZATION"
}
```

No `concept.kxbd` file existed.

The same accepted concept was then passed with `requires_binary=true`. Result:

- wire encoding selected: `RAW_BINARY`;
- wire bytes: `1727`;
- wire SHA-256: `b22058442c2dde3128467bbd45f7202b8f86f541355055bad88ee76797ddf4fd`;
- semantic digest: `4c45218c93ceae1fd57b88d6f4a80866643096cbd383e7a1eb180472422338fe`;
- round-trip equality: `True`.

The real HTML workload selected `RAW_BINARY`. That is not a failure of the A/B system; it is the evidence-driven result that the HTML byte distribution does not benefit from bit-run packing under this codec.

### 9.2 A/B definition

R5 uses the KEX A/B law:

- `A1 … A9` encode runs of binary `1`;
- `B1 … B9` encode runs of binary `0`;
- runs longer than 9 are decomposed into maximal 9-sized chunks plus remainder;
- each packed token uses five bits: one symbol bit plus a four-bit count;
- decode re-encodes the bitstream to enforce canonical run segmentation.

`KXBD` v2 carries:

```text
magic | version | mode | bit_length | token_count
| semantic_digest_prefix[8] | payload_sha256[32] | payload
```

The payload mode is either `KEX_AB` or `RAW_BINARY`.

### 9.3 Codec falsification

Two controlled 128-byte inputs were executed:

```json
{
  "alternating": {
    "ab_token_count": 1024,
    "encoding": "RAW_BINARY",
    "roundtrip_equal": true,
    "schema": "keddeh.report03.semantic-boundary-integration.v1",
    "semantic_digest": "2222222222222222222222222222222222222222222222222222222222222222",
    "source_bytes": 128,
    "source_sha256": "55dbd20dff3ae84c9bc6bcd1546194d272793727ca6c03585a8804178b640342",
    "wire_bytes": 186,
    "wire_sha256": "77f98adc27c6a010885cc1b2c6e72f384ccbb273703184847a2669cebba386ef"
  },
  "event": "codec_workloads_observed",
  "uniform": {
    "ab_token_count": 114,
    "encoding": "KEX_AB",
    "roundtrip_equal": true,
    "schema": "keddeh.report03.semantic-boundary-integration.v1",
    "semantic_digest": "1111111111111111111111111111111111111111111111111111111111111111",
    "source_bytes": 128,
    "source_sha256": "38723a2e5e8a17aa7950dc008209944e898f69a7bd10a23c839d341e935fd5ca",
    "wire_bytes": 130,
    "wire_sha256": "a869caf75038c93fa2da3a6748c461b667fd5deefe0bf42f26694c3ef0c1d450"
  }
}
```

Uniform zero bytes selected `KEX_AB`; alternating `0xAA` bytes selected `RAW_BINARY`. Therefore the codec is **not** promoted as universal compression. It is a reversible representation option selected by observed payload efficiency.

Note also that the 128-byte uniform source produced a 130-byte complete wire packet once the 58-byte integrity/semantic header was included. A/B reduced payload size relative to the equivalent RAW packet, but the entire packet did not beat the naked source bytes. This is precisely why the report distinguishes codec payload efficiency from whole-protocol overhead.

### 9.4 Boundary integrity attacks

Two independent attacks fail closed:

- mutate the final payload byte → `BOUNDARY_PAYLOAD_DIGEST_MISMATCH`;
- decode a valid packet with another semantic digest → `SEMANTIC_DIGEST_PREFIX_MISMATCH`.

A third attack changes the accepted directory semantic digest itself. Binary materialization stops before encoding because `verify_accepted()` detects that accepted authority no longer matches the resident concept. This prevents a healthy codec from being used to legitimize a semantically corrupted accepted record.

## 10. Executed qualification surface

R5 is qualified through three independently exiting processes rather than one giant runner whose multiprocessing teardown could obscure exit state.

| Suite | Scope | Tests | Runtime | Result |
|---|---|---:|---:|---|
| `test_progression.py` | inherited local ToT/directory/reconciler semantics | 36 | 0.119s | PASS |
| `test_report03_v3.py` | independent process ToT, directory, Layer‑2 + new failed-prepare regression | 16 | 23.893s | PASS |
| `test_semantic_boundary_integration.py` | resident IL‑LLM → KEX → accepted state → projection/binary closure | 12 | 10.846s | PASS |
| **Total** | | **64** | **34.858s summed suite runtime** | **PASS** |

`python -m compileall` also passes for current source/tests.

The observed end-to-end evidence run is separate from the unit/invariant tests. It records `11` positive effect events, `8` fault/negative-control events and evidence root `9b0b4d9299c3ba5355b49d2de12a93828ac14d413b8a7fd19b74402f6d9ff765`.

All `13` SQLite files created by the final observed run pass `PRAGMA integrity_check`. Every observed database reports WAL mode and `synchronous=FULL` (`2`).

## 11. Falsification record

The following are retained because they materially changed the implementation or claim boundary. A receipt that omits them would be less informative than the failures themselves.

### F-R5-01 — The symbolic/binary boundary had already been partially engineered in resident artifacts before this run.

**Observed effect.** Work was treated as recovered baseline, not claimed as new implementation.

**Engineering response.** Integrated resident IL-LLM semantics and newer independent-process Report 03 V3 instead of duplicating the earlier package.

### F-R5-02 — R4 combined clean execution exceeded the command execution window, while isolated distributed tests completed.

**Observed effect.** Stored R4 PASS receipt was not used as proof of this rerun.

**Engineering response.** Qualified current R5 using separately exiting suites and current source.

### F-R5-03 — A monolithic 63-test invocation printed successful assertions but failed to exit cleanly after repeated multiprocessing teardown.

**Observed effect.** The invocation was not counted as a completed PASS.

**Engineering response.** Qualification is three independent exit-code-checked suites; aggregate passes only if each process exits 0.

### F-R5-04 — A failed one-triad minority prepare left uncommitted conflicting entries that blocked a later valid proposal at the same log index.

**Observed effect.** Minority failure could poison liveness despite preserving committed-state safety.

**Engineering response.** Replica append now permits supersession only for uncommitted entries from a strictly lower term and only when the new proposal extends the committed head. Same-term conflict remains fenced. Added regression test test_08b.

### F-R5-05 — Project-local deterministic JSON serializes 1e-7 as 1e-07 while ECMAScript JSON.stringify emits 1e-7.

**Observed effect.** Cross-language canonical hashes differ; RFC 8785/JCS compatibility is false for the observed input.

**Engineering response.** Report forbids JCS conformance claim and specifies canonicalization replacement as missing architecture.

### F-R5-06 — A/B encoding is workload-dependent. Uniform zero bytes selected KEX_AB; alternating 0xAA bytes selected RAW_BINARY.

**Observed effect.** A/B cannot be promoted as universal compression.

**Engineering response.** Adaptive boundary selects representation by payload size and keeps semantic identity independent from representation.

### F-R5-07 — Resident IL-LLM recovered adapter contains 1084 lexicon entries, but 2 are marked DEGRADED_SOURCE.

**Observed effect.** Semantic source completeness/cleanliness is not universal.

**Engineering response.** require_clean=True fails closed for degraded entries; full corpus repair remains explicit.

### F-R5-08 — The HTML manifestation was externally replaced with visual drift.

**Observed effect.** Projection bytes changed while accepted semantic state did not.

**Engineering response.** Layer-2 detected REPLACE and restored the exact accepted HTML hash without changing semantic_digest.

### F-R5-09 — Binary payload mutation changed packet bytes.

**Observed effect.** Readback integrity failed.

**Engineering response.** SHA-256 payload digest check rejected the packet with BOUNDARY_PAYLOAD_DIGEST_MISMATCH.

### F-R5-10 — A valid packet was decoded under the wrong expected semantic digest.

**Observed effect.** Representation could otherwise be detached from its semantic authority.

**Engineering response.** Semantic digest prefix binding rejected it with SEMANTIC_DIGEST_PREFIX_MISMATCH.

### F-R5-11 — Accepted directory metadata semantic_digest was maliciously patched to a different value.

**Observed effect.** The accepted object no longer matched the resident semantic concept.

**Engineering response.** Binary lowering failed closed at verify_accepted before substrate materialization.

## 12. Current standards comparison

Standards are used here as comparison surfaces, not as borrowed certifications. “Similar to” never means “conformant.”

### 12.1 RFC 8785 JSON Canonicalization Scheme (JCS)

**Current comparison:** `FAIL / NOT CONFORMANT`

**Observed R5 state:** Python project-local JSON and ECMAScript serialization differ for 1e-7; hashes differ.

**Architectural consequence:** Semantic/consensus hashes are deterministic only inside the current Python profile. Cross-language cryptographic identity is not established.

**Missing implementation for promotion:** Adopt and test a standards-conformant JCS implementation or define a different normative canonical format and cross-language vectors.

**Current source:** https://www.rfc-editor.org/rfc/rfc8785.html

### 12.2 RFC 8949 CBOR deterministic encoding

**Current comparison:** `NOT IMPLEMENTED`

**Observed R5 state:** KXBD is a custom binary packet; no CBOR codec is used.

**Architectural consequence:** KEX binary boundary is project-specific and lacks standardized deterministic binary interchange.

**Missing implementation for promotion:** Either retain KXBD as explicitly private protocol with a formal spec/test vectors, or add deterministic CBOR profile and semantic binding.

**Current source:** https://www.rfc-editor.org/rfc/rfc8949.html#section-4.2

### 12.3 RFC 9846 TLS 1.3

**Current comparison:** `ABSENT ON REPLICA TRANSPORT`

**Observed R5 state:** Process and directory RPC use plaintext loopback TCP; no ssl/TLS layer is instantiated.

**Architectural consequence:** Loopback tests prove message mechanics but not authenticated/confidential/integrity-protected multi-host transport.

**Missing implementation for promotion:** TLS 1.3 transport profile plus peer identity verification, certificate/key lifecycle, replay/session policy and fault tests.

**Current source:** https://www.rfc-editor.org/info/rfc9846/

### 12.4 SQLite WAL

**Current comparison:** `LOCAL-HOST APPROPRIATE / MULTI-HOST LIMIT`

**Observed R5 state:** 13 observed databases pass integrity_check and use WAL + synchronous FULL.

**Architectural consequence:** Durable local journals are real, but SQLite WAL explicitly requires processes sharing a database to be on the same host.

**Missing implementation for promotion:** For multi-host deployment, each host needs local durable state plus replicated-log protocol; never place a shared WAL database on a network filesystem.

**Current source:** https://www.sqlite.org/wal.html

### 12.5 Kubernetes controller pattern

**Current comparison:** `CONTROL-LOOP ANALOGUE, NOT COMPATIBILITY`

**Observed R5 state:** Layer-2 separates accepted desired state, observed manifestation, plan, effect, readback and NOOP convergence.

**Architectural consequence:** The reconciliation model now matches the desired/current control-loop discipline at a conceptual level.

**Missing implementation for promotion:** Production target-specific actuators/observers, retries, timeouts, compensation policy, status reporting and external-system qualification.

**Current source:** https://kubernetes.io/docs/concepts/architecture/controller/

### 12.6 etcd learner / membership safety

**Current comparison:** `MISSING DYNAMIC MEMBERSHIP`

**Observed R5 state:** ToT voter and directory replica sets are fixed. Catch-up exists for known replicas; learner admission/promotion does not.

**Architectural consequence:** Rejoin of known identities is tested, but adding/removing voting members safely is unproven.

**Missing implementation for promotion:** Non-voting learner state, catch-up thresholds, explicit promotion, overlapping/joint configuration safety, removal fencing and persistent membership history.

**Current source:** https://etcd.io/docs/v3.8/learning/design-learner/

### 12.7 SPIFFE workload identity / Workload API

**Current comparison:** `NOT IMPLEMENTED`

**Observed R5 state:** Replica identity is a configured logical voter string, not a cryptographically attested workload identity.

**Architectural consequence:** Process identity, authorization and vote authenticity are not bound to a workload trust domain.

**Missing implementation for promotion:** Workload identity issuance/attestation, short-lived verifiable identities, trust bundle/key rotation and mTLS binding to vote/commit receipts.

**Current source:** https://spiffe.io/docs/latest/spiffe/concepts/

### 12.8 Unicode UAX #15 Normalization Forms 18.0.0

**Current comparison:** `NORMALIZATION POLICY ABSENT`

**Observed R5 state:** Resident adapter casefolds lookup keys but does not apply Unicode normalization.

**Architectural consequence:** Canonical-equivalent Unicode spellings have not been proven to resolve to one semantic identity.

**Missing implementation for promotion:** Define NFC/NFKC policy per semantic domain, normalize before lookup/hash where intended, preserve original form for provenance, and add multilingual conformance vectors.

**Current source:** https://www.unicode.org/reports/tr15/

### 12.9 WHATWG HTML Living Standard data-*

**Current comparison:** `VALID PRIVATE PROJECTION METADATA / NOT GENERIC SEMANTIC INTERCHANGE`

**Observed R5 state:** HTML projection stores KEX/IL-LLM identity in data-* attributes.

**Architectural consequence:** This is suitable for application-private projection metadata, but WHATWG explicitly does not make data-* a generic cross-tool extension vocabulary.

**Missing implementation for promotion:** If public machine-interoperable semantics are required, define a stable external vocabulary/profile rather than treating data-* as universal authority.

**Current source:** https://html.spec.whatwg.org/multipage/dom.html#embedding-custom-non-visible-data-with-the-data-*-attributes

### 12.10 Raft consensus reference

**Current comparison:** `PARTIAL SAFETY ANALOGUE, NOT RAFT`

**Observed R5 state:** R5 has terms, majority/quorum gates, committed prefixes, restart/catch-up and higher-term uncommitted conflict supersession. It still uses external ProcessCluster orchestration and fixed membership.

**Architectural consequence:** The mechanics are stronger than an in-process model but do not constitute Raft implementation/conformance.

**Missing implementation for promotion:** Autonomous peer timers/elections, replicated progress tracking, formally specified log conflict algorithm, membership changes, snapshots, proof/model checking and multi-host failure-domain tests.

**Current source:** https://raft.github.io/

## 13. Standards probes executed against the implementation

The current source was also probed directly rather than only compared in prose.

```json
{
  "binary_standard_probe": {
    "cbor_library_used": false,
    "custom_kxbd_present": true,
    "status": "CUSTOM_CODEC_NOT_CBOR"
  },
  "jcs_probe": {
    "byte_equal": false,
    "ecmascript_json_stringify": "{\"n\":1e-7}",
    "ecmascript_sha256": "747d6d23b64d1b2d579adb832b44de31c91c875bbef7a8e397f5d183a746b54b",
    "python_project_local": "{\"n\":1e-07}",
    "python_sha256": "ff7a1315299260617fe404199e54e6d976a0b03e47da54fccec073c2fa48ff5c",
    "status": "FAIL_JCS_COMPATIBILITY"
  },
  "schema": "keddeh.report03.r5.standards-probe.v1",
  "transport_probe": {
    "loopback_tcp_present": true,
    "status": "PLAINTEXT_LOOPBACK_NOT_TLS",
    "tls_module_used": false
  },
  "unicode_probe": {
    "casefold_used": true,
    "status": "NORMALIZATION_POLICY_ABSENT",
    "unicode_normalization_module_used": false
  }
}
```

The JCS result is particularly decisive. RFC 8785 relies on ECMAScript primitive serialization as part of its canonical form. R5's project-local Python serializer emits `1e-07`, while ECMAScript emits `1e-7`. Because the bytes and hashes differ, R5 must not claim JCS compatibility.

The transport probe confirms loopback TCP is present and TLS code is absent. The Unicode probe confirms casefold is used but no Unicode normalization module/policy is applied. The binary-standard probe confirms the custom `KXBD` codec is not CBOR.

## 14. What advanced versus what did not

### Advanced and directly evidenced

- resident IL‑LLM semantics are an executable upstream input rather than a four-entry synthetic boundary dictionary;
- source provenance and source degradation survive translation;
- KEX-L-TRANS is observed from the recovered translator surface;
- semantic digest is checked before accepted-state creation and before binary lowering;
- semantic identity survives ToT commit, three-process directory replay/rejoin and Layer‑2 manifestation drift/repair;
- HTML projection is an effect, not the authority root;
- binary materialization is absent until explicit boundary activation;
- binary representation can select RAW or A/B without redefining semantic identity;
- binary payload tampering and wrong semantic binding fail closed;
- accepted semantic metadata tampering blocks substrate lowering;
- failed minority prepare poisoning was discovered and repaired with higher-term-only uncommitted supersession;
- 64 current tests pass across independently exiting qualification processes;
- 13 final observed SQLite databases pass integrity checks.

### Not advanced into a proved state

- multi-host consensus;
- autonomous peer consensus;
- dynamic voting membership;
- cryptographic peer/workload identity;
- standardized cross-language canonical semantic hashing;
- Unicode normalization semantics across the full language corpus;
- full IL‑LLM runtime/corpus completeness;
- full 256-bit semantic digest binding inside KXBD itself;
- standardized binary interchange;
- generic public semantic interoperability for the HTML projection;
- electrical/storage-hardware crash durability;
- autonomous directory replication;
- production target actuation;
- cryptographic semantic-policy authorization;
- Byzantine fault tolerance.

Those are not “later nice-to-haves.” They are the exact remaining architectures whose absence prevents broader claim promotion.

## 15. Architecture deficiency matrix — causal decomposition

This section deliberately repeats causality rather than hiding it in a one-line backlog. Each item answers the complete chain requested: what advanced; what is still unproven; why; why that reason has not been addressed; why the unresolved condition still exists; exactly which architecture is absent; and what evidence would be required to promote it.

### D-R5-01 — Independent multi-host failure domains

**What advanced.** Nine ToT voters and three directory replicas execute as independent OS processes with independent SQLite files and TCP sockets.

**What remains unproven.** Safety/liveness across separate physical hosts, regions, kernels and failure domains.

**Why it remains unproven.** Every final test runs on one host and loopback network; SQLite persistence is local.

**Why that why remains unaddressed.** The work closed process separation first because no authenticated multi-host transport/storage substrate is presently bound to these replicas.

**Why the unaddressed condition remains.** Without a host-to-host transport and deployment plane, moving processes onto separate machines would be an unqualified hosting change rather than a tested architecture.

**Architecture that is actually missing.** Multi-host peer transport; node discovery; per-host durable store; network-fault harness; clocks/timers policy; deployment topology; host identity; remote restart/rejoin; cross-host evidence collector.

**Evidence required before claim promotion.** At least 3 independent hosts across >=2 failure domains; real partitions/asymmetric loss/process pause/restart; no incompatible committed roots; recovery receipts from each host.

### D-R5-02 — Autonomous peer consensus

**What advanced.** Terms, elections, log append/commit, quorum certificates, conflict fencing, crash/rejoin and higher-term uncommitted supersession execute over nine voter processes.

**What remains unproven.** Peers do not autonomously discover/elect/replicate without ProcessCluster acting as the external protocol driver.

**Why it remains unproven.** ProcessCluster constructs certificates, schedules RPC phases and decides transitions.

**Why that why remains unaddressed.** Replacing the coordinator requires a peer protocol with timeouts, leader state, replication progress and recovery rules; none of those can be inferred from the current client harness.

**Why the unaddressed condition remains.** The present layer was intentionally bounded to make distributed effects falsifiable before claiming a complete consensus algorithm.

**Architecture that is actually missing.** Peer-resident election timers; leader/follower state machine; nextIndex/matchIndex or equivalent progress; heartbeats; retransmission/backoff; conflict repair; durable election state; formal safety specification/model checking.

**Evidence required before claim promotion.** Cluster starts with no external coordinator and reaches one leader; concurrent candidates/partitions/restarts never create incompatible commits; model checking plus destructive tests.

### D-R5-03 — Dynamic membership and learner admission

**What advanced.** Known replicas can restart stale, catch up and rejoin while preserving roots.

**What remains unproven.** Safe addition/removal/replacement of voting members.

**Why it remains unproven.** VOTERS and directory replica IDs are static constants; no membership log exists.

**Why that why remains unaddressed.** Membership changes alter quorum intersection and cannot be safely represented as a normal metadata update.

**Why the unaddressed condition remains.** No joint configuration/learner state has yet been engineered or persisted.

**Architecture that is actually missing.** Committed membership configuration history; non-voting learner; catch-up threshold; explicit promotion; overlapping/joint quorum transition; removal fence; identity rejoin/replacement law.

**Evidence required before claim promotion.** Property/model tests over add/remove during partitions plus multi-process destructive runs proving quorum intersection across every configuration transition.

### D-R5-04 — Cryptographic workload/peer identity

**What advanced.** Logical voter IDs and semantic authority are explicit and receipts are hash-linked.

**What remains unproven.** A received vote/RPC is not cryptographically proven to originate from the named workload.

**Why it remains unproven.** Transport is plaintext loopback TCP and voter names are configuration strings.

**Why that why remains unaddressed.** No certificate/trust-domain/key lifecycle is attached to the process identities.

**Why the unaddressed condition remains.** Identity work was deliberately not faked by embedding static secrets or labels into receipts.

**Architecture that is actually missing.** mTLS TLS 1.3 profile; workload attestation/SPIFFE-like identity plane; trust bundles; short-lived credentials; key rotation/revocation; signed vote/session binding; authorization policy.

**Evidence required before claim promotion.** Forged peer and replay tests fail; rotated/revoked credentials behave correctly; each commit certificate links to independently verifiable authenticated sessions.

### D-R5-05 — Cross-language canonical semantic hashing

**What advanced.** One Python canonical profile deterministically hashes resident semantic records and committed state.

**What remains unproven.** The same semantic object produces the same cryptographic identity across compliant non-Python implementations.

**Why it remains unproven.** Observed RFC8785 probe differs for 1e-7 between Python profile and ECMAScript serialization.

**Why that why remains unaddressed.** Canonicalization is currently an implementation helper rather than a normative cross-language protocol.

**Why the unaddressed condition remains.** Earlier work optimized deterministic local evidence before defining an interoperable canonical wire identity.

**Architecture that is actually missing.** Normative JCS implementation or deterministic CBOR profile; language-independent test vectors; numeric/unicode edge cases; versioned canonicalization identifier in hashes/receipts.

**Evidence required before claim promotion.** Independent Python/JS/Rust/Go implementations produce byte-identical canonical vectors and roots for the complete corpus edge-case suite.

### D-R5-06 — Unicode semantic normalization

**What advanced.** Resident lookup uses exact source entities plus casefold; original provenance is preserved.

**What remains unproven.** Canonical-equivalent Unicode spellings resolve to one intended semantic identity across languages.

**Why it remains unproven.** No Unicode normalization form is applied before lookup or semantic hashing.

**Why that why remains unaddressed.** Normalization can change semantics in some domains, so choosing NFC/NFKC cannot be guessed globally.

**Why the unaddressed condition remains.** The recovered lexicon is predominantly English and does not supply a full multilingual normalization policy.

**Architecture that is actually missing.** Per-domain normalization policy; UAX #15 implementation; original-form provenance; normalized lookup key; multilingual collision/confusable tests; script-specific exceptions.

**Evidence required before claim promotion.** NFC/NFD/NFKC vectors across supported languages resolve according to declared policy without unintended identity collapse.

### D-R5-07 — Resident IL-LLM completeness

**What advanced.** The integrated translator reads 1084 recovered lexicon entries, 71 router entries, 7 translator domains and 11 runtime registers; KEX-L-TRANS is actually observed.

**What remains unproven.** This adapter is not the complete IL-LLM runtime/dictionary/grammar corpus.

**Why it remains unproven.** It is a read-only adapter over recovered workbook surfaces and two lexicon entries are degraded.

**Why that why remains unaddressed.** The full authoritative grammar/dictionary execution surface has not been identified as one complete, versioned, executable source.

**Why the unaddressed condition remains.** Merging incomplete workbook fragments would fabricate authority and erase source defects.

**Architecture that is actually missing.** Versioned IL-LLM corpus manifest; complete grammar/rule tables; multilingual dictionaries/thesauri; source repair workflow; provenance per entry; deterministic compiler from corpus to runtime index; corpus validation.

**Evidence required before claim promotion.** Complete corpus inventory and hashes; zero unresolved/degraded required entries; grammar test suite; rebuild from corpus to runtime producing identical semantic index.

### D-R5-08 — Full semantic binding in binary packet

**What advanced.** KXBD packet binds an 8-byte prefix of semantic_digest and a full payload SHA-256; wrong digest prefix is rejected.

**What remains unproven.** The packet itself does not carry or authenticate the full 256-bit semantic digest.

**Why it remains unproven.** Header currently stores only the first 8 bytes to keep fixed metadata compact.

**Why that why remains unaddressed.** There is no signed external semantic-reference object that upgrades the prefix into full authenticated identity.

**Why the unaddressed condition remains.** The boundary was designed to prove separation of semantic identity from byte representation, not to define the final security protocol.

**Architecture that is actually missing.** Full semantic digest or collision-resistant content-address reference in packet; versioned schema; optional signature/MAC bound to full semantic digest + payload digest + codec profile.

**Evidence required before claim promotion.** Collision/adversarial corpus tests and cryptographic verification prove a packet cannot be rebound to a different accepted semantic object.

### D-R5-09 — Standardized binary interchange

**What advanced.** A/B and RAW adaptive binary lowering is reversible, deterministic for tested inputs and integrity checked.

**What remains unproven.** Interoperability with standard binary serialization ecosystems.

**Why it remains unproven.** KXBD is a private codec and is not CBOR/Protobuf/ASN.1/etc.

**Why that why remains unaddressed.** A/B expresses bit runs, not a general semantic data model with standard schema evolution.

**Why the unaddressed condition remains.** The custom codec is intentionally a KEX boundary experiment, and universal compression was falsified.

**Architecture that is actually missing.** Formal KXBD specification/test vectors and/or deterministic CBOR profile; schema/version negotiation; extensibility; independent decoder implementation; resource limits.

**Evidence required before claim promotion.** Independent implementation decodes/encodes all normative vectors; malformed/fuzzed packets fail safely; semantic roots match across implementations.

### D-R5-10 — HTML semantic interoperability

**What advanced.** HTML concept projection contains escaped human-readable meaning and private data-* identity metadata; Layer-2 repairs drift.

**What remains unproven.** Generic third-party software can interpret KEX semantic metadata without project knowledge.

**Why it remains unproven.** WHATWG data-* is application-private metadata, not a generic vocabulary.

**Why that why remains unaddressed.** No public vocabulary/namespace/schema has been standardized for KEX semantic concepts.

**Why the unaddressed condition remains.** Publishing internal data-* names as if they were universal semantics would repeat the exact presentation/authority conflation this work is avoiding.

**Architecture that is actually missing.** External semantic vocabulary/profile if needed; schema identifiers; version negotiation; mapping from IL-LLM semantic records to standardized machine-readable representation; conformance validator.

**Evidence required before claim promotion.** Independent consumer correctly interprets semantic objects without KEX source-code knowledge and without relying on visual layout.

### D-R5-11 — Power-loss durability

**What advanced.** 13 persisted databases pass integrity_check and run WAL + synchronous FULL; atomic file actuator uses fsync + os.replace + directory fsync.

**What remains unproven.** Survival of actual machine power loss, filesystem/kernel crash, disk-full/torn-write/controller failure.

**Why it remains unproven.** Tests terminate processes and modify databases, not electrical/storage hardware.

**Why that why remains unaddressed.** A process crash cannot reproduce every storage-controller and filesystem failure mode.

**Why the unaddressed condition remains.** No destructive hardware/VM power-cut harness with storage-level telemetry has been connected.

**Architecture that is actually missing.** Power-cut VM or hardware test rig; filesystem matrix; disk-full/fault injection; WAL/checkpoint policy; backup/restore; torn-write corruption corpus; durability SLA.

**Evidence required before claim promotion.** Repeated cut-at-every-transition campaigns recover to either prior or committed valid state with no silent accepted-root divergence.

### D-R5-12 — Autonomous directory replication

**What advanced.** Three independent directory processes persist and converge from the canonical committed log; one was killed stale, restarted, and caught up.

**What remains unproven.** Directory replicas autonomously subscribe to accepted commits and repair gaps without an external sync() call.

**Why it remains unproven.** DirectoryCluster explicitly pushes the canonical log to replicas.

**Why that why remains unaddressed.** There is no commit-stream subscription/watch protocol or per-replica replication cursor negotiated between peers.

**Why the unaddressed condition remains.** The current design proved authority projection and rejoin before adding another distributed transport.

**Architecture that is actually missing.** Authenticated commit stream; durable applied cursor; snapshot bootstrap; gap request/repair; backpressure; stale-replica fencing; root gossip/comparison; automatic resubscription.

**Evidence required before claim promotion.** Kill/restart/partition replicas without calling sync(); replicas autonomously catch up and converge with bounded recovery evidence.

### D-R5-13 — Production Layer-2 actuation

**What advanced.** Closed-loop reconciler performs actual atomic filesystem effects, idempotency receipts, readback, drift detection/repair and stale accepted-state fencing.

**What remains unproven.** Real DNS/TLS/compute/container/device/provider manifestations converge under partial external failures.

**Why it remains unproven.** Only a local managed filesystem actuator is bound in R5.

**Why that why remains unaddressed.** Each real target has different create/update/delete semantics, idempotency, eventual consistency and rollback constraints.

**Why the unaddressed condition remains.** Inventing one generic actuator would falsely claim control over systems not connected to the test environment.

**Architecture that is actually missing.** Typed actuator interface; target-specific adapters; observers; retry/backoff; timeout/cancel; idempotency keys; compensation semantics; per-target credentials/policies; status feedback.

**Evidence required before claim promotion.** Closed-loop destructive staging tests against each real target with induced timeouts/partial failures and verified convergence/readback.

### D-R5-14 — Semantic policy authorization

**What advanced.** Semantic owner, KEX route, source locator/status and accepted digest are explicit and fail-closed on mismatch.

**What remains unproven.** Who is authorized to create/change a semantic definition or promote a repaired degraded source is not cryptographically enforced.

**Why it remains unproven.** Authority is represented as metadata and trusted source files, not an authorization decision with principals and signed policy.

**Why that why remains unaddressed.** The present work verifies consistency of supplied semantics, not governance of who may redefine them.

**Why the unaddressed condition remains.** No capability lease/policy engine/signature chain is connected to IL-LLM mutation or KEX commit admission.

**Architecture that is actually missing.** Principal identity; signed semantic revisions; capability/policy engine; review/promotion states; revocation; immutable audit chain; quorum policy for semantic schema changes.

**Evidence required before claim promotion.** Unauthorized mutation/replay/rollback fails; authorized revision creates traceable new semantic version without rewriting prior history.

### D-R5-15 — Byzantine/malicious replica tolerance

**What advanced.** Crash, omission, stale state, tamper detection and minority-quorum failures are tested.

**What remains unproven.** Safety with arbitrary malicious replicas sending equivocal or forged protocol messages.

**Why it remains unproven.** Quorum arithmetic assumes crash/omission behavior and trusted process identities.

**Why that why remains unaddressed.** Byzantine tolerance requires a different threat model, quorum mathematics and authenticated message protocol.

**Why the unaddressed condition remains.** No BFT protocol was requested or honestly implemented; labeling current majority behavior BFT would be false.

**Architecture that is actually missing.** Explicit BFT decision; authenticated signed messages; 3f+1-style or selected protocol constraints; equivocation evidence; view change; state transfer; formal proof/model; adversarial network tests.

**Evidence required before claim promotion.** Byzantine test harness with malicious peers cannot create conflicting commits within the stated fault threshold; proof assumptions are documented and checked.

## 16. Evidence receipts and reproducibility

The report is backed by machine-readable artifacts rather than a single “PASS” label.

Primary evidence:

- `evidence/QUALIFICATION_RECEIPT_R5.json` — qualification root `264c85c12939f3a6ceed23ec976e567e564ece1c08ef6d3d30f6a7326aba2706`;
- `evidence/observed_run_r5/OBSERVED_EVIDENCE_R5.json` — evidence root `9b0b4d9299c3ba5355b49d2de12a93828ac14d413b8a7fd19b74402f6d9ff765`;
- `evidence/FALSIFICATION_LOG_R5.json` — failure/repair history;
- `evidence/ARCHITECTURE_DEFICIENCY_MATRIX_R5.json` — causal gap matrix;
- `evidence/CURRENT_STANDARDS_COMPARISON_R5.json` — current standards mapping;
- `evidence/STANDARDS_PROBE_R5.json` — executable standards-related probes;
- `evidence/SQLITE_INTEGRITY_R5.json` — persistent store integrity;
- `evidence/TOT_PROCESS_CLUSTER_R5_PATCH.diff` — exact consensus-liveness repair;
- individual test transcripts for 36, 16 and 12 test suites.

Source provenance includes the recovered IL‑LLM cell corpus and three workbook sources. The executable adapter reports source SHA-256 `25b59aa77b58d3445f08bee2db2a7f72b60705bf87e306db4ac2354a0fe0eed3` for the recovered cell corpus.

## 17. Exact claim boundary

R5 proves a stronger statement than previous Report 03 iterations, but a narrower statement than a production distributed semantic operating system.

**Supported by observed evidence:**

> A resident recovered IL‑LLM semantic record can be deterministically translated into a KEX semantic concept, committed through a nine-process non-Byzantine accepted-state model, replayed by three independently persisted directory processes, reconciled into a real filesystem HTML manifestation, kept semantically stable across visual drift, and lowered into a reversible integrity-checked binary packet only when an explicit substrate boundary requires byte materialization.

**Not supported by current evidence:**

> The same guarantees hold across independent physical sites, hostile/malicious replicas, dynamic membership, standardized interoperable canonicalization, cryptographically authenticated peers, the entire IL‑LLM corpus/runtime, arbitrary production infrastructure actuators, or hardware power loss.

That separation is the result of the engineering, not cautionary wording added after the fact.

## 18. Engineering determination

The missing symbolic/binary boundary is no longer merely described. Its principal mechanics are now executable and connected to the accepted-state/control-plane layers:

```text
IL-LLM = semantic authority / dictionary source
KEX    = translation + boundary control
ToT    = accepted-state safety model
Directory = committed semantic/desired-state projection
Layer 2   = desired-versus-observed reconciliation and effect
HTML      = symbolic/human concept projection
KXBD      = explicit byte-boundary carrier
A/B       = optional bit-run representation chosen only when beneficial
```

The strongest architectural result is separation of identity from representation. The same semantic digest survives while the observer-facing representation changes, while a directory replica disappears and returns, and while binary encoding changes according to workload. Conversely, a change to the semantic authority cannot be smuggled through as a harmless rendering or codec change: stale/mutated semantic digests fail closed.

The strongest falsification result is the minority-prepare poisoning bug. It demonstrated that a system can satisfy existing safety tests and still contain a liveness trap at an untested transition boundary. R5 repairs that defect and adds a permanent regression test. That is a more meaningful advance than another “architecture complete” banner.

The remaining gaps are now dominated by externalization: independent hosts, autonomous peer protocol, cryptographic workload identity, dynamic membership, standardized canonicalization/serialization, complete IL‑LLM corpus governance and real infrastructure actuators. None of those properties can be produced by adding more visual projections or status receipts. They require the missing architectures enumerated in Section 15 and corresponding destructive evidence.