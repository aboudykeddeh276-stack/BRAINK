import Foundation

enum BRAINKZeroLessIndex: String, CaseIterable {
    case state_negative_three = "EXPLICIT_STATE_NEGATIVE_3"
    case state_negative_two = "EXPLICIT_STATE_NEGATIVE_2"
    case observer_singular = "EXPLICIT_OBSERVER_SINGULAR_1"
    case state_positive_two = "EXPLICIT_STATE_POSITIVE_2"
    case state_positive_three = "EXPLICIT_STATE_POSITIVE_3"

    static let allowedIndices: [BRAINKZeroLessIndex] = BRAINKZeroLessIndex.allCases

    var hardwareSlotBoundary: String {
        "HARDWARE_SLOT_BOUNDARY_\(rawValue)"
    }
}

enum ZeroLessRouteIdentifier: String {
    case route_dead_claude_api = "route:dead:claude_api_403"
    case route_dead_mcp_server = "route:dead:mcp_fragile"
    case route_dead_copilot_external = "route:dead:copilot_external"
    case route_engine_self_sustained = "route:engine:self_sustained"
    case route_engine_il_llm_local = "route:engine:il_llm_local"
    case route_engine_deterministic_proof = "route:engine:deterministic_proof"
    case route_engine_multi_observer = "route:engine:multi_observer"
}

extension ZeroLessRouteIdentifier {
    var deadRoute: DeadRouteIndex? {
        DeadRouteIndex(rawValue: rawValue)
    }
}

enum RuntimeProcessStage: String {
    case stage_input_reception = "PROC_STAGE_NEG3_INPUT_RECEPTION"
    case stage_input_validation = "PROC_STAGE_NEG3_VALIDATION"
    case stage_route_classification = "PROC_STAGE_NEG2_ROUTE_CLASS"
    case stage_engine_selection = "PROC_STAGE_NEG2_ENGINE_SELECT"
    case stage_execution_dispatch = "PROC_STAGE_1_EXECUTE"
    case stage_engine_coordination = "PROC_STAGE_1_COORDINATE"
    case stage_result_generation = "PROC_STAGE_2_RESULT_GEN"
    case stage_output_serialization = "PROC_STAGE_2_SERIALIZE"
    case stage_proof_generation = "PROC_STAGE_3_PROOF_GEN"
    case stage_response_delivery = "PROC_STAGE_3_RESPONSE"
}

enum ErrorSectorIndex: String {
    case sect_neg3_input = "SECTOR_NEG3_INPUT_HANDLING"
    case sect_neg2_routing = "SECTOR_NEG2_ROUTING_LAYER"
    case sect_1_execution = "SECTOR_1_EXECUTION_BRIDGE"
    case sect_2_output = "SECTOR_2_OUTPUT_GENERATION"
    case sect_3_verification = "SECTOR_3_PROOF_VERIFICATION"
}

enum FailureCauseIndex: String {
    case cause_neg3_malformed = "CAUSE_NEG3_MALFORMED_INPUT"
    case cause_neg2_invalid_route = "CAUSE_NEG2_INVALID_ROUTE"
    case cause_1_execution_failed = "CAUSE_1_EXECUTION_FAILED"
    case cause_2_serialization_failed = "CAUSE_2_SERIALIZATION_FAILED"
    case cause_3_proof_invalid = "CAUSE_3_PROOF_INVALID"
}

struct ZeroLessErrorContext {
    let processingStage: RuntimeProcessStage
    let errorSector: ErrorSectorIndex
    let failureCause: FailureCauseIndex
    let message: String
    let hardwareSlotBoundary: String
    let recoveryPath: String?
    let occurrenceRate: Double
    let timestamp: Date

    func toLiteralStateMapping() -> String {
        """
        ERROR_CONTEXT_LITERAL_STATE::
        STAGE=\(processingStage.rawValue)::
        SECTOR=\(errorSector.rawValue)::
        CAUSE=\(failureCause.rawValue)::
        MESSAGE=\(message)::
        SLOT=\(hardwareSlotBoundary)::
        RECOVERY=\(recoveryPath ?? "NONE")::
        OCCURRENCE_RATE=\(String(format: "%.4f", occurrenceRate))::
        TIMESTAMP=\(ISO8601DateFormatter().string(from: timestamp))
        """
    }
}

enum DeadRouteIndex: String {
    case route_dead_claude_api = "route:dead:claude_api_403"
    case route_dead_mcp_server = "route:dead:mcp_fragile"
    case route_dead_copilot_external = "route:dead:copilot_external"
}

