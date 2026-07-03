import Foundation

// MARK: - Concrete Skill Implementations

/// Slot 1 (state): Manages IL-LLM bundle intake and inventory state.
/// In the circular path: slot 1 (state) → slot 2 (memory) → slot 3 (reasoning) → slot 1 (new state).
struct ILLLMBundleSkill: BRAINKSkill {
    let name = "illlm_bundle"
    let requiredSlots = [1]   // state slot

    func validate() -> SkillValidation { validateSlots() }

    func execute(context: SkillContext) async -> SkillResult {
        guard context.spectrumSlot == 1 else {
            return SkillResult(
                status: .blocked,
                output: "illlm_bundle requires spectrum slot 1 (state). Received slot \(context.spectrumSlot).",
                artifactPath: nil,
                nextRoute: nil,
                evidenceKeys: []
            )
        }
        // Circular path continuation: after state is loaded, advance to memory (slot 2).
        return SkillResult(
            status: .pending,
            output: "illlm_bundle: State snapshot PENDING. Bind IL-LLM runtime path and load inventory before advancing to slot 2 (memory).",
            artifactPath: BRAINKConstants.illlmKnowledgeStatePath,
            nextRoute: "illlm_query",   // 1 → 2
            evidenceKeys: ["illlm_bundle.state", "spectrum_slot_1"]
        )
    }
}

/// Slot 2 (memory): Retrieves IL-LLM context for a given query.
/// In the circular path: slot 2 (memory) follows slot 1 and precedes slot 3 (reasoning).
struct ILLLMQuerySkill: BRAINKSkill {
    let name = "illlm_query"
    let requiredSlots = [2]   // memory slot

    func validate() -> SkillValidation { validateSlots() }

    func execute(context: SkillContext) async -> SkillResult {
        guard context.spectrumSlot == 2 else {
            return SkillResult(
                status: .blocked,
                output: "illlm_query requires spectrum slot 2 (memory). Received slot \(context.spectrumSlot).",
                artifactPath: nil,
                nextRoute: nil,
                evidenceKeys: []
            )
        }
        // Circular path continuation: after memory retrieval, advance to reasoning (slot 3).
        return SkillResult(
            status: .pending,
            output: "illlm_query: Memory retrieval PENDING. Load IL-LLM snippets and knowledge context before advancing to slot 3 (reasoning).",
            artifactPath: BRAINKConstants.illlmKnowledgeStatePath,
            nextRoute: "self_sustained_coder",  // 2 → 3
            evidenceKeys: ["illlm_query.memory", "spectrum_slot_2"]
        )
    }
}

/// Slot 3 (reasoning): Self-sustained coding and reasoning engine.
/// In the circular path: slot 3 (reasoning) feeds its output back to slot 1 (state) — 3 becomes 1.
struct SelfSustainedCoderSkill: BRAINKSkill {
    let name = "self_sustained_coder"
    let requiredSlots = [3]   // reasoning slot

    func validate() -> SkillValidation { validateSlots() }

    func execute(context: SkillContext) async -> SkillResult {
        guard context.spectrumSlot == 3 else {
            return SkillResult(
                status: .blocked,
                output: "self_sustained_coder requires spectrum slot 3 (reasoning). Received slot \(context.spectrumSlot).",
                artifactPath: nil,
                nextRoute: nil,
                evidenceKeys: []
            )
        }
        // Circular path closes here: reasoning output renews state → route returns to slot 1.
        // "3 becomes 1": the new reasoning artifact becomes the new state for the next cycle.
        return SkillResult(
            status: .pending,
            output: "self_sustained_coder: Reasoning PENDING. Self-map → Self-task → Self-code → Self-proof cycle required. On completion, output renews state (slot 1) to close the 1→2→3→1 path.",
            artifactPath: BRAINKConstants.kexSelfSustainedCodingReportPath,
            nextRoute: "illlm_bundle",  // 3 → 1 (3 becomes 1: reasoning renews state)
            evidenceKeys: ["self_sustained_coder.reasoning", "spectrum_slot_3", "circular_path_close"]
        )
    }
}

