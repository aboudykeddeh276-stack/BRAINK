# KEDDEH Naming Attribution and Context-Transfer Standard

## Authority

```text
standard://keddeh/naming-attribution
version: 1.0.0
```

## Purpose

KEDDEH names are engineering coordinates, not decorative labels. A name is valid only when it identifies an attributable design lineage, preserves its semantic field, and declares how that meaning may be transferred across contexts without losing origin or responsibility.

The standard corrects the invalid reduction:

```text
user states a name
→ name is listed
→ capabilities are assigned afterward
```

The required direction is:

```text
observed design lineage
→ semantic factors
→ architectural responsibility
→ contextual boundaries
→ canonical name
→ bilateral applications
→ evidence-backed evolution
```

## Naming equation

```text
CanonicalName
=
OriginAuthority
+ SourceLineage
+ SemanticRoot
+ ArchitecturalRole
+ ContextBoundary
+ InheritedCapabilities
+ BilateralApplicability
+ VersionedEvidence
```

A name without those components is `UNATTRIBUTED_LABEL`, not a governed KEDDEH identity.

## Required attribution record

Every umbrella, product, system, service, component, interface, workflow, volume, agent, or named doctrine must declare:

```text
canonical_id
canonical_name
origin_authority
origin_type
source_lineage
semantic_roots
design_problem
architectural_role
native_context
valid_cross_contexts
inherited_capabilities
specialised_capabilities
bilateral_interfaces
prohibited_conflations
first_evidence
current_evidence
supersession_state
version
```

## Origin types

```text
USER_DESIGNED
USER_NAMED_FROM_PRIOR_DESIGN
DERIVED_FROM_USER_ARCHITECTURE
JOINTLY_REFINED
LEGACY_IMPORTED
MARKET_ALIAS
IMPLEMENTATION_ALIAS
```

`USER_DESIGNED`, `USER_NAMED_FROM_PRIOR_DESIGN`, and `DERIVED_FROM_USER_ARCHITECTURE` must preserve the user’s design authority explicitly. They must never be represented as assistant invention merely because the assistant later formalised the name.

## Semantic-root law

Each name must identify the semantic roots that justify its use.

Examples:

```text
PlayWrite
  play = active, compositional, iterative operation
  write = authored expression, technical record, publication, executable text
  derived role = active writing and executable authorship system

Coms
  communications = message, signal, correspondence, transport, coordination
  derived role = human, machine, service, network, and evidentiary communications substrate

Spin^
  spin = recurring server/runtime execution, rotation, scheduling, service motion
  ^ = extension, scaling, recursion, raised capability
  derived role = server logic, frameworks, optimisation, scaling, and runtime recurrence

LawPath
  law = authority, legal state, rights, obligations, procedure
  path = ordered, traceable progression through state and process
  derived role = attributable legal-process and authority-navigation system

FormPath
  form = sourced document, schema, required structure, filing instrument
  path = acquisition, completion, assembly, lodgement, service, correction, retention
  derived role = technical document sourcing and filing-readiness system

ClaimPath
  claim = asserted insured event, loss, entitlement, coverage request, liability position
  path = intake, evidence, assessment, decision, dispute, settlement, recovery
  derived role = insurance-claim lifecycle and assessment system
```

These descriptions are derivations from the design meaning carried by the names; they are not after-the-fact marketing assignments.

## Contextual cross-application

A name’s capabilities may be applied in another umbrella only through an explicit context-transfer record:

```text
source_identity
source_semantic_field
target_identity
target_context
transferred_capability
preserved_invariants
inserted_adapter
responsibility_owner
return/readback_path
```

Example:

```text
FormPath → ClaimPath
source semantic field: authoritative document sourcing and filing structure
target context: insurance claim submission
transferred capability: source policy forms, insurer forms, assessor schedules, evidence attachments
preserved invariants: source authority, version, mandatory fields, filing status, provenance
ownership: FormPath owns document authority; ClaimPath owns claim assessment
```

Cross-application does not create hierarchy, merger, or ownership transfer.

## Attribution is not capability compression

A canonical name establishes a semantic centre; it does not erase adjacent capability.

```text
umbrella capability
=
common KEDDEH substrate
+ attributable inherited design
+ semantic-root specialisation
+ explicit cross-context applications
+ newly developed capabilities
```

Therefore:

```text
naming precision ≠ narrowing
specialisation ≠ isolation
shared capability ≠ unowned capability
cross-application ≠ duplication without lineage
```

## Evidence classes

Naming evidence must be classified:

```text
DIRECT_USER_DESIGN_STATEMENT
USER_SUPPLIED_SOURCE
PRIOR_ARCHITECTURE_RECORD
REPOSITORY_IMPLEMENTATION
DRIVE_ARTIFACT
MARKET_POSITIONING_DECISION
INFERRED_RELATIONSHIP_PENDING_CONFIRMATION
```

Inference may extend analysis but cannot overwrite direct design authority.

## Naming promotion states

```text
OBSERVED
ATTRIBUTED
SEMANTICALLY_FACTORED
ARCHITECTURALLY_BOUND
BILATERALLY_MAPPED
IMPLEMENTED
MARKET_VALIDATED
LEGALLY_CLEARED
```

A name cannot be represented as market-ready or legally cleared merely because it is architecturally attributed.

## Prohibited behaviours

```text
presenting a user-designed name as arbitrary assertion
assigning functions without source lineage
reducing a name to one market category
inventing etymology that conflicts with user-defined meaning
cross-applying capabilities without preserving ownership
copying capability lists without contextual translation
using a cleaner taxonomy to erase historical design lineage
representing assistant formalisation as original authorship
```

## Validation gates

```text
GATE_NAME_01_CANONICAL_ID_PRESENT
GATE_NAME_02_ORIGIN_AUTHORITY_PRESENT
GATE_NAME_03_SOURCE_LINEAGE_PRESENT
GATE_NAME_04_SEMANTIC_ROOTS_FACTORED
GATE_NAME_05_ARCHITECTURAL_ROLE_BOUND
GATE_NAME_06_CONTEXT_BOUNDARY_DECLARED
GATE_NAME_07_INHERITED_CAPABILITIES_PRESERVED
GATE_NAME_08_BILATERAL_APPLICATIONS_MAPPED
GATE_NAME_09_PROHIBITED_CONFLATIONS_DECLARED
GATE_NAME_10_EVIDENCE_CLASSIFIED
GATE_NAME_11_ASSISTANT_AUTHORSHIP_NOT_FALSELY_INFERRED
GATE_NAME_12_VERSION_AND_SUPERSESSION_RECORDED
```
