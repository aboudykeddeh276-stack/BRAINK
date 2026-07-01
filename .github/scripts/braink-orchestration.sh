#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NATIVE_ROOT="${ROOT}/NativeChatBot"
BUILD_DIR="${NATIVE_ROOT}/build"

mkdir -p "${BUILD_DIR}"

export BRAINK_RUNTIME_MODE="${BRAINK_RUNTIME_MODE:-deterministic}"
export BRAINK_EXECUTION_POLICY="${BRAINK_EXECUTION_POLICY:-self_sustained_with_proofs}"
export BRAINK_PROOF_GENERATION="${BRAINK_PROOF_GENERATION:-enabled}"
export BRAINK_ALIGNMENT_AUDIT="${BRAINK_ALIGNMENT_AUDIT:-enabled}"
export IL_LLM_RUNTIME_PATH="${IL_LLM_RUNTIME_PATH:-${ROOT}}"
export IL_LLM_MEMORY_BUDGET_CHARS="${IL_LLM_MEMORY_BUDGET_CHARS:-2097152}"

if [[ "${BRAINK_RUNTIME_MODE}" != "bridged" ]]; then
  export BRAINK_RUNTIME_MODE="deterministic"
fi

if [[ -z "${BRAINK_CHAT_RUNTIME:-}" ]]; then
  if [[ -v BRAINK_CHAT_RUNTIME ]]; then
    unset BRAINK_CHAT_RUNTIME
  fi
  export BRAINK_RUNTIME_MODE="deterministic"
fi

TMP_SWIFT="$(mktemp /tmp/braink-orchestration-XXXXXX.swift)"
TMP_BIN="$(mktemp /tmp/braink-orchestration-runner-XXXXXX)"
trap 'rm -f "${TMP_SWIFT}" "${TMP_BIN}"' EXIT

cat > "${TMP_SWIFT}" <<'SWIFT'
import Foundation

struct RouteExecution: Codable {
    let prompt: String
    let assistantRoute: String
    let assistantResponse: String
    let fallbackEngaged: Bool
}

struct OrchestrationSummary: Codable {
    let profile: String
    let runtimeMode: String
    let runtimeEndpoint: String
    let ilLlmRuntimePath: String
    let auditOutcome: String
    let auditAlignment: String
    let routeResults: [RouteExecution]
    let generatedAt: String
}

