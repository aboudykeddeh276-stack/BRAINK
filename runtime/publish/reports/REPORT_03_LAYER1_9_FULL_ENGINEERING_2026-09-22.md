# REPORT 03 — Full Software Suite, Distributed Directory and Layer 1–9 Engineering Qualification

Date: 2026-09-22

## Executive result

This pass replaces the previous Layer 1–9 hash-label pipeline with an executable, typed, receipted transaction pipeline and binds it to the current Report 03 ToT/directory/Layer-2/evidence contracts.

Observed local qualification:

- unit/integration tests: **16 passed, 0 failed**;
- fault campaign: **14 scenarios passed, 0 failed**;
- all nine layer-specific injected failures failed closed at the faulted layer;
- all nine transient layer failures converged on retry when the committed prefix was unchanged;
- all nine same-generation payload mutations were rejected;
- **180/180** randomized receipt-hash tamper attempts were rejected;
- **2/2** false observation-state assertions were rejected;
- 100 resident-stack trials with 30% L2 actuator failure probability produced 72 commits and 28 failures;
- evidence-boundary violations across those 100 trials: **0**.

The result materially advances the software suite. It does not prove the missing distributed/physical architectures listed later in this report.

## 1. Baseline inspected

The repository already contained:

- `runtime/publish/src/braink_runtime/tot_safety.py`;
- `coordinate_directory.py`;
- `layer2_reconciler.py`;
- `evidence_journal.py`;
- Report 03 v2 tests with 16 prior safety/directory/L2 checks;
- a separate `docs/kex-boundary-runtime-r03/src/layer1_9_reconciler.py`;
- a separate `full_suite_kernel.py`.

The existing Layer 1–9 implementation enforced a deterministic hash chain and generation ordering. Its limitation was structural: each layer accepted an arbitrary dictionary, derived another hash and called the stage `ACTIVE`. That did not prove identity, directory, consensus, execution, observation or evidence semantics.

This pass keeps the stronger runtime/publish ToT/directory/L2/evidence components and replaces the missing Layer 1–9 integration layer.

## 2. Layer 1–9 contracts implemented

### Layer 1 — INGRESS
Required fields:
`payload_hash`, `payload_bytes`, `media_type`.

Validation:
- byte count cannot be negative;
- payload hash must be a 64-character digest.

Meaning:
the transaction starts from a content identity rather than a descriptive label.

### Layer 2 — IDENTITY
Required:
`actor_id`, `authority_ref`, `capability`.

Validation:
- zero cannot be actor identity;
- authority reference is mandatory.

Still unproven:
actual distributed authentication and authorization. This stage records and gates identity metadata; it does not issue service credentials.

### Layer 3 — COORDINATE
Required:
`coordinate`, `directory_root`, `coordinate_generation`.

Validation:
- zero address rejected;
- generation positive.

The full-suite resident adapter consumes the root produced by the current distributed coordinate directory after application of a committed ToT transition.

### Layer 4 — GEOMETRY
Required:
`mapping`, `origin`, `geometry_root`.

This is deliberately an abstract geometry contract. It does not claim physical toroidal signal propagation merely because the word geometry appears in a dictionary.

### Layer 5 — PROPAGATION
Required:
`route_id`, `signal_type`, `destination`.

This binds routing intent into the receipt chain. It does not itself provide network delivery.

### Layer 6 — CONSENSUS
Required:
`epoch`, `index`, `commit_root`, `quorum_size`, `membership_hash`, `certificate_hash`, `receipt_hash`.

This is the most important hardening over the previous Layer 1–9 implementation. A consensus-looking payload is no longer enough. The stage binds to actual ToT membership, quorum-certificate and commit-receipt identities.

Validation:
- positive epoch/index;
- quorum size >= 2;
- all cryptographic identity fields are 64-character hex digests.

Still unproven:
multi-host consensus. The values are produced by the current fixed-membership ToT kernel.

### Layer 7 — EXECUTION
Required:
`operation`, `target`, `result_root`.

The resident adapter binds Layer 7 to the current Layer-2 reconciler through an injected actuator. Failure to converge stops the transaction before observation/evidence.

### Layer 8 — OBSERVATION
Required:
`observer_id`, `before_root`, `after_root`, `changed`.

Validation catches contradictory observation claims:
- `changed=false` with different before/after roots is rejected;
- `changed=true` with identical roots is rejected.