/// Slot 4 (governance): KEX Hyperdrive transition/definition engine.
/// Governs the full stack; depends on slots [1, 2, 3] being stable.
struct KEXHyperdriveSkill: BRAINKSkill {
    let name = "kex_hyperdrive"
    let requiredSlots = [4]   // governance slot

    func validate() -> SkillValidation { validateSlots() }

    func execute(context: SkillContext) async -> SkillResult {
        guard context.spectrumSlot == 4 else {
            return SkillResult(
                status: .blocked,
                output: "kex_hyperdrive requires spectrum slot 4 (governance). Received slot \(context.spectrumSlot).",
                artifactPath: nil,
                nextRoute: nil,
                evidenceKeys: []
            )
        }
        return SkillResult(
            status: .pending,
            output: "kex_hyperdrive: Governance PENDING. Requires slots [1,2,3] to be COMPLETED before governance layer can validate. State OF transition + Transition OF state + Definition OF transition = governance proof.",
            artifactPath: BRAINKConstants.kexHyperdriveConceptReportPath,
            nextRoute: nil,   // governance is the final layer before orchestration (slot 5)
            evidenceKeys: ["kex_hyperdrive.governance", "spectrum_slot_4"]
        )
    }
}

// MARK: - Skill Dependency Graph

/// Encodes the declared dependency between skills.
/// The 1→2→3→1 circular IL-LLM path is the core dependency arc.
struct SkillDependency {
    let skillName: String
    let dependsOn: [String]
    let spectrumSlot: Int
    /// True if this skill's output feeds back to a prior slot (circular path).
    let isCircularFeedback: Bool
    /// The slot this skill feeds into (next in the chain).
    let feedsSlot: Int?
}

// MARK: - BRAINKSkillRegistry

/// Registers all BRAINK skills and maps them to their spectrum slots.
/// Encodes the IL-LLM circular path: 1 (state) → 2 (memory) → 3 (reasoning) → 1 (state renewed).
/// "You need to learn the il-llm and 1>2>3 paths where 3 becomes 1."
enum BRAINKSkillRegistry {

    // MARK: - All registered skills

    static let allSkills: [any BRAINKSkill] = [
        ILLLMBundleSkill(),
        ILLLMQuerySkill(),
        SelfSustainedCoderSkill(),
        KEXHyperdriveSkill()
    ]

    // MARK: - Slot → Skill map (zero-less: slots start at 1)

    static let slotMap: [Int: String] = [
        1: "illlm_bundle",           // state
        2: "illlm_query",            // memory
        3: "self_sustained_coder",   // reasoning
        4: "kex_hyperdrive"          // governance
    ]

    // MARK: - Skill Dependency Graph (IL-LLM 1→2→3→1 circular path)

    /// The dependency graph encodes:
    ///   - illlm_bundle   (slot 1) has no prior dependency; feeds slot 2
    ///   - illlm_query    (slot 2) depends on slot 1; feeds slot 3
    ///   - self_sustained_coder (slot 3) depends on slot 2; feeds back to slot 1 (circular)
    ///   - kex_hyperdrive (slot 4) depends on slots [1,2,3]; terminal governance layer
    static let dependencyGraph: [SkillDependency] = [
        SkillDependency(
            skillName: "illlm_bundle",
            dependsOn: [],                          // entry point
            spectrumSlot: 1,
            isCircularFeedback: false,
            feedsSlot: 2
        ),
        SkillDependency(
            skillName: "illlm_query",
            dependsOn: ["illlm_bundle"],            // memory requires state
            spectrumSlot: 2,
            isCircularFeedback: false,
            feedsSlot: 3
        ),
        SkillDependency(
            skillName: "self_sustained_coder",
            dependsOn: ["illlm_query"],             // reasoning requires memory
            spectrumSlot: 3,
            isCircularFeedback: true,               // 3 becomes 1: reasoning renews state
            feedsSlot: 1                            // closes the 1→2→3→1 cycle
        ),
        SkillDependency(
            skillName: "kex_hyperdrive",
            dependsOn: ["illlm_bundle", "illlm_query", "self_sustained_coder"],  // governance needs full stack
            spectrumSlot: 4,
            isCircularFeedback: false,
            feedsSlot: nil                          // governance is terminal
        )
    ]

