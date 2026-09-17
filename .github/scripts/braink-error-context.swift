#!/usr/bin/env swift
import Foundation

enum ErrorSector: String, Codable {
    case authentication
    case externalApi
    case storage
    case routing
    case execution
    case proof
    case processing
    case unknown
}

enum FailureCause: String, Codable {
    case forbidden403
    case timeout
    case notFound404
    case invalidData
    case missingEndpoint
    case cartesianZero
    case processExit
    case noFallback
}

struct ErrorContext: Codable {
    let sector: ErrorSector
    let cause: FailureCause
    let message: String
    let timestamp: Date
    let occurrenceRate: Double
    let deadRoute: String?
    let recoveryPath: String?
    let severity: Int
    let isRecoverable: Bool
}

struct FailureAnalysis: Codable {
    let jobId: String
    let workflowName: String
    let timestamp: Date
    let errors: [ErrorContext]
    let occurrenceHistory: [Date]
    let occurrenceRate: Double
    let dominantSector: ErrorSector
    let dominantCause: FailureCause
    let recommendedActions: [String]
}

private enum CLI {
    static func readOption(_ name: String, in args: [String]) -> String? {
        guard let index = args.firstIndex(of: name), index + 1 < args.count else { return nil }
        return args[index + 1]
    }
}

struct ErrorContextEngine {
    func analyze(logText: String, jobId: String, workflowName: String, historicalDates: [Date]) -> FailureAnalysis {
        let now = Date()
        let lines = logText.split(whereSeparator: \.isNewline).map(String.init)
        let lowerLines = lines.map { $0.lowercased() }

        let postAttempts = lowerLines.filter { $0.contains("post /v1/messages?beta=true") }.count
        let forbiddenCount = lowerLines.filter { $0.contains("403 access to this endpoint is forbidden") || $0.contains("api error: 403") }.count
        let mcpCount = lowerLines.filter { $0.contains("runtime-tools-server") || $0.contains("mcp server") }.count
        let processExitCount = lowerLines.filter { $0.contains("process exited with code 1") || $0.contains("claudeerror") }.count
        let cartesianCount = lowerLines.filter { $0.contains("cartesian zero") || $0.contains("critical exception") }.count
        let hasProofArtifact = lowerLines.contains { $0.contains("proof packet generated") || $0.contains("proof artifact generated") || $0.contains("proof_packet") }
        let hasErrorContext = lowerLines.contains { $0.contains("error context") || $0.contains("sector:") || $0.contains("cause:") }
        let hasFallback = lowerLines.contains { $0.contains("fallback") || $0.contains("deterministic mode") }

        var errors: [ErrorContext] = []

        if forbiddenCount > 0 {
            errors.append(
                ErrorContext(
                    sector: .authentication,
                    cause: .forbidden403,
                    message: "External Claude/Anthropic endpoint denied authentication (403 Forbidden).",
                    timestamp: now,
                    occurrenceRate: postAttempts > 0 ? 100.0 : 100.0,
                    deadRoute: "external.claude.api",
                    recoveryPath: "self_sustained_coder",
                    severity: 9,
                    isRecoverable: true
                )
            )
        }

        if mcpCount > 0 {
            errors.append(
                ErrorContext(
                    sector: .externalApi,
                    cause: .missingEndpoint,
                    message: "MCP server dependency failed or became unreliable after external route failure.",
                    timestamp: now,
                    occurrenceRate: 100.0,
                    deadRoute: "external.runtime-tools.mcp",
                    recoveryPath: "local_proof_generation",
                    severity: 8,
                    isRecoverable: true
                )
            )
        }

        if processExitCount > 0 {
            errors.append(
                ErrorContext(
                    sector: .execution,
                    cause: .processExit,
                    message: "Process terminated with exit code 1 due to upstream ClaudeError escalation.",
                    timestamp: now,
                    occurrenceRate: 100.0,
                    deadRoute: "external.claude.process",
                    recoveryPath: "deterministic_local_mode",
                    severity: 8,
                    isRecoverable: true
                )
            )
        }

        if cartesianCount > 0 {
            errors.append(
                ErrorContext(
                    sector: .storage,
                    cause: .cartesianZero,
                    message: "Storage/alignment layer signaled cartesian zero in cell alignment.",
                    timestamp: now,
                    occurrenceRate: 100.0,
                    deadRoute: "storage.cell_alignment",
                    recoveryPath: "stack_audit",
                    severity: 7,
                    isRecoverable: true
                )
            )
        }

        if forbiddenCount > 0 && processExitCount > 0 && !hasFallback {
            errors.append(
                ErrorContext(
                    sector: .routing,
                    cause: .noFallback,
                    message: "No fallback routing was activated after authentication/process failure.",
                    timestamp: now,
                    occurrenceRate: 100.0,
                    deadRoute: "claude.primary.route",
                    recoveryPath: "illlm_bundle",
                    severity: 10,
                    isRecoverable: true
                )
            )
        }

        if processExitCount > 0 && !hasProofArtifact {
            errors.append(
                ErrorContext(
                    sector: .proof,
                    cause: .invalidData,
                    message: "Proof packet artifacts were not generated on failure.",
                    timestamp: now,
                    occurrenceRate: 100.0,
                    deadRoute: "proof.artifact.pipeline",
                    recoveryPath: "proof_packet",
                    severity: 7,
                    isRecoverable: true
                )
            )
        }

        if processExitCount > 0 && !hasErrorContext {
            errors.append(
                ErrorContext(
                    sector: .processing,
                    cause: .invalidData,
                    message: "Error context propagation missing (sector/cause analysis absent in failure stream).",
                    timestamp: now,
                    occurrenceRate: 100.0,
                    deadRoute: "error.context.pipeline",
                    recoveryPath: "braink_error_context_engine",
                    severity: 8,
                    isRecoverable: true
                )
            )
        }

        let history = (historicalDates + errors.map(\.timestamp)).sorted()
        let dominantSector = dominantValue(errors.map(\.sector)) ?? .unknown
        let dominantCause = dominantValue(errors.map(\.cause)) ?? .invalidData
        let analysisRate = errors.isEmpty ? 0.0 : 100.0

        return FailureAnalysis(
            jobId: jobId,
            workflowName: workflowName,
            timestamp: now,
            errors: errors,
            occurrenceHistory: history,
            occurrenceRate: analysisRate,
            dominantSector: dominantSector,
            dominantCause: dominantCause,
            recommendedActions: recommendedActions(from: errors)
        )
    }

