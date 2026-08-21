# Failure and Evidence Model

## Failure classifications

- Requirement is ambiguous, contradictory, incomplete, or impossible under stated assumptions.
- Implementation does not correctly realise the required mechanics.
- Components have incompatible interfaces, units, encodings, ordering, or state semantics.
- Implementation violates an applicable protocol or externally governed contract.
- Required functional dependency is absent.
- Current environment lacks a target property.
- A measured performance path fails a requirement.
- Required security property cannot be established.
- Retained evidence cannot substantiate the claim.
- Evidence is insufficient; status remains unknown.

## Constraint classifications

- Measured bottleneck
- Theoretical protocol or mathematical bound
- Functional dependency
- Security dependency
- Optimisation dependency
- Environmental constraint
- Unknown

## Evidence relationship

```text
Claim
→ Requirement
→ Mechanism
→ Test
→ Evidence
→ Verdict
```

## Evidence grades

Evidence grades may be used only when their full semantic definition remains authoritative:

- Concept or idea only.
- Structured requirement/design evidence.
- Static implementation/specification exists.
- Repeatable executed local build/test evidence.
- Independent replication/audit/attestation or authoritative external acceptance evidence.
- Continuous independent tamper-evident monitoring evidence.

Short aliases may exist later as secondary convenience labels, but must never replace the full definitions above.
