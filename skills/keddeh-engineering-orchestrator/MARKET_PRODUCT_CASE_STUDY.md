# KEDDEH Engineering Orchestrator — Market Product Case Study

## Study question

What turns a technically rigorous engineering framework into a product that engineers, teams, and organisations can discover, trial, adopt, trust, purchase, and operate?

## Comparable product patterns

### Backstage

Backstage addresses fragmented software ownership, tooling, documentation, and project creation through a software catalog, templates, plugins, and docs-as-code. The commercially relevant lesson is not its frontend technology; it is that a complex engineering ecosystem becomes usable when every software entity is discoverable, owned, templated, and connected to documentation and operational evidence.

### Structurizr

Structurizr commercialises model-as-code architecture through a single source model, multiple generated views, ADR and documentation integration, prebuilt binaries, quick-start workflows, a trial period, and team-sized licensing. The relevant lesson is that architecture becomes purchasable when the model is immediately executable, viewable, versionable, and supported by clear packaging.

### Temporal

Temporal provides an open-source engine and a managed cloud service. It markets an operational outcome—durable execution—rather than a language construct. The relevant lesson is that KEDDEH must sell verified engineering continuity, translation integrity, topology control, and evidence, not the novelty of KIR syntax.

### Terraform

Terraform combines declarative models, reusable modules, registries, VCS integration, and a develop–distribute–consume lifecycle. The relevant lesson is that KEDDEH needs reusable engineering profiles, a registry/catalog model, deterministic project scaffolding, compatibility metadata, and versioned distribution.

## Market problem

Engineering organisations routinely lose consistency between:

- requirements and architecture;
- architecture and source code;
- source code and runtime behaviour;
- software abstractions and hardware contracts;
- implementation claims and actual evidence;
- multiple programming languages representing the same system;
- generated documentation and the system it describes.

Existing tools usually solve one part: cataloguing, architecture diagrams, workflow durability, infrastructure provisioning, code generation, documentation, or CI. KEDDEH Engineering Orchestrator is positioned as the bilateral semantic and topology control plane across those boundaries.

## Product category

```text
category: Engineering Synthesis and Evidence Platform
short name: KEO
primary surface: local CLI + model files + CI validation
future surfaces: desktop workstation + collaborative server + managed control plane
```

## Target customers

### Initial beachhead

- systems and platform engineering teams;
- firmware, kernel, hypervisor, and embedded teams;
- architecture groups maintaining multi-language systems;
- regulated or high-assurance software teams;
- organisations building internal developer platforms;
- research teams translating hardware concepts into executable software models.

### Primary buyer

Engineering leadership, platform leadership, chief architects, CTO organisations, and assurance/compliance engineering groups.

### Primary daily user

Software architects, systems programmers, platform engineers, firmware engineers, DevOps engineers, technical leads, and verification engineers.

## Core jobs to be done

1. Turn an engineering request into a complete system topology and iteration plan.
2. Generate consistent project foundations for servers, firmware, BIOS, hardware abstractions, services, and control planes.
3. Preserve one canonical identity while producing multiple language and runtime projections.
4. Validate that generated or modified implementations still represent the intended system.
5. Record evidence, promotion state, lineage, and unresolved gates automatically.
6. Make complex system ownership, dependencies, runtime flows, and deployment projections inspectable.

## Differentiation

```text
Backstage: catalog and developer portal
Structurizr: architecture model and views
Temporal: durable workflow execution
Terraform: infrastructure model and modules
KEO: bilateral engineering translation + topology + implementation/evidence equivalence
```

KEO's defensible product capability is the round-trip contract:

```text
requirement → KIR → target projection → observed execution → KIR readback → equivalence decision
```

## Minimum marketable product

The first sellable/trialable product must provide:

- a dependency-free local CLI;
- `init`, `validate`, and `inspect` commands;
- server, BIOS/firmware, and hardware-abstraction starter profiles;
- KIR, topology, interface, iteration, and product-state files;
- deterministic naming and versioning;
- CI-ready validation;
- example projects and a five-minute quickstart;
- explicit local-only privacy boundary;
- stable semantic versioning and release notes;
- an evaluation edition and a team edition definition;
- failure messages that state the exact missing contract;
- no requirement for Lovable or unrelated hosted builders.

## Product editions

### Community

Local CLI, open project format, validators, starter profiles, examples, and GitHub CI integration.

### Team

Shared catalog, policy packs, topology registry, evidence history, role-based review, private templates, and support.

### Enterprise

Self-hosted control plane, SSO, audit export, policy enforcement, custom adapters, assurance packs, deployment evidence federation, and contractual support.

### Managed

Future hosted control plane where allowed by customer sovereignty requirements. Source-code ingestion must remain optional and explicitly scoped.

## Adoption funnel

```text
discover
→ run five-minute local demo
→ initialise one real project
→ validate in CI
→ onboard one team
→ register multiple systems
→ enforce organisation policy
→ purchase support/control-plane capabilities
```

## Market-readiness gates

```text
GATE_PRODUCT_01_CLEAR_CATEGORY_AND_USER
GATE_PRODUCT_02_FIVE_MINUTE_QUICKSTART
GATE_PRODUCT_03_DEPENDENCY_FREE_LOCAL_RUN
GATE_PRODUCT_04_THREE_REAL_ENGINEERING_PROFILES
GATE_PRODUCT_05_ACTIONABLE_VALIDATION_ERRORS
GATE_PRODUCT_06_VERSIONED_OPEN_PROJECT_FORMAT
GATE_PRODUCT_07_CI_REFERENCE_INTEGRATION
GATE_PRODUCT_08_SECURITY_AND_PRIVACY_BOUNDARY
GATE_PRODUCT_09_LICENSE_AND_EDITION_MODEL
GATE_PRODUCT_10_SUPPORT_AND_UPDATE_POLICY
GATE_PRODUCT_11_REAL_CASE_STUDY
GATE_PRODUCT_12_RELEASE_ARTIFACT_READBACK
```

## Current conclusion

The repository skill has strong architecture and validation foundations but was not yet a marketable product because it lacked a user-facing executable, onboarding, project scaffolding, edition boundaries, and a concrete evaluation path. The KEO CLI and product package close the first of those gaps. A public-market claim remains blocked until release artifacts, external users, usability evidence, and a complete legal/licensing review exist.
