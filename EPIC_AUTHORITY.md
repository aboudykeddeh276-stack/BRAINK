# EPIC Authority Contract

## Sector class
Evidence mapping, invariant evaluation, provenance and claim qualification.

## Owns
- evidence-to-claim mapping;
- property-scoped invariant evaluation;
- provenance relations;
- claim qualification status;
- distinction between originator, router, executor, validator and lineage relations.

## Does not own
- runtime execution;
- node or child execution;
- executor selection;
- authority assignment;
- runtime state mutation;
- deployment activation;
- service restart/failover;
- state promotion outside EPIC claim qualification.

## Core rule
Lineage is not execution. Routing is not execution. Provisioning is not execution. Validation is not execution. A parent may create, teach, configure, route, supervise or validate a child without performing the child's operation.

Execution attribution requires evidence that names the actual executor for the property being claimed.

## Relationship rule
Parent, child, twin, sibling, variant and descendant relations describe provenance or topology only. They do not impose permanent authority ordering. EPIC records such relations but does not synthesize an authority hierarchy from age, ancestry or creation order.

## Claim gate
A claim may be QUALIFIED only when its required property evidence exists, is observed where observation is required, has the required receipt where a receipt is required, and any asserted executor matches the executor named by the evidence.

Otherwise the result is PARTIAL, REJECTED or UNOBSERVED. EPIC must not mutate another system to make a claim become true.
