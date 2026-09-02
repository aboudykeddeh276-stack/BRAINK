# BRAINK / KEX Engineering Documentation

This directory is the evidence, case-study and determination layer for the repository. Documentation should derive claims from source, runtime structure and receipts; it must not manufacture implementation state.

## Core documents

- `ILLLM_RECURSIVE_AUGMENTED_INTELLIGENCE_CASE_STUDY_R2.md` — recursive IL-LLM, observer/Mirror Lane and augmented-intelligence determination.
- `KEX_CAPABILITY_FABRIC_CASE_STUDY_R1.md` — capability fabric, runtime integration and proof boundaries.
- `KEX_SYSTEMS_ENGINEERING_PARADIGM_EXPLOITATION_R1.md` — external paradigms used as engineering donors and their claim limits.
- `ARCHITECTURE_LIVE_DEPLOYMENT.md` / `DEPLOYMENT_LIVE_GUIDE.md` — deployment/publication architecture.
- `ILLLM_CAPABILITY_MARKET_IMPACT_LEDGER_R1.md` — file/module → capability → evidence → market-impact ledger.

## Reading rule

Every technical claim should resolve through this chain:

```text
claim
→ definition
→ source/module
→ runtime role
→ test/receipt
→ promotion boundary
→ market consequence
```

That structure intentionally mirrors IL-LLM: definitions are themselves defined by lower-level objects and relations, so claims remain machine-traceable rather than floating prose.

## Primary advantage classes

### Recursive IL-LLM

Definitions, definitions-of-definitions, semantic/mathematical relations, execution routes and proof references are represented as machine objects. Context and memory are secondary selection/continuation layers.

### Workbook substrate

Workbooks are first-class machine carriers because they can preserve structured data, formulas, dependency graphs, tables, sheet locality and human-operable state without flattening those structures into plain text. `workbook_illlm_bridge.py` now hydrates that static structure directly into the recursive IL-LLM graph.

### Resident capability execution

Action/runtime modules separate intent, authorization, execution, readback and proof. The design attempts to prevent source presence, configuration or UI state from being promoted as execution.

### Service authority objects

DNS/domain, HTTP, mail, server, VFS and related service classes may exist as resident authority/state objects independently of a currently available external actuator. External provider success remains separately receipt-bound.

## Evidence vocabulary

Use explicit evidence states such as:

```text
SOURCE_RESIDENT
STRUCTURALLY_VERIFIED
LOCAL_EXECUTED
TL2_LIVE
PUBLIC_LIVE
BENCHMARKED
EXTERNALLY_VALIDATED
EXTERNAL_ADAPTER_UNBOUND
```

No later state is implied by an earlier one.
