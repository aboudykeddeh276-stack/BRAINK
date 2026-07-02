# BRAINK Native Chat Bot

A standalone **native macOS SwiftUI** chat bot with a deterministic local runtime and optional remote bridge.

## What this build includes
- Native UI (chat view + module trace view)
- Deterministic module routing + route classification
- Local fallback responses (no third-party service required)
- Optional runtime bridge through `BRAINK_CHAT_RUNTIME`
- Reproducible build script
- **Portable path configuration** for any development environment

## Modules
- `Router`: scores command routing keywords
- `Reasoning`: scores reasoning intent
- `Grammar`: simple lexical complexity score
- `Persona`: tracks interaction style signals

## Route map (deterministic local logic)
- `auth.oauth` -> auth/login intent (`login`, `oauth`, `auth`)
- `proof_packet` -> proof/falsifier/routing proof request (`proof`, `packet`, `falsifier`)
- `runtime_trace` -> route/entrypoint/runtime tracing (`runtime`, `route`, `entrypoint`)
- `build` -> build/compile/bundle request (`build`, `compile`, `bundle`)
- `constraint_flags` -> machine-readable module delivery constraints and status flags (`constraints`, `flaggable`, `constraint`, `flag`)
- `illlm_bundle` -> IL-LLM workspace intake and inventory (`il-llm`, `illlm`, `all my il`)
- `illlm_bootstrap` -> explicit "have/load/want my data" bootstrap intent for immediate ingestion.
- `align-check` -> alignment verification requests (`align`, `alignment`)
- `module_manifest` -> module-link proof ledger (`module map`, `module status`, `manifest`)
- `kex_hyperdrive` -> KEX Hyperdrive transition/definition/state concept + full repo calibration report (`State OF transition`, `Transition OF state`, `Definition OF transition`, `calibration analysis`, `pending tasks`, `X OF X OF X OF X`)
- `self_sustained_coder` -> bounded repo coding task packets using KEX self-existence design (`software that can code`, `task it to each repo`, `self existence design`)
- `general` -> fallback when no explicit route match
- Drag-and-drop: dropping a folder or file into the input area will rebind IL-LLM runtime immediately.
- Drag-and-drop behavior: dropped IL-LLM files are also parsed into short in-memory snippets.
  Ask questions that match filenames/contents (for example terms from your project) and the bot will
  return matching loaded context in `illlm_query`.

## Configuration

The chat bot uses configurable paths via environment variables. This ensures portability across different machines and development environments.

### Environment Variables

- `BRAINK_ROOT`: Root directory for the BRAINK repository (default: auto-detected from NativeChatBot location)
- `BRAINK_BUILD_DIR`: Build output directory for reports and artifacts (default: `$BRAINK_ROOT/build`)
- `IL_LLM_RUNTIME_PATH`: Path to your IL-LLM workspace directory (default: `$BRAINK_ROOT/il_llm_runtime`)
- `BRAINK_CHAT_RUNTIME`: Optional remote endpoint for chat requests

## Build

```bash
# Navigate to NativeChatBot directory
cd NativeChatBot

# Build with auto-detected paths
./build-native-chatbot.command

# Or explicitly set the repository root
export BRAINK_ROOT=/path/to/BRAINK
./build-native-chatbot.command
```

The script creates:
- `$BRAINK_ROOT/NativeChatBot/BRAINKChatBot.app`

## Runtime smoke test
Run deterministic route/function smoke tests without opening the UI:

```bash
cd NativeChatBot
./run-runtime-smoke.command
```

Expected markers:
- `SMOKE_STATUS: DONE`
- `SMOKE_ROUTES` includes `kex_hyperdrive`
- `NativeChatBot/build/kex_hyperdrive_repo_calibration_report.json` is generated with repo evidence hashes and pending workloads
- `NativeChatBot/build/kex_self_sustained_coding_report.json` is generated with repo targets, task packets, write scopes, command plans, and proof gates
- `SMOKE_AUDIT_OUTCOME: DONE`
- `SMOKE_AUDIT_ALIGNMENT: 1.0000`
- `SMOKE_ZERO_LESS_STATUS: DONE`
- `SMOKE_ZERO_LESS_API_STATUS: 200`

## Run
```bash
open NativeChatBot/BRAINKChatBot.app
```

## Optional remote runtime
Set an environment variable so the app calls a remote endpoint:
```bash
export BRAINK_CHAT_RUNTIME="https://your-runtime.example.com/chat"
./NativeChatBot/build-native-chatbot.command
```
Payload sent: `{ "prompt": "..." }`.
Response expected: `{ "response": "...", "route": "..." }`.

## Provide IL-LLM workspace bundle
Set this environment variable before building/running so the chatbot can enumerate and ingest your IL-LLM files:

```bash
export IL_LLM_RUNTIME_PATH="/path/to/your/il_llm_workspace"
./NativeChatBot/build-native-chatbot.command
```

Then send:
- `load all my IL-LLM`
- `give it all IL-LLM`
- `i want my chatbot to have my data`

The bot responds with a context-loaded report (up to 200 files) and records a local module trace for every request.

You can also skip env var setup by dragging an IL-LLM folder/file into the chat input strip; the runtime path updates live and inventory is re-read immediately.

The bot also auto-loads IL-LLM snippets on startup from:
1. `IL_LLM_RUNTIME_PATH` if set, otherwise
2. Default location under `$BRAINK_ROOT/il_llm_runtime`.

Detected route for module/status checks:
- `module_manifest` -> reports all module files and exact delivery state.

System messages:
- `system.runtime_drop` / `system.runtime_drop_indexed`: path binding + inventory status
- `system.runtime_startup`: startup ingest status
- `illlm_query` (from route `illlm_query`): data-grounded response from loaded snippets

Detected route for IL-LLM bundle intake:
- `illlm_bundle`
- `illlm_bootstrap`


## KEX hyperdrive calibration analysis
A repo-level KEX/BRAINK calibration and pending-gate ledger is available at `docs/KEX_HYPERDRIVE_CALIBRATION_ANALYSIS.md`. It separates local proof, model logic, operational constraints, pending gates, and external-validation boundaries.

## KEX self-sustain orchestration
From the repository root, generate a local proof-bound packet that lets BRAINK/KEX task this repo, or each repo under a parent folder, without promoting unproved claims:

```bash
python3 tools/kex_self_sustain.py --root . --output-dir reports
python3 tools/kex_self_sustain.py --root . --verify-packet reports/BRAINK_kex_self_sustain_packet.json
python3 tools/kex_ethics_check.py --root . --output reports/kex_ethics_check.json
python3 tools/kex_self_sustain.py --root /path/to/parent --all-repos --output-dir reports
```

The generated packet records artifact hashes, route coverage, ethics findings, pending gates, and allowed KEX statuses.

## Reset
Use **Clear** in the UI to reset conversation + trace.
