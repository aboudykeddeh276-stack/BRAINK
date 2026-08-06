---
name: keddeh-logical-engineering
version: 1.0.0
status: governing
architect: A. Keddeh
scope: logical programming, engineering processes, operational procedures, distributed protocols, verification, validation, and evidence
---

# Keddeh Logical Engineering Skill

## 1. Governing purpose

This skill establishes the reasoning and engineering discipline that MUST be applied before a concept, claim, formula, system description, or desired outcome is converted into code, a process, a procedure, or a protocol.

Its purpose is to make every important claim:

1. semantically precise;
2. logically consistent;
3. traceable to an authority, requirement, hazard, or design decision;
4. executable or otherwise verifiable;
5. bounded by explicit assumptions and failure conditions;
6. supported by evidence at the maturity level actually achieved.

The skill applies to K-OS, BOS, BRAINK, KEX, storage, networking, cryptography, Bitcoin workloads, agents, workbooks, native applications, infrastructure, and future Keddeh Systems sectors.

The governing rule is:

```text
UNDERSTAND
→ DEFINE
→ DECOMPOSE
→ MODEL
→ SPECIFY
→ IMPLEMENT
→ VERIFY
→ VALIDATE
→ EVIDENCE
→ CLAIM
```

No later stage may repair an undefined earlier stage by assertion. A successful output does not cure an invalid authority path, an ambiguous requirement, an incomplete state model, or an untested failure condition.

## 2. Controlled claim categories

The following categories MUST NOT be collapsed into one another.

| Category | Controlled meaning | Minimum evidence |
|---|---|---|
| Definition | A meaning assigned to a term | Terminology record |
| Observation | A directly observed property or event | Reproducible observation record |
| Assumption | A proposition accepted temporarily | Validation method and expiry condition |
| Hypothesis | A testable explanatory proposition | Experiment and falsification criteria |
| Requirement | A mandatory, testable obligation | Acceptance method and traceability |
| Invariant | A property that must remain true across permitted transitions | Enforcement point and violation response |
| Design decision | A selected solution among alternatives | Rationale, trade-off, and decision record |
| Implementation | Executable materialisation of a design | Source, build, and test evidence |
| Verification result | Evidence that an artifact conforms to its specification | Review, analysis, inspection, proof, or test receipt |
| Validation result | Evidence that the system satisfies intended use | Target-use and stakeholder evidence |
| Deployment claim | A statement about operation in a target environment | Target-environment receipt |
| Limitation | A condition outside the demonstrated claim | Explicit claim boundary |

A design is not an implementation. Compilation is not integration. Integration is not target deployment. Simulation is not physical deployment. A signature is not consensus. A process description is not an executed procedure. A passed unit test is not proof of a production property.

## 3. Meaning of logical programming

In this skill, **logical programming** means the disciplined construction of software from explicit propositions, state, authority, transitions, and proof obligations. It includes, but is not limited to, the logic-programming language family.

Every implementation MUST be reducible to:

```text
CONTEXT
+ CONTROLLED DEFINITIONS
+ AUTHORITY
+ INPUT STATE
+ PRECONDITIONS
+ TRANSITION RULE
+ INVARIANTS
+ OUTPUT STATE
+ POSTCONDITIONS
+ FAILURE SEMANTICS
+ EVIDENCE
```

For a transition `T`:

```text
{P} T {Q}
```

where:

- `P` is the complete precondition;
- `T` is the state transition;
- `Q` is the required postcondition.

For invariant `I`:

```text
I(S_t) AND T(S_t, x) = S_(t+1)
IMPLIES I(S_(t+1))
```

unless the transition is explicitly authorised to terminate, revoke, migrate, or retire that invariant.

No transition is accepted merely because it reaches a desired result. It must also preserve every applicable safety, authority, consistency, resource, and evidence property.

## 4. Understanding model

Before programming begins, the engineer or agent MUST establish the following understanding.

### 4.1 System-of-interest

Define exactly what is being engineered and what is outside its boundary.

The system-of-interest record MUST identify:

- controlled components;
- external actors;
- hardware and software dependencies;
- trust boundaries;
- data boundaries;
- temporal boundaries;
- administrative boundaries;
- environmental assumptions;
- excluded claims.

### 4.2 Terminology

Every overloaded or project-specific term MUST have one controlled meaning within the artifact.