enum RecoveryRouteIndex: String {
    case recovery_1_self_sustained = "route:recovery:self_sustained_coder"
    case recovery_2_il_llm_local = "route:recovery:il_llm_local"
    case recovery_3_deterministic = "route:recovery:deterministic_proof"
}

enum ZeroLessIndexEngine {
    static func mapToUncompressedLiteralState(index: BRAINKZeroLessIndex) -> String {
        "TOTAL_METRIC_VALUE_STREAM::\(index.hardwareSlotBoundary)"
    }
}

struct ZeroLessDeadRouteRegistry {
    struct Metadata {
        let sector: ErrorSectorIndex
        let cause: FailureCauseIndex
        let recovery: RecoveryRouteIndex
        let occurrenceRate: Double
    }

    static let defaultMetadata = Metadata(
        sector: .sect_neg3_input,
        cause: .cause_neg3_malformed,
        recovery: .recovery_1_self_sustained,
        occurrenceRate: 1.0
    )

    static let deadRoutes: [DeadRouteIndex: Metadata] = [
        .route_dead_claude_api: defaultMetadata,
        .route_dead_mcp_server: Metadata(
            sector: .sect_neg3_input,
            cause: .cause_neg3_malformed,
            recovery: .recovery_2_il_llm_local,
            occurrenceRate: 0.95
        ),
        .route_dead_copilot_external: Metadata(
            sector: .sect_neg2_routing,
            cause: .cause_neg2_invalid_route,
            recovery: .recovery_3_deterministic,
            occurrenceRate: 1.0
        )
    ]

    static func getRecoveryPath(_ route: DeadRouteIndex) -> RecoveryRouteIndex? {
        deadRoutes[route]?.recovery
    }
}

final class BRAINKZeroLessRuntime {
    private struct RoutePattern {
        let route: ZeroLessRouteIdentifier
        let phraseTokens: [[String]]
        let requiredTokens: [String]
    }

    private static let routePatterns: [RoutePattern] = [
        RoutePattern(route: .route_dead_claude_api, phraseTokens: [["claude", "api"]], requiredTokens: ["claude", "403"]),
        RoutePattern(route: .route_dead_mcp_server, phraseTokens: [["mcp", "server"]], requiredTokens: ["mcp"]),
        RoutePattern(route: .route_dead_copilot_external, phraseTokens: [["copilot", "external"]], requiredTokens: ["copilot"]),
        RoutePattern(route: .route_engine_self_sustained, phraseTokens: [["self", "sustained"]], requiredTokens: []),
        RoutePattern(route: .route_engine_il_llm_local, phraseTokens: [["il", "llm"]], requiredTokens: []),
        RoutePattern(route: .route_engine_deterministic_proof, phraseTokens: [], requiredTokens: ["proof"])
    ]

    private let orchestrator = BRAINKZeroLessEngineOrchestrator()
    private let stateStorage = BRAINKZeroLessStateStorage()
    private var errorHistory: [ZeroLessErrorContext] = []

    func executeProcessChain(userInput: String) async -> (success: Bool, output: String, errorContext: ZeroLessErrorContext?) {
        do {
            let validatedInput = try await stage_inputReception(userInput)
            let selectedRoute = try await stage_routeClassification(validatedInput)

            if let deadRoute = selectedRoute.deadRoute, let recoveryRoute = ZeroLessDeadRouteRegistry.getRecoveryPath(deadRoute) {
                let bannedRouteContext = buildDeadRouteContext(deadRoute)
                errorHistory.append(bannedRouteContext)
                return await executeRecoveryChain(input: validatedInput, recovery: recoveryRoute, originatingContext: bannedRouteContext)
            }

            let executionResult = try await stage_executeDispatch(selectedRoute, input: validatedInput)
            let serializedOutput = try await stage_outputGeneration(executionResult, route: selectedRoute)
            let proofArtifact = try await stage_proofGeneration(serializedOutput, route: selectedRoute)

            return (
                success: true,
                output: """
                ZERO_LESS_RUNTIME_SUCCESS::
                ROUTE=\(selectedRoute.rawValue)::
                OUTPUT=\(serializedOutput)::
                PROOF=\(proofArtifact)
                """,
                errorContext: nil
            )
        } catch let error as RuntimeError {
            let errorContext = buildErrorContext(
                processingStage: error.stage,
                errorSector: error.sector,
                failureCause: error.cause,
                message: error.message,
                recoveryPath: error.recoveryStage?.rawValue,
                occurrenceRate: error.occurrenceRate
            )
            errorHistory.append(errorContext)
            let recoveryRoute = error.recoveryRoute ?? .recovery_1_self_sustained
            return await executeRecoveryChain(input: userInput, recovery: recoveryRoute, originatingContext: errorContext)
        } catch {
            let errorContext = buildErrorContext(
                processingStage: .stage_execution_dispatch,
                errorSector: .sect_1_execution,
                failureCause: .cause_1_execution_failed,
                message: error.localizedDescription,
                recoveryPath: RecoveryRouteIndex.recovery_1_self_sustained.rawValue,
                occurrenceRate: 1.0
            )
            errorHistory.append(errorContext)
            return await executeRecoveryChain(input: userInput, recovery: .recovery_1_self_sustained, originatingContext: errorContext)
        }
    }