This prevents an execution receipt from automatically becoming observation proof.

### Layer 9 — EVIDENCE
Required:
`evidence_root`, `receipt_count`, `claim_state`.

Layer 9 requires eight prior layer receipts. The complete chain is then appended through the evidence sink. Failure to append evidence prevents the kernel result from becoming `COMMITTED`.

## 3. Receipt-chain semantics

Each committed layer receipt binds:

- run ID;
- layer number/name;
- generation;
- prior receipt hash;
- upstream input root;
- payload root;
- output root;
- status/error;
- receipt hash.

The chain is anchored at a deterministic genesis root.

A retry at the same generation is idempotent only when the payload root is unchanged. A different payload at the same generation raises `SAME_GENERATION_PAYLOAD_CONFLICT`.

When an upstream layer commits at a newer generation, the downstream suffix is invalidated and must be recomputed.

## 4. Full-suite resident adapter

The new composition root binds:

1. ToT proposal/vote/commit;
2. distributed coordinate-directory apply;
3. Layer-2 desired/observed reconciliation;
4. Layer 1–9 transaction receipts;
5. evidence-journal append.

On first coordinate materialization, the resident adapter commits registration and manifestation-upsert transitions before exposing the directory root to Layer 3.

Layer 6 receives the committed ToT receipt/certificate identities. Layer 7 receives the L2 receipt root. Layer 8 hashes observed state before and after the L2 action. Layer 9 seals only after the nine-stage chain verifies.

## 5. Executed tests

Observed command result:

`16 passed in 0.07s`

Test classes exercised:

- all-nine-stage commit;
- idempotent same-generation replay;
- same-generation mutation rejection;
- missing-layer rejection;
- zero actor and zero coordinate rejection;
- false observation rejection;
- incorrect Layer 9 receipt count;
- transient Layer 7 failure and same-generation resume;
- upstream generation invalidation;
- receipt tampering;
- full kernel commit;
- missing consensus readback;
- evidence append failure;
- resident ToT/directory/L2/layer/evidence integration;
- resident L2 failure preventing Layer 9 seal;
- malformed consensus certificate hash rejection.

## 6. Fault injection

Observed campaign:

`14 scenarios PASS / 0 FAIL`

### 6.1 Layer faults
Layers 1 through 9 were each independently faulted. In every case:
- no layer after the fault was committed;
- the failure receipt identified the faulted layer;
- the prior committed prefix remained intact.

### 6.2 Retry
All nine transient layer-failure cases converged on a retry using the same run ID/generation and unchanged committed prefix.

### 6.3 Same-generation mutation
All nine attempts to change one layer payload after that generation was already committed were rejected.

### 6.4 Receipt tamper
180 randomly selected receipt hashes were replaced after successful execution. `verify_chain()` rejected 180/180.

### 6.5 Observation lie
Both contradictory observation combinations were rejected.

### 6.6 Resident L2 fault boundary
100 independent resident-stack trials ran with 30% injected actuator-failure probability.

Observed:
- 72 transactions committed;
- 28 failed before final evidence seal;
- 0 failure transactions appended Layer 9 evidence.

This demonstrates the local evidence boundary under the tested fault model. It does not prove a real provider/device exactly-once property.

## 7. What advanced

### 7.1 Layer labels became executable contracts
The previous nine-layer chain primarily proved that nine hashes could be ordered. R2 proves that each stage carries stage-specific required state and rejects several classes of contradictory/fabricated state.

### 7.2 Layer 6 now binds actual consensus evidence
Membership, quorum certificate and receipt identities are part of the stage contract.

### 7.3 Execution no longer implies observation
Layer 7 and Layer 8 are separately validated.

### 7.4 Observation no longer implies evidence
Layer 9 requires the complete eight-stage prefix and a successful evidence append.

### 7.5 Retry is fenced
Same-generation replay is permitted only for identical already-committed stage payloads.

### 7.6 Correction/partial failure does not create false completion
A faulted stage leaves a committed prefix, not a fabricated Layer 9 root.

## 8. What remains unproven

The following are still unproven by this execution:

- independent-host ToT consensus;
- leader/equivalent ordering authority;
- safe membership changes;
- Byzantine consensus;
- linearizable network coordinate service;
- independently durable replicated state;
- cross-process Layer 1–9 atomicity/recovery;
- real physical/external Layer 7 actuation;
- independent observation authority at Layer 8;
- IEEE 802.1Q bridge behavior;
- RFC 8785/JCS conformance;
- authenticated SLSA/in-toto provenance;
- formal verification;
- long-run compaction/migration;
- production performance/SLOs.