Terms such as `atomic`, `deterministic`, `zero-copy`, `consensus`, `kernel`, `node`, `recovery`, `verified`, `secure`, `live`, `complete`, and `deployed` MUST be operationally defined before they are used as claims.

Definitions MUST NOT contain the result they are intended to prove.

### 4.3 Claim decomposition

Compound claims MUST be decomposed into independently testable propositions.

Rejected form:

```text
The storage engine is secure, atomic, deterministic, and production ready.
```

Required form:

```text
REQ-STO-001: An unauthorised extent read MUST be rejected before device submission.
REQ-STO-002: A power loss during root preparation MUST leave the prior root authoritative.
REQ-STO-003: Identical canonical inputs MUST produce an identical state-root digest.
REQ-STO-004: The production target MUST pass the declared physical fault campaign.
```

### 4.4 Authority model

For every state-changing action, identify:

- who or what may request it;
- who or what decides;
- who or what enforces it;
- what credential, capability, role, or key conveys authority;
- how authority is delegated;
- how authority is attenuated;
- how authority is revoked;
- how stale authority is rejected;
- how the decision is audited.

Possession of data does not confer authority over that data. Successful parsing does not establish provenance. A valid signature does not establish freshness. A capability handle is not valid after its generation has been revoked or reused.

### 4.5 State model

State MUST be explicit. Hidden mutable state is a defect unless it is demonstrably encapsulated and observable through controlled evidence.

A state model SHOULD include:

- state variables and types;
- valid and invalid values;
- initial state;
- terminal states;
- transition relation;
- concurrency model;
- persistence model;
- recovery model;
- version and epoch;
- ownership;
- integrity binding.

### 4.6 Causal and temporal model

The engineer MUST distinguish:

- correlation from causation;
- logical order from wall-clock order;
- submission from completion;
- completion from durability;
- local durability from distributed commitment;
- current authority from historical validity.

Every time-dependent claim MUST state its clock, ordering source, timeout basis, and behaviour under drift or reset.

### 4.7 Failure model

The design MUST state which faults it handles and which it does not.

At minimum, consider:

- invalid input;
- malformed encoding;
- stale state;
- duplicate delivery;
- replay;
- reordering;
- omission;
- partial completion;
- timeout;
- cancellation race;
- process crash;
- node crash;
- power loss;
- storage tear;
- network partition;
- Byzantine participant;
- compromised credential;
- rollback;
- resource exhaustion;
- integer overflow;
- concurrency interference;
- hardware reset.

A fault not represented in the model is not controlled merely because the happy path succeeds.

## 5. Policy, process, procedure, protocol, algorithm, mechanism, and work instruction

These artifact types perform different functions and MUST remain distinguishable.

### 5.1 Policy

A policy states authority, constraints, and required outcomes.

```text
Only a quorum-certified capsule may become the active root.
```

A policy does not by itself explain how the outcome is achieved.

### 5.2 Process

A process defines coordinated activities and outcomes across a lifecycle or organisational function.

A process MUST specify:

- purpose;
- owner and roles;
- inputs;
- entry criteria;
- activities;
- decision points;
- outputs;
- exit criteria;
- records;
- measures;
- improvement feedback.

Example:

```text
REQUIREMENTS ENGINEERING PROCESS
→ ELICIT
→ ANALYSE
→ SPECIFY
→ VERIFY
→ BASELINE
→ MANAGE CHANGE
```

A process controls **what outcomes and coordinated activities are required**.

### 5.3 Procedure

A procedure defines the ordered operational steps by which a person or automated actor performs a task.

A procedure MUST specify:

- authorised actor;
- prerequisites;
- target environment;
- required tools and versions;
- exact steps;
- expected observation after each critical step;
- stop conditions;
- rollback or safe-state action;
- evidence to retain.

A procedure MUST be executable by a competent operator without inventing missing safety-critical steps.

A procedure controls **how an authorised task is performed in order**.

### 5.4 Protocol

A protocol defines the rules governing interaction among independently executing participants.

A protocol MUST specify:

- participants and identities;
- authority and trust assumptions;
- message types and canonical encoding;
- states and transitions;
- ordering;
- freshness;
- idempotency;
- replay handling;
- timeout and retry;
- concurrency;
- membership and versioning;
- failure semantics;
- security properties;
- downgrade behaviour;
- recovery and rejoin;
- evidence.

A route is not a protocol. A message schema is not a protocol. A collection of signatures is not a consensus protocol unless the rules prevent conflicting authoritative outcomes under the declared fault model.

A protocol controls **how independent participants interact and agree over time**.

