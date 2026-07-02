import Foundation

struct SectorFailureContext: Codable, Hashable {
    let sector: ErrorSector
    let cause: FailureCause
    let severity: Int
    let message: String
    let service: String?
    let endpoint: String?
}

struct DeadRouteContext: Codable, Hashable {
    let route: RouteIdentifier
    let occurrenceRate: String
    let replacement: RouteIdentifier
    let reason: String
}

struct ErrorContext: Codable, Hashable {
    let jobId: String
    let workflowFile: String
    let timestamp: String
    let sectorsAffected: [SectorFailureContext]
    let deadRoutesDetected: [DeadRouteContext]
    let recoveryExecuted: RouteIdentifier
    let recoverySuccess: Bool
    let proofArtifactsGenerated: Bool

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case workflowFile = "workflow_file"
        case timestamp
        case sectorsAffected = "sectors_affected"
        case deadRoutesDetected = "dead_routes_detected"
        case recoveryExecuted = "recovery_executed"
        case recoverySuccess = "recovery_success"
        case proofArtifactsGenerated = "proof_artifacts_generated"
    }
}

struct ErrorContextEnvelope: Codable {
    let errorContext: ErrorContext

    enum CodingKeys: String, CodingKey {
        case errorContext = "error_context"
    }
}

struct FailureAnalysisReport: Codable {
    let errorContext: ErrorContext
    let dominantSector: ErrorSector
    let dominantCause: FailureCause
    let occurrenceRateSummary: [String: String]
    let recommendations: [String]
    let generatedAt: String

    enum CodingKeys: String, CodingKey {
        case errorContext = "error_context"
        case dominantSector = "dominant_sector"
        case dominantCause = "dominant_cause"
        case occurrenceRateSummary = "occurrence_rate_summary"
        case recommendations
        case generatedAt = "generated_at"
    }
}

enum OccurrenceRateCalculator {
    static func occurrenceRate(for sector: ErrorSector, cause: FailureCause, history: [ErrorContext]) -> String {
        let matching = history.filter { context in
            context.sectorsAffected.contains { $0.sector == sector && $0.cause == cause }
        }.count
        guard !history.isEmpty else { return matching == 0 ? "0%" : "100%" }
        let percentage = (Double(matching) / Double(history.count)) * 100
        return String(format: "%.0f%%", percentage)
    }
}

enum ErrorContextTracker {
    static func loadHistory() -> [ErrorContext] {
        let url = URL(fileURLWithPath: BRAINKConstants.errorContextHistoryPath)
        guard let data = try? Data(contentsOf: url),
              let history = try? JSONDecoder().decode([ErrorContext].self, from: data) else {
            return []
        }
        return history
    }

    @discardableResult
    static func record(_ context: ErrorContext) -> FailureAnalysisReport {
        var history = loadHistory()
        history.append(context)
        write(history, to: BRAINKConstants.errorContextHistoryPath)
        write(ErrorContextEnvelope(errorContext: context), to: BRAINKConstants.errorContextArtifactPath)

        let report = analyze(context, history: history)
        write(report, to: BRAINKConstants.failureAnalysisReportPath)
        return report
    }

    static func analyze(_ context: ErrorContext, history: [ErrorContext]? = nil) -> FailureAnalysisReport {
        let resolvedHistory = history ?? loadHistory()
        let dominantFailure = context.sectorsAffected.max { lhs, rhs in lhs.severity < rhs.severity }
            ?? SectorFailureContext(
                sector: .fallbackAttempt,
                cause: .noFallbackConfigured,
                severity: 0,
                message: "No failure context recorded.",
                service: nil,
                endpoint: nil
            )

        var occurrenceRateSummary: [String: String] = [:]
        for failure in context.sectorsAffected {
            occurrenceRateSummary["\(failure.sector.rawValue)|\(failure.cause.rawValue)"] =
                OccurrenceRateCalculator.occurrenceRate(for: failure.sector, cause: failure.cause, history: resolvedHistory)
        }

        let recommendations = context.deadRoutesDetected.map {
            "Route around \($0.route.rawValue) using \($0.replacement.rawValue) (\($0.reason))."
        } + context.sectorsAffected.map {
            "Review \($0.sector.rawValue) because \($0.cause.rawValue) triggered: \($0.message)"
        }

        return FailureAnalysisReport(
            errorContext: context,
            dominantSector: dominantFailure.sector,
            dominantCause: dominantFailure.cause,
            occurrenceRateSummary: occurrenceRateSummary,
            recommendations: recommendations,
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
    }

    private static func write<T: Codable>(_ value: T, to path: String) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(value) else { return }
        let url = URL(fileURLWithPath: path)
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url)
    }
}
