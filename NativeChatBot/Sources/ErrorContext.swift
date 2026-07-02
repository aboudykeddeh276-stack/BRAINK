import Foundation

enum BRAINKErrorSector: String, Codable {
    case authentication = "sector:authentication"
    case externalAPI = "sector:external_api"
    case routing = "sector:routing"
    case execution = "sector:execution"
    case governance = "sector:governance"
}

enum BRAINKFailureCause: String, Codable {
    case http403Forbidden = "cause:http:403_forbidden"
    case httpTimeout = "cause:http:timeout"
    case remoteUnavailable = "cause:system:remote_unavailable"
    case processExit = "cause:os:process_exit"
    case fallback = "cause:system:fallback"
}

struct BRAINKErrorContext: Codable {
    let id: String
    let sector: BRAINKErrorSector
    let cause: BRAINKFailureCause
    let stage: String
    let message: String
    let timestamp: String
    let deadRoute: String?
    let recoveryRoute: String?
    let metadata: [String: String]
}

enum BRAINKErrorContextFactory {
    static func make(
        sector: BRAINKErrorSector,
        cause: BRAINKFailureCause,
        stage: String,
        message: String,
        deadRoute: String?,
        recoveryRoute: String?,
        metadata: [String: String] = [:]
    ) -> BRAINKErrorContext {
        BRAINKErrorContext(
            id: "err_ctx_\(Int(Date().timeIntervalSince1970))",
            sector: sector,
            cause: cause,
            stage: stage,
            message: message,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            deadRoute: deadRoute,
            recoveryRoute: recoveryRoute,
            metadata: metadata
        )
    }

    static func toCompactString(_ context: BRAINKErrorContext) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        guard let data = try? encoder.encode(context),
              let json = String(data: data, encoding: .utf8) else {
            return "error_context_serialization_failed"
        }
        return json
    }
}
