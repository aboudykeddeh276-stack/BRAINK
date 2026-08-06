# Keddeh Logical Engineering — Standards Baseline

**Baseline date:** 2026-08-07  
**Applies to:** `keddeh-logical-engineering` v1.0.0  
**Status:** Controlled reference baseline

## 1. Use of standards

This baseline identifies the external standards used to structure Keddeh Systems logical programming, processes, procedures, protocols, verification, validation, security, and evidence.

Reference to a standard does not, by itself, establish certification, accreditation, product conformity, or organisational compliance. Every conformance claim MUST identify:

- the exact edition;
- the applicable clauses or controls;
- the tailoring decision;
- the required assessment method;
- the evidence produced;
- the independent authority, where required;
- the limitations and exclusions.

Where a newer edition is under development but not yet published, the latest published edition remains normative unless the project formally adopts the draft as an additional informative source.

## 2. Normative baseline

| Domain | Baseline | Function within the skill |
|---|---|---|
| Software lifecycle | ISO/IEC/IEEE 12207:2026 | Common software lifecycle framework, processes, activities, and tasks |
| System lifecycle | ISO/IEC/IEEE 15288:2023 | Broader system-of-interest, hardware/software/interface lifecycle |
| Lifecycle management | ISO/IEC/IEEE 24748-1:2024 | Lifecycle selection, adaptation, stages, and process application |
| Requirements engineering | ISO/IEC/IEEE 29148:2018 | Requirements processes, quality, specifications, and information items |
| Lifecycle documentation | ISO/IEC/IEEE 15289:2019 | Purpose and content of lifecycle information items |
| Product quality | ISO/IEC 25010:2023 | Product-quality requirements and evaluation model |
| Verification and validation | IEEE 1012-2024 | System, software, and hardware V&V, including integrity-sensitive independence |
| Secure development | NIST SP 800-218, SSDF v1.1 | Outcome-oriented secure software development practices |
| Security engineering | NIST SP 800-160 Vol. 1 Rev. 1 | Trustworthy secure-system engineering across the lifecycle |
| Information security management | ISO/IEC 27001:2022 and applicable amendments | Organisational information-security management and risk treatment |
| Normative language | BCP 14: RFC 2119 and RFC 8174 | Meaning of uppercase MUST, SHOULD, MAY, and related terms |
| Canonical JSON | RFC 8785 where JSON is signed or hashed | Deterministic representation for repeatable cryptographic operations |

## 3. Edition status

### 3.1 ISO/IEC/IEEE 12207

ISO/IEC/IEEE 12207:2026 is the current published software-lifecycle edition. Project references frozen to ISO/IEC/IEEE 12207:2017 MUST be reviewed and either migrated or explicitly retained through a recorded tailoring decision.

### 3.2 ISO/IEC/IEEE 29148

ISO/IEC/IEEE 29148:2018 remains the current published requirements-engineering edition and was confirmed in 2024. A third edition was at Draft International Standard stage in July 2026. The draft MAY be monitored, but it MUST NOT silently replace the published edition.

### 3.3 ISO/IEC/IEEE 15289

ISO/IEC/IEEE 15289:2019 remains the current published lifecycle-documentation edition and was confirmed in 2025. It is marked for revision. The 2019 edition remains normative until a replacement is published or contractually adopted.

### 3.4 IEEE 1012

IEEE 1012-2024 is the active verification-and-validation edition and supersedes IEEE 1012-2016. Integrity-sensitive projects MUST review independence, rigour, and evidence against the active edition rather than relying on the superseded reference.

### 3.5 NIST SSDF

NIST SP 800-218 v1.1 remains the final published Secure Software Development Framework baseline. Draft revisions MAY inform future planning but MUST be labelled informative until final publication.

## 4. Standards-to-artifact mapping

| Engineering artifact | Minimum baseline |
|---|---|
| Lifecycle plan | 12207, 15288, 24748-1 |
| Requirements specification | 29148, BCP 14 |
| Architecture and design description | 12207, 15289, 25010 |
| Process description | 12207, 24748-1, 15289 |
| Procedure or work instruction | 15289 plus applicable safety/security rules |
| Distributed protocol specification | BCP 14, 29148, applicable IETF/industry protocol standards |
| Verification plan and report | IEEE 1012, 29148, 15289 |
| Secure-development plan | NIST SP 800-218, NIST SP 800-160 |
| Security-management controls | ISO/IEC 27001 and project risk treatment |
| Signed JSON evidence | RFC 8785 or a separately specified canonical encoding |
| Quality model and acceptance criteria | ISO/IEC 25010, 29148 |
| Release and operational evidence | 12207, 15289, IEEE 1012, SSDF |

