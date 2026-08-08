import Foundation

// MARK: - SkillStatus (Zero-Less: no null, no zero-state)

/// The possible status values for a skill execution.
/// Zero-less: every state is named; no silent failures.
enum SkillStatus: String, Codable {
    case completed = "COMPLETED"
    case pending   = "PENDING"
    case blocked   = "BLOCKED"
    case failed    = "FAILED"
}

// MARK: - SkillContext

/// Runtime context passed to each skill during execution.
/// Spectrum slots are 1-indexed (zero-less): valid range is [1, 2, 3, 4, 5].
/// Slot meanings:
///   1 = state   (illlm_bundle)
///   2 = memory  (illlm_query)
///   3 = reasoning (self_sustained_coder)
///   4 = governance (kex_hyperdrive)
///   5 = orchestration (nested_runtime_orchestrator)
struct SkillContext {
    let spectrumSlot: Int
    let runtimePath: String
    let userObjective: String
    let illlmPayload: [String: String]
    /// Previous route in the circular 1→2→3→1 path; nil on initial entry.
    let priorRoute: String?
}

// MARK: - SkillResult

/// The output of a skill execution.
/// nextRoute encodes the circular path: slot 3 (reasoning) returns nextRoute = "illlm_bundle" (slot 1 = state),
/// which is the 1→2→3→1 cycle: state feeds memory, memory feeds reasoning, reasoning renews state.
struct SkillResult {
    let status: SkillStatus
    let output: String
    let artifactPath: String?
    /// The next route in the circular IL-LLM path: 1→2→3→1.
    /// Slot 3 (reasoning) sets nextRoute = "illlm_bundle" to complete the cycle.
    let nextRoute: String?
    let evidenceKeys: [String]
}

// MARK: - SkillValidation

/// Pre-flight validation result before a skill is executed.
struct SkillValidation {
    let isValid: Bool
    let reasons: [String]
    let requiredSlotsAvailable: Bool
}

// MARK: - BRAINKSkill Protocol

/// All BRAINK skills conform to this protocol.
/// Skills are bound to zero-less spectrum slots [1, 2, 3, 4, 5] — never slot 0.
/// The IL-LLM circular path: slot 1 (state) → slot 2 (memory) → slot 3 (reasoning) → slot 1 (new state).
protocol BRAINKSkill {
    /// The unique route name for this skill, matching the chat engine route classifier.
    /// Must stay in sync with the `case` labels in `BRAINKChatEngine.resolveLocally()`;
    /// mismatches will cause routes to fall through to the unrecognised-route handler silently.
    var name: String { get }
    /// The spectrum slots this skill requires (1-indexed, zero-less).
    var requiredSlots: [Int] { get }
    /// Execute the skill within the given context.
    func execute(context: SkillContext) async -> SkillResult
    /// Validate that the skill can run (slots available, path valid, etc.).
    func validate() -> SkillValidation
}

// MARK: - BRAINKSkill Default Validation Helper

extension BRAINKSkill {
    /// Default slot guard: confirms no slot is 0 and all are in [1..5].
    func validateSlots() -> SkillValidation {
        let invalid = requiredSlots.filter { $0 < 1 || $0 > 5 }
        if invalid.isEmpty {
            return SkillValidation(isValid: true, reasons: [], requiredSlotsAvailable: true)
        }
        return SkillValidation(
            isValid: false,
            reasons: invalid.map { "Slot \($0) is outside zero-less spectrum [1..5]" },
            requiredSlotsAvailable: false
        )
    }
}