@main
struct BRAINKOrchestrationRunner {
    @MainActor
    static func main() async throws {
        let environment = ProcessInfo.processInfo.environment
        let outputPath = environment["BRAINK_ORCHESTRATION_OUTPUT"] ?? ""
        let profile = environment["BRAINK_ORCHESTRATION_PROFILE"] ?? "primary"
        guard !outputPath.isEmpty else {
            throw NSError(domain: "BRAINKOrchestration", code: 1, userInfo: [NSLocalizedDescriptionKey: "BRAINK_ORCHESTRATION_OUTPUT is required"])
        }

        let prompts = [
            "knowledge center status",
            "proof packet",
            "State OF transition + Transition OF state / Definition OF transition + Transition OF definitions / Definition OF state + State OF definitions / X OF X OF X OF X",
            "software that can code using my software and task it to each repo using my self existence design",
            "stack audit line for line module alignment"
        ]

        let engine = BRAINKChatEngine()
        var executions: [RouteExecution] = []

        for prompt in prompts {
            let beforeCount = engine.messages.count
            await engine.send(userInput: prompt)
            let recentMessages = Array(engine.messages.dropFirst(beforeCount))
            let fallbackEngaged = recentMessages.contains { $0.route == "system.fallback" }
            guard let assistantMessage = recentMessages.last(where: { $0.role == .assistant }) else {
                throw NSError(domain: "BRAINKOrchestration", code: 2, userInfo: [NSLocalizedDescriptionKey: "No assistant response for prompt: \(prompt)"])
            }

            executions.append(RouteExecution(
                prompt: prompt,
                assistantRoute: assistantMessage.route,
                assistantResponse: assistantMessage.text,
                fallbackEngaged: fallbackEngaged
            ))
        }

        let summary = OrchestrationSummary(
            profile: profile,
            runtimeMode: engine.runtimeModeLabel,
            runtimeEndpoint: engine.runtimeEndpointLabel,
            ilLlmRuntimePath: engine.ilLlmRuntimePath,
            auditOutcome: engine.dashboardAuditOutcome,
            auditAlignment: engine.dashboardAuditWeightedAlignment,
            routeResults: executions,
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(summary)
        try data.write(to: URL(fileURLWithPath: outputPath))

        print("BRAINK_ORCHESTRATION_PROFILE: \(summary.profile)")
        print("BRAINK_ORCHESTRATION_OUTPUT: \(outputPath)")
        print("BRAINK_ORCHESTRATION_AUDIT: \(summary.auditOutcome) alignment=\(summary.auditAlignment)")
        for result in executions {
            print("BRAINK_ORCHESTRATION_ROUTE: \(result.assistantRoute) fallback=\(result.fallbackEngaged)")
        }
    }
}
SWIFT

SWIFTC_FLAGS=()
if [[ "$(uname -s)" == "Darwin" ]]; then
  SWIFTC_FLAGS+=( -framework AppKit )
fi

swiftc \
  "${SWIFTC_FLAGS[@]}" \
  "${TMP_SWIFT}" \
  "${NATIVE_ROOT}/Sources/BRAINKChatEngine.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKConstants.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKDeliveryAudit.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKFrontierSeal.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKILLLMCompatibility.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKILLLMKnowledgeCenter.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKILLLMWorkflow.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKInnerRuntime.swift" \
  "${NATIVE_ROOT}/Sources/KEXHyperdriveConceptEngine.swift" \
  "${NATIVE_ROOT}/Sources/KEXSelfSustainedCodingEngine.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKOAuth.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKPlatformAPI.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKScraperTool.swift" \
  "${NATIVE_ROOT}/Sources/BRAINKChromePlugin.swift" \
  "${NATIVE_ROOT}/Sources/ModuleManifest.swift" \
  -o "${TMP_BIN}"

PRIMARY_SUMMARY="${BUILD_DIR}/braink_primary_orchestration_summary.json"
FALLBACK_SUMMARY="${BUILD_DIR}/braink_fallback_orchestration_summary.json"
FALLBACK_PROBE_ENDPOINT="${BRAINK_FALLBACK_PROBE_ENDPOINT:-http://127.0.0.1:9}"
FALLBACK_PROBE_TIMEOUT_SECONDS="${BRAINK_FALLBACK_PROBE_TIMEOUT_SECONDS:-0.2}"

BRAINK_ORCHESTRATION_PROFILE="primary" \
BRAINK_ORCHESTRATION_OUTPUT="${PRIMARY_SUMMARY}" \
"${TMP_BIN}"

python3 - "${FALLBACK_PROBE_ENDPOINT}" "${FALLBACK_PROBE_TIMEOUT_SECONDS}" <<'PY'
from __future__ import annotations

import socket
import sys
from urllib.parse import urlparse

endpoint = urlparse(sys.argv[1])
timeout_seconds = float(sys.argv[2])
host = endpoint.hostname
if endpoint.scheme not in {"http", "https"}:
    raise SystemExit(f"Fallback probe endpoint must use http or https: {sys.argv[1]}")
if endpoint.port is not None:
    port = endpoint.port
else:
    port = 443 if endpoint.scheme == "https" else 80

if not host:
    raise SystemExit("Fallback probe endpoint is missing a hostname")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(timeout_seconds)
    endpoint_is_reachable = sock.connect_ex((host, port)) == 0

if endpoint_is_reachable:
    raise SystemExit(f"Fallback probe endpoint is reachable: {sys.argv[1]}")
PY

BRAINK_RUNTIME_MODE="bridged" \
BRAINK_CHAT_RUNTIME="${FALLBACK_PROBE_ENDPOINT}" \
BRAINK_ORCHESTRATION_PROFILE="fallback_probe" \
BRAINK_ORCHESTRATION_OUTPUT="${FALLBACK_SUMMARY}" \
IL_LLM_RUNTIME_PATH="${IL_LLM_RUNTIME_PATH}" \
"${TMP_BIN}"

ln -sfn "braink_stack_alignment_report.json" "${BUILD_DIR}/braink_module_alignment_audit.json"

python3 - "${PRIMARY_SUMMARY}" "${FALLBACK_SUMMARY}" "${BUILD_DIR}" "${ROOT}" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

primary_path = Path(sys.argv[1])
fallback_path = Path(sys.argv[2])
build_dir = Path(sys.argv[3])
repo_root = Path(sys.argv[4])

primary = json.loads(primary_path.read_text())
fallback = json.loads(fallback_path.read_text())
module_audit = json.loads((build_dir / "braink_stack_alignment_report.json").read_text())

proof_packet = {"raw": ""}
for route in primary["routeResults"]:
    if route["assistantRoute"] == "proof_packet":
        try:
            proof_packet = json.loads(route["assistantResponse"])
        except json.JSONDecodeError:
            proof_packet = {"raw": route["assistantResponse"]}
        break

artifact_paths = [
    build_dir / "kex_hyperdrive_transition_definition_report.json",
    build_dir / "kex_self_sustained_coding_report.json",
    build_dir / "kex_hyperdrive_repo_calibration_report.json",
    build_dir / "braink_stack_alignment_report.json",
    build_dir / "braink_module_alignment_audit.json",
    build_dir / "braink_primary_orchestration_summary.json",
    build_dir / "braink_fallback_orchestration_summary.json",
]

artifacts = []
for path in artifact_paths:
    if not path.exists():
        continue
    data = path.read_bytes()
    artifacts.append(
        {
            "path": str(path.relative_to(repo_root)),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )

delivery_evidence = {
    "packet_type": "BRAINK_NATIVE_DELIVERY_EVIDENCE_V1",
    "runtime": {
        "mode": primary["runtimeMode"],
        "endpoint": primary["runtimeEndpoint"],
        "execution_policy": os.environ.get("BRAINK_EXECUTION_POLICY", "self_sustained_with_proofs"),
        "proof_generation": os.environ.get("BRAINK_PROOF_GENERATION", "enabled"),
        "alignment_audit": os.environ.get("BRAINK_ALIGNMENT_AUDIT", "enabled"),
        "il_llm_runtime_path": primary["ilLlmRuntimePath"],
        "il_llm_memory_budget_chars": os.environ.get("IL_LLM_MEMORY_BUDGET_CHARS", ""),
    },
    "alignment": {
        "weighted_alignment": module_audit.get("weightedAlignment"),
        "mathematically_aligned": module_audit.get("mathematicallyAligned"),
        "done_count": module_audit.get("doneCount"),
        "blocked_count": module_audit.get("blockedCount"),
        "not_done_count": module_audit.get("notDoneCount"),
    },
    "primary_orchestration": primary,
    "fallback_probe": fallback,
    "proof_packet": proof_packet,
    "artifacts": artifacts,
}

(build_dir / "braink_delivery_evidence.json").write_text(json.dumps(delivery_evidence, indent=2, sort_keys=True) + "\n")
print("BRAINK_DELIVERY_EVIDENCE:", build_dir / "braink_delivery_evidence.json")
PY

printf 'BRAINK orchestration complete. Artifacts in %s\n' "${BUILD_DIR}"
