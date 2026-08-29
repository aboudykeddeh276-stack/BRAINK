# V98 Research, Development, Population and Deployment Plan

## 1. Purpose

V98 converts the V97 functional service spine into a protocol-governed deployment pack. The pack does not promote narrative status. It promotes only machine-checked states produced by the acceptance harness.

## 2. Research baseline

The standards catalog is populated as a reference-alignment pack covering software lifecycle, AI governance, information security, privacy, secure development, software assurance, supply-chain provenance, SBOM, POSIX target-host gates, MISRA guidance and DO-178C external assurance. The pack does not claim certification.

## 3. Development baseline

Every service is forced into one lifecycle contract:

```text
recognize -> execute -> verify -> write_receipt -> readback -> handoff
```

A service missing any stage cannot promote to LOCAL_PASS.

## 4. Population baseline

The pack populates:

- standards catalog
- authority map
- service protocol registry
- functional protocol register
- control objectives
- orphaned service registry
- macOS M3 deployment profile
- launchd template
- host acceptance workflow
- tests and acceptance harness

## 5. Deployment baseline

Deployment is performed by branch and pull request. Host execution is performed by a self-hosted macOS ARM64 runner with the label `KEDDEH-M3`. macOS service continuity is performed by launchd using the template in `launchd/`.

## 6. Promotion rule

A human can define and edit. Codex can implement. Reviewers can inspect. The acceptance harness alone can promote LOCAL_PASS. Target-host and provider-dependent claims stay gated until receipts are produced.
