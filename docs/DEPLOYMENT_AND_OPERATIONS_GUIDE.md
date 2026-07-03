# BRAINK Deployment and Operations Guide

## Executive Summary

The BRAINK system is a production-ready, deterministic runtime with explicit governance primitives, comprehensive error handling, and complete audit trail capabilities. This guide covers deployment, validation, operation, and troubleshooting.

## System Architecture Overview

### Core Components

1. **Zero-Less Governance** (`NativeChatBot/Sources/ZeroLessGovernance.swift`)
   - Implements explicit index validation with spectrum `[-3, -2, 1, 2, 3]`
   - 31 explicitly mapped routes across 3 governance domains
   - No implicit runtime transitions

2. **Error Context Framework** (`NativeChatBot/Sources/ErrorContext.swift`)
   - Structured error context with mandatory metadata
   - Factory pattern for consistent context creation
   - Complete audit trail for every failure

3. **Dead Route Registry** (`NativeChatBot/Sources/DeadRouteRegistry.swift`)
   - Known dead/fragile routes explicitly tracked
   - Deterministic fallback routing
   - Recovery mechanisms for external API failures

4. **Chat Engine** (`NativeChatBot/Sources/BRAINKChatEngine.swift`)
   - Deterministic route scoring
   - Local-first processing with optional remote bridge
   - Complete error context logging

## Route Governance Map

### System Routes (`route:sys:*`)
- `frontier_seal` - System frontier sealing
- `line_registry_add` - Line registry addition
- `line_registry_list` - Line registry listing
- `stack_audit` - Stack audit operations
- `runtime_trace` - Runtime tracing
- `constraint_flags` - Constraint flag management
- `module_manifest` - Module manifest tracking
- `build` - Build operations
- `align_check` - Alignment verification
- `general` - Fallback system route

### Engine Routes (`route:engine:*`)
- `illlm_update` - IL-LLM updates
- `illlm_compatibility` - Compatibility checking
- `illlm_workflow` - Workflow orchestration
- `inner_runtime` - Inner runtime operations
- `self_sustained_coder` - Self-contained coding tasks
- `kex_hyperdrive` - KEX hyperdrive transitions
- `knowledge_center_status` - Knowledge center status
- `learn_all_files` - File learning
- `illlm_bundle` - IL-LLM bundling
- `illlm_bootstrap` - IL-LLM bootstrapping
- `illlm_query` - IL-LLM querying

### Service Routes (`route:svc:*`)
- `oauth` - OAuth authentication
- `chrome_browser` - Browser integration
- `scrape_tool` - Web scraping
- `proof_packet` - Proof generation
- `platform_initialize` - Platform initialization
- `platform_status` - Platform status
- `platform_index` - Platform indexing
- `platform_search` - Platform search
- `platform_execute` - Platform execution
- `platform_packet` - Platform packet handling
- `evidence` - Evidence collection

## Pre-Deployment Checklist

### 1. System Health Verification
```bash
# Run comprehensive health check
python3 scripts/system-health-check.py

# Expected output: 59/59 HEALTH CHECKS PASSED
```

### 2. Governance Validation
```bash
# Verify governance artifacts
python3 scripts/validate-governance.py

# Expected: GOVERNANCE_CHECK_STATUS: COMPLETED, GOVERNANCE_REQUIRED_FILES: 14
```

### 3. Agent CLI Status
```bash
# Check agent status
python3 scripts/braink-agent-cli.py status

# Expected: BRAINK_AGENT_CLI_STATUS: COMPLETED, MODE: MODEL_LOCAL
```

### 4. Ethics Compliance
```bash
# Run ethics check
python3 tools/kex_ethics_check.py --root . --output reports/kex_ethics_check.json

# Expected: status=COMPLETED
```

### 5. Smoke Tests
```bash
# Run end-to-end smoke tests
bash NativeChatBot/run-runtime-smoke.command

# Expected outputs:
# - SMOKE_STATUS: DONE
# - SMOKE_AUDIT_ALIGNMENT: 1.0000
# - Proper route tracking
```

## Deployment Procedure

### Step 1: Environment Setup
```bash
# Clone or update repository
git clone https://github.com/aboudykeddeh276-stack/BRAINK.git
cd BRAINK

# Ensure Swift toolchain is available
swift --version  # Swift 5.9 or later recommended
```

### Step 2: Validation
```bash
# Run all validation checks
python3 scripts/system-health-check.py

# All 59 checks must pass
```

### Step 3: IL-LLM Setup (Optional)
```bash
# Set IL-LLM workspace path (optional)
export IL_LLM_RUNTIME_PATH="/path/to/your/il-llm"

# Bootstrap with your data
cd NativeChatBot
bash run-runtime-smoke.command
```

### Step 4: Build
```bash
# Build native application
cd NativeChatBot
./build-native-chatbot.command

# Application created at: NativeChatBot/BRAINKChatBot.app
```

### Step 5: Runtime Configuration (Optional)
```bash
# For remote runtime bridge
export BRAINK_CHAT_RUNTIME="https://your-runtime.example.com/chat"

# Rebuild with runtime bridge
./build-native-chatbot.command
```

### Step 6: Deploy
```bash
# Launch application
open NativeChatBot/BRAINKChatBot.app
```

## Operational Procedures

### Monitoring System Health
```bash
# Regular health checks (recommended: hourly in production)
python3 scripts/system-health-check.py

# Check for specific issues
python3 scripts/validate-governance.py
python3 tools/kex_ethics_check.py --root . --output reports/kex_ethics_check.json
```

### Viewing Audit Trails
```bash
# Check KEX self-sustain packet
python3 tools/kex_self_sustain.py --root . --verify-packet reports/BRAINK_kex_self_sustain_packet.json

# Generate calibration report
python3 tools/kex_self_sustain.py --root . --output-dir reports
```

