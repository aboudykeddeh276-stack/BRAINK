#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TMP_SWIFT="$(mktemp /tmp/braink-smoke-XXXXXX.swift)"
TMP_BIN="$(mktemp /tmp/braink-smoke-runner-XXXXXX)"
trap 'rm -f "$TMP_SWIFT" "$TMP_BIN"' EXIT

cat > "$TMP_SWIFT" <<'SWIFT'
import Foundation

@main
struct BRAINKSmokeRunner {
    @MainActor
    static func main() async {
        let engine = BRAINKChatEngine()

        await engine.send(userInput: "knowledge center status")
        await engine.send(userInput: "stack audit line for line module alignment")
        await engine.send(userInput: "proof packet")
        await engine.send(userInput: "State OF transition + Transition OF state / Definition OF transition + Transition OF definitions / Definition OF state + State OF definitions / X OF X OF X OF X")
        await engine.send(userInput: "software that can code using my software and task it to each repo using my self existence design")
        await engine.send(userInput: "learn every last file and code and skill")

        let total = engine.messages.count
        let users = engine.messages.filter { $0.role == .user }.count
        let assistants = engine.messages.filter { $0.role == .assistant }.count
        let systems = engine.messages.filter { $0.role == .system }.count
        let routes = engine.messages.suffix(8).map(\.route).joined(separator: ",")

        print("SMOKE_STATUS: DONE")
        print("SMOKE_MESSAGES: total=\(total), user=\(users), assistant=\(assistants), system=\(systems)")
        print("SMOKE_ROUTES: \(routes)")
        print("SMOKE_AUDIT_OUTCOME: \(engine.dashboardAuditOutcome)")
        print("SMOKE_AUDIT_COUNTS: \(engine.dashboardAuditCounts)")
        print("SMOKE_AUDIT_ALIGNMENT: \(engine.dashboardAuditWeightedAlignment)")
        print("SMOKE_ILLLM_LOADED: \(engine.ilLlmLoadedCount)")
        print("SMOKE_ILLLM_STATUS: \(engine.ilLlmLoadedStatus)")
        print("SMOKE_NEXT_ACTION: \(engine.dashboardNextAction)")
    }
}
SWIFT

SWIFTC_FLAGS=()
if [[ "$(uname -s)" == "Darwin" ]]; then
  SWIFTC_FLAGS+=( -framework AppKit )
fi

swiftc \
  "${SWIFTC_FLAGS[@]}" \
  "$TMP_SWIFT" \
  "$ROOT/Sources/BRAINKChatEngine.swift" \
  "$ROOT/Sources/BRAINKConstants.swift" \
  "$ROOT/Sources/BRAINKDeliveryAudit.swift" \
  "$ROOT/Sources/BRAINKFrontierSeal.swift" \
  "$ROOT/Sources/BRAINKILLLMCompatibility.swift" \
  "$ROOT/Sources/BRAINKILLLMKnowledgeCenter.swift" \
  "$ROOT/Sources/BRAINKILLLMWorkflow.swift" \
  "$ROOT/Sources/BRAINKInnerRuntime.swift" \
  "$ROOT/Sources/BRAINKZeroLessSpectrum.swift" \
  "$ROOT/Sources/KEXHyperdriveConceptEngine.swift" \
  "$ROOT/Sources/KEXSelfSustainedCodingEngine.swift" \
  "$ROOT/Sources/BRAINKOAuth.swift" \
  "$ROOT/Sources/BRAINKPlatformAPI.swift" \
  "$ROOT/Sources/BRAINKScraperTool.swift" \
  "$ROOT/Sources/BRAINKChromePlugin.swift" \
  "$ROOT/Sources/ModuleManifest.swift" \
  -o "$TMP_BIN"

"$TMP_BIN"
