import Foundation

enum EngineTypeIndex: String {
    case engine_neg2_prep = "ENGINE_NEG2_PREPARATION"
    case engine_1_self_sustained = "ENGINE_1_SELF_SUSTAINED"
    case engine_1_hyperdrive = "ENGINE_1_HYPERDRIVE"
    case engine_1_il_llm = "ENGINE_1_IL_LLM"
    case engine_2_coordination = "ENGINE_2_COORDINATION"
    case engine_3_proof = "ENGINE_3_PROOF"
}

final class BRAINKZeroLessEngineOrchestrator {
    func executeMultiEngine(route: ZeroLessRouteIdentifier, input: String) async -> String {
        let engines = enginesForRoute(route)
        let observerInput = input.trimmingCharacters(in: .whitespacesAndNewlines)
        return [
            "MULTI_ENGINE_RESULT",
            "ROUTE=\(route.rawValue)",
            "ENGINES=\(engines.map { $0.rawValue }.joined(separator: ","))",
            "OBSERVER_INPUT=\(observerInput)"
        ].joined(separator: "::")
    }

    private func enginesForRoute(_ route: ZeroLessRouteIdentifier) -> [EngineTypeIndex] {
        switch route {
        case .route_engine_self_sustained:
            return [.engine_neg2_prep, .engine_1_self_sustained, .engine_2_coordination, .engine_3_proof]
        case .route_engine_il_llm_local:
            return [.engine_neg2_prep, .engine_1_il_llm, .engine_2_coordination, .engine_3_proof]
        case .route_engine_deterministic_proof:
            return [.engine_neg2_prep, .engine_1_hyperdrive, .engine_2_coordination, .engine_3_proof]
        case .route_engine_multi_observer:
            return [.engine_neg2_prep, .engine_1_self_sustained, .engine_1_il_llm, .engine_2_coordination, .engine_3_proof]
        case .route_dead_claude_api, .route_dead_mcp_server, .route_dead_copilot_external:
            return [.engine_neg2_prep, .engine_2_coordination, .engine_3_proof]
        }
    }
}