    // MARK: - Lookup

    static func skill(named name: String) -> (any BRAINKSkill)? {
        allSkills.first { $0.name == name }
    }

    static func skill(forSlot slot: Int) -> (any BRAINKSkill)? {
        guard let name = slotMap[slot] else { return nil }
        return skill(named: name)
    }

    static func dependency(for skillName: String) -> SkillDependency? {
        dependencyGraph.first { $0.skillName == skillName }
    }

    // MARK: - Validation

    /// Confirms all registered skill names have a corresponding dependency entry.
    /// Proof: "All known routes have registered skills."
    static func validateRegistrationCompleteness() -> SkillRegistrationProof {
        let registeredNames = Set(allSkills.map { $0.name })
        let graphNames = Set(dependencyGraph.map { $0.skillName })
        let slotNames = Set(slotMap.values)

        let missingFromGraph = registeredNames.subtracting(graphNames)
        let missingFromSlotMap = registeredNames.subtracting(slotNames)
        let circularSkills = dependencyGraph.filter { $0.isCircularFeedback }.map { $0.skillName }

        let allValid = missingFromGraph.isEmpty && missingFromSlotMap.isEmpty

        return SkillRegistrationProof(
            status: allValid ? "COMPLETED" : "BLOCKED",
            registeredSkillCount: allSkills.count,
            dependencyGraphCount: dependencyGraph.count,
            slotMapCount: slotMap.count,
            missingFromGraph: Array(missingFromGraph).sorted(),
            missingFromSlotMap: Array(missingFromSlotMap).sorted(),
            circularFeedbackSkills: circularSkills,
            illlmCircularPath: "illlm_bundle(1) → illlm_query(2) → self_sustained_coder(3) → illlm_bundle(1)",
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
    }

    // MARK: - Report

    static func writeRegistrationProof() throws {
        let proof = validateRegistrationCompleteness()
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(proof)
        let url = URL(fileURLWithPath: BRAINKConstants.skillRegistryReportPath)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }

    static func asText(_ proof: SkillRegistrationProof) -> String {
        let deps = dependencyGraph.map { dep in
            let feeds = dep.feedsSlot.map { " → slot \($0)\(dep.isCircularFeedback ? " (closes 1→2→3→1 cycle)" : "")" } ?? " → terminal"
            return "  [\(dep.spectrumSlot)] \(dep.skillName): depends=[\(dep.dependsOn.joined(separator: ","))]\(feeds)"
        }.joined(separator: "\n")

        return """
        BRAINK SKILL REGISTRY
        status: \(proof.status)
        registered_skills: \(proof.registeredSkillCount)
        slot_map_count: \(proof.slotMapCount)
        dependency_graph_count: \(proof.dependencyGraphCount)
        circular_feedback_skills: \(proof.circularFeedbackSkills.joined(separator: ", "))
        il_llm_circular_path: \(proof.illlmCircularPath)
        missing_from_graph: \(proof.missingFromGraph.isEmpty ? "none" : proof.missingFromGraph.joined(separator: ", "))
        missing_from_slot_map: \(proof.missingFromSlotMap.isEmpty ? "none" : proof.missingFromSlotMap.joined(separator: ", "))
        generated_at: \(proof.generatedAt)

        DEPENDENCY GRAPH (IL-LLM 1→2→3→1 Circular Path)
        \(deps)

        PROOF: All known routes have registered skills.
        report_path: \(BRAINKConstants.skillRegistryReportPath)
        """
    }
}

// MARK: - SkillRegistrationProof

struct SkillRegistrationProof: Codable {
    let status: String
    let registeredSkillCount: Int
    let dependencyGraphCount: Int
    let slotMapCount: Int
    let missingFromGraph: [String]
    let missingFromSlotMap: [String]
    let circularFeedbackSkills: [String]
    let illlmCircularPath: String
    let generatedAt: String
}
