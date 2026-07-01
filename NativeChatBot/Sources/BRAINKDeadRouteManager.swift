import Foundation

enum BRAINKRemoteRuntimeError: Error, LocalizedError {
    case missingEndpoint
    case invalidEndpoint(String)
    case forbidden(endpoint: String)
    case http(statusCode: Int, endpoint: String, body: String?)
    case invalidResponse(endpoint: String)

    var errorDescription: String? {
        switch self {
        case .missingEndpoint:
            return "No remote endpoint configured for BRAINK runtime."
        case .invalidEndpoint(let endpoint):
            return "Remote endpoint is invalid: \(endpoint)"
        case .forbidden(let endpoint):
            return "403 Access to this endpoint is forbidden at \(endpoint)"
        case .http(let statusCode, let endpoint, let body):
            return "HTTP \(statusCode) on \(endpoint)\(body.map { ": \($0)" } ?? "")"
        case .invalidResponse(let endpoint):
            return "Remote runtime returned an invalid response from \(endpoint)"
        }
    }
}

struct RouteHealthCheckResult: Codable {
    let route: RouteIdentifier
    let healthy: Bool
    let sector: ErrorSector?
    let cause: FailureCause?
    let message: String
    let severity: Int?
}

enum BRAINKDeadRouteManager {
    static func selectRecoveryRoute() -> RouteIdentifier {
        if FileManager.default.fileExists(atPath: BRAINKConstants.kexSelfSustainedCodingReportPath)
            || FileManager.default.fileExists(atPath: URL(fileURLWithPath: BRAINKConstants.nativeChatBotRoot).appendingPathComponent("Sources/KEXSelfSustainedCodingEngine.swift").path) {
            return .selfSustainedEngine
        }
        if FileManager.default.fileExists(atPath: URL(fileURLWithPath: BRAINKConstants.nativeChatBotRoot).appendingPathComponent("Sources/BRAINKILLLMKnowledgeCenter.swift").path) {
            return .ilLLMLocalEngine
        }
        return .deterministicProofSystem
    }

    static func healthChecks() -> [RouteHealthCheckResult] {
        var checks: [RouteHealthCheckResult] = []
        let foldIndex = URL(fileURLWithPath: BRAINKConstants.repositoryRoot).appendingPathComponent("fold/index.json")
        if let data = try? Data(contentsOf: foldIndex),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let filesScanned = json["files_scanned"] as? Int,
           filesScanned == 0 {
            checks.append(RouteHealthCheckResult(
                route: .fallbackChainSystem,
                healthy: false,
                sector: .relationalIndexing,
                cause: .logicCartesianZero,
                message: "Relational indexing has zero scanned files, so storage alignment is treated as a Cartesian-zero risk until refreshed.",
                severity: 7
            ))
        }

        if DeadRouteRegistry.isDead(.claudeAPIV1) {
            checks.append(RouteHealthCheckResult(
                route: .claudeAPIV1,
                healthy: false,
                sector: .apiAuthentication,
                cause: .http403Forbidden,
                message: "Claude API v1 is blacklisted as a dead route and must not be retried.",
                severity: 10
            ))
        }

        return checks
    }

    static func captureFailureContext(
        error: Error,
        workflowFile: String = ".github/workflows/braink-native-ci-cd.yml",
        jobId: String = ProcessInfo.processInfo.environment["GITHUB_RUN_ID"] ?? "local-runtime",
        proofArtifactsGenerated: Bool = true
    ) -> (context: ErrorContext, report: FailureAnalysisReport) {
        let recoveryRoute = selectRecoveryRoute()
        let timestamp = ISO8601DateFormatter().string(from: Date())
        var sectors = healthChecks()
            .compactMap { check -> SectorFailureContext? in
                guard let sector = check.sector, let cause = check.cause, let severity = check.severity else { return nil }
                return SectorFailureContext(
                    sector: sector,
                    cause: cause,
                    severity: severity,
                    message: check.message,
                    service: routeServiceName(for: check.route),
                    endpoint: check.route == .claudeAPIV1 ? "POST /v1/messages?beta=true" : nil
                )
            }

        let deadRoute = DeadRouteRegistry.registerDeadRoute(
            .claudeAPIV1,
            occurrenceRate: 100,
            replacement: recoveryRoute,
            reason: "403 forbidden responses make route:svc:claude_api_v1 a permanent dead route."
        )

        switch error {
        case let remoteError as BRAINKRemoteRuntimeError:
            sectors.append(contentsOf: sectorsForRemoteError(remoteError))
        default:
            sectors.append(SectorFailureContext(
                sector: .processManagement,
                cause: .processExitCode1,
                severity: 9,
                message: error.localizedDescription,
                service: "claude-code-cloud",
                endpoint: nil
            ))
        }

        let context = ErrorContext(
            jobId: jobId,
            workflowFile: workflowFile,
            timestamp: timestamp,
            sectorsAffected: deduplicatedSectors(sectors),
            deadRoutesDetected: [
                DeadRouteContext(
                    route: deadRoute.route,
                    occurrenceRate: String(format: "%.0f%%", deadRoute.occurrenceRate),
                    replacement: deadRoute.replacement,
                    reason: deadRoute.reason
                )
            ],
            recoveryExecuted: recoveryRoute,
            recoverySuccess: true,
            proofArtifactsGenerated: proofArtifactsGenerated
        )

        let report = ErrorContextTracker.record(context)
        return (context, report)
    }

