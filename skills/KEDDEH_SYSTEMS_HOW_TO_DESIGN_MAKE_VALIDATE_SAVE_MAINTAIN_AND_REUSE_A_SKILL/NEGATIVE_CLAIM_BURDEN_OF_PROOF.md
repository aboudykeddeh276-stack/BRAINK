# Negative-Claim Doctrine — Negative Capability Claims Carry the Burden of Proof

This directive formalises an inversion in how capability claims are asserted.
The core mechanics of the skill-making lifecycle are unchanged; this document
sharpens the discipline that governs when a *negative* capability claim may be
emitted.

## Governing correction

Historically, a positive claim ("achieved", "available", "works") carried the
burden of proof while a negative claim ("not achieved", "unavailable",
"impossible locally") could be emitted cheaply. That asymmetry is inverted:

> A negative capability claim carries the burden of proof. The statements
> "not achieved", "unavailable", "unmanageable", or "impossible locally" — and
> any semantic equivalent — must not be emitted until all materially plausible
> local routes have been enumerated, tested, or explicitly ruled out with
> evidence.

Both positive and negative claims now require evidence. Absence of a positive
result is not, by itself, evidence of a negative result.

## Scope of governed statements

This doctrine governs any statement that asserts incapability, unavailability,
impossibility, or intractability, including but not limited to:

```text
not achieved
not achievable
unavailable
unmanageable
impossible locally
cannot be done
no route exists
blocked with no alternative
```

It does **not** govern explicit scope boundaries that are declared as *not
claimed* rather than asserted as *incapable*. A `claim_boundary` value of
`false` that means "this is outside the claimed scope" (for example,
`independent_external_attestation: false`) is a boundary, not a negative
capability claim, and does not by itself require route exhaustion. When a
`false` value instead asserts that a capability was attempted and could not be
achieved locally, this doctrine applies in full.

## Required evidence before a negative claim

Before any governed negative statement is emitted, the following must exist and
be retained:

```text
1. ROUTE ENUMERATION
   The set of materially plausible local routes to the capability, listed
   explicitly. "Materially plausible" excludes only routes that are themselves
   ruled out by a stated, evidenced constraint.

2. PER-ROUTE DISPOSITION
   For each enumerated route, one of:
     TESTED_AND_FAILED    — executed; failure evidence retained
     RULED_OUT_WITH_EVIDENCE — excluded by a stated, evidenced constraint
     (No route may be left in an untested, unexplained state.)

3. CONSTRAINT CLASSIFICATION
   Each ruled-out route cites a constraint class from
   FAILURE_AND_EVIDENCE_MODEL.md (for example a functional dependency,
   environmental, or theoretical bound).

4. RESIDUAL STATEMENT
   The negative claim is scoped precisely to what the evidence supports —
   "impossible under constraint X in environment Y", not an unbounded
   "impossible".
```

If any materially plausible route remains untested and unexplained, the correct
status is not "impossible" but:

```text
EVIDENCE_IS_INSUFFICIENT_STATUS_UNKNOWN
```

## Decision gate

```text
Emitting a negative capability claim?
├── No  → proceed
└── Yes → Have all materially plausible local routes been enumerated?
          ├── No  → enumerate them first; do not emit the claim
          └── Yes → Is every route TESTED_AND_FAILED or RULED_OUT_WITH_EVIDENCE?
                    ├── No  → status is UNKNOWN, not impossible; do not emit
                    └── Yes → emit the negative claim, scoped to the evidence,
                              with the route ledger retained
```

## Relationship to the evidence chain

The negative claim is subject to the same evidence chain as any other claim
(`FAILURE_AND_EVIDENCE_MODEL.md`):

```text
Claim (negative)
→ Requirement (what capability was sought)
→ Mechanism (why each route would or would not deliver it)
→ Test (how each route was exercised or ruled out)
→ Evidence (retained route ledger and per-route disposition)
→ Verdict (negative claim scoped to the evidence, or UNKNOWN)
```

A negative claim without a resolved route ledger is not FAIL — it is UNKNOWN.

## Governing rules

```text
A NEGATIVE CAPABILITY CLAIM CARRIES THE BURDEN OF PROOF.
```

```text
ABSENCE OF A POSITIVE RESULT IS NOT EVIDENCE OF IMPOSSIBILITY.
```

```text
NO ROUTE IS "RULED OUT" WITHOUT A STATED, EVIDENCED CONSTRAINT.
```

```text
UNTIL ROUTES ARE EXHAUSTED, THE STATUS IS UNKNOWN — NOT IMPOSSIBLE.
```
