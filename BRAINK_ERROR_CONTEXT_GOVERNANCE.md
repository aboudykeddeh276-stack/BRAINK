# BRAINK Error Context Governance

## Explicit route naming
- `route:svc:oauth` — OAuth handoff service
- `route:svc:claude_api_v1` — dead external Claude API route
- `route:engine:self_sustained` — primary local self-sustained recovery engine
- `route:engine:hyperdrive` — Hyperdrive concept/calibration engine
- `route:engine:il_llm_local` — secondary local deterministic engine
- `route:sys:deterministic_proof` — tertiary guaranteed proof generator
- `route:sys:fallback_chain` — governed route selector for recovery
- `route:err:auth_failed` — explicit fatal auth route marker

## Explicit sector naming
- `sect_auth:api_authentication`
- `sect_api:external_service`
- `sect_api:mcp_connection`
- `sect_storage:relational_indexing`
- `sect_execution:process_management`
- `sect_recovery:fallback_attempt`

## Explicit cause naming
- `cause:http:403_forbidden`
- `cause:http:timeout`
- `cause:logic:cartesian_zero`
- `cause:os:process_exit:code_1`
- `cause:system:external_dependency`
- `cause:system:no_fallback_configured`

## Dead-route governance
- `route:svc:claude_api_v1` is blacklisted in the dead-route registry.
- Replacement route: `route:engine:self_sustained`
- Occurrence rate is tracked in error-context artifacts and failure-analysis reports.

## Recovery chain
1. `route:engine:self_sustained`
2. `route:engine:il_llm_local`
3. `route:sys:deterministic_proof`

## Artifacts
- `NativeChatBot/build/braink_dead_route_registry.json`
- `NativeChatBot/build/braink_error_context.json`
- `NativeChatBot/build/braink_error_context_history.json`
- `NativeChatBot/build/braink_failure_analysis_report.json`
- `reports/braink-native-ci/braink_error_context.json`
- `reports/braink-native-ci/braink_failure_analysis_report.json`