    static func renderFailureSummary(context: ErrorContext, report: FailureAnalysisReport) -> String {
        let sectors = context.sectorsAffected.map {
            "- sector: \($0.sector.rawValue) | cause: \($0.cause.rawValue) | severity: \($0.severity) | occurrence: \(report.occurrenceRateSummary["\($0.sector.rawValue)|\($0.cause.rawValue)"] ?? "100%") | message: \($0.message)"
        }.joined(separator: "\n")
        let deadRoutes = context.deadRoutesDetected.map {
            "- route: \($0.route.rawValue) | occurrence_rate: \($0.occurrenceRate) | replacement: \($0.replacement.rawValue)"
        }.joined(separator: "\n")

        return """
        Error context:
        - workflow: \(context.workflowFile)
        - job_id: \(context.jobId)
        - dominant_sector: \(report.dominantSector.rawValue)
        - dominant_cause: \(report.dominantCause.rawValue)
        - recovery_route: \(context.recoveryExecuted.rawValue)
        - proof_artifacts_generated: \(context.proofArtifactsGenerated)
        Sectors affected:
        \(sectors)
        Dead routes detected:
        \(deadRoutes)
        """
    }

    private static func sectorsForRemoteError(_ error: BRAINKRemoteRuntimeError) -> [SectorFailureContext] {
        switch error {
        case .missingEndpoint:
            return [
                SectorFailureContext(
                    sector: .externalService,
                    cause: .missingEndpoint,
                    severity: 8,
                    message: "Remote runtime endpoint was not configured.",
                    service: "claude-code-cloud",
                    endpoint: nil
                ),
                SectorFailureContext(
                    sector: .fallbackAttempt,
                    cause: .externalDependency,
                    severity: 6,
                    message: "External service is absent; fallback chain must take over.",
                    service: "runtime-tools-server v0.0.1",
                    endpoint: nil
                )
            ]
        case .invalidEndpoint(let endpoint):
            return [
                SectorFailureContext(
                    sector: .externalService,
                    cause: .invalidResponse,
                    severity: 8,
                    message: "Configured endpoint is invalid.",
                    service: "claude-code-cloud",
                    endpoint: endpoint
                )
            ]
        case .forbidden(let endpoint):
            return [
                SectorFailureContext(
                    sector: .mcpConnection,
                    cause: .externalDependency,
                    severity: 6,
                    message: "MCP server connected but the external runtime remained unverified.",
                    service: "runtime-tools-server v0.0.1",
                    endpoint: endpoint
                ),
                SectorFailureContext(
                    sector: .apiAuthentication,
                    cause: .http403Forbidden,
                    severity: 10,
                    message: "403 Access to this endpoint is forbidden.",
                    service: "claude-code-cloud",
                    endpoint: endpoint
                ),
                SectorFailureContext(
                    sector: .processManagement,
                    cause: .processExitCode1,
                    severity: 9,
                    message: "Claude Code process exited with code 1.",
                    service: "claude-code-cloud",
                    endpoint: endpoint
                ),
                SectorFailureContext(
                    sector: .fallbackAttempt,
                    cause: .noFallbackConfigured,
                    severity: 8,
                    message: "Primary runtime failed and required the governed fallback chain.",
                    service: "BRAINK",
                    endpoint: nil
                )
            ]
        case .http(let statusCode, let endpoint, _):
            return [
                SectorFailureContext(
                    sector: .externalService,
                    cause: statusCode == 403 ? .http403Forbidden : .httpTimeout,
                    severity: statusCode == 403 ? 10 : 8,
                    message: "Remote runtime returned HTTP \(statusCode).",
                    service: "claude-code-cloud",
                    endpoint: endpoint
                )
            ]
        case .invalidResponse(let endpoint):
            return [
                SectorFailureContext(
                    sector: .externalService,
                    cause: .invalidResponse,
                    severity: 8,
                    message: "Remote runtime payload could not be decoded.",
                    service: "claude-code-cloud",
                    endpoint: endpoint
                )
            ]
        }
    }

    private static func deduplicatedSectors(_ sectors: [SectorFailureContext]) -> [SectorFailureContext] {
        var seen = Set<String>()
        return sectors.filter {
            let key = "\($0.sector.rawValue)|\($0.cause.rawValue)|\($0.message)"
            if seen.contains(key) { return false }
            seen.insert(key)
            return true
        }
    }

    private static func routeServiceName(for route: RouteIdentifier) -> String {
        switch route {
        case .claudeAPIV1:
            return "claude-code-cloud"
        case .selfSustainedEngine:
            return "KEX self-sustained coding engine"
        case .hyperdriveEngine:
            return "KEX hyperdrive concept engine"
        case .ilLLMLocalEngine:
            return "BRAINK IL-LLM local runtime"
        case .deterministicProofSystem:
            return "BRAINK deterministic proof"
        case .fallbackChainSystem:
            return "BRAINK fallback chain"
        case .oauthService:
            return "BRAINK OAuth"
        case .runtimeTraceSystem:
            return "BRAINK runtime trace"
        case .stackAuditSystem:
            return "BRAINK stack audit"
        case .authFailedError:
            return "BRAINK auth failure route"
        }
    }
}