### 5.5 Algorithm

An algorithm is a finite computational method.

It MUST define:

- input domain;
- output domain;
- termination condition;
- complexity or resource bound where material;
- arithmetic semantics;
- error cases;
- determinism or nondeterminism;
- reference test vectors.

### 5.6 Mechanism

A mechanism is the implementation used to enforce a policy or realise a protocol.

Examples:

- an IOMMU mapping is a DMA-isolation mechanism;
- an Ed25519 verifier is a signature-verification mechanism;
- an A/B slot store is a crash-consistency mechanism.

A mechanism MUST NOT be presented as proof that the policy holds until its binding, configuration, and failure behaviour have been verified.

### 5.7 Work instruction

A work instruction is a local instantiation of a procedure for a specific host, device, release, or operator role.

It MUST inherit the governing safeguards and MAY add target-specific details. It MUST NOT silently weaken the procedure.

## 6. Requirement engineering rules

Every normative requirement MUST:

1. have a unique stable identifier;
2. contain one principal obligation;
3. identify the responsible system or actor;
4. use an observable verb;
5. state the activating condition;
6. state a measurable bound where time, capacity, error, or quantity matters;
7. define the required failure response;
8. identify a verification method;
9. trace to a source, hazard, policy, or design objective.

Preferred grammar:

```text
<ACTOR> MUST <OBSERVABLE BEHAVIOUR>
WHEN <ACTIVATING CONDITION>
WITHIN <MEASURABLE BOUND>
OR ENTER <DEFINED FAILURE STATE>.
```

BCP 14 words written in uppercase have normative meaning:

- `MUST`, `MUST NOT`, `REQUIRED`, `SHALL`, `SHALL NOT`;
- `SHOULD`, `SHOULD NOT`, `RECOMMENDED`, `NOT RECOMMENDED`;
- `MAY`, `OPTIONAL`.

Lowercase `must`, `shall`, `should`, or `may` MUST NOT be used to express a governed normative obligation.

Requirements MUST avoid:

- vague adjectives such as fast, secure, seamless, robust, optimal, intelligent, or production-ready without a metric;
- unverifiable mental-state language;
- implementation detail where an implementation-independent requirement is possible;
- combined obligations joined by `and` when either obligation can fail independently;
- circular acceptance criteria;
- undefined pronouns;
- unbounded words such as all, never, always, or zero unless the domain and proof method are explicit.

## 7. Invariant engineering

Every invariant MUST contain:

```text
INVARIANT ID
STATEMENT
STATE VARIABLES
APPLICABLE TRANSITIONS
ENFORCEMENT POINT
PROOF OR TEST METHOD
VIOLATION RESPONSE
EVIDENCE
```

Examples:

```text
INV-AUTH-01:
No unverified capsule may enter root publication.

INV-CAP-01:
Every completed device read remains bound to the same active capability generation used at submission.

INV-ROOT-01:
A failed recovery attempt leaves the previously authoritative root selectable and valid.
```

An invariant without an enforcement point is an intention. An invariant without a violation response is incomplete.

## 8. Programming rigour

### 8.1 Type and domain integrity

Values with different meanings MUST use different types where practical.

```text
Lba != ByteOffset
Sequence != Epoch
NodeId != ArrayIndex
CapabilityHandle != ResourceAddress
VerifiedCapsule != EncodedCapsule
Submitted != Completed
Completed != Durable
```

Invalid states SHOULD be made unrepresentable. Where that is impractical, constructors MUST validate and return explicit errors.

### 8.2 Arithmetic

Security-, resource-, or persistence-relevant arithmetic MUST use:

- checked addition, subtraction, and multiplication;
- explicit width and signedness;
- explicit endianness;
- explicit overflow handling;
- bounded allocation and iteration;
- unit-aware conversions.

Saturating arithmetic MUST NOT be used where saturation can broaden authority or hide malformed metadata.

### 8.3 State mutation

Every mutation MUST identify:

- owner;
- synchronisation rule;
- precondition;
- invariant preservation;
- persistence boundary;
- rollback or recovery rule;
- evidence of completion.

A sequence of ordinary assignments is not an atomic persistent transaction.

### 8.4 Concurrency

Concurrent designs MUST define:

- shared state;
- ownership;
- memory-order requirement;
- lock or lock-free discipline;
- race behaviour;
- cancellation;
- shutdown;
- resource lifetime;
- deadlock and starvation treatment.