## 5. Domain overlays

The following overlays apply only when their domain is in scope:

| Domain | Overlay examples |
|---|---|
| Safety-critical C/C++ | MISRA C or MISRA C++, CERT C/C++, applicable IEC 61508 or sector standard |
| Aviation | DO-178C/ED-12C and approved supplements |
| Automotive | ISO 26262 and applicable cybersecurity standards |
| Medical devices | IEC 62304 and applicable risk-management standards |
| Cryptographic modules | FIPS 140-3 or applicable assurance scheme |
| Common Criteria | ISO/IEC 15408 and selected protection profile/assurance package |
| Networking | Applicable IETF RFCs, IEEE 802 standards, and device specifications |
| TPM | TCG TPM 2.0 library and attestation specifications; ISO/IEC 11889 where applicable |
| Bitcoin | Applicable BIPs, Bitcoin Core consensus behaviour, and RPC contracts |
| Rust | Rust Reference, explicit unsafe-code invariants, static-analysis policy, dependency control, and reproducible-build controls |

An overlay MUST NOT be described as completed unless the required assessment has actually been performed.

## 6. Precedence

Unless law or contract establishes another order, conflicts are resolved through:

```text
LAW / REGULATION
→ CONTRACTUAL REQUIREMENT
→ SAFETY OR SECURITY AUTHORITY
→ EXTERNAL NORMATIVE STANDARD
→ KEDDEH GOVERNING POLICY
→ PROJECT SPECIFICATION
→ DESIGN DECISION
→ LOCAL WORK INSTRUCTION
```

A lower-precedence artifact MUST NOT silently weaken a higher-precedence obligation.

## 7. Tailoring record

Every standards tailoring decision MUST contain:

```text
TAILORING ID
STANDARD AND EDITION
CLAUSE OR SUBJECT
ORIGINAL OBLIGATION
TAILORED APPLICATION
RATIONALE
REPLACEMENT CONTROL
RISK
APPROVING AUTHORITY
REVIEW TRIGGER
EVIDENCE
```

## 8. Review cadence

This baseline MUST be reviewed:

- at least quarterly while governed systems are under active development;
- before a major release;
- when a referenced standard is revised, withdrawn, or superseded;
- when a new legal, regulatory, contractual, or safety obligation applies;
- after a serious defect, security incident, or failed recovery event.

The review receipt MUST record sources checked, editions found, changes adopted, changes deferred, and resulting impact.

## 9. Official source records

- ISO/IEC/IEEE 12207:2026: <https://www.iso.org/standard/90219.html>
- ISO/IEC/IEEE 15288:2023: <https://www.iso.org/standard/81702.html>
- ISO/IEC/IEEE 24748-1:2024: <https://www.iso.org/standard/84709.html>
- ISO/IEC/IEEE 29148:2018: <https://www.iso.org/standard/72089.html>
- ISO/IEC/IEEE DIS 29148 development record: <https://www.iso.org/standard/94091.html>
- ISO/IEC/IEEE 15289:2019: <https://www.iso.org/standard/74909.html>
- ISO/IEC 25010:2023: <https://www.iso.org/standard/78176.html>
- IEEE 1012-2024: <https://standards.ieee.org/ieee/1012/7324/>
- NIST SP 800-218 SSDF v1.1: <https://csrc.nist.gov/pubs/sp/800/218/final>
- NIST SP 800-160 Vol. 1 Rev. 1: <https://csrc.nist.gov/pubs/sp/800/160/v1/r1/final>
- RFC 2119: <https://www.rfc-editor.org/rfc/rfc2119.html>
- RFC 8174: <https://www.rfc-editor.org/rfc/rfc8174.html>
- RFC 8785: <https://www.rfc-editor.org/rfc/rfc8785.html>

Some complete standards texts require licensed access. The issuing organisations' records establish edition and publication status; implementation teams remain responsible for obtaining authorised copies of applicable normative text.
