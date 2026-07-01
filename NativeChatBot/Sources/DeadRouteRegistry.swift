import Foundation

struct DeadRouteResolution {
    let deadRoute: String
    let sector: BRAINKErrorSector
    let cause: BRAINKFailureCause
    let recoveryRoute: BRAINKRouteIdentifier
}

enum DeadRouteRegistry {
    static let claudeAPIv1 = "route:svc:claude_api_v1"

    private static let registry: [String: DeadRouteResolution] = [
        claudeAPIv1: DeadRouteResolution(
            deadRoute: claudeAPIv1,
            sector: .authentication,
            cause: .http403Forbidden,
            recoveryRoute: .selfSustainedCoder
        ),
        "route:svc:mcp_runtime_tools": DeadRouteResolution(
            deadRoute: "route:svc:mcp_runtime_tools",
            sector: .externalAPI,
            cause: .remoteUnavailable,
            recoveryRoute: .illlmQuery
        )
    ]

    static func resolve(deadRoute: String?) -> DeadRouteResolution? {
        guard let deadRoute else { return nil }
        return registry[deadRoute]
    }
}
