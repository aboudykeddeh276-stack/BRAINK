# Evidence Context Resolution

## Canonical model

Evidence classification is now governed by:

```text
S = f(I,V,O,E,X,R,L)
```

Where:

- `I` is invariant.
- `V` is variant.
- `O` is observer.
- `E` is environment.
- `X` is execution plane.
- `R` is evidence/readback class.
- `L` is lineage.

A single signal cannot determine the full capability state. A label such as `ONLINE`, `ATTESTED`, `TPU`, `simulated`, `Math.random()` or `quantum core` is not allowed to produce a terminal judgement by itself.

## Preserved invariants

The resolver preserves identity, source state, declared capability, dependency boundary, observer, environment, execution plane, evidence origin, time/freshness, lineage and impact radius.

## Legitimate variants

Projection, simulation, fixture, benchmark, fallback, emulator, local execution, host execution, provider execution, imported observation, target declaration, degraded execution and deferred execution are legitimate variants. A variant must be classified, bounded and correlated. It must not be collapsed into a one-word judgement.

## Bounded derivation rule

Signals such as `Math.random()`, `ONLINE`, `ATTESTED`, `TPU`, `quantum core` and `simulated` must enter a contextual resolution pipeline:

```text
identify character/capability
identify purpose
identify observer
identify environment
identify execution plane
identify evidence class
determine freshness and lineage
derive capability-scoped state
```

The resolver may derive `DECLARED_TARGET`, `DECLARED_VARIANT`, `PROJECTION_ACTIVE`, `FIXTURE_ACTIVE`, `EMULATOR_ACTIVE`, `LOCAL_EXECUTED`, `HOST_EXECUTED`, `PROVIDER_EXECUTED`, `DEGRADED_VALID`, `DEFERRED_COMMIT`, `EVIDENCE_CORRELATION_REQUIRED`, `CONTEXT_RESOLUTION_REQUIRED` or `REINTEGRATION_REQUIRED`.

Only a proven invariant violation may produce `BOUNDED_STOP`. Only a proven global safety, semantic or integrity violation may produce `GLOBAL_SAFETY_STOP`.

## Command

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_evidence_context_resolver.py --root . --emit-receipt
python3 -m unittest tests.test_evidence_context_resolver -v
```

## Outputs

```text
evidence/evidence_context_resolution_receipt.json
exports/evidence_context_resolution_matrix.csv
runtime_volume/workplans/evidence_context/*.json
runtime_volume/outbox/evidence_context_resolution/*.handoff.json
runtime_volume/proof_bundles.ledger
```

## Boundary

This resolver does not prove target hardware, TPU execution, v86 guest boot, provider attestation, DNS/TLS or certification. It prevents bad evidence interpretation and forces each signal into a capability-scoped resolution task.
