# BRAINK GitHub Actions agent orchestration

## Purpose
This repository now ships a BRAINK-owned workflow at `.github/workflows/braink-agent-orchestration.yml` so code-generation and audit flows run through repository-local BRAINK tooling instead of external Claude/Anthropic APIs.

## Required GitHub Actions secrets
Set these repository secrets before enabling bridged runtime mode:

- `BRAINK_CHAT_RUNTIME` — optional explicit BRAINK runtime endpoint. If omitted, the workflow falls back to `EXPO_PUBLIC_API_BASE_URL`.
- `EXPO_PUBLIC_OAUTH_PORTAL_URL` — OAuth portal used by the BRAINK auth route.
- `EXPO_PUBLIC_OAUTH_SERVER_URL` — OAuth server URL. Optional only when `EXPO_PUBLIC_API_BASE_URL` is set.
- `EXPO_PUBLIC_APP_ID` — BRAINK application identifier.
- `EXPO_PUBLIC_API_BASE_URL` — BRAINK API base URL used for auth callback resolution and runtime fallback mapping.
- `EXPO_PUBLIC_OWNER_OPEN_ID` — optional owner identity for audit visibility.
- `EXPO_PUBLIC_OWNER_NAME` — optional owner label for audit visibility.

## Environment mapping used by the workflow
| Environment variable | Source | Role |
| --- | --- | --- |
| `BRAINK_CHAT_RUNTIME` | `secrets.BRAINK_CHAT_RUNTIME` or `secrets.EXPO_PUBLIC_API_BASE_URL` | Remote BRAINK runtime endpoint |
| `EXPO_PUBLIC_OAUTH_PORTAL_URL` | GitHub secret | OAuth route classification support |
| `EXPO_PUBLIC_OAUTH_SERVER_URL` | GitHub secret | OAuth callback base |
| `EXPO_PUBLIC_APP_ID` | GitHub secret | OAuth app identification |
| `EXPO_PUBLIC_API_BASE_URL` | GitHub secret | Fallback BRAINK runtime/API base |
| `IL_LLM_RUNTIME_PATH` | `${{ github.workspace }}` | Repository-local IL-LLM knowledge center context |

## Route orchestration
The workflow runs `scripts/braink_workflow_orchestrator.py`, which enforces this BRAINK route policy:

1. `auth` — validate BRAINK auth env mapping when bridged runtime is requested.
2. `self_sustained_coder` — drive repo coding orchestration.
3. `kex_hyperdrive` — generate repository calibration support.
4. `proof_packet` — generate and verify proof packets through `tools/kex_self_sustain.py`.
5. `stack_audit` — validate deterministic alignment via `NativeChatBot/run-runtime-smoke.command`.

## Fallback behavior
If `BRAINK_CHAT_RUNTIME` is absent, or an endpoint is present without complete `EXPO_PUBLIC_*` auth mapping, the workflow automatically switches to deterministic local mode. In that mode it still:

- validates governance,
- generates proof packets,
- runs ethics checks,
- executes the runtime smoke flow,
- requires `SMOKE_AUDIT_ALIGNMENT: 1.0000`.

## Outputs and audit trail
The workflow uploads:

- `artifacts/braink-workflow/orchestration_plan.json`
- `artifacts/braink-workflow/workflow_report.json`
- per-step logs from the orchestrator
- `NativeChatBot/build/*.json`
- `reports/*.json`

These artifacts provide the route decisions, execution policy, fallback state, proof packet verification, and stack-audit evidence.