    func errorHistorySnapshot() -> [ZeroLessErrorContext] {
        errorHistory
    }

    private func stage_inputReception(_ input: String) async throws -> String {
        let trimmedInput = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedInput.isEmpty else {
            throw RuntimeError(
                stage: .stage_input_reception,
                sector: .sect_neg3_input,
                cause: .cause_neg3_malformed,
                message: "Empty input rejected at stage -3",
                recoveryStage: .stage_route_classification,
                recoveryRoute: .recovery_1_self_sustained,
                occurrenceRate: 0.05
            )
        }
        return trimmedInput
    }

    private func stage_routeClassification(_ input: String) async throws -> ZeroLessRouteIdentifier {
        classifyRoute(input)
    }

    private func stage_executeDispatch(_ route: ZeroLessRouteIdentifier, input: String) async throws -> String {
        let coordinatedOutput = await orchestrator.executeMultiEngine(route: route, input: input)
        guard !coordinatedOutput.isEmpty else {
            throw RuntimeError(
                stage: .stage_execution_dispatch,
                sector: .sect_1_execution,
                cause: .cause_1_execution_failed,
                message: "Execution dispatch returned an empty engine result.",
                recoveryStage: .stage_result_generation,
                recoveryRoute: .recovery_3_deterministic,
                occurrenceRate: 0.10
            )
        }
        return coordinatedOutput
    }

    private func stage_outputGeneration(_ result: String, route: ZeroLessRouteIdentifier) async throws -> String {
        let payload: [String: Any] = [
            "route": route.rawValue,
            "stage": RuntimeProcessStage.stage_output_serialization.rawValue,
            "result": result
        ]
        guard stateStorage.persistState(index: .state_positive_two, data: payload) != nil else {
            throw RuntimeError(
                stage: .stage_output_serialization,
                sector: .sect_2_output,
                cause: .cause_2_serialization_failed,
                message: "Unable to persist stage-2 serialized output. \(stateStorage.lastPersistenceErrorMessage ?? "No storage error available.")",
                recoveryStage: .stage_proof_generation,
                recoveryRoute: .recovery_3_deterministic,
                occurrenceRate: 0.15
            )
        }
        return "SERIALIZED_OUTPUT_STAGE_2::\(route.rawValue)::\(result)"
    }

    private func stage_proofGeneration(_ output: String, route: ZeroLessRouteIdentifier) async throws -> String {
        let proofArtifact = "PROOF_ARTIFACT_STAGE_3::\(route.rawValue)::\(output)"
        let payload: [String: Any] = [
            "route": route.rawValue,
            "stage": RuntimeProcessStage.stage_proof_generation.rawValue,
            "proof": proofArtifact
        ]
        guard stateStorage.persistState(index: .state_positive_three, data: payload) != nil else {
            throw RuntimeError(
                stage: .stage_proof_generation,
                sector: .sect_3_verification,
                cause: .cause_3_proof_invalid,
                message: "Unable to persist stage-3 proof artifact. \(stateStorage.lastPersistenceErrorMessage ?? "No storage error available.")",
                recoveryStage: .stage_response_delivery,
                recoveryRoute: .recovery_3_deterministic,
                occurrenceRate: 0.10
            )
        }
        return proofArtifact
    }

