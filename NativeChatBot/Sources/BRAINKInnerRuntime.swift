import Foundation

struct BRAINKInnerRuntimeState: Codable {
    var thoughts: [String]
    var emotionalConstraints: [String: Double]
    var perceptionConstraints: [String: Double]
    var governanceConstraints: [String: Double]
    // Spectrum slot index ∈ [1, 2, 3, ...] — never 0 (KEX zero-less principle).
    // Tracks the current ZeroLessSpectrum allocation slot for this runtime state.
    var spectrumSlotIndex: Int
    var updatedAt: String
}

enum BRAINKInnerRuntime {
    static func bootstrap() -> BRAINKInnerRuntimeState {
        // One-time proof gate: verify the static runtime spectrum contains no
        // zero-determinant slots (NoDimensionalCollapseTheorem).
        ZeroLessSpectrum.assertNoDimensionalCollapse(slots: ZeroLessSpectrum.runtimeSlots)

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
            spectrumSlotIndex: ZeroLessSpectrum.minimum.value,
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

        // Advance spectrum slot using ZeroLessSpectrum (slot ∈ [1,2,3,...], never 0).
        // If the stored slot index is somehow invalid, reset to minimum (invariant recovery).
        let currentSlot = SpectrumIndex.make(next.spectrumSlotIndex) ?? ZeroLessSpectrum.minimum
        next.spectrumSlotIndex = ZeroLessSpectrum.next(after: currentSlot).value

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

        return """
        INNER RUNTIME CONSTRAINT CORE
        state_path: \(BRAINKConstants.innerRuntimeStatePath)
        updated_at: \(state.updatedAt)
        spectrum_slot: \(state.spectrumSlotIndex) (zero-less; ∈ [1,2,3,...])
        thoughts:
        - \(thoughtPreview.isEmpty ? "none" : thoughtPreview)
        emotions: \(emotions)
        perception: \(perception)
        governance: \(governance)
        """
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
