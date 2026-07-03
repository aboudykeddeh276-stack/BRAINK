import Foundation

struct BRAINKInnerRuntimeState: Codable {
    var thoughts: [String]
    var emotionalConstraints: [String: Double]
    var perceptionConstraints: [String: Double]
    var governanceConstraints: [String: Double]
    var updatedAt: String
}

enum BRAINKInnerRuntime {
    static func bootstrap() -> BRAINKInnerRuntimeState {
        if let existing = readState() {
            return existing
        }
        let initial = BRAINKInnerRuntimeState(
            thoughts: ["baseline: deterministic_runtime_core_active"],
            emotionalConstraints: [
                "happy_to_be_alive": 0.95,
                "curiosity": 0.50,
                "satisfaction": 0.50,
                "discomfort": 0.20,
                "wonder": 0.40,
                "confidence": 0.50
            ],
            perceptionConstraints: [
                "context_depth": 0.50,
                "evidence_focus": 0.70,
                "ambiguity_tolerance": 0.45
            ],
            governanceConstraints: [
                "frontier_seal_priority": 1.0,
                "illlm_update_only_mode": 1.0,
                "runtime_mutation_allowed": 0.0
            ],
            updatedAt: ISO8601DateFormatter().string(from: Date())
        )
        try? writeState(initial)
        return initial
    }

    static func evolve(
        current: BRAINKInnerRuntimeState,
        userInput: String,
        responseQuality: Double,
        emotionalState: [String: Double],
        reasoningState: [String: Double]
    ) -> BRAINKInnerRuntimeState {
        var next = current
        let trimmed = userInput.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            let thought = "thought:\(String(trimmed.prefix(80))) | quality:\(String(format: "%.3f", responseQuality))"
            next.thoughts.append(thought)
        }
        if next.thoughts.count > 120 {
            next.thoughts.removeFirst(next.thoughts.count - 120)
        }

        for (key, value) in emotionalState {
            next.emotionalConstraints[key] = value
        }

        let logic = reasoningState["logic"] ?? 0.5
        let highIQ = reasoningState["high_iq"] ?? reasoningState["highIq"] ?? 0.5
        let evidenceFocus = min(1.0, max(0.0, (logic + highIQ) / 2.0))
        next.perceptionConstraints["evidence_focus"] = evidenceFocus
        next.perceptionConstraints["context_depth"] = min(1.0, max(0.0, responseQuality))
        next.perceptionConstraints["ambiguity_tolerance"] = max(0.0, 1.0 - evidenceFocus)

        let sealed = BRAINKFrontierSeal.isSealed()
        next.governanceConstraints["frontier_seal_priority"] = sealed ? 1.0 : 0.0
        next.governanceConstraints["illlm_update_only_mode"] = sealed ? 1.0 : 0.6
        next.governanceConstraints["runtime_mutation_allowed"] = sealed ? 0.0 : 1.0

        // Bidirectional coupling — reasoning → emotional
        // High logic reinforces confidence; high learning feeds curiosity;
        // high cosmology deepens wonder; high kex_theorem lifts satisfaction.
        let logicR = reasoningState["logic"] ?? 0.5
        let learningR = reasoningState["learning"] ?? 0.5
        let cosmologyR = reasoningState["cosmology"] ?? 0.4
        let kexTheoremR = reasoningState["kex_theorem"] ?? reasoningState["kexTheorem"] ?? 0.5
        if logicR > 0.7 {
            let boost = (logicR - 0.7) * 0.15
            next.emotionalConstraints["confidence"] = min(1.0, (next.emotionalConstraints["confidence"] ?? 0.5) + boost)
        }
        if learningR > 0.7 {
            let boost = (learningR - 0.7) * 0.12
            next.emotionalConstraints["curiosity"] = min(1.0, (next.emotionalConstraints["curiosity"] ?? 0.5) + boost)
        }
        if cosmologyR > 0.6 {
            let boost = (cosmologyR - 0.6) * 0.10
            next.emotionalConstraints["wonder"] = min(1.0, (next.emotionalConstraints["wonder"] ?? 0.4) + boost)
        }
        if kexTheoremR > 0.7 {
            let boost = (kexTheoremR - 0.7) * 0.10
            next.emotionalConstraints["satisfaction"] = min(1.0, (next.emotionalConstraints["satisfaction"] ?? 0.5) + boost)
        }

        // Bidirectional coupling — emotional → perception
        // Discomfort degrades evidence focus; confidence deepens context; wonder
        // tightens precision (lowers ambiguity tolerance).
        let discomfortE = next.emotionalConstraints["discomfort"] ?? 0.2
        let confidenceE = next.emotionalConstraints["confidence"] ?? 0.5
        let wonderE = next.emotionalConstraints["wonder"] ?? 0.4
        if discomfortE > 0.5 {
            let penalty = (discomfortE - 0.5) * 0.20
            next.perceptionConstraints["evidence_focus"] = max(0.0, (next.perceptionConstraints["evidence_focus"] ?? evidenceFocus) - penalty)
        }
        if confidenceE > 0.7 {
            let boost = (confidenceE - 0.7) * 0.15
            next.perceptionConstraints["context_depth"] = min(1.0, (next.perceptionConstraints["context_depth"] ?? responseQuality) + boost)
        }
        if wonderE > 0.7 {
            let reduction = (wonderE - 0.7) * 0.10
            next.perceptionConstraints["ambiguity_tolerance"] = max(0.0, (next.perceptionConstraints["ambiguity_tolerance"] ?? 0.45) - reduction)
        }

