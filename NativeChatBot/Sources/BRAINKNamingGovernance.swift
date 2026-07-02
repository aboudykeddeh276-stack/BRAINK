import Foundation

enum RouteIdentifier: String, Codable, CaseIterable {
    case oauthService = "route:svc:oauth"
    case claudeAPIV1 = "route:svc:claude_api_v1"
    case selfSustainedEngine = "route:engine:self_sustained"
    case hyperdriveEngine = "route:engine:hyperdrive"
    case ilLLMLocalEngine = "route:engine:il_llm_local"
    case deterministicProofSystem = "route:sys:deterministic_proof"
    case fallbackChainSystem = "route:sys:fallback_chain"
    case runtimeTraceSystem = "route:sys:runtime_trace"
    case stackAuditSystem = "route:sys:stack_audit"
    case authFailedError = "route:err:auth_failed"

    var contextualDescription: String {
        switch self {
        case .oauthService:
            return "Explicit OAuth authentication handoff service."
        case .claudeAPIV1:
            return "Legacy Claude API v1 external service route."
        case .selfSustainedEngine:
            return "Primary local self-sustained coding engine."
        case .hyperdriveEngine:
            return "KEX Hyperdrive concept and calibration engine."
        case .ilLLMLocalEngine:
            return "Secondary local IL-LLM deterministic engine."
        case .deterministicProofSystem:
            return "Deterministic proof generator with no external dependencies."
        case .fallbackChainSystem:
            return "Recovery orchestrator that selects the next safe route."
        case .runtimeTraceSystem:
            return "Runtime trace and route introspection system."
        case .stackAuditSystem:
            return "Line-for-line module alignment audit system."
        case .authFailedError:
            return "Explicit terminal route for authentication failures."
        }
    }

    var legacyAliases: Set<String> {
        switch self {
        case .oauthService:
            return ["auth.oauth"]
        case .claudeAPIV1:
            return ["remote_runtime", "claude_api", "claude-code-cloud"]
        case .selfSustainedEngine:
            return ["self_sustained_coder"]
        case .hyperdriveEngine:
            return ["kex_hyperdrive"]
        case .ilLLMLocalEngine:
            return ["general", "illlm_bundle", "illlm_bootstrap", "illlm_query", "inner_runtime"]
        case .deterministicProofSystem:
            return ["proof", "proof_packet", "evidence"]
        case .fallbackChainSystem:
            return ["system.fallback"]
        case .runtimeTraceSystem:
            return ["runtime_trace"]
        case .stackAuditSystem:
            return ["stack_audit", "align", "align-check"]
        case .authFailedError:
            return ["auth_failed"]
        }
    }

    static func fromLegacyRoute(_ route: String) -> RouteIdentifier? {
        allCases.first { $0.legacyAliases.contains(route) || $0.rawValue == route }
    }
}

enum ErrorSector: String, Codable, CaseIterable {
    case apiAuthentication = "sect_auth:api_authentication"
    case externalService = "sect_api:external_service"
    case mcpConnection = "sect_api:mcp_connection"
    case relationalIndexing = "sect_storage:relational_indexing"
    case processManagement = "sect_execution:process_management"
    case fallbackAttempt = "sect_recovery:fallback_attempt"
}

enum FailureCause: String, Codable, CaseIterable {
    case http403Forbidden = "cause:http:403_forbidden"
    case httpTimeout = "cause:http:timeout"
    case logicCartesianZero = "cause:logic:cartesian_zero"
    case processExitCode1 = "cause:os:process_exit:code_1"
    case externalDependency = "cause:system:external_dependency"
    case noFallbackConfigured = "cause:system:no_fallback_configured"
    case missingEndpoint = "cause:system:missing_endpoint"
    case invalidResponse = "cause:system:invalid_response"
}

struct DeadRouteRecord: Codable, Hashable {
    let route: RouteIdentifier
    let occurrenceRate: Double
    let replacement: RouteIdentifier
    let reason: String
    let firstDetectedAt: String
    let lastDetectedAt: String
}

private struct DeadRouteRegistrySnapshot: Codable {
    let deadRoutes: [DeadRouteRecord]
    let generatedAt: String
}

enum DeadRouteRegistry {
    static func load() -> [DeadRouteRecord] {
        let url = URL(fileURLWithPath: BRAINKConstants.deadRouteRegistryPath)
        guard let data = try? Data(contentsOf: url),
              let snapshot = try? JSONDecoder().decode(DeadRouteRegistrySnapshot.self, from: data) else {
            return seededDeadRoutes()
        }
        return mergedSeededRoutes(snapshot.deadRoutes)
    }

    static func isDead(_ route: RouteIdentifier) -> Bool {
        load().contains { $0.route == route }
    }

    @discardableResult
    static func registerDeadRoute(
        _ route: RouteIdentifier,
        occurrenceRate: Double,
        replacement: RouteIdentifier,
        reason: String,
        detectedAt: Date = Date()
    ) -> DeadRouteRecord {
        let timestamp = ISO8601DateFormatter().string(from: detectedAt)
        var routes = load()
        if let index = routes.firstIndex(where: { $0.route == route }) {
            let current = routes[index]
            routes[index] = DeadRouteRecord(
                route: route,
                occurrenceRate: max(current.occurrenceRate, occurrenceRate),
                replacement: replacement,
                reason: reason,
                firstDetectedAt: current.firstDetectedAt,
                lastDetectedAt: timestamp
            )
        } else {
            routes.append(DeadRouteRecord(
                route: route,
                occurrenceRate: occurrenceRate,
                replacement: replacement,
                reason: reason,
                firstDetectedAt: timestamp,
                lastDetectedAt: timestamp
            ))
        }
        persist(routes)
        return routes.first { $0.route == route }!
    }

    private static func seededDeadRoutes() -> [DeadRouteRecord] {
        let seededAt = "2026-07-01T13:09:54Z"
        return [
            DeadRouteRecord(
                route: .claudeAPIV1,
                occurrenceRate: 100,
                replacement: .selfSustainedEngine,
                reason: "Permanent 403 failure on POST /v1/messages?beta=true from claude-code-cloud.",
                firstDetectedAt: seededAt,
                lastDetectedAt: seededAt
            )
        ]
    }

    private static func mergedSeededRoutes(_ routes: [DeadRouteRecord]) -> [DeadRouteRecord] {
        var merged = routes
        for seeded in seededDeadRoutes() where !merged.contains(where: { $0.route == seeded.route }) {
            merged.append(seeded)
        }
        return merged.sorted { $0.route.rawValue < $1.route.rawValue }
    }

    private static func persist(_ routes: [DeadRouteRecord]) {
        let snapshot = DeadRouteRegistrySnapshot(
            deadRoutes: mergedSeededRoutes(routes),
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(snapshot) else { return }
        let url = URL(fileURLWithPath: BRAINKConstants.deadRouteRegistryPath)
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url)
    }
}