## 9. WHY each remains unproven

They remain unproven because the executed failure domain was local Python/process/filesystem plus controlled actuator faults. The missing properties depend on independent schedulers, networks, disks, credentials, external providers and formal state-space exploration that were not present in this qualification environment.

## 10. WHY the reason remains unaddressed

The cause is not a shortage of test cases around the same code. The required execution substrates are absent.

A network partition cannot be honestly tested without independent peers and a controllable network fault layer. External exactly-once-equivalent behavior cannot be proven without a real provider/device contract. Formal consensus safety cannot be established by increasing randomized unit tests.

## 11. WHY the unaddressed concepts remain

Each remaining concept belongs to an architecture class separate from the code completed here:

- distributed consensus runtime;
- durable transaction/recovery plane;
- production actuator/observer plane;
- identity/trust plane;
- interoperability/canonicalization plane;
- provenance/signing plane;
- formal-verification plane.

Those classes are detailed in `REPORT_03_DEFICIENCY_ARCHITECTURE_MATRIX_2026-09-22.md`.

## 12. Explicit required architecture

### Distributed consensus runtime
Authenticated peer messaging, term/view persistence, leader/equivalent ordering, replicated WAL, conflict repair, safe membership transition, snapshots, network partition handling.

### Distributed Layer 1–9 transaction plane
Durable run IDs, per-stage ownership/fencing, recovery coordinator, cross-process replay, compensation policy, exactly-one evidence seal.

### Production execution/observation plane
Target-specific adapters, credentials, persistent idempotency identities, timeout ambiguity resolution, independent readback, rollback/compensation and external sandbox fault injection.

### Interoperability
RFC 8785/JCS or another defined canonical format, cross-language test vectors, schema/version rules; YANG projection where management interoperability is required.

### Provenance
in-toto/SLSA statement envelope, trusted builder identity, signatures/identity-backed signing, independent verifier and publication path.

### Formal verification
TLA+/PlusCal or equivalent state model, safety/liveness invariants, fault assumptions, model checking and mapping between formal operations and runtime methods.

## 13. Evidence fingerprints

Primary local source SHA-256:

```json
{
  "braink_runtime/layer1_9_reconciler.py": "f55061b7e97120af91898917c72dec6e7d8be4899d416cb61d415a7cd09828b9",
  "braink_runtime/full_suite_kernel.py": "96bcaf5a7c06540109fed7b8c6a2a8506a51cbb694a693a052525f7c19dc5cfb",
  "tests/test_layer1_9_full_suite.py": "b5817ba71b3f67d5643424931f120bc4c61379ed9fa6449542041b02fd4cfb59",
  "tests/test_resident_full_suite.py": "d2c37d6f4abf6585dab9fac6cf23a63a0bc4ecbd965d82baba9cc1fc0ac559c0",
  "tools/run_layer1_9_fault_campaign.py": "c8385d745126fb0918801bc757d816176f883ac3e9253110a85b01141b206a41"
}
```

The machine-readable execution receipt is:
`evidence/REPORT03_LAYER1_9_EXECUTION_RECEIPT_R2.json`.

The raw fault result is:
`evidence/fault_campaign_output.json`.

## 14. Evidence classification

### Qualified by this pass
- typed local Layer 1–9 receipt chain;
- same-generation mutation fencing;
- downstream invalidation on new upstream generation;
- local transient fault recovery;
- local receipt tamper detection;
- observation consistency checking;
- resident ToT/directory/L2/evidence composition API;
- no Layer 9 evidence leakage in the 100 injected L2-failure trials.

### Not qualified
Everything requiring a failure domain not actually exercised: independent hosts, networks, physical devices, external providers, adversarial participants, standard canonical encoders, trusted provenance authorities or exhaustive formal schedules.

## 15. Conclusion

The missing engineering layer was not another nine-layer diagram. It was the mechanism that forces each named layer to prove its own contract and prevents later layers from claiming completion when an earlier layer failed or lied.

That mechanism now exists and executed successfully in the tested local failure domain.

The remaining deficiencies are separated explicitly by absent architecture rather than being relabelled as “future work.”
