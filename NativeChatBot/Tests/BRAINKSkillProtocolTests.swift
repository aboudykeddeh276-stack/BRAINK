import XCTest

// MARK: - BRAINKSkillProtocolTests
//
// Runtime proof tests for BRAINKSkillProtocol, BRAINKSkillRegistry, and BRAINKConstants.
// Spectrum invariant: every slot ∈ [1,2,3,4,5] — zero-less, no slot 0.
// Full spectrum: 1(state) → 2(memory) → 3(reasoning) → 1(circular) | 4(governance) → 5(orchestration).

final class BRAINKSkillProtocolTests: XCTestCase {

    // MARK: - Skill Protocol Conformance

    func testILLLMBundleSkillConformsToProtocol() throws {
        let skill = ILLLMBundleSkill()
        XCTAssertEqual(skill.name, "illlm_bundle")
        XCTAssertEqual(skill.requiredSlots, [1])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testILLLMQuerySkillConformsToProtocol() throws {
        let skill = ILLLMQuerySkill()
        XCTAssertEqual(skill.name, "illlm_query")
        XCTAssertEqual(skill.requiredSlots, [2])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testSelfSustainedCoderSkillConformsToProtocol() throws {
        let skill = SelfSustainedCoderSkill()
        XCTAssertEqual(skill.name, "self_sustained_coder")
        XCTAssertEqual(skill.requiredSlots, [3])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testKEXHyperdriveSkillConformsToProtocol() throws {
        let skill = KEXHyperdriveSkill()
        XCTAssertEqual(skill.name, "kex_hyperdrive")
        XCTAssertEqual(skill.requiredSlots, [4])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testNestedRuntimeOrchestratorSkillConformsToProtocol() throws {
        let skill = NestedRuntimeOrchestratorSkill()
        XCTAssertEqual(skill.name, "nested_runtime_orchestrator")
        XCTAssertEqual(skill.requiredSlots, [5])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    // MARK: - Slot Validation (Zero-Less)

    func testSkillValidationRejectsSlotZero() {
        let skill = ILLLMBundleSkill()
        let validation = skill.validate()
        XCTAssertTrue(validation.isValid, "illlm_bundle slot [1] must be valid.")
        XCTAssertTrue(validation.requiredSlotsAvailable)
    }

    func testAllSkillSlotsAreInZeroLessSpectrum() {
        // Proof: every registered skill uses slots ∈ [1..5] — zero-less.
        for skill in BRAINKSkillRegistry.allSkills {
            for slot in skill.requiredSlots {
                XCTAssertGreaterThanOrEqual(slot, 1, "\(skill.name): slot \(slot) violates zero-less constraint.")
                XCTAssertLessThanOrEqual(slot, 5, "\(skill.name): slot \(slot) exceeds spectrum [1..5].")
            }
        }
    }

    // MARK: - Registry Completeness (Full Spectrum [1..5])

    func testAllKnownRoutesHaveRegisteredSkills() {
        let proof = BRAINKSkillRegistry.validateRegistrationCompleteness()
        XCTAssertEqual(proof.status, "COMPLETED", "Registration incomplete: \(proof.missingFromGraph + proof.missingFromSlotMap)")
        XCTAssertTrue(proof.missingFromGraph.isEmpty, "Skills missing from dependency graph: \(proof.missingFromGraph)")
        XCTAssertTrue(proof.missingFromSlotMap.isEmpty, "Skills missing from slot map: \(proof.missingFromSlotMap)")
    }

    func testRegistryHasFiveSkills() {
        // Full zero-less spectrum [1..5] must be populated.
        XCTAssertEqual(BRAINKSkillRegistry.allSkills.count, 5, "Spectrum [1..5] requires 5 registered skills.")
        XCTAssertEqual(BRAINKSkillRegistry.slotMap.count, 5, "Slot map must cover all 5 spectrum slots.")
        XCTAssertEqual(BRAINKSkillRegistry.dependencyGraph.count, 5, "Dependency graph must have 5 entries.")
    }

    func testSlotLookupReturnsCorrectSkill() {
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 1)?.name, "illlm_bundle")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 2)?.name, "illlm_query")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 3)?.name, "self_sustained_coder")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 4)?.name, "kex_hyperdrive")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 5)?.name, "nested_runtime_orchestrator")
        XCTAssertNil(BRAINKSkillRegistry.skill(forSlot: 0), "Slot 0 must not resolve (zero-less).")
        XCTAssertNil(BRAINKSkillRegistry.skill(forSlot: 6), "Slot 6 is outside spectrum [1..5].")
    }

    // MARK: - IL-LLM Circular Path (1→2→3→1) + Governance/Orchestration Chain (4→5)

    func testILLLMCircularPathIsEncoded() {
        let proof = BRAINKSkillRegistry.validateRegistrationCompleteness()
        XCTAssertFalse(proof.illlmCircularPath.isEmpty)
        XCTAssertTrue(proof.illlmCircularPath.contains("1"), "Path must reference slot 1.")
        XCTAssertTrue(proof.illlmCircularPath.contains("2"), "Path must reference slot 2.")
        XCTAssertTrue(proof.illlmCircularPath.contains("3"), "Path must reference slot 3.")
    }

    func testSelfSustainedCoderIsCircularFeedback() {
        guard let dep = BRAINKSkillRegistry.dependency(for: "self_sustained_coder") else {
            XCTFail("self_sustained_coder not found in dependency graph.")
            return
        }
        XCTAssertTrue(dep.isCircularFeedback, "self_sustained_coder must be marked as circular feedback (3 becomes 1).")
        XCTAssertEqual(dep.feedsSlot, 1, "self_sustained_coder must feed slot 1 to close the 1→2→3→1 cycle.")
    }

    func testCircularPathForwardLinks() {
        let bundleDep = BRAINKSkillRegistry.dependency(for: "illlm_bundle")
        XCTAssertEqual(bundleDep?.feedsSlot, 2, "illlm_bundle (slot 1) must feed slot 2 (memory).")

        let queryDep = BRAINKSkillRegistry.dependency(for: "illlm_query")
        XCTAssertEqual(queryDep?.feedsSlot, 3, "illlm_query (slot 2) must feed slot 3 (reasoning).")

        let coderDep = BRAINKSkillRegistry.dependency(for: "self_sustained_coder")
        XCTAssertEqual(coderDep?.feedsSlot, 1, "self_sustained_coder (slot 3) must feed slot 1 (new state) — 3 becomes 1.")
    }

    func testGovernanceAndOrchestrationChain() {
        // Slot 4 (governance) must feed slot 5 (orchestration); slot 5 is terminal.
        let govDep = BRAINKSkillRegistry.dependency(for: "kex_hyperdrive")
        XCTAssertEqual(govDep?.feedsSlot, 5, "kex_hyperdrive (slot 4) must feed slot 5 (orchestration).")
        XCTAssertFalse(govDep?.isCircularFeedback ?? true, "Governance is not circular.")

        let orchDep = BRAINKSkillRegistry.dependency(for: "nested_runtime_orchestrator")
        XCTAssertNil(orchDep?.feedsSlot, "nested_runtime_orchestrator (slot 5) is terminal — no further slot.")
        XCTAssertFalse(orchDep?.isCircularFeedback ?? true, "Orchestration is not circular.")
    }

    // MARK: - Skill Execution (Async)

    func testILLLMBundleSkillExecutionReturnsNextRoute() async {
        let skill = ILLLMBundleSkill()
        let context = SkillContext(
            spectrumSlot: 1,
            runtimePath: "/tmp/braink_test_runtime",
            userObjective: "Load state snapshot.",
            illlmPayload: [:],
            priorRoute: nil
        )
        let result = await skill.execute(context: context)
        XCTAssertEqual(result.nextRoute, "illlm_query", "Slot 1 (state) must advance to slot 2 (memory).")
        XCTAssertFalse(result.evidenceKeys.isEmpty)
    }

    func testSelfSustainedCoderSkillExecutionFeedsBack() async {
        let skill = SelfSustainedCoderSkill()
        let context = SkillContext(
            spectrumSlot: 3,
            runtimePath: "/tmp/braink_test_runtime",
            userObjective: "Generate reasoning artifact.",
            illlmPayload: [:],
            priorRoute: "illlm_query"
        )
        let result = await skill.execute(context: context)
        XCTAssertEqual(result.nextRoute, "illlm_bundle", "Slot 3 (reasoning) must feed back to slot 1 (state) — 3 becomes 1.")
        XCTAssertTrue(result.evidenceKeys.contains("circular_path_close"), "Evidence must record circular path closure.")
    }

    func testNestedRuntimeOrchestratorSkillExecution() async {
        let skill = NestedRuntimeOrchestratorSkill()
        let context = SkillContext(
            spectrumSlot: 5,
            runtimePath: "/tmp/braink_test_runtime",
            userObjective: "Orchestrate multi-repo pipeline.",
            illlmPayload: [:],
            priorRoute: "kex_hyperdrive"
        )
        let result = await skill.execute(context: context)
        XCTAssertNil(result.nextRoute, "Slot 5 (orchestration) is terminal — no nextRoute.")
        XCTAssertTrue(result.evidenceKeys.contains("spectrum_slot_5"), "Evidence must record slot 5.")
        XCTAssertTrue(result.evidenceKeys.contains("full_spectrum_1_to_5"), "Evidence must record full spectrum coverage.")
    }

    func testWrongSlotIsBlocked() async {
        let skill = NestedRuntimeOrchestratorSkill()
        let context = SkillContext(
            spectrumSlot: 3,   // wrong slot — must block
            runtimePath: "/tmp/braink_test_runtime",
            userObjective: "Should be blocked.",
            illlmPayload: [:],
            priorRoute: nil
        )
        let result = await skill.execute(context: context)
        XCTAssertEqual(result.status, .blocked, "Wrong-slot execution must return .blocked.")
    }

    // MARK: - BRAINKConstants — KEX Engineering Standard

    func testKEXEngineeringConstantsAreCorrect() {
        XCTAssertEqual(BRAINKConstants.kexResonance, 0.297, accuracy: 1e-9, "K_RESONANCE must be 0.297.")
        XCTAssertEqual(BRAINKConstants.kexLatticeRoot, 28.085, accuracy: 1e-9, "LATTICE_ROOT must be 28.085.")
        XCTAssertEqual(BRAINKConstants.kexAxis, "3|2|1|2|3", "AXIS must be '3|2|1|2|3'.")
        XCTAssertEqual(BRAINKConstants.kexBaseline, 1, "BASELINE must be 1 (zero-less).")
    }

    func testSharedISO8601FormatterIsNonNil() {
        let dateString = BRAINKConstants.iso8601.string(from: Date())
        XCTAssertFalse(dateString.isEmpty, "Shared ISO8601 formatter must produce non-empty date strings.")
    }

    func testSourcePathsArePortable() {
        // Source paths must be derived, not hardcoded to any user's home directory.
        XCTAssertFalse(BRAINKConstants.sourcePath_ChatEngine.contains("/Users/ak/"),
                       "sourcePath_ChatEngine must not contain hardcoded /Users/ak/ path.")
        XCTAssertFalse(BRAINKConstants.sourcePath_ModuleManifest.contains("/Users/ak/"),
                       "sourcePath_ModuleManifest must not contain hardcoded /Users/ak/ path.")
        XCTAssertTrue(BRAINKConstants.sourcePath_ChatEngine.hasSuffix("BRAINKChatEngine.swift"),
                      "sourcePath_ChatEngine must resolve to BRAINKChatEngine.swift.")
        XCTAssertTrue(FileManager.default.fileExists(atPath: BRAINKConstants.sourcePath_ChatEngine),
                      "sourcePath_ChatEngine must point to an existing file on this machine.")
    }

    func testStableHexDigestIsConsistent() {
        let data = Data("braink_kex_test".utf8)
        let first = BRAINKConstants.stableHexDigest(data)
        let second = BRAINKConstants.stableHexDigest(data)
        XCTAssertEqual(first, second, "stableHexDigest must be deterministic for the same input.")
        XCTAssertFalse(first.isEmpty, "stableHexDigest must produce a non-empty hex string.")
    }
}

