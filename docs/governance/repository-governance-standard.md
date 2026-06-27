# BRAINK/KEX Repository Governance Standard

## 1. Purpose

This standard defines one main governance route for BRAINK/KEX repositories so general application and engineering standards can be directed, named, checked, and adopted consistently.

## 2. Control anchor

Every governed repository must identify:

- `GOVERNANCE_ROOT`: the main source of standards, normally `GENERAL-GOVERNANCE-`.
- `REPOSITORY_WHOLE`: the complete repository identity as a whole system.
- `REPOSITORY_ENVIRONMENT`: the environment where the repository is running, built, checked, or deployed.
- `REPOSITORY_STATE`: the current proof state of the repository.
- `REPOSITORY_FUNCTION`: the primary function performed by the repository.

## 3. Strict explicit naming convention

Names must be literal, explicit, and environment-readable. A name is invalid if it hides whether it is an environment, state, function, artifact, or whole.

Required prefixes:

| Category | Required prefix | Example |
| --- | --- | --- |
| Environment | `ENVIRONMENT_` | `ENVIRONMENT_LOCAL_DEVELOPMENT` |
| State | `STATE_` | `STATE_MODEL_LOCAL` |
| Function | `FUNCTION_` | `FUNCTION_VALIDATE_GOVERNANCE` |
| Whole system | `WHOLE_` | `WHOLE_NATIVE_CHATBOT_APPLICATION` |
| Artifact | `ARTIFACT_` | `ARTIFACT_GOVERNANCE_MANIFEST` |
| Proof gate | `PROOF_GATE_` | `PROOF_GATE_CHECKER_PASSED` |
| Pending boundary | `PENDING_` | `PENDING_EXTERNAL_REPOSITORY_ADOPTION` |

## 4. Environment self-identification rule

An environment must identify itself regardless of what it is.

Minimum required environment names:

- `ENVIRONMENT_LOCAL_DEVELOPMENT`
- `ENVIRONMENT_CONTINUOUS_INTEGRATION`
- `ENVIRONMENT_STAGING`
- `ENVIRONMENT_PRODUCTION`
- `ENVIRONMENT_EXTERNAL_VALIDATION`

If a repository does not use one of these environments, it must still declare the unused environment as `PENDING` or `NOT_APPLICABLE` rather than leaving it unnamed.

## 5. State self-identification rule

Allowed repository states:

- `STATE_COMPLETED`
- `STATE_PENDING`
- `STATE_BLOCKED`
- `STATE_FAILED`
- `STATE_MODEL_LOCAL`
- `STATE_EXTERNALLY_UNVALIDATED`

A state claim is valid only when paired with an artifact, executable check, derivation, result, evidence, and status.

## 6. Function self-identification rule

Every script, document, workflow, and module must declare the function it performs.

Function declarations should answer:

1. What input does this function accept?
2. What action does this function perform?
3. What output does this function produce?
4. What proof gate verifies that output?
5. What remains pending after the function completes?

## 7. Whole self-identification rule

A repository whole must describe the complete system boundary it controls. The whole cannot be replaced by a single component name.

Required whole declaration fields:

- `WHOLE_NAME`
- `WHOLE_OWNER_LINEAGE`
- `WHOLE_PRIMARY_FUNCTION`
- `WHOLE_ENVIRONMENTS`
- `WHOLE_STATES`
- `WHOLE_ARTIFACTS`
- `WHOLE_PENDING_GATES`

## 8. Directed update model

Governance updates flow through this route:

```text
LANGUAGE -> MEANING -> FUNCTION -> CONSTRAINT -> ACTION -> PROOF -> STATUS
```

Repository update route:

```text
GENERAL-GOVERNANCE-
  -> governance artifact update
  -> local checker update
  -> manifest hash update
  -> downstream repository pull/copy
  -> downstream checker run
  -> downstream proof record
```

## 9. Boundary rules

- Local checker success proves only local artifact conformance.
- Local governance does not prove external adoption.
- A copied standard is not current unless its manifest hash matches the governance root or records an intentional divergence.
- A pending gate is not a failure; it is the exact proof gate still open.

## 10. Required proof record

Every completed governance update must record:

- what was required,
- what was changed,
- what command checked it,
- what passed,
- what failed,
- what remains pending.
