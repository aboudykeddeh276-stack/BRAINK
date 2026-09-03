# Process, Workflow and Administration Standard R16

Lifecycle: `DISCOVER → DESIGN → IMPLEMENT → TEST → VERIFY → DOCUMENT → DEPLOY → READBACK → OPERATE → REVIEW → RETIRE`.

Every workflow transition declares current state, trigger, actor, authority, required inputs, preconditions, exact action, expected output, proof target, failure state, rollback and next state.

Administration requires: capability register, role matrix, permission boundary, approval rule, publish/deploy authority, rollback authority, emergency stop/recovery path, audit trail, configuration revision, secret/credential boundary, backup/restore policy and health/status readback.

Failure classes: `INPUT_INVALID`, `AUTHORITY_BLOCKED`, `DEPENDENCY_BLOCKED`, `EXECUTION_FAIL`, `VERIFICATION_FAIL`, `READBACK_FAIL`, `PLATFORM_INCOMPATIBLE`, `UNKNOWN`.

Recovery actions require receipts exactly like normal actions. A sector may extend the lifecycle but may not remove verification or readback.