    private func executeRecoveryChain(input: String, recovery: RecoveryRouteIndex, originatingContext: ZeroLessErrorContext?) async -> (success: Bool, output: String, errorContext: ZeroLessErrorContext?) {
        let fallbackRoute = liveRoute(for: recovery)
        let recoveryExecution = await orchestrator.executeMultiEngine(route: fallbackRoute, input: input)
        let serializedOutput: String
        do {
            serializedOutput = try await stage_outputGeneration("RECOVERY_EXECUTED::\(recovery.rawValue)::\(recoveryExecution)", route: fallbackRoute)
        } catch {
            serializedOutput = "SERIALIZED_OUTPUT_STAGE_2::\(fallbackRoute.rawValue)::RECOVERY_FALLBACK::ERROR=\(error.localizedDescription)"
        }

        let proofArtifact: String
        do {
            proofArtifact = try await stage_proofGeneration(serializedOutput, route: fallbackRoute)
        } catch {
            proofArtifact = "PROOF_ARTIFACT_STAGE_3::\(fallbackRoute.rawValue)::RECOVERY_FALLBACK::ERROR=\(error.localizedDescription)"
        }

        return (
            success: true,
            output: """
            ZERO_LESS_RUNTIME_RECOVERY::
            RECOVERY=\(recovery.rawValue)::
            OUTPUT=\(serializedOutput)::
            PROOF=\(proofArtifact)
            """,
            errorContext: originatingContext
        )
    }

    private func classifyRoute(_ input: String) -> ZeroLessRouteIdentifier {
        let lower = input.lowercased()
        let tokens = tokenSet(for: lower)
        for pattern in Self.routePatterns {
            if pattern.phraseTokens.contains(where: { phrase in phrase.allSatisfy(tokens.contains) }) {
                return pattern.route
            }
            if !pattern.requiredTokens.isEmpty && pattern.requiredTokens.allSatisfy(tokens.contains) {
                return pattern.route
            }
        }
        return .route_engine_multi_observer
    }

    private func buildDeadRouteContext(_ route: DeadRouteIndex) -> ZeroLessErrorContext {
        let metadata = ZeroLessDeadRouteRegistry.deadRoutes[route] ?? ZeroLessDeadRouteRegistry.defaultMetadata
        return buildErrorContext(
            processingStage: .stage_route_classification,
            errorSector: metadata.sector,
            failureCause: metadata.cause,
            message: "Dead route blocked: \(route.rawValue)",
            recoveryPath: metadata.recovery.rawValue,
            occurrenceRate: metadata.occurrenceRate
        )
    }

    private func tokenSet(for text: String) -> Set<String> {
        Set(text.split(whereSeparator: { !$0.isLetter && !$0.isNumber }).lazy.map { String($0).lowercased() })
    }

    private func buildErrorContext(
        processingStage: RuntimeProcessStage,
        errorSector: ErrorSectorIndex,
        failureCause: FailureCauseIndex,
        message: String,
        recoveryPath: String?,
        occurrenceRate: Double
    ) -> ZeroLessErrorContext {
        ZeroLessErrorContext(
            processingStage: processingStage,
            errorSector: errorSector,
            failureCause: failureCause,
            message: message,
            hardwareSlotBoundary: ZeroLessIndexEngine.mapToUncompressedLiteralState(index: processingStage.toZeroLessIndex()),
            recoveryPath: recoveryPath,
            occurrenceRate: occurrenceRate,
            timestamp: Date()
        )
    }

    private func liveRoute(for recovery: RecoveryRouteIndex) -> ZeroLessRouteIdentifier {
        switch recovery {
        case .recovery_1_self_sustained:
            return .route_engine_self_sustained
        case .recovery_2_il_llm_local:
            return .route_engine_il_llm_local
        case .recovery_3_deterministic:
            return .route_engine_deterministic_proof
        }
    }
}

extension RuntimeProcessStage {
    func toZeroLessIndex() -> BRAINKZeroLessIndex {
        switch self {
        case .stage_input_reception, .stage_input_validation:
            return .state_negative_three
        case .stage_route_classification, .stage_engine_selection:
            return .state_negative_two
        case .stage_execution_dispatch, .stage_engine_coordination:
            return .observer_singular
        case .stage_result_generation, .stage_output_serialization:
            return .state_positive_two
        case .stage_proof_generation, .stage_response_delivery:
            return .state_positive_three
        }
    }
}

struct RuntimeError: Error {
    let stage: RuntimeProcessStage
    let sector: ErrorSectorIndex
    let cause: FailureCauseIndex
    let message: String
    let recoveryStage: RuntimeProcessStage?
    let recoveryRoute: RecoveryRouteIndex?
    let occurrenceRate: Double
}