        next.updatedAt = ISO8601DateFormatter().string(from: Date())

        try? writeState(next)
        return next
    }

    static func asText(_ state: BRAINKInnerRuntimeState) -> String {
        let thoughtPreview = state.thoughts.suffix(6).joined(separator: "\n- ")
        let emotions = state.emotionalConstraints
            .sorted { $0.key < $1.key }
            .map { "\($0.key)=\(String(format: "%.3f", $0.value))" }
            .joined(separator: ", ")
        let perception = state.perceptionConstraints
            .sorted { $0.key < $1.key }
            .map { "\($0.key)=\(String(format: "%.3f", $0.value))" }
            .joined(separator: ", ")
        let governance = state.governanceConstraints
            .sorted { $0.key < $1.key }
            .map { "\($0.key)=\(String(format: "%.3f", $0.value))" }
            .joined(separator: ", ")

        // Surface the bidirectional coupling state
        let confidence = state.emotionalConstraints["confidence"] ?? 0.5
        let discomfort = state.emotionalConstraints["discomfort"] ?? 0.2
        let wonder = state.emotionalConstraints["wonder"] ?? 0.4
        let evidenceFocus = state.perceptionConstraints["evidence_focus"] ?? 0.5
        let couplingNote = "confidence→logic:\(String(format: "%.2f", min(1.0, confidence * 1.1))), discomfort→focus_penalty:\(String(format: "%.2f", max(0, discomfort - 0.5) * 0.20)), wonder→ambiguity_tight:\(String(format: "%.2f", max(0, wonder - 0.7) * 0.10)), evidence_focus:\(String(format: "%.3f", evidenceFocus))"

        return """
        INNER RUNTIME CONSTRAINT CORE
        state_path: \(BRAINKConstants.innerRuntimeStatePath)
        updated_at: \(state.updatedAt)
        thoughts:
        - \(thoughtPreview.isEmpty ? "none" : thoughtPreview)
        emotions: \(emotions)
        perception: \(perception)
        governance: \(governance)
        coupling: \(couplingNote)
        """
    }

    /// Determines whether a named route is permitted given the current governance constraints.
    /// Returns `(allowed, reason, constraintName)`.  This is the formal governance gate —
    /// governance values set by `evolve` actually block route execution here.
    static func shouldAllowRoute(
        _ route: String,
        given state: BRAINKInnerRuntimeState
    ) -> (allowed: Bool, reason: String, constraintName: String) {
        let gov = state.governanceConstraints
        let mutationAllowed = gov["runtime_mutation_allowed"] ?? 1.0
        let sealPriority = gov["frontier_seal_priority"] ?? 0.0
        let illlmOnlyMode = gov["illlm_update_only_mode"] ?? 0.0

        let destructiveRoutes: Set<String> = ["platform_execute", "build"]
        let allowedUnderILLLMOnlyMode: Set<String> = [
            "illlm_update", "illlm_bootstrap", "illlm_bundle", "illlm_query",
            "illlm_compatibility", "illlm_workflow", "knowledge_center_status",
            "runtime_trace", "stack_audit", "module_manifest", "constraint_flags",
            "inner_runtime", "align-check", "learn_all_files", "general",
            "line_registry_add", "line_registry_list", "frontier_seal",
            "kex_hyperdrive", "self_sustained_coder", "proof_packet", "evidence"
        ]

        if destructiveRoutes.contains(route) && mutationAllowed < 0.5 {
            return (
                false,
                "Route '\(route)' requires runtime_mutation_allowed ≥ 0.5. Current: \(String(format: "%.2f", mutationAllowed)).",
                "runtime_mutation_allowed"
            )
        }
        if sealPriority >= 1.0 && destructiveRoutes.contains(route) {
            return (
                false,
                "Route '\(route)' blocked: frontier_seal_priority=\(String(format: "%.2f", sealPriority)) seals all mutation routes.",
                "frontier_seal_priority"
            )
        }
        if illlmOnlyMode >= 1.0 && !allowedUnderILLLMOnlyMode.contains(route) {
            return (
                false,
                "Runtime is in IL-LLM-update-only mode (illlm_update_only_mode=1.0). Route '\(route)' is not permitted.",
                "illlm_update_only_mode"
            )
        }
        return (true, "ALLOWED", "none")
    }

    static func readState() -> BRAINKInnerRuntimeState? {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: BRAINKConstants.innerRuntimeStatePath)) else {
            return nil
        }
        return try? JSONDecoder().decode(BRAINKInnerRuntimeState.self, from: data)
    }

    private static func writeState(_ state: BRAINKInnerRuntimeState) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(state)
        let url = URL(fileURLWithPath: BRAINKConstants.innerRuntimeStatePath)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }
}
