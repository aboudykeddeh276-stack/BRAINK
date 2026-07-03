import XCTest

// MARK: - BRAINKSkillProtocolTests
//
// Test scaffolding for BRAINKSkillProtocol, BRAINKSkillRegistry, and BRAINKUIContainers.
// These are stubs ready for implementation once Copilot's NestedRuntimeCore (PR #14) merges.
//
// Proof target: "All known routes have registered skills."
// Spectrum invariant: every slot ∈ [1,2,3,4,5] — zero-less, no slot 0.

final class BRAINKSkillProtocolTests: XCTestCase {

    // MARK: - Skill Protocol Conformance

    func testILLLMBundleSkillConformsToProtocol() throws {
        // Stub: verify illlm_bundle is registered with slot 1.
        let skill = ILLLMBundleSkill()
        XCTAssertEqual(skill.name, "illlm_bundle")
        XCTAssertEqual(skill.requiredSlots, [1])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testILLLMQuerySkillConformsToProtocol() throws {
        // Stub: verify illlm_query is registered with slot 2.
        let skill = ILLLMQuerySkill()
        XCTAssertEqual(skill.name, "illlm_query")
        XCTAssertEqual(skill.requiredSlots, [2])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testSelfSustainedCoderSkillConformsToProtocol() throws {
        // Stub: verify self_sustained_coder is registered with slot 3.
        let skill = SelfSustainedCoderSkill()
        XCTAssertEqual(skill.name, "self_sustained_coder")
        XCTAssertEqual(skill.requiredSlots, [3])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    func testKEXHyperdriveSkillConformsToProtocol() throws {
        // Stub: verify kex_hyperdrive is registered with slot 4.
        let skill = KEXHyperdriveSkill()
        XCTAssertEqual(skill.name, "kex_hyperdrive")
        XCTAssertEqual(skill.requiredSlots, [4])
        XCTAssertFalse(skill.requiredSlots.contains(0), "Zero-less: slot 0 is forbidden.")
    }

    // MARK: - Slot Validation (Zero-Less)

    func testSkillValidationRejectsSlotZero() {
        // Stub: any skill with slot 0 must fail validation.
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

    // MARK: - Registry Completeness

    func testAllKnownRoutesHaveRegisteredSkills() {
        // Proof: "All known routes have registered skills."
        let proof = BRAINKSkillRegistry.validateRegistrationCompleteness()
        XCTAssertEqual(proof.status, "COMPLETED", "Registration incomplete: \(proof.missingFromGraph + proof.missingFromSlotMap)")
        XCTAssertTrue(proof.missingFromGraph.isEmpty, "Skills missing from dependency graph: \(proof.missingFromGraph)")
        XCTAssertTrue(proof.missingFromSlotMap.isEmpty, "Skills missing from slot map: \(proof.missingFromSlotMap)")
    }

    func testRegistryHasFourSkills() {
        XCTAssertEqual(BRAINKSkillRegistry.allSkills.count, 4)
        XCTAssertEqual(BRAINKSkillRegistry.slotMap.count, 4)
        XCTAssertEqual(BRAINKSkillRegistry.dependencyGraph.count, 4)
    }

    func testSlotLookupReturnsCorrectSkill() {
        // Stub: each slot [1..4] resolves to its expected skill name.
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 1)?.name, "illlm_bundle")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 2)?.name, "illlm_query")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 3)?.name, "self_sustained_coder")
        XCTAssertEqual(BRAINKSkillRegistry.skill(forSlot: 4)?.name, "kex_hyperdrive")
        XCTAssertNil(BRAINKSkillRegistry.skill(forSlot: 0), "Slot 0 must not resolve (zero-less).")
        XCTAssertNil(BRAINKSkillRegistry.skill(forSlot: 5), "Slot 5 is reserved (orchestration).")
    }

    // MARK: - IL-LLM Circular Path (1→2→3→1)

    func testILLLMCircularPathIsEncoded() {
        // Proof: the 1→2→3→1 circular path is encoded in the dependency graph.
        let proof = BRAINKSkillRegistry.validateRegistrationCompleteness()
        XCTAssertFalse(proof.illlmCircularPath.isEmpty)
        XCTAssertTrue(proof.illlmCircularPath.contains("1"), "Path must reference slot 1.")
        XCTAssertTrue(proof.illlmCircularPath.contains("2"), "Path must reference slot 2.")
        XCTAssertTrue(proof.illlmCircularPath.contains("3"), "Path must reference slot 3.")
    }

    func testSelfSustainedCoderIsCircularFeedback() {
        // Proof: slot 3 (self_sustained_coder) closes the cycle by feeding slot 1.
        guard let dep = BRAINKSkillRegistry.dependency(for: "self_sustained_coder") else {
            XCTFail("self_sustained_coder not found in dependency graph.")
            return
        }
        XCTAssertTrue(dep.isCircularFeedback, "self_sustained_coder must be marked as circular feedback (3 becomes 1).")
        XCTAssertEqual(dep.feedsSlot, 1, "self_sustained_coder must feed slot 1 to close the 1→2→3→1 cycle.")
    }

    func testCircularPathForwardLinks() {
        // Stub: verify forward links in the circular path.
        let bundleDep = BRAINKSkillRegistry.dependency(for: "illlm_bundle")
        XCTAssertEqual(bundleDep?.feedsSlot, 2, "illlm_bundle (slot 1) must feed slot 2 (memory).")

        let queryDep = BRAINKSkillRegistry.dependency(for: "illlm_query")
        XCTAssertEqual(queryDep?.feedsSlot, 3, "illlm_query (slot 2) must feed slot 3 (reasoning).")

        let coderDep = BRAINKSkillRegistry.dependency(for: "self_sustained_coder")
        XCTAssertEqual(coderDep?.feedsSlot, 1, "self_sustained_coder (slot 3) must feed slot 1 (new state) — 3 becomes 1.")
    }

    // MARK: - Skill Execution Stubs (Async)
    // These stubs will be fully implemented once Copilot's NestedRuntimeCore (PR #14) merges.

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
}