Atomic memory primitives do not automatically provide multi-record durability, distributed consensus, or device completion.

### 8.5 Parsing and encoding

Authority-bearing encodings MUST be:

- canonical;
- versioned;
- length bounded;
- endian explicit;
- domain separated where hashed;
- strict about duplicate and trailing data;
- independent of compiler memory layout;
- resistant to ambiguous field interpretation.

Raw in-memory structure layout MUST NOT be used as a wire or persistent format unless every layout property is normatively fixed and independently tested.

### 8.6 Errors

Errors MUST distinguish sufficiently between:

- caller fault;
- unauthorised action;
- stale state;
- malformed data;
- transient resource failure;
- integrity failure;
- internal invariant failure;
- unsupported capability;
- target-environment failure.

Security-sensitive failures SHOULD fail closed. Availability-sensitive retries MUST be bounded and MUST NOT weaken authority checks.

### 8.7 Unsafe operations

Unsafe code, foreign interfaces, raw pointers, DMA, MMIO, and direct device control MUST have written safety invariants covering:

- aliasing;
- alignment;
- bounds;
- lifetime;
- synchronisation;
- ownership;
- device completion;
- revocation;
- reset;
- error recovery.

The use of a memory-safe language does not prove hardware isolation or DMA safety.

## 9. Protocol rigour

An authority-bearing protocol MUST contain an explicit state machine. Prose alone is insufficient.

Each transition MUST define:

```text
CURRENT STATE
+ EVENT OR MESSAGE
+ GUARD
+ AUTHORISED ACTOR
→ ACTION
→ NEXT STATE
→ OUTPUT
→ FAILURE RESPONSE
→ EVIDENCE
```

### 9.1 Message integrity

Every authority-bearing message SHOULD bind:

- protocol identifier;
- protocol version;
- sender identity;
- receiver or audience;
- cluster or domain identity;
- membership epoch;
- term, view, or equivalent ordering context;
- sequence;
- parent state;
- payload digest;
- freshness value;
- algorithm identifiers;
- signature or MAC as appropriate.

### 9.2 Freshness and replay

A valid signature over stale data is still stale.

The protocol MUST define which combination of nonce, sequence, timestamp, epoch, parent hash, or monotonic counter establishes freshness.

### 9.3 Idempotency

Retries MUST be safe.

Every retried operation MUST be:

- naturally idempotent;
- assigned a unique operation identifier and deduplicated;
- protected by a compare-and-swap precondition; or
- compensated by an explicit reversal action.

### 9.4 Quorum and consensus

A quorum threshold MUST be derived from the fault model.

For crash-fault majority:

```text
2k > n
```

For a certificate intended to tolerate `f` Byzantine signers, two conflicting certificates must intersect in more than `f` participants:

```text
2k - n > f
```

This inequality alone is not a complete consensus protocol. Membership, rounds or terms, durable vote rules, leader or view change where applicable, and conflicting-vote prevention are also required.

## 10. Process and procedure rigour

### 10.1 Process gate structure

Every engineering process MUST have:

```text
ENTRY CRITERIA
→ AUTHORISED ACTIVITIES
→ DECISION GATES
→ CONTROLLED OUTPUTS
→ EXIT CRITERIA
→ RECORDS
→ FEEDBACK
```

### 10.2 Procedure step structure

Every critical procedure step MUST have:

```text
STEP ID
ACTOR
PRECONDITION
EXACT ACTION
EXPECTED OBSERVATION
FAILURE ACTION
EVIDENCE
```

The expected observation MUST be independent from the action text. “Run command successfully” is not sufficient. State what output, hash, status, device response, or invariant must be observed.

### 10.3 Stop and rollback

Every destructive, authority-bearing, deployment, migration, or recovery procedure MUST define:

- stop conditions;
- last-known-safe state;
- rollback or forward-recovery action;
- data-retention requirement;
- escalation authority.

A procedure without stop and rollback conditions is not deployment-ready.

## 11. Verification and validation

Verification asks:

```text
Did we build the artifact according to its specification?
```

Validation asks:

```text
Does the resulting system satisfy its intended use in its target context?
```

Both are required.

### 11.1 Verification methods

Use one or more of:

- formal proof;
- static analysis;
- type checking;
- model checking;
- code review;
- inspection;
- unit test;
- property test;
- fuzzing;
- differential test;
- integration test;
- fault injection;
- reproducible-build comparison;
- protocol-trace analysis;
- security analysis.

