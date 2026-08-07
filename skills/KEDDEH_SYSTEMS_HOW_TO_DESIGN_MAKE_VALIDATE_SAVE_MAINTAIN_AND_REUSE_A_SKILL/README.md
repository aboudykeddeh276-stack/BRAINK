# Keddeh Systems — How to Design, Make, Validate, Save, Maintain, and Reuse a Skill

**Canonical identifier:** `KEDDEH_SYSTEMS_HOW_TO_DESIGN_MAKE_VALIDATE_SAVE_MAINTAIN_AND_REUSE_A_SKILL`
**Version:** `1.1.0`

## What this package contains

| File | Purpose |
|---|---|
| `SKILL.md` | Authoritative engineering method — full lifecycle |
| `DIRECTIVE_LEDGER.md` | Naming and semantic-preservation governing correction |
| `REQUIREMENTS.md` | Normative requirements for every skill package |
| `WORKFLOW.md` | Deterministic step-by-step skill-making workflow |
| `FAILURE_AND_EVIDENCE_MODEL.md` | Failure classifications and evidence chain |
| `manifest.json` | Machine-readable identity and claim boundary |
| `src/validate_skill_package.py` | **Executable** — validates a skill directory against this methodology |
| `tests/test_validate_skill_package.py` | Unit tests for the validator |

## Governing rule

Full semantic names are authoritative.
Abbreviations may only be secondary aliases after demonstrated semantic equivalence.

```
R(C(D)) = D
```

Compression is acceptable only when every material distinction required to understand,
implement, test, operate, or audit the capability survives transformation.

## Running the validator

```bash
python3 src/validate_skill_package.py path/to/skill/directory
```

Exits 0 on pass, 1 on failure. Outputs a JSON report to stdout.
