# BRAINK Failure Analysis Report

- Job ID: `84541143511`
- Workflow: `Running Claude`
- Occurrence rate: `100.00%`
- Dominant sector: `externalApi`
- Dominant cause: `invalidData`

## Error contexts

1. Sector `authentication`, Cause `forbidden403`, Severity `9`
   - Message: External Claude/Anthropic endpoint denied authentication (403 Forbidden).
   - Dead route: external.claude.api
   - Recovery path: self_sustained_coder
   - Recoverable: True
2. Sector `externalApi`, Cause `missingEndpoint`, Severity `8`
   - Message: MCP server dependency failed or became unreliable after external route failure.
   - Dead route: external.runtime-tools.mcp
   - Recovery path: local_proof_generation
   - Recoverable: True
3. Sector `execution`, Cause `processExit`, Severity `8`
   - Message: Process terminated with exit code 1 due to upstream ClaudeError escalation.
   - Dead route: external.claude.process
   - Recovery path: deterministic_local_mode
   - Recoverable: True
4. Sector `storage`, Cause `cartesianZero`, Severity `7`
   - Message: Storage/alignment layer signaled cartesian zero in cell alignment.
   - Dead route: storage.cell_alignment
   - Recovery path: stack_audit
   - Recoverable: True
5. Sector `routing`, Cause `noFallback`, Severity `10`
   - Message: No fallback routing was activated after authentication/process failure.
   - Dead route: claude.primary.route
   - Recovery path: illlm_bundle
   - Recoverable: True
6. Sector `proof`, Cause `invalidData`, Severity `7`
   - Message: Proof packet artifacts were not generated on failure.
   - Dead route: proof.artifact.pipeline
   - Recovery path: proof_packet
   - Recoverable: True
7. Sector `processing`, Cause `invalidData`, Severity `8`
   - Message: Error context propagation missing (sector/cause analysis absent in failure stream).
   - Dead route: error.context.pipeline
   - Recovery path: braink_error_context_engine
   - Recoverable: True

## Recommended actions

- Disable external Claude/Anthropic route for CI and force BRAINK local orchestration.
- Treat runtime-tools MCP as optional; continue with local deterministic proof generation.
- Capture process-exit context and route to self_sustained_coder + kex_hyperdrive fallback.
- Run stack_audit and rebuild relational index mapping before next attempt.
- Enforce multi-level fallback policy (self_sustained_coder -> illlm_bundle -> proof_packet).
- Always emit error-context and proof artifacts even on controlled failure.