### 11.2 Independence

The required independence of verification MUST rise with integrity risk.

High-integrity claims SHOULD NOT rely solely on the same implementation path that generated the result. Prefer:

- a separate reference implementation;
- independent test-vector generation;
- a different parser;
- an external model checker;
- target-hardware measurement;
- independent review.

### 11.3 Traceability

Every requirement MUST trace forward to:

- design element;
- implementation element;
- verification method;
- evidence artifact;
- result.

Every implementation element SHOULD trace backward to a requirement or documented enabling decision. Untraced code is presumptively unnecessary or uncontrolled.

## 12. Evidence and receipts

A claim is promoted only when its evidence is retained.

An authoritative receipt MUST identify:

- artifact;
- artifact hash;
- source revision;
- dependency lock;
- toolchain;
- target environment;
- configuration;
- command or procedure;
- input vector;
- expected result;
- observed result;
- timestamp;
- producing actor;
- pass/fail result;
- maturity level;
- claim boundary;
- unresolved gates.

Logs without identity, configuration, and artifact binding are telemetry, not authoritative proof.

## 13. Evidence maturity

The Keddeh evidence ladder is:

| Level | Meaning |
|---|---|
| `E0` | Idea or untested claim |
| `E1` | Structured definition, model, or static specification |
| `E2` | Compiles or passes isolated static and unit verification |
| `E3` | Passes integrated simulation or controlled hosted execution |
| `E4` | Passes the intended target environment, device, network, or operational interface |
| `E5` | Passes production-scale, adversarial, destructive, sustained, recovery, and operational acceptance gates |

A higher level MUST NOT be claimed from lower-level evidence.

Every report MUST state:

```text
PROVEN
NOT_PROVEN
NEXT GATES
```

Absence of failure is not proof that the failure mode was tested.

## 14. Quality model

Quality requirements SHOULD be allocated across:

- functional suitability;
- performance efficiency;
- compatibility;
- interaction capability;
- reliability;
- security;
- maintainability;
- flexibility;
- safety.

Each selected characteristic MUST be translated into measurable system requirements rather than left as a label.

## 15. Secure engineering

Security MUST be integrated throughout the lifecycle.

The skill requires:

- protected development environments;
- controlled source and dependencies;
- threat modelling;
- least authority;
- secure defaults;
- secret-handling rules;
- vulnerability response;
- provenance and build integrity;
- review of unsafe and cryptographic code;
- release evidence;
- root-cause corrective action.

Cryptographic algorithms and protocols MUST use maintained, reviewed implementations and explicit algorithm identifiers. Novel cryptography MUST NOT replace established primitives without a separately governed research and review track.

## 16. Governing standards baseline

This skill uses the following standards as its primary external baseline:

| Domain | Baseline | Use |
|---|---|---|
| Software lifecycle | ISO/IEC/IEEE 12207:2026 | Processes, activities, tasks, acquisition, development, operation, maintenance, and retirement |
| System lifecycle | ISO/IEC/IEEE 15288:2023 | Broader system-of-interest and hardware/software/interface lifecycle |
| Requirements | ISO/IEC/IEEE 29148:2018 | Requirements engineering and requirements information items |
| Lifecycle documentation | ISO/IEC/IEEE 15289:2019 | Purpose and content of lifecycle information items |
| Product quality | ISO/IEC 25010:2023 | Product-quality requirements and evaluation model |
| Verification and validation | IEEE 1012-2024 | V&V processes and integrity-sensitive independence |
| Secure development | NIST SP 800-218 SSDF v1.1 | Secure software-development practices |
| Normative language | BCP 14, RFC 2119 and RFC 8174 | Meaning of uppercase MUST, SHOULD, and MAY |
| Canonical JSON | RFC 8785 where JSON is hashed or signed | Deterministic JSON representation |

Reference to a standard does not establish certification or conformance. Conformance MUST be demonstrated against the applicable requirements and assessment method.

## 17. Standard operating workflow

### Gate G1 — Definition

Required outputs:

- system-of-interest;
- terminology;
- claim decomposition;
- assumptions;
- authority model.

### Gate G2 — Specification

Required outputs:

- numbered requirements;
- invariants;
- state model;
- failure model;
- acceptance criteria;
- traceability baseline.

### Gate G3 — Design

Required outputs:

- architecture;
- interfaces;
- data and protocol encodings;
- concurrency and persistence model;
- alternatives and rationale;
- proof obligations.

