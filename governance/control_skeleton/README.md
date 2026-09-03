# KEDDEH/BRAINK Governance Control Skeleton

This subsystem generates a consistent governance/control package for any BRAINK/KEX sector, repository, module, runtime, adapter, actuator, workflow or consequential function.

The skeleton is intentionally separate from implementation logic. It defines the control contract around implementation without replacing the implementation.

## Generated control set

Every governed component should receive:

```text
CONTROL_INDEX.md
FILING_STANDARD.md
SCHEMA_STANDARD.md
AUTHORSHIP_AUTHORITY.md
PROCESS_CONTROL.md
WORKFLOW_CONTROL.md
OPERATIONS_RUNBOOK.md
CROSS_PLATFORM_CONTRACT.md
ACCOUNTABILITY_EVIDENCE.md
KEY_CONSIDERATIONS.md
GOVERNANCE_MANIFEST.json
```

## Governance dimensions

The skeleton records:

- component identity/classification;
- repository/sector ownership;
- substrate boundary;
- state and persistence class;
- interfaces;
- producers/consumers;
- addressing/namespace;
- communication mechanisms;
- virtualisation type;
- runtime and mutation authority;
- dependencies;
- proof/readback conditions;
- rollback requirements;
- filing/evidence destinations;
- authorship/accountability;
- workflow/admission gates;
- operator/help/admin controls;
- cross-platform capability requirements;
- invalid claims/overclaims;
- promotion states.

## Usage

Create a component specification JSON, then run:

```bash
python3 governance/control_skeleton/generate_governance.py \
  --spec path/to/component-governance-spec.json \
  --output path/to/governed-component/control
```

The generator is deterministic for a given specification and refuses to overwrite existing control files unless `--force` is supplied.

## Design rule

Governance documents do not prove runtime capability. They define what evidence is required before capability may be promoted.
