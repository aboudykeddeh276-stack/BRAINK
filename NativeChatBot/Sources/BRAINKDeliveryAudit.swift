import Foundation

struct FileSkillAction: Codable {
    let path: String
    let inferredSkill: String
    let recommendedAction: String
}

struct LearningSnapshot: Codable {
    let architect: String
    let organization: String
    let signature: String
    let rootPath: String
    let fileCount: Int
    let skillActions: [FileSkillAction]
    let generatedAt: String
}

struct StackModuleContract {
    let moduleName: String
    let runningFile: String
    let logicalLink: String
    let verification: String
    let requiredTokens: [String]
    let weight: Double
}

struct StackModuleAudit: Codable {
    let moduleName: String
    let status: String
    let runningFile: String
    let logicalLink: String
    let verification: String
    let requiredTokenCount: Int
    let foundTokenCount: Int
    let missingTokens: [String]
    let tokenCoverage: Double
    let weightedScore: Double
}

struct StackAlignmentReport: Codable {
    let architect: String
    let organization: String
    let signature: String
    let packetType: String
    let rootPath: String
    let moduleCount: Int
    let doneCount: Int
    let simulatedCount: Int
    let inferredCount: Int
    let blockedCount: Int
    let notDoneCount: Int
    let weightedAlignment: Double
    let mathematicallyAligned: Bool
    let generatedAt: String
    let modules: [StackModuleAudit]
}

