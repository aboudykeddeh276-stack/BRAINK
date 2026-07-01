# BRAINK GitHub Actions setup

Use `.github/workflows/braink-native-orchestration.yml` instead of Claude/Anthropic-backed automation.

## Secrets

| Secret | Required | Purpose |
| --- | --- | --- |
| `BRAINK_API_ENDPOINT` | No | Optional BRAINK bridge endpoint. Leave unset to force deterministic local execution. |
| `IL_LLM_RUNTIME_PATH` | No | Optional absolute path for IL-LLM context loading. When unset, the workflow uses the checked-out repository root. |

## Runtime environment

The workflow sets these environment variables:

```yaml
BRAINK_RUNTIME_MODE: bridged | deterministic
BRAINK_CHAT_RUNTIME: ${{ secrets.BRAINK_API_ENDPOINT }}
BRAINK_EXECUTION_POLICY: self_sustained_with_proofs
IL_LLM_RUNTIME_PATH: ${{ secrets.IL_LLM_RUNTIME_PATH }}
IL_LLM_MEMORY_BUDGET_CHARS: "2097152"
BRAINK_PROOF_GENERATION: enabled
BRAINK_ALIGNMENT_AUDIT: enabled
```

## Behavior

1. Validates repository governance and the local BRAINK CLI boundary.
2. Runs `./NativeChatBot/run-runtime-smoke.command`.
3. Runs `./.github/scripts/braink-orchestration.sh`.
4. Uploads generated audit, proof, and orchestration artifacts from `/home/runner/work/BRAINK/BRAINK/NativeChatBot/build`.

## Migration note

No Anthropic or Claude secrets are required. If `BRAINK_API_ENDPOINT` is unavailable or unreachable, the orchestration script automatically proves the local deterministic fallback path.