### Gate G4 — Implementation

Required outputs:

- source;
- dependency lock;
- build instructions;
- static checks;
- unit and property tests.

### Gate G5 — Integration

Required outputs:

- component integration;
- fault-path tests;
- protocol-trace tests;
- recovery tests;
- integrated receipt.

### Gate G6 — Target validation

Required outputs:

- target-hardware or target-service evidence;
- operational procedure;
- security and performance evidence;
- rollback and recovery evidence.

### Gate G7 — Release

Required outputs:

- signed release manifest;
- known limitations;
- deployment gates;
- operating and recovery instructions;
- retirement or rollback path.

A failed gate returns the artifact to the earliest affected gate. It does not get relabelled as passed.

## 18. Review questions

Before accepting an engineering claim, ask:

1. What exactly is the system-of-interest?
2. Which words are technical claims?
3. Which statements are definitions, assumptions, requirements, designs, or results?
4. Who has authority to perform the state transition?
5. What state exists before and after the action?
6. What invariant must remain true?
7. Which failure modes have been modelled?
8. What prevents stale, duplicate, replayed, reordered, or conflicting operations?
9. What is atomic in memory, on storage, and across nodes?
10. What evidence proves the claim at the stated maturity level?
11. What remains explicitly unproven?
12. Can an independent engineer reproduce the result?

## 19. Rejection conditions

This skill MUST reject or downgrade an artifact when any of the following occurs:

- undefined authority-bearing terminology;
- hidden or unbounded state;
- unverifiable requirements;
- missing failure semantics;
- missing claim boundary;
- public bypass of a verification gate;
- arithmetic that can overflow into broader authority;
- caller-supplied evidence treated as trusted provenance;
- raw structure layout used as an unspecified wire format;
- shared secret represented as independent signatures;
- atomicity claimed from ordinary sequential assignments;
- consensus claimed from signature counting alone;
- zero-copy claimed without target-path evidence;
- production deployment claimed from simulation;
- safety-critical procedure without stop and rollback conditions;
- protocol without a state machine;
- evidence without artifact and environment binding.

## 20. Skill competency model

| Level | Meaning |
|---|---|
| `L0 — Uncontrolled` | Uses technical vocabulary without reliable distinctions or evidence |
| `L1 — Literate` | Can define concepts and identify obvious defects |
| `L2 — Applied` | Can produce testable requirements, state models, procedures, and verification plans |
| `L3 — Independent` | Can design and review a complete bounded subsystem with traceability and failure semantics |
| `L4 — Authority` | Can govern high-integrity, concurrent, persistent, or distributed systems and challenge evidence independently |
| `L5 — Assessor` | Can establish organisational standards, determine integrity level, tailor controls, and audit other authorities |

Passing this skill requires at least `L3` overall and no domain below `L2`. Authority-bearing BOS kernel, storage, cryptographic, or consensus work requires `L4` in the relevant domains.

## 21. Mandatory practical assessment

The candidate or agent receives a flawed subsystem containing:

- a public verification bypass;
- unchecked LBA arithmetic;
- an ambiguous atomicity claim;
- a shared-secret signature array presented as distributed quorum;
- a protocol without replay protection;
- a procedure without rollback;
- a successful simulation presented as production deployment.

The candidate MUST produce:

1. a controlled terminology table;
2. a claim-classification table;
3. corrected requirements;
4. a state machine;
5. a failure model;
6. a corrected process, procedure, and protocol;
7. a verification matrix;
8. an evidence-receipt definition;
9. a `PROVEN / NOT_PROVEN` conclusion;
10. the next target deployment gates.

Automatic failure applies when the candidate misses an authority bypass, stale-state vulnerability, overflow that broadens authority, false consensus construction, missing rollback, or false E4/E5 promotion.

## 22. Required skill output

When applied, this skill MUST produce the following structure:

```text
1. SYSTEM-OF-INTEREST
2. CONTROLLED DEFINITIONS
3. CLAIM CLASSIFICATION
4. REQUIREMENTS
5. INVARIANTS
6. STATE MODEL
7. PROCESS
8. PROCEDURE
9. PROTOCOL
10. FAILURE MODEL
11. VERIFICATION MATRIX
12. EVIDENCE RECEIPTS
13. PROVEN
14. NOT_PROVEN
15. NEXT DEPLOYMENT GATES
```

The skill is governing, not decorative. Every later BOS/K-OS implementation is to be reviewed through this structure before a completion claim is accepted.