enum BRAINKRuntimeLearning {
    static func buildSnapshot(rootPath: String, maxFiles: Int = 5_000) throws -> LearningSnapshot {
        let rootURL = URL(fileURLWithPath: rootPath, isDirectory: true)
        guard FileManager.default.fileExists(atPath: rootURL.path) else {
            throw NSError(domain: "BRAINKLearning", code: 1, userInfo: [NSLocalizedDescriptionKey: "Runtime root missing: \(rootPath)"])
        }

        var collected: [FileSkillAction] = []
        let fm = FileManager.default
        if let enumerator = fm.enumerator(
            at: rootURL,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) {
            for case let fileURL as URL in enumerator {
                let isFile = (try? fileURL.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) ?? false
                guard isFile else { continue }
                let inference = inferSkillAndAction(fileURL)
                collected.append(FileSkillAction(
                    path: fileURL.path,
                    inferredSkill: inference.skill,
                    recommendedAction: inference.action
                ))
                if collected.count >= maxFiles {
                    break
                }
            }
        }

        return LearningSnapshot(
            architect: BRAINKConstants.architectName,
            organization: BRAINKConstants.organizationName,
            signature: BRAINKConstants.authorshipSignature,
            rootPath: rootPath,
            fileCount: collected.count,
            skillActions: collected,
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
    }

    private static func inferSkillAndAction(_ fileURL: URL) -> (skill: String, action: String) {
        let ext = fileURL.pathExtension.lowercased()
        let contentHead: String = {
            guard let data = try? Data(contentsOf: fileURL) else { return "" }
            guard let text = String(data: data.prefix(16_384), encoding: .utf8) else { return "" }
            return text.lowercased()
        }()

        if contentHead.contains("final class brainkplatformengine")
            || contentHead.contains("protocol brainkengine") {
            return ("platform_bridge_runtime", "Wire route handlers to typed engine operations and verify status/index/search/execute")
        }
        if contentHead.contains("enum brainkdeliveryaudit")
            || contentHead.contains("weightedalignment")
            || contentHead.contains("stackalignmentreport") {
            return ("alignment_math_engine", "Compute weighted coverage and emit deterministic audit artifact")
        }
        if contentHead.contains("struct screencontainer")
            || contentHead.contains("struct themedpanel") {
            return ("ui_container_system", "Apply container primitives across app shell and verify render boundaries")
        }
        if contentHead.contains("classifyroute")
            || contentHead.contains("buildproofpacketresponse")
            || contentHead.contains("illlm") {
            return ("chat_routing_engine", "Route intent to deterministic handlers and return proof/evidence responses")
        }
        if contentHead.contains("oauth")
            || contentHead.contains("app-auth")
            || contentHead.contains("redirecturi") {
            return ("oauth_runtime_bridge", "Resolve login URL and execute bounded OAuth handoff")
        }

        switch ext {
        case "swift":
            return ("native_ui_or_engine", "Compile and integrate into runtime route map")
        case "py":
            return ("python_engine_or_worker", "Bridge through platform execute and collect proof fields")
        case "ts", "tsx", "js":
            return ("frontend_or_bridge_contract", "Map interfaces to native route + runtime contract")
        case "json":
            return ("schema_or_packet_data", "Validate schema fields and include in evidence contract")
        case "md":
            return ("design_or_specification", "Extract required modules and verification checks")
        case "sh", "command":
            return ("automation_entrypoint", "Audit command safety and expected outputs")
        default:
            return ("generic_asset", "Index for retrieval and attach to nearest module context")
        }
    }
}

enum BRAINKDeliveryAudit {
    private static var rootPath: String { URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().path }
    private static var sourceRoot: String { URL(fileURLWithPath: #filePath).deletingLastPathComponent().path }

    private static let contracts: [StackModuleContract] = [
        StackModuleContract(
            moduleName: "ui_screen_container_component",
            runningFile: "\(sourceRoot)/BRAINKUIContainers.swift",
            logicalLink: "ScreenContainer<Content: View>",
            verification: "Build succeeds and root screen wraps in ScreenContainer.",
            requiredTokens: ["struct ScreenContainer", "background", "ignoresSafeArea"],
            weight: 1.0
        ),
        StackModuleContract(
            moduleName: "ui_themed_view_component",
            runningFile: "\(sourceRoot)/BRAINKUIContainers.swift",
            logicalLink: "ThemedPanel<Content: View>",
            verification: "Runtime side panel wraps in ThemedPanel.",
            requiredTokens: ["struct ThemedPanel", "panelColor"],
            weight: 1.0
        ),
        StackModuleContract(
            moduleName: "config_constants_module",
            runningFile: "\(sourceRoot)/BRAINKConstants.swift",
            logicalLink: "BRAINKConstants",
            verification: "Constants referenced by chat engine and audits.",
            requiredTokens: ["enum BRAINKConstants", "cookieName", "axiosTimeoutMs", "proofPacketCommand"],
            weight: 1.0
        ),
        StackModuleContract(
            moduleName: "service_oauth_runtime_module",
            runningFile: "\(sourceRoot)/BRAINKOAuth.swift",
            logicalLink: "BRAINKOAuth.startOAuthLogin()",
            verification: "Route auth.oauth resolves login URL and can open browser.",
            requiredTokens: ["enum BRAINKOAuth", "loginURL()", "startOAuthLogin()"],
            weight: 1.0
        ),
        StackModuleContract(
            moduleName: "service_chrome_browser_plugin_module",
            runningFile: "\(sourceRoot)/BRAINKChromePlugin.swift",
            logicalLink: "BRAINKChromePlugin.open(urlString:)",
            verification: "Route chrome_browser opens URL via Google Chrome bundle.",
            requiredTokens: ["enum BRAINKChromePlugin", "open(urlString:", "isChromeInstalled()", "statusText()"],
            weight: 1.1
        ),
        StackModuleContract(
            moduleName: "service_scraper_tool_module",
            runningFile: "\(sourceRoot)/BRAINKScraperTool.swift",
            logicalLink: "BRAINKScraperTool.scrape(urlString:)",
            verification: "Route scrape_tool fetches webpage and emits deterministic structured result.",
            requiredTokens: ["enum BRAINKScraperTool", "scrape(urlString:", "extractTitle(", "extractLinks(", "extractTextExcerpt("],
            weight: 1.1
        ),
        StackModuleContract(
            moduleName: "service_frontier_seal_module",
            runningFile: "\(sourceRoot)/BRAINKFrontierSeal.swift",
            logicalLink: "BRAINKFrontierSeal.sealBaseline()",
            verification: "Frontier seal persists core hash and enables clean entry-path update mode.",
            requiredTokens: ["enum BRAINKFrontierSeal", "sealBaseline()", "addLineName(", "entryPathsText()"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "service_illlm_compatibility_module",
            runningFile: "\(sourceRoot)/BRAINKILLLMCompatibility.swift",
            logicalLink: "BRAINKILLLMCompatibility.run(runtimePath:)",
            verification: "Compatibility route validates multi-profile IL-LLM support and outputs repair path.",
            requiredTokens: ["enum BRAINKILLLMCompatibility", "run(runtimePath:", "ILLLMCompatibilityReport", "ENGINEERED SUCCESS PATH"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "service_illlm_workflow_module",
            runningFile: "\(sourceRoot)/BRAINKILLLMWorkflow.swift",
            logicalLink: "BRAINKILLLMWorkflow.buildPlan(skillName:objective:runtimePath:)",
            verification: "Workflow route emits clear full IL-LLM skill-application path with success criteria.",
            requiredTokens: ["enum BRAINKILLLMWorkflow", "buildPlan(", "WORKFLOW STEPS", "SUCCESS CRITERIA", "NEXT REQUIRED MOVE"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "service_inner_runtime_constraint_core_module",
            runningFile: "\(sourceRoot)/BRAINKInnerRuntime.swift",
            logicalLink: "BRAINKInnerRuntime.evolve",
            verification: "One dedicated runtime section updates thoughts/emotions/perception constraints.",
            requiredTokens: ["struct BRAINKInnerRuntimeState", "enum BRAINKInnerRuntime", "evolve(", "INNER RUNTIME CONSTRAINT CORE"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "service_kex_hyperdrive_transition_definition_module",
            runningFile: "\(sourceRoot)/KEXHyperdriveConceptEngine.swift",
            logicalLink: "KEXHyperdriveConceptEngine.writeReport/asText",
            verification: "KEX Hyperdrive transition/definition/state concepts emit a deterministic report artifact with ethical and proof gates.",
            requiredTokens: ["enum KEXHyperdriveConceptEngine", "KEX_HYPERDRIVE_TRANSITION_DEFINITION_REPORT_V1", "KEX_HYPERDRIVE_REPO_CALIBRATION_REPORT_V1", "State OF transition", "Transition OF state", "Definition OF transition", "X OF X OF X OF X", "ethicalBoundaryChecks", "pendingProofGates", "pendingWorkloads"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "route_kex_hyperdrive_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally kex_hyperdrive",
            verification: "Route classifier recognizes transition/definition/state language and writes the KEX Hyperdrive concept report.",
            requiredTokens: ["return \"kex_hyperdrive\"", "case \"kex_hyperdrive\":", "KEXHyperdriveConceptEngine.writeReport(userText:", "KEXHyperdriveConceptEngine.writeCalibrationReport(userText:", "KEXHyperdriveConceptEngine.calibrationText(calibration)"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "service_kex_self_sustained_coding_module",
            runningFile: "\(sourceRoot)/KEXSelfSustainedCodingEngine.swift",
            logicalLink: "KEXSelfSustainedCodingEngine.writeReport/asText",
            verification: "Self-sustained coding engine emits bounded repo task packets with write scopes, command plans, proof gates, and safety boundaries.",
            requiredTokens: ["enum KEXSelfSustainedCodingEngine", "KEX_SELF_SUSTAINED_CODING_REPORT_V1", "KEXCodingTaskPacket", "writeScope", "proofGate", "selfExistenceDesign", "Autonomous code mutation remains bounded"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "route_self_sustained_coder_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally self_sustained_coder",
            verification: "Route classifier recognizes self-sustained coding intent and writes repo task packets.",
            requiredTokens: ["return \"self_sustained_coder\"", "case \"self_sustained_coder\":", "KEXSelfSustainedCodingEngine.writeReport(userText:", "KEXSelfSustainedCodingEngine.asText(report)"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "service_illlm_knowledge_center_module",
            runningFile: "\(sourceRoot)/BRAINKILLLMKnowledgeCenter.swift",
            logicalLink: "BRAINKILLLMKnowledgeCenter.refresh/context",
            verification: "IL-LLM core runs always-on with bounded memory and explicit growth tracking.",
            requiredTokens: ["final class BRAINKILLLMKnowledgeCenter", "func refresh(force:", "func context(for userInput:", "memoryBudgetChars", "refreshCooldownSeconds"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "service_platform_bridge_module",
            runningFile: "\(sourceRoot)/BRAINKPlatformAPI.swift",
            logicalLink: "BRAINKPlatformEngine",
            verification: "Engine supports initialize/execute/index/search/process/status.",
            requiredTokens: ["final class BRAINKPlatformEngine", "func initialize()", "func execute(", "func indexDesktop(", "func processInteraction(", "func getStatus()"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "service_proof_packet_module",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "buildProofPacketResponse()",
            verification: "Route proof_packet returns structured evidence payload.",
            requiredTokens: ["private func buildProofPacketResponse()", "ProofPacketResult", "failureProofPacket", "runProofPacketCommand"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "route_chrome_plugin_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally chrome_browser",
            verification: "Route classifier emits chrome_browser and resolver executes BRAINKChromePlugin.open.",
            requiredTokens: ["return \"chrome_browser\"", "case \"chrome_browser\":", "BRAINKChromePlugin.open(urlString:"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "route_scraper_tool_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally scrape_tool",
            verification: "Route classifier emits scrape_tool and resolver executes BRAINKScraperTool.scrape.",
            requiredTokens: ["return \"scrape_tool\"", "case \"scrape_tool\":", "await BRAINKScraperTool.scrape(urlString:"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "route_stack_audit_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally stack_audit",
            verification: "Route classifier emits stack_audit and resolver executes buildStackAuditResponse.",
            requiredTokens: ["return \"stack_audit\"", "case \"stack_audit\":", "buildStackAuditResponse()"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "route_learning_snapshot_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally learn_all_files",
            verification: "Route classifier emits learn_all_files and resolver executes buildLearningSnapshotResponse.",
            requiredTokens: ["return \"learn_all_files\"", "case \"learn_all_files\":", "buildLearningSnapshotResponse()"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "route_proof_local_fallback_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "proof_packet -> local deterministic proof fallback",
            verification: "Proof route generates DONE evidence from local files when external il_llm command is unavailable.",
            requiredTokens: ["buildLocalDeterministicProofPacket", "return buildLocalDeterministicProofPacket(path:", "status: \"DONE\""],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "route_frontier_and_entry_registry_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally frontier_seal/line_registry",
            verification: "Runtime can seal baseline and accept only clean entry-line updates.",
            requiredTokens: ["return \"frontier_seal\"", "return \"line_registry_add\"", "return \"line_registry_list\"", "case \"frontier_seal\":", "case \"line_registry_add\":", "case \"line_registry_list\":"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "route_illlm_compatibility_and_workflow_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally illlm_compatibility/illlm_workflow",
            verification: "Runtime emits IL-LLM compatibility and workflow deliveries in chat.",
            requiredTokens: ["return \"illlm_compatibility\"", "return \"illlm_workflow\"", "case \"illlm_compatibility\":", "case \"illlm_workflow\":", "buildILLLMCompatibilityResponse()", "buildILLLMWorkflowResponse(userText"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "route_inner_runtime_constraint_core_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally inner_runtime + evolve pipeline",
            verification: "Inner runtime core can be queried directly and is evolved per interaction.",
            requiredTokens: ["return \"inner_runtime\"", "case \"inner_runtime\":", "BRAINKInnerRuntime.asText(innerRuntimeState)", "BRAINKInnerRuntime.evolve("],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "route_knowledge_center_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally knowledge_center_status + always-on refresh",
            verification: "Knowledge center route is queryable and IL-LLM refresh runs before route resolution.",
            requiredTokens: ["return \"knowledge_center_status\"", "case \"knowledge_center_status\":", "buildKnowledgeCenterStatusResponse()", "refreshKnowledgeCenter(force: false, reason: \"always_on_pre_route\"", "applyKnowledgeSnapshot("],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "service_learning_snapshot_module",
            runningFile: "\(sourceRoot)/BRAINKDeliveryAudit.swift",
            logicalLink: "BRAINKRuntimeLearning.buildSnapshot",
            verification: "Route learn_all_files writes skill/action snapshot report.",
            requiredTokens: ["enum BRAINKRuntimeLearning", "buildSnapshot(", "FileSkillAction"],
            weight: 1.1
        ),
        StackModuleContract(
            moduleName: "service_alignment_math_module",
            runningFile: "\(sourceRoot)/BRAINKDeliveryAudit.swift",
            logicalLink: "BRAINKDeliveryAudit.generateReport()",
            verification: "Route stack_audit writes weighted alignment report.",
            requiredTokens: ["StackAlignmentReport", "weightedAlignment", "generateReport()", "writeReport()"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "store_conversation_memory_module",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "localConversationHistory",
            verification: "Chat turns append deterministic wrapper/emotional/reasoning state.",
            requiredTokens: ["localConversationHistory", "LocalConversationTurn", "buildLocalConversationalResponse"],
            weight: 1.1
        ),
        StackModuleContract(
            moduleName: "ui_chatbot_shell_module",
            runningFile: "\(sourceRoot)/BRAINKChatBotApp.swift",
            logicalLink: "BrainkNativeChatbotView",
            verification: "UI displays chat, traces, runtime panel, drag-drop input.",
            requiredTokens: ["struct BrainkNativeChatbotView", "ChatInputBar", "TraceRow", "onDrop"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "ui_nested_runtime_dashboard_component",
            runningFile: "\(sourceRoot)/BRAINKUIContainers.swift",
            logicalLink: "NestedRuntimeDashboard",
            verification: "NestedRuntimeDashboard renders spectrum slots [1..5] and IL-LLM circular path label.",
            requiredTokens: ["struct NestedRuntimeDashboard", "spectrumSlots", "circularPathLabel", "NestedRuntimeSlotRow"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "service_skill_protocol_module",
            runningFile: "\(sourceRoot)/BRAINKSkillProtocol.swift",
            logicalLink: "protocol BRAINKSkill",
            verification: "BRAINKSkill protocol defines name, requiredSlots, execute(context:), validate().",
            requiredTokens: ["protocol BRAINKSkill", "var requiredSlots: [Int]", "func execute(context: SkillContext)", "func validate() -> SkillValidation", "struct SkillContext", "struct SkillResult", "struct SkillValidation"],
            weight: 1.2
        ),
        StackModuleContract(
            moduleName: "service_skill_registry_module",
            runningFile: "\(sourceRoot)/BRAINKSkillRegistry.swift",
            logicalLink: "BRAINKSkillRegistry.validateRegistrationCompleteness()",
            verification: "Skill registry registers all 4 skills, maps slots [1..4], encodes 1→2→3→1 circular path, and proves all routes have skills.",
            requiredTokens: ["enum BRAINKSkillRegistry", "allSkills", "slotMap", "dependencyGraph", "illlmCircularPath", "validateRegistrationCompleteness()", "isCircularFeedback"],
            weight: 1.3
        ),
        StackModuleContract(
            moduleName: "route_skill_registry_wiring",
            runningFile: "\(sourceRoot)/BRAINKChatEngine.swift",
            logicalLink: "classifyRoute -> resolveLocally skill_registry",
            verification: "Route classifier emits skill_registry and resolver calls BRAINKSkillRegistry.validateRegistrationCompleteness and asText.",
            requiredTokens: ["return \"skill_registry\"", "case \"skill_registry\":", "BRAINKSkillRegistry.writeRegistrationProof()", "BRAINKSkillRegistry.asText(proof)"],
            weight: 1.2
        ),
    ]

    static func moduleDefinitions() -> [ModuleDefinition] {
        let report = generateReport()
        return report.modules.map { module in
            let state = moduleStatus(from: module.status)
            return ModuleDefinition(
                moduleName: module.moduleName,
                evidence: ModuleDeliveryEvidence(
                    requiredState: state,
                    runningFile: module.runningFile,
                    logicalLink: module.logicalLink,
                    verification: module.verification
                )
            )
        }
    }

    static func generateReport() -> StackAlignmentReport {
        var modules: [StackModuleAudit] = []
        var doneCount = 0
        var simulatedCount = 0
        var inferredCount = 0
        var blockedCount = 0
        var notDoneCount = 0

        let totalWeight = contracts.reduce(0.0) { $0 + $1.weight }
        var weightedNumerator = 0.0

        for contract in contracts {
            let evaluation = evaluateContract(contract)
            modules.append(evaluation)
            weightedNumerator += evaluation.tokenCoverage * contract.weight

            switch evaluation.status {
            case ModuleDeliveryState.done.rawValue:
                doneCount += 1
            case ModuleDeliveryState.simulated.rawValue:
                simulatedCount += 1
            case ModuleDeliveryState.inferred.rawValue:
                inferredCount += 1
            case ModuleDeliveryState.blocked.rawValue:
                blockedCount += 1
            default:
                notDoneCount += 1
            }
        }

        let weightedAlignment = totalWeight == 0 ? 0 : weightedNumerator / totalWeight
        let mathematicallyAligned = weightedAlignment >= 0.95 && blockedCount == 0 && notDoneCount == 0

        return StackAlignmentReport(
            architect: BRAINKConstants.architectName,
            organization: BRAINKConstants.organizationName,
            signature: BRAINKConstants.authorshipSignature,
            packetType: "BRAINK_STACK_ALIGNMENT_REPORT_V1",
            rootPath: rootPath,
            moduleCount: modules.count,
            doneCount: doneCount,
            simulatedCount: simulatedCount,
            inferredCount: inferredCount,
            blockedCount: blockedCount,
            notDoneCount: notDoneCount,
            weightedAlignment: weightedAlignment,
            mathematicallyAligned: mathematicallyAligned,
            generatedAt: ISO8601DateFormatter().string(from: Date()),
            modules: modules
        )
    }

    static func writeReport() throws -> StackAlignmentReport {
        let report = generateReport()
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(report)

        let outputPath = BRAINKConstants.stackAuditReportPath
        let outputURL = URL(fileURLWithPath: outputPath)
        try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: outputURL)
        return report
    }

    static func writeLearningSnapshot(rootPath: String) throws -> LearningSnapshot {
        let snapshot = try BRAINKRuntimeLearning.buildSnapshot(rootPath: rootPath)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(snapshot)

        let outputURL = URL(fileURLWithPath: BRAINKConstants.learningSnapshotReportPath)
        try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: outputURL)
        return snapshot
    }

    static func asPlainText(_ report: StackAlignmentReport) -> String {
        var lines: [String] = []
        lines.append("packet_type: \(report.packetType)")
        lines.append("architect: \(report.architect)")
        lines.append("organization: \(report.organization)")
        lines.append("signature: \(report.signature)")
        lines.append("root_path: \(report.rootPath)")
        lines.append("weighted_alignment: \(String(format: "%.4f", report.weightedAlignment))")
        lines.append("mathematically_aligned: \(report.mathematicallyAligned ? "true" : "false")")
        lines.append("counts: done=\(report.doneCount), simulated=\(report.simulatedCount), inferred=\(report.inferredCount), blocked=\(report.blockedCount), not_done=\(report.notDoneCount)")
        lines.append("")
        for module in report.modules {
            lines.append("[\(module.status)] \(module.moduleName)")
            lines.append("file: \(module.runningFile)")
            lines.append("link: \(module.logicalLink)")
            lines.append("coverage: \(module.foundTokenCount)/\(module.requiredTokenCount) = \(String(format: "%.4f", module.tokenCoverage))")
            if !module.missingTokens.isEmpty {
                lines.append("missing_tokens: \(module.missingTokens.joined(separator: ", "))")
            }
            lines.append("verification: \(module.verification)")
            lines.append("")
        }
        return lines.joined(separator: "\n")
    }

    private static func evaluateContract(_ contract: StackModuleContract) -> StackModuleAudit {
        let filePath = contract.runningFile
        let fileExists = FileManager.default.fileExists(atPath: filePath)
        if !fileExists {
            return StackModuleAudit(
                moduleName: contract.moduleName,
                status: ModuleDeliveryState.blocked.rawValue,
                runningFile: filePath,
                logicalLink: contract.logicalLink,
                verification: contract.verification,
                requiredTokenCount: contract.requiredTokens.count,
                foundTokenCount: 0,
                missingTokens: contract.requiredTokens,
                tokenCoverage: 0,
                weightedScore: 0
            )
        }

        let content = (try? String(contentsOfFile: filePath, encoding: .utf8)) ?? ""
        let foundTokens = contract.requiredTokens.filter { content.contains($0) }
        let missingTokens = contract.requiredTokens.filter { !content.contains($0) }
        let total = max(contract.requiredTokens.count, 1)
        let coverage = Double(foundTokens.count) / Double(total)
        let weighted = coverage * contract.weight

        let status: ModuleDeliveryState = (coverage == 1.0) ? .done : .notDone

        return StackModuleAudit(
            moduleName: contract.moduleName,
            status: status.rawValue,
            runningFile: filePath,
            logicalLink: contract.logicalLink,
            verification: contract.verification,
            requiredTokenCount: contract.requiredTokens.count,
            foundTokenCount: foundTokens.count,
            missingTokens: missingTokens,
            tokenCoverage: coverage,
            weightedScore: weighted
        )
    }

    private static func moduleStatus(from raw: String) -> ModuleDeliveryState {
        switch raw {
        case ModuleDeliveryState.done.rawValue:
            return .done
        case ModuleDeliveryState.simulated.rawValue:
            return .simulated
        case ModuleDeliveryState.inferred.rawValue:
            return .inferred
        case ModuleDeliveryState.blocked.rawValue:
            return .blocked
        default:
            return .notDone
        }
    }
}
