import Foundation

struct ILLLMWorkflowStep: Codable {
    let id: Int
    let name: String
    let action: String
    let expectedEvidence: String
}

struct ILLLMWorkflowPlan: Codable {
    let architect: String
    let organization: String
    let signature: String
    let status: String
    let runtimePath: String
    let skillName: String
    let objective: String
    let frontierSealed: Bool
    let entryLines: [String]
    let createdAt: String
    let steps: [ILLLMWorkflowStep]
    let successCriteria: [String]
    let nextMove: String
}

enum BRAINKILLLMWorkflow {
    static func buildPlan(skillName: String, objective: String, runtimePath: String) -> ILLLMWorkflowPlan {
        let sealState = BRAINKFrontierSeal.isSealed()
        let entryLines = BRAINKFrontierSeal.readRegistry()?.lines ?? []

        let skill = normalizeSkill(skillName)
        let objectiveClean = objective.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "Apply IL-LLM skill pipeline to current user objective."
            : objective.trimmingCharacters(in: .whitespacesAndNewlines)

        let steps: [ILLLMWorkflowStep] = [
            ILLLMWorkflowStep(
                id: 1,
                name: "runtime_integrity_gate",
                action: sealState
                    ? "Confirm frontier seal is active. Core runtime code is immutable."
                    : "Seal baseline runtime before production flow (`frontier seal`).",
                expectedEvidence: "frontier seal state and core hash"
            ),
            ILLLMWorkflowStep(
                id: 2,
                name: "illlm_runtime_binding",
                action: "Bind IL-LLM root (`illlm_update <path>`) and load inventory/snippets.",
                expectedEvidence: "loaded file count + runtime path confirmation"
            ),
            ILLLMWorkflowStep(
                id: 3,
                name: "compatibility_validation",
                action: "Run IL-LLM multi-compatibility check and ensure status is DONE.",
                expectedEvidence: "compatibility report with passed profiles"
            ),
            ILLLMWorkflowStep(
                id: 4,
                name: "skill_scope_resolution",
                action: "Resolve target skill `\(skill)` and map related files, specs, and tests.",
                expectedEvidence: "skill->file map and selected entry lines"
            ),
            ILLLMWorkflowStep(
                id: 5,
                name: "entry_line_focus",
                action: "Apply clean entry lines (\(entryLines.isEmpty ? "none configured" : entryLines.joined(separator: ", "))) to constrain runtime attention.",
                expectedEvidence: "entry-line constrained query context"
            ),
            ILLLMWorkflowStep(
                id: 6,
                name: "skill_execution",
                action: "Execute objective through deterministic route stack using selected skill and IL-LLM context.",
                expectedEvidence: "route, output artifact, and evidence packet"
            ),
            ILLLMWorkflowStep(
                id: 7,
                name: "proof_and_handoff",
                action: "Emit proof packet, audit outcome, next required move, and engineered repair/research path.",
                expectedEvidence: "chat delivery with outcome + next move + success path"
            )
        ]

        let successCriteria = [
            "IL-LLM compatibility status is DONE.",
            "Audit counts: simulated=0, inferred=0, blocked=0, not_done=0.",
            "Skill execution references real IL-LLM file evidence.",
            "Core runtime remains sealed and unchanged."
        ]

        return ILLLMWorkflowPlan(
            architect: BRAINKConstants.architectName,
            organization: BRAINKConstants.organizationName,
            signature: BRAINKConstants.authorshipSignature,
            status: "DONE",
            runtimePath: runtimePath,
            skillName: skill,
            objective: objectiveClean,
            frontierSealed: sealState,
            entryLines: entryLines,
            createdAt: ISO8601DateFormatter().string(from: Date()),
            steps: steps,
            successCriteria: successCriteria,
            nextMove: "Run step 2 -> 7 sequence now for the current objective and capture proof artifacts."
        )
    }

    static func writePlan(_ plan: ILLLMWorkflowPlan) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(plan)
        let url = URL(fileURLWithPath: BRAINKConstants.illlmWorkflowReportPath)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }

    static func asText(_ plan: ILLLMWorkflowPlan) -> String {
        let stepLines = plan.steps.map { step in
            """
            \(step.id). \(step.name)
            action: \(step.action)
            expected_evidence: \(step.expectedEvidence)
            """
        }.joined(separator: "\n")

        return """
        ILLLM SKILL WORKFLOW DELIVERY
        architect: \(plan.architect)
        organization: \(plan.organization)
        signature: \(plan.signature)
        status: \(plan.status)
        runtime_path: \(plan.runtimePath)
        skill: \(plan.skillName)
        objective: \(plan.objective)
        frontier_sealed: \(plan.frontierSealed ? "yes" : "no")
        workflow_report_path: \(BRAINKConstants.illlmWorkflowReportPath)

        WORKFLOW STEPS
        \(stepLines)

        SUCCESS CRITERIA
        \(plan.successCriteria.map { "- \($0)" }.joined(separator: "\n"))

        NEXT REQUIRED MOVE
        \(plan.nextMove)
        """
    }

    private static func normalizeSkill(_ raw: String) -> String {
        let cleaned = raw
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "\\s+", with: "_", options: .regularExpression)
            .lowercased()
        return cleaned.isEmpty ? "general_skill" : cleaned
    }
}
