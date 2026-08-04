# KEO Support and Lifecycle Policy

## Current release class

```text
0.1.0-mmp — local alpha / minimum marketable product implementation
```

This release class is suitable for controlled evaluation and real engineering case studies. It is not yet a production support commitment.

## Supported environment

- Python 3.10 or newer.
- macOS, Linux, and Windows environments capable of running standard Python.
- Local filesystem access.
- UTF-8 project files.

## Compatibility policy

- Project format versions use semantic versioning.
- Patch changes must preserve existing valid project behaviour.
- Minor changes may add optional fields and new profiles.
- Major changes may alter required fields and require migration.
- Migrations must preserve canonical identities, topology lineage, iteration history, and evidence references.

## Support tiers

### Community

Documentation, examples, issue-based defect reports, and published compatibility notes. Response times are not guaranteed.

### Team

Planned: defined response targets, onboarding support, private templates, policy packs, and upgrade guidance.

### Enterprise

Planned: contractual response targets, self-hosted deployment assistance, assurance packs, custom adapters, migration support, and incident escalation.

## Defect classification

```text
P0 — data loss, security compromise, or invalid promotion with no safe workaround
P1 — core init/validate/inspect workflow unavailable
P2 — one profile or validation rule materially incorrect
P3 — documentation, usability, or non-blocking compatibility defect
```

## Deprecation

A public interface must not be removed without:

- deprecation notice;
- replacement identity;
- migration instructions;
- compatibility window;
- topology and ADR lineage;
- release-note entry.

## Update policy

No automatic updater exists in the local alpha. Future updates must be signed, independently read back, and accompanied by release notes, checksums, and compatibility information.
