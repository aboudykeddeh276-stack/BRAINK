# BRAINK Error Context Engine

`/.github/scripts/braink-error-context.swift` provides deterministic failure analysis for BRAINK-native CI/CD.

## Error context types

- **ErrorSector**
  - `authentication`
  - `externalApi`
  - `storage`
  - `routing`
  - `execution`
  - `proof`
  - `processing`
  - `unknown`
- **FailureCause**
  - `forbidden403`
  - `timeout`
  - `notFound404`
  - `invalidData`
  - `missingEndpoint`
  - `cartesianZero`
  - `processExit`
  - `noFallback`

## Output model

- `ErrorContext`
  - sector/cause classification
  - failure message
  - occurrence rate
  - dead route
  - recovery path
  - severity
  - recoverability
- `FailureAnalysis`
  - job metadata
  - context list
  - occurrence history/rate
  - dominant sector/cause
  - recommended actions

## Failure recovery flow

1. Parse logs and classify sector/cause.
2. Detect dead routes (`external.claude.api`, MCP dependency routes, execution dead-ends).
3. Compute occurrence rates.
4. Pull recovery route (`self_sustained_coder`, `illlm_bundle`, `proof_packet`, `stack_audit`).
5. Emit JSON analysis artifact for CI and post-mortem.

## Usage

```bash
swift .github/scripts/braink-error-context.swift \
  --input-log reports/job_84541143511.log \
  --job-id 84541143511 \
  --workflow-name "Running Claude" \
  --output reports/braink_failure_analysis_job_84541143511.json
```