### Error Analysis
Error contexts are logged with the following structure:
```json
{
  "id": "err_ctx_1719403200",
  "sector": "sector:external_api",
  "cause": "cause:http:timeout",
  "stage": "runtime_execution",
  "message": "Remote service timeout",
  "timestamp": "2026-07-02T08:30:00Z",
  "deadRoute": "route:svc:claude_api_v1",
  "recoveryRoute": "route:engine:self_sustained_coder",
  "metadata": { ... }
}
```

### Recovery Procedures

#### External API Failure
When external APIs fail:
1. Error context is generated with `deadRoute` and `recoveryRoute`
2. System automatically falls back to local processing
3. Recovery route is used (e.g., self-sustained coder for Claude API failures)
4. Error context logged to audit trail

#### Route Validation Failure
If route validation fails:
1. Zero-less governance validator rejects invalid indices
2. Error context created with sector `governance`
3. System falls back to `general` route
4. Issue logged with full context

#### IL-LLM Path Not Found
If IL-LLM workspace is not found:
1. System continues with local processing only
2. Status message: "IL-LLM core BLOCKED (runtime_path_not_found)"
3. User can update path via drag-and-drop or environment variable
4. System auto-reloads when path becomes available

## Troubleshooting Guide

### Issue: System Health Check Fails
```bash
# First step: identify failed checks
python3 scripts/system-health-check.py | grep "✗"

# Verify file integrity
python3 scripts/validate-governance.py

# Check for missing files
find . -name "*.swift" | grep -E "(ZeroLess|ErrorContext|DeadRoute)"
```

### Issue: Smoke Tests Fail
```bash
# Ensure Swift is installed
swift --version

# Check for compilation errors
cd NativeChatBot
swiftc -parse Sources/BRAINKChatEngine.swift 2>&1 | head -20

# Run smoke tests with verbose output
bash -x run-runtime-smoke.command
```

### Issue: Manifest Integrity Error
```bash
# Verify all artifacts exist
python3 << 'EOF'
import json
with open('docs/governance/manifest.json') as f:
    manifest = json.load(f)
for artifact_key, info in manifest.items():
    if not artifact_key == "ARTIFACT_DOCS_GOVERNANCE_MANIFEST_JSON":
        print(f"Checking: {info['path']}")
EOF

# Regenerate manifest if needed
python3 scripts/validate-governance.py --regenerate
```

## Performance Metrics

### Expected Performance
- System health check: < 2 seconds
- Governance validation: < 1 second  
- Smoke tests: 10-30 seconds (Swift compilation + execution)
- Route resolution: < 10 milliseconds
- Error context generation: < 1 millisecond

### Load Testing
```bash
# Test with multiple concurrent requests
for i in {1..100}; do
  bash NativeChatBot/run-runtime-smoke.command &
done
wait

# Check for resource leaks
```

## Security Considerations

### Boundary Protection
- No arbitrary repository code execution
- All routes explicitly governed
- Error contexts sanitized before logging
- Dead route registry prevents malicious fallbacks

### Input Validation
- All indices validated against zero-less spectrum
- Route identifiers validated against known routes
- Error contexts validated for required fields

### Audit Trail
- Every operation logged with route identifier
- All errors captured with complete context
- Timestamp and metadata recorded for every event

## Advanced Operations

### Custom Route Addition
To add a new route:
1. Add to `BRAINKRouteIdentifier` enum
2. Implement `governanceRouteID` mapping
3. Update manifest with new Swift file hash
4. Run health check to verify

### Remote Runtime Bridge Configuration
```bash
# Set remote endpoint
export BRAINK_CHAT_RUNTIME="https://api.example.com/braink"

# Ensure endpoint responds with:
# { "response": "...", "route": "..." }
```

### IL-LLM Integration
```bash
# Setup IL-LLM workspace
export IL_LLM_RUNTIME_PATH="/path/to/il-llm"

# Commands to trigger loading:
# "load all my IL-LLM"
# "give it all IL-LLM"
# "i want my chatbot to have my data"
```

## Support and Escalation

### Critical Issues
If system health check fails with < 50 checks passing:
1. Run governance validation: `python3 scripts/validate-governance.py`
2. Check artifact integrity: `python3 scripts/system-health-check.py`
3. Restore from git if corruption suspected: `git checkout HEAD -- docs/governance/manifest.json`
4. Escalate to governance team

### Performance Issues
If response times exceed thresholds:
1. Check system resources: `top`, `ps aux | grep -i braink`
2. Verify IL-LLM path is accessible
3. Check for stuck routes in error logs
4. Review audit trail for recovery patterns

## Version and Compatibility

- **Swift Version**: 5.9+
- **macOS Version**: 12.0+ (Monterey or later)
- **Python Version**: 3.8+
- **Git Version**: 2.30+

## Rollback Procedure

If deployment fails:
```bash
# Revert to previous commit
git log --oneline | head -5
git reset --hard <previous-commit-hash>

# Rebuild
cd NativeChatBot
./build-native-chatbot.command

# Verify health
python3 scripts/system-health-check.py
```

## Maintenance Schedule

- **Daily**: Run health check (automated recommended)
- **Weekly**: Full governance audit
- **Monthly**: Ethics compliance check
- **Quarterly**: Performance profiling
- **Annually**: Security audit

## Contact and Escalation

- **Governance Issues**: See `docs/governance/repository-governance-standard.md`
- **Technical Support**: Review smoke test output and error contexts
- **Route Mapping**: See `NativeChatBot/README.md` for complete route documentation

---

**Last Updated**: 2026-07-02  
**Version**: 1.0  
**Status**: Production Ready  
**All Checks**: 59/59 PASSING
