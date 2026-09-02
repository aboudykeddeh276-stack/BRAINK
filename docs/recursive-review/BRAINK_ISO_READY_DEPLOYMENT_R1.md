# BRAINK ISO-Ready Deployment R1

## Classification

This package implements an internal ISO-ready engineering method. It does **not** assert certification, accredited conformity assessment, or external auditor approval.

## Current standards baseline

- ISO/IEC/IEEE 12207:2026 — software life-cycle processes.
- ISO/IEC 25010:2023 — ICT/software product quality model.
- ISO/IEC 27001:2022 — information-security management system requirements.
- ISO/IEC 42001:2023 — AI management system requirements.
- ISO/IEC 23894:2023 — AI risk-management guidance.
- ISO/IEC 42005:2025 — AI-system impact assessment guidance.

## BRAINK self-evolution control loop

1. ORC/continuation runtime detects a real missing callable capability.
2. A requirement record and WorkModule contract are created with acceptance-test IDs and risk/impact links.
3. The bounded synthesis engine creates a candidate implementation.
4. Source/contract/dependency roots are recorded.
5. Mandatory syntax, static, security, contract and acceptance checks execute.
6. A verification group independent from the generator records verification evidence.
7. The release qualifier checks requirements traceability, tests, security, risk, SBOM, rollback, change control and independent review.
8. A promoter independent from both generator and verifier may bind the function into the target registry/aperture.
9. Execution receipts are retained.
10. Observer edges are integrated by BRAINK/IL-LLM reconciliation without becoming execution-permission gates.
11. Nonconformities, revocation, rollback, repair and continual-improvement items feed the next ORC ranking.

## Implemented repository controls

- `enterprise/iso_ready_control.py`: evidence/control/nonconformity readiness plane.
- `enterprise/self_coding_governance.py`: requirement traceability, independent verification, promotion segregation, rollback requirement and revocation.
- `enterprise/release_qualification.py`: fail-closed release gates.
- `enterprise/software_supply_chain.py`: component/SBOM and build-provenance evidence.
- `enterprise/ISO_READY_CONTROL_MATRIX_R1.json`: standards/control mapping.
- `enterprise/SELF_EVOLUTION_RELEASE_POLICY_R1.json`: active internal release policy.
- `scripts/kex-ci/test_iso_ready_controls.py`: governance invariants.
- `scripts/kex-ci/test_supply_chain_and_release.py`: supply-chain invariants.
- `.github/workflows/braink-iso-ready.yml`: CI enforcement for enterprise/self-evolution changes.

## Required organizational evidence still outside code

Code can make conformity evidence mechanically producible and fail closed when it is absent. It cannot itself create accredited certification or substitute for organizational governance. Before any certification claim, Keddeh Systems still needs the applicable organizational scope, approved policies/objectives, interested-party/context records, formal risk-acceptance ownership, management review evidence, internal-audit evidence, corrective-action records, competence/awareness records, and an external certification process where certification is sought.

## Governing claim law

`IMPLEMENTED != EXECUTED != VERIFIED != CERTIFIED`

BRAINK may call an internal control `VERIFIED` only when its required evidence exists and is independently checked. The organization may call the management system certified only after a valid external certification process supports that claim.
