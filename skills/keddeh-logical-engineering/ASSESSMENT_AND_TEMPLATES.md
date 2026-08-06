# Keddeh Logical Engineering — Assessment and Templates

## 1. Operational competency model

A skill definition is not an operational skill until a practitioner or agent can apply it consistently and produce independently reviewable evidence.

The assessment covers six domains:

1. semantic and logical analysis;
2. requirements and invariants;
3. programming and state integrity;
4. process and procedure design;
5. protocol and distributed-state design;
6. verification, validation, and claim discipline.

## 2. Competency levels

| Level | Meaning |
|---|---|
| `L0 — Uncontrolled` | Uses technical vocabulary without reliable distinctions or evidence |
| `L1 — Literate` | Can define concepts and identify obvious defects |
| `L2 — Applied` | Can produce testable requirements, state models, procedures, and verification plans |
| `L3 — Independent` | Can design and review a complete bounded subsystem with traceability and failure semantics |
| `L4 — Authority` | Can govern high-integrity, concurrent, persistent, or distributed systems and independently challenge evidence |
| `L5 — Assessor` | Can establish organisational standards, determine integrity level, tailor controls, and audit other authorities |

Passing the skill requires at least `L3` overall and no domain below `L2`. Authority-bearing BOS kernel, storage, cryptographic, or consensus work requires `L4` in the relevant domains.

## 3. Domain assessment

### D1 — Semantic and logical analysis

The candidate MUST be able to:

- separate definitions, assumptions, requirements, designs, results, and limitations;
- identify circular definitions and hidden assumptions;
- define the system-of-interest and trust boundary;
- decompose compound claims;
- write preconditions, postconditions, and invariants;
- identify invalid inference from implementation mechanism to system property.

Automatic failures include treating a hash as authority, parsing as provenance, compilation as deployment, or an atomic variable as a durable transaction.

### D2 — Requirements and invariants

The candidate MUST be able to:

- write atomic, measurable, uniquely identified requirements;
- use BCP 14 normative terms correctly;
- assign verification methods;
- maintain bidirectional traceability;
- specify invariant enforcement and violation response;
- detect ambiguous, unbounded, or unfalsifiable requirements.

### D3 — Programming and state integrity

The candidate MUST be able to:

- distinguish values with different semantic types;
- define checked arithmetic and encoding rules;
- model ownership and resource lifetime;
- explain concurrency and memory ordering;
- distinguish memory atomicity, storage durability, and distributed commitment;
- specify parser strictness, bounds, error types, and unsafe-code invariants;
- design fail-closed authority checks without uncontrolled retry loops.

### D4 — Process and procedure design

The candidate MUST be able to:

- distinguish policy, process, procedure, protocol, algorithm, mechanism, and work instruction;
- define process entry and exit criteria and records;
- write an executable procedure with prerequisites, observations, stop conditions, rollback, and retained evidence;
- identify when a procedure improperly depends on operator invention;
- establish change control and improvement feedback.

### D5 — Protocol and distributed-state design

The candidate MUST be able to:

- specify participants, identities, messages, states, transitions, ordering, retries, freshness, and versioning;
- define idempotency and deduplication;
- derive quorum requirements from the stated fault model;
- distinguish authentication, attestation, quorum certificates, and consensus;
- prevent stale, replayed, duplicate, and conflicting authority;
- describe partition, recovery, rejoin, and membership-change behaviour.

### D6 — Verification, validation, and claims

The candidate MUST be able to:

- distinguish verification from validation;
- select static, dynamic, formal, integration, fault-injection, and target-environment evidence;
- assign independence according to integrity risk;
- create receipts bound to source, artifact, toolchain, configuration, target, and result;
- classify evidence from E0 through E5;
- state `PROVEN` and `NOT_PROVEN` without promotion by implication.

## 4. Mandatory practical assessment

The candidate receives a flawed subsystem containing:

- a public verification bypass;
- unchecked LBA arithmetic;
- an ambiguous atomicity claim;
- a shared-secret signature array presented as distributed quorum;
- a protocol without replay protection;
- a procedure without rollback;
- a successful simulation presented as production deployment.

The candidate MUST produce:

1. controlled terminology;
2. claim classification;
3. corrected requirements;
4. invariants;
5. a state machine;
6. a failure model;
7. a corrected process;
8. a corrected procedure;
9. a corrected protocol;
10. a verification matrix;
11. an evidence receipt;
12. `PROVEN / NOT_PROVEN / NEXT GATES`.

## 5. Scoring

Each domain is scored from 0 to 5.

| Score | Evidence |
|---|---|
| 0 | Missing or materially incorrect |
| 1 | Terminology recognition only |
| 2 | Correct isolated application |
| 3 | Correct integrated application with traceability |
| 4 | Handles adversarial, concurrent, persistent, and recovery conditions |
| 5 | Independently governs, tailors, audits, and improves the standard |

Default weights:

```text
D1 = 1
D2 = 2
D3 = 2
D4 = 1
D5 = 2
D6 = 2
```

Weighted score:

```text
S = SUM(weight[d] * score[d]) / SUM(weight[d])
```

Pass rules:

```text
S >= 3.0
AND every domain >= 2
AND D2, D3, D5, D6 >= 3 for authority-bearing systems
AND no critical rejection condition is missed
```

High-integrity authority qualification:

```text
S >= 4.0
AND D2, D3, D5, D6 >= 4
AND practical work survives independent review
AND target evidence supports the claimed maturity
```

## 6. Critical rejection conditions

Missing any of the following is an automatic failure:

- public bypass of an authority gate;
- stale-state or rollback vulnerability;
- unauthenticated input treated as hardware provenance;
- arithmetic overflow that can broaden resource authority;
- absence of protocol state or failure semantics;
- absence of procedure stop and rollback behaviour;
- false promotion from E2/E3 to E4/E5;
- claim of consensus from non-independent signatures;
- evidence not bound to the tested artifact.

## 7. Requirement template

```text
ID:
TITLE:
SOURCE:
CRITICALITY:

<ACTOR> MUST <OBSERVABLE BEHAVIOUR>
WHEN <ACTIVATING CONDITION>
WITHIN <MEASURABLE BOUND>
OR ENTER <DEFINED FAILURE STATE>.

RATIONALE:
INPUTS:
OUTPUTS:
PRECONDITIONS:
POSTCONDITIONS:
INVARIANTS:
VERIFICATION METHOD:
EVIDENCE ARTIFACT:
DEPENDENCIES:
CLAIM BOUNDARY:
```

## 8. Invariant template

```text
INVARIANT ID:
STATEMENT:
STATE VARIABLES:
APPLICABLE TRANSITIONS:
ENFORCEMENT POINT:
PROOF OR TEST METHOD:
VIOLATION RESPONSE:
EVIDENCE:
```

## 9. Process template

```text
PROCESS ID:
PURPOSE:
OWNER:
SCOPE:
APPLICABLE AUTHORITIES:

INPUTS:
ENTRY CRITERIA:
ROLES:

ACTIVITY:
  id:
  actor:
  action:
  output:
  decision:
  record:

EXIT CRITERIA:
OUTPUTS:
EXCEPTIONS:
MEASURES:
FEEDBACK / IMPROVEMENT:
RECORD RETENTION:
```

## 10. Procedure template

```text
PROCEDURE ID:
AUTHORISED ACTOR:
TARGET ENVIRONMENT:
TOOLS AND VERSIONS:
PREREQUISITES:
SAFETY / SECURITY WARNINGS:

STEP:
  id:
  precondition:
  exact action:
  expected observation:
  failure action:
  evidence:

STOP CONDITIONS:
ROLLBACK OR SAFE-STATE ACTION:
SUCCESS CRITERIA:
RETAINED RECEIPTS:
CLAIM BOUNDARY:
```

## 11. Protocol template

```text
PROTOCOL ID:
VERSION:
PURPOSE:
SYSTEM-OF-INTEREST:
FAULT MODEL:
SECURITY MODEL:

PARTICIPANTS:
IDENTITY AND AUTHORITY:
MEMBERSHIP:

CANONICAL MESSAGE ENCODING:
ALGORITHM IDENTIFIERS:

MESSAGE:
  id:
  sender:
  receiver:
  fields:
  authentication:
  freshness:
  maximum size:

STATES:
INITIAL STATE:
TERMINAL STATES:

TRANSITION:
  id:
  from:
  trigger:
  guard:
  authorised actor:
  action:
  output:
  to:
  failure:
  evidence:

ORDERING:
IDEMPOTENCY:
DUPLICATE HANDLING:
REPLAY HANDLING:
TIMEOUTS:
RETRIES:
CONCURRENCY:
PARTITION BEHAVIOUR:
REJOIN:
VERSION NEGOTIATION:
DOWNGRADE HANDLING:
REVOCATION:
RECOVERY:
SECURITY CONSIDERATIONS:
VERIFICATION VECTORS:
```

## 12. Decision record template

```text
DECISION ID:
STATUS:
DATE:
DECISION AUTHORITY:
CONTEXT:
PROBLEM:
OPTIONS:
SELECTED OPTION:
RATIONALE:
TRADE-OFFS:
RISKS:
CONSTRAINTS:
REVISIT TRIGGER:
RELATED REQUIREMENTS:
EVIDENCE:
```

## 13. Verification matrix template

| Requirement | Design | Implementation | Static evidence | Dynamic evidence | Fault evidence | Target evidence | Result |
|---|---|---|---|---|---|---|---|
| `REQ-...` | `DES-...` | file/symbol | report | test | campaign | receipt | PASS/FAIL |

## 14. Evidence receipt template

```json
{
  "receipt_version": "1.0",
  "artifact": "name",
  "artifact_hash": "sha256:...",
  "source_revision": "immutable revision",
  "toolchain": ["compiler version", "dependency lock hash"],
  "environment": {
    "platform": "target",
    "hardware": "device identity",
    "kernel_or_firmware": "version",
    "configuration_hash": "sha256:..."
  },
  "command_or_procedure": "identifier",
  "input_vector": "identifier or hash",
  "expected_result": "bounded expectation",
  "observed_result": "bounded observation",
  "timestamp": "RFC3339 timestamp",
  "producer": "identity",
  "result": "PASS",
  "maturity": "E3",
  "claim_boundary": {
    "proven": [],
    "not_proven": [],
    "deployment_gates": []
  }
}
```

## 15. Review report template

```text
SYSTEM-OF-INTEREST
CONTROLLED DEFINITIONS
CLAIM CLASSIFICATION
FINDINGS BY SEVERITY
CORRECTED REQUIREMENTS
INVARIANTS
STATE MODEL
PROCESS
PROCEDURE
PROTOCOL
FAILURE MODEL
VERIFICATION MATRIX
EVIDENCE REVIEW
PROVEN
NOT_PROVEN
NEXT GATES
FINAL ACCEPT / REJECT / CONDITIONAL DECISION
```

## 16. Continuing competence

Competence expires operationally when standards, target hardware, language toolchains, or threat models materially change.

Continuing competence requires:

- quarterly standards review;
- review of at least one failed or adversarial case;
- one independently reproduced evidence receipt;
- correction of discovered process defects;
- explicit update of claim boundaries.

A previously passed assessment does not authorise claims beyond the domain and maturity level demonstrated.