    private func recommendedActions(from errors: [ErrorContext]) -> [String] {
        var actions: [String] = []
        for error in errors {
            switch error.cause {
            case .forbidden403:
                actions.append("Disable external Claude/Anthropic route for CI and force BRAINK local orchestration.")
            case .missingEndpoint:
                actions.append("Treat runtime-tools MCP as optional; continue with local deterministic proof generation.")
            case .processExit:
                actions.append("Capture process-exit context and route to self_sustained_coder + kex_hyperdrive fallback.")
            case .cartesianZero:
                actions.append("Run stack_audit and rebuild relational index mapping before next attempt.")
            case .noFallback:
                actions.append("Enforce multi-level fallback policy (self_sustained_coder -> illlm_bundle -> proof_packet).")
            case .invalidData:
                actions.append("Always emit error-context and proof artifacts even on controlled failure.")
            case .timeout:
                actions.append("Introduce bounded retries with timeout-specific fallback.")
            case .notFound404:
                actions.append("Verify endpoint and route registry for missing resources.")
            }
        }
        var deduped: [String] = []
        var seen: Set<String> = []
        for action in actions where !seen.contains(action) {
            deduped.append(action)
            seen.insert(action)
        }
        return deduped
    }

    private func dominantValue<T: Hashable>(_ values: [T]) -> T? {
        let counts = values.reduce(into: [T: Int]()) { partialResult, value in
            partialResult[value, default: 0] += 1
        }
        return counts.max(by: { lhs, rhs in
            lhs.value < rhs.value
        })?.key
    }
}

private func parseHistoricalDates(from path: String?) -> [Date] {
    guard let path, !path.isEmpty, let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return [] }
    guard let strings = try? JSONDecoder().decode([String].self, from: data) else { return [] }
    let formatter = ISO8601DateFormatter()
    return strings.compactMap { formatter.date(from: $0) }
}

private func readLogText(path: String?) -> String {
    if let path, !path.isEmpty, let text = try? String(contentsOfFile: path, encoding: .utf8) {
        return text
    }
    let data = FileHandle.standardInput.readDataToEndOfFile()
    if data.isEmpty { return "" }
    return String(decoding: data, as: UTF8.self)
}

private func ensureParentDirectory(for outputPath: String) throws {
    let outputURL = URL(fileURLWithPath: outputPath)
    let parent = outputURL.deletingLastPathComponent()
    try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
}

let args = CommandLine.arguments
let inputPath = CLI.readOption("--input-log", in: args)
let outputPath = CLI.readOption("--output", in: args) ?? "reports/braink_failure_analysis.json"
let historyPath = CLI.readOption("--history", in: args)
let jobId = CLI.readOption("--job-id", in: args) ?? "unknown"
let workflowName = CLI.readOption("--workflow-name", in: args) ?? "BRAINK Native CI/CD"

let logText = readLogText(path: inputPath)
let historicalDates = parseHistoricalDates(from: historyPath)
let engine = ErrorContextEngine()
let analysis = engine.analyze(logText: logText, jobId: jobId, workflowName: workflowName, historicalDates: historicalDates)

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
encoder.dateEncodingStrategy = .iso8601
let encoded = try encoder.encode(analysis)
try ensureParentDirectory(for: outputPath)
try encoded.write(to: URL(fileURLWithPath: outputPath))

print("ERROR_CONTEXT_STATUS: COMPLETED")
print("ERROR_CONTEXT_OUTPUT: \(outputPath)")
print("ERROR_CONTEXT_ERRORS: \(analysis.errors.count)")
print("ERROR_CONTEXT_OCCURRENCE_RATE: \(String(format: "%.2f", analysis.occurrenceRate))")
