# Failure and Evidence Model

## Failure classifications

Each failure class has a machine-stable identifier and a full semantic name.
Use the full name in documentation and the machine id in code and JSON.

| Machine identifier | Full semantic name |
|---|---|
| `REQUIREMENT_IS_AMBIGUOUS_OR_INCOMPLETE` | Requirement is ambiguous, contradictory, incomplete, or impossible under stated assumptions |
| `IMPLEMENTATION_DOES_NOT_REALISE_THE_REQUIRED_MECHANICS` | Implementation does not correctly realise the required mechanics |
| `INCOMPATIBLE_INTERFACE_BETWEEN_COMPONENTS` | Components have incompatible interfaces, units, encodings, ordering, or state semantics |
| `IMPLEMENTATION_VIOLATES_AN_APPLICABLE_PROTOCOL` | Implementation violates an applicable protocol or externally governed contract |
| `REQUIRED_FUNCTIONAL_DEPENDENCY_IS_ABSENT` | Required functional dependency is absent |
| `ENVIRONMENT_LACKS_A_REQUIRED_TARGET_PROPERTY` | Current environment lacks a required target property |
| `MEASURED_PERFORMANCE_PATH_FAILS_REQUIREMENT` | A measured performance path fails a stated requirement |
| `REQUIRED_SECURITY_PROPERTY_CANNOT_BE_ESTABLISHED` | Required security property cannot be established in the current configuration |
| `EVIDENCE_CANNOT_SUBSTANTIATE_THE_CLAIM` | Retained evidence cannot substantiate the claim being made |
| `EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN` | Evidence is insufficient; capability status remains unknown |
| `EXISTING_ARTIFACT_TREATED_AS_AUTHORITY_WITHOUT_MECHANIC_VALIDATION` | An existing artifact was reused as a dependency, module, or authoritative runtime before its mechanics were extracted and independently validated |
| `MISSING_FILE_OR_DIRECTORY` | A required file or directory was not found at the expected path |
| `SYNTAX_ERROR_IN_SOURCE` | Source file contains a syntax error that prevents parsing or compilation |
| `TEST_ASSERTION_FAILED` | A test assertion evaluated to false against a declared acceptance criterion |
| `DEPENDENCY_NOT_INSTALLED` | A required package, module, or tool is not installed in the environment |
| `PERMISSION_DENIED` | The process does not have permission to read, write, or execute the required resource |
| `NETWORK_OR_AUTHENTICATION_ERROR` | A required network resource or API endpoint could not be reached or authenticated |
| `TIMEOUT` | An operation exceeded its allowed time limit |
| `UNKNOWN` | Root cause could not be classified with the available evidence |

## Constraint classifications

| Machine identifier | Full semantic name |
|---|---|
| `MEASURED_BOTTLENECK` | Measured bottleneck — empirically observed performance limit |
| `THEORETICAL_PROTOCOL_OR_MATHEMATICAL_BOUND` | Theoretical protocol or mathematical bound — e.g. bandwidth limit, complexity class |
| `FUNCTIONAL_DEPENDENCY_CONSTRAINT` | Functional dependency constraint — capability requires another that is absent |
| `SECURITY_DEPENDENCY_CONSTRAINT` | Security dependency constraint — security property requires another that is absent |
| `OPTIMISATION_DEPENDENCY` | Optimisation dependency — performance target requires a change not yet made |
| `ENVIRONMENTAL_CONSTRAINT` | Environmental constraint — target environment imposes a limit |
| `UNKNOWN_CONSTRAINT` | Unknown constraint — constraint exists but cannot yet be classified |

## Evidence chain

```
Claim
→ Requirement (what must be true)
→ Mechanism (why it would be true)
→ Test (how it is verified)
→ Evidence (the retained artifact that demonstrates it)
→ Verdict (PASS | FAIL | UNKNOWN)
```

A claim is valid only when this full chain resolves without gaps.
A missing or unresolvable link makes the verdict UNKNOWN, not PASS.

## Evidence grades

| Grade | Full semantic name | Meaning |
|---|---|---|
| `CONCEPT_ONLY` | Concept or idea only | No design, implementation, or test exists |
| `STRUCTURED_DESIGN_EVIDENCE` | Structured requirement or design evidence | Requirements and/or design documents exist |
| `STATIC_IMPLEMENTATION_EXISTS` | Static implementation or specification exists | Source files exist but have not been executed |
| `REPEATABLE_EXECUTED_LOCAL_EVIDENCE` | Repeatable executed local build and test evidence | Build and tests execute and pass locally |
| `INDEPENDENT_REPLICATION_OR_ATTESTATION` | Independent replication, audit, or authoritative external acceptance evidence | Third-party confirmation or CI pass |
| `CONTINUOUS_TAMPER_EVIDENT_MONITORING` | Continuous independent tamper-evident monitoring evidence | Ongoing instrumented verification |

Short aliases may exist as secondary convenience labels but must never replace the full definitions.

## Prohibited claim behaviours

- Claiming PASS on a check that was not executed.
- Inferring capability presence from source file existence alone.
- Treating an existing artifact as a dependency, module, or authoritative runtime before its mechanics are extracted and independently validated.
- Reusing a whole module when only some of its mechanics are validated, instead of reconstructing cleanly from the validated mechanics.
- Treating a document reference as equivalent to a retained artifact.
- Treating simulation, emulation, hosted, and physical execution as the same evidence class.
- Asserting hardware, deployment, legal, financial, or certification proof that was not produced.
- Using `null` or placeholder strings in `claim_boundary` where booleans are required.
