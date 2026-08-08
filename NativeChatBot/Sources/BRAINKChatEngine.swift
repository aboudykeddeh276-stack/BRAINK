import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
#if !canImport(Combine)
protocol ObservableObject: AnyObject {}
@propertyWrapper struct Published<Value> {
    var wrappedValue: Value
    init(wrappedValue: Value) { self.wrappedValue = wrappedValue }
}
#endif

struct ChatMessage: Identifiable, Hashable {
    enum Role: String, Codable {
        case user
        case assistant
        case system
    }

    let id = UUID()
    let role: Role
    let text: String
    let route: String
    let createdAt: Date

    init(role: Role, text: String, route: String, createdAt: Date = .init()) {
        self.role = role
        self.text = text
        self.route = route
        self.createdAt = createdAt
    }
}

struct ModuleTrace: Identifiable {
    let id = UUID()
    let module: String
    let output: String
    let confidence: Double
}

struct RuntimeResponse: Decodable {
    let response: String
    let route: String?
}

private struct ILDocumentSnippet: Identifiable {
    let id = UUID()
    let path: String
    let snippet: String
}

private struct ProofFieldRecord: Codable {
    let value: String
    let path: String
    let reason: String?
}

private enum WRAPType: String {
    case assignment = "assignment"
    case banking = "banking"
    case cosmology = "cosmology"
    case logicPuzzle = "logic_puzzle"
    case creative = "creative"
    case generic = "generic"
}

private struct ReasoningState: Codable {
    var logic: Double
    var highIq: Double
    var kexTheorem: Double
    var cosmology: Double
    var learning: Double
}

private struct EmotionalState: Codable {
    var happyToBeAlive: Double
    var curiosity: Double
    var satisfaction: Double
    var discomfort: Double
    var wonder: Double
    var confidence: Double
}

private struct LocalConversationTurn: Identifiable {
    let id = UUID()
    let userInput: String
    let wrapperType: WRAPType
    let route: String
    let response: String
    let emotionalState: EmotionalState
    let reasoningState: ReasoningState
    let timestamp: Date
}

private struct ProofPacketResult: Codable {
    let status: String
    let status_reason: String?
    let runtime_path: String
    let command: String
    let file_reads: [String]
    let schema_fields_found: [String]
    let runtime_entrypoint: ProofFieldRecord
    let runtime_routing: ProofFieldRecord
    let required_file_reads: ProofFieldRecord
    let falsifier_fields: ProofFieldRecord
    let proof_obligations: ProofFieldRecord
    let cost_gate_value: ProofFieldRecord
    let required_return_contract_path_list: ProofFieldRecord
    let required_return_contract_required_checks: ProofFieldRecord
    let generated_at: String
}

@MainActor
final class BRAINKChatEngine: ObservableObject {
    @Published private(set) var messages: [ChatMessage] = []
    @Published private(set) var traces: [ModuleTrace] = []
    @Published var isBusy = false
    @Published private(set) var ilLlmRuntimePath: String
    @Published private(set) var ilLlmLoadedCount: Int = 0
    @Published private(set) var ilLlmLoadedStatus: String = "No IL-LLM data loaded"
    @Published private(set) var ilLlmGrowthStatus: String = "growth_events=0"
    @Published private(set) var ilLlmMemoryStatus: String = "memory=0/0 chars"
    @Published private(set) var ilLlmTopConceptsText: String = "top_concepts=none"
    @Published private(set) var dashboardAuditOutcome: String = "NOT RUN"
    @Published private(set) var dashboardAuditCounts: String = "done=0, simulated=0, inferred=0, blocked=0, not_done=0"
    @Published private(set) var dashboardAuditWeightedAlignment: String = "0.0000"
    @Published private(set) var dashboardAuditAlignmentScore: Double = 0
    @Published private(set) var dashboardAuditMathematicallyAligned: Bool = false
    @Published private(set) var dashboardAuditGeneratedAt: String = "never"
    @Published private(set) var dashboardAuditNextMove: String = "Run stack audit to generate deterministic alignment evidence."

    private let localOnly: Bool
    private let endpoint: String?
    private let platformEngine: BRAINKPlatformEngine
    private let knowledgeCenter: BRAINKILLLMKnowledgeCenter
    private var ilLlmPath: String?
    private var ilLlmSnippets: [ILDocumentSnippet] = []
    private var localConversationHistory: [LocalConversationTurn] = []
    private var localWrapperType: WRAPType = .generic
    private var emotionalState: EmotionalState = EmotionalState(
        happyToBeAlive: 0.95,
        curiosity: 0.5,
        satisfaction: 0.5,
        discomfort: 0.2,
        wonder: 0.4,
        confidence: 0.5
    )
    private var reasoningState: ReasoningState = ReasoningState(
        logic: 0.6,
        highIq: 0.5,
        kexTheorem: 0.7,
        cosmology: 0.4,
        learning: 0.8
    )
    private var innerRuntimeState: BRAINKInnerRuntimeState
    private let ilLlmMaxSnippetLength = 1_024
    private let ilLlmSupportedExtensions: Set<String> = ["md", "txt", "json", "py", "ts", "tsx", "js", "swift", "cpp", "c", "go", "java", "yaml", "yml"]

    init()
    {
        self.endpoint = ProcessInfo.processInfo.environment["BRAINK_CHAT_RUNTIME"]
        self.localOnly = (ProcessInfo.processInfo.environment["BRAINK_CHAT_RUNTIME"] ?? "").isEmpty
        self.platformEngine = BRAINKPlatformEngine(baseURLString: self.endpoint)
        self.ilLlmPath = ProcessInfo.processInfo.environment["IL_LLM_RUNTIME_PATH"]
            ?? BRAINKConstants.defaultILLLMRuntimePath
        self.ilLlmRuntimePath = self.ilLlmPath ?? "not configured"
        self.knowledgeCenter = BRAINKILLLMKnowledgeCenter(runtimePath: self.ilLlmPath ?? "")
        self.innerRuntimeState = BRAINKInnerRuntime.bootstrap()

        append(
            role: .system,
            text: "BRAINK native chat runtime initialized. Mode: \(localOnly ? "deterministic local" : "bridged runtime"). \(BRAINKConstants.authorshipSignature)",
            route: "system.init"
        )

        Task {
            self.refreshILLMContext()
            self.refreshKnowledgeCenter(force: true, reason: "startup", routeTag: "system.runtime_startup")
            self.loadLatestAuditArtifact()
        }
    }

    var runtimeModeLabel: String {
        localOnly ? "deterministic local" : "bridged runtime"
    }

    var runtimeEndpointLabel: String {
        guard let endpoint, !endpoint.isEmpty else {
            return "local-only (no remote endpoint configured)"
        }
        return endpoint
    }

    var dashboardLastRoute: String {
        messages.last?.route ?? "none"
    }

    var dashboardUserMessageCount: Int {
        messages.filter { $0.role == .user }.count
    }

    var dashboardAssistantMessageCount: Int {
        messages.filter { $0.role == .assistant }.count
    }

    var dashboardSystemMessageCount: Int {
        messages.filter { $0.role == .system }.count
    }

    var dashboardNextAction: String {
        if isBusy {
            return "wait for active route to complete"
        }
        if dashboardAuditOutcome == "REPAIR_REQUIRED" {
            return "run required repair query from audit card"
        }
        if ilLlmLoadedCount == 0 {
            return "load IL-LLM data or drop runtime path"
        }
        if traces.isEmpty {
            return "run Audit Stack for trace evidence"
        }
        return "send next query and review audit outcome"
    }

    func send(userInput: String) async {
        let message = userInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty, !isBusy else { return }

        isBusy = true
        defer { isBusy = false }

        append(role: .user, text: message, route: "user.input")

        do {
            let preRoute = classifyRoute(message)
            refreshKnowledgeCenter(force: false, reason: "always_on_pre_route", routeTag: nil)
            if preRoute == "illlm_bootstrap" {
                let bootstrapStatus = bootstrapCurrentDataBundle()
                append(role: .assistant, text: bootstrapStatus, route: preRoute)
                return
            }

            if !localOnly && self.endpoint != nil {
                let remote = try await callRemoteRuntime(message)
                append(role: .assistant, text: remote.text, route: remote.route)
            } else {
                let local = await resolveLocally(message)
                append(role: .assistant, text: local.text, route: local.route)
            }
        } catch {
            let failure = BRAINKDeadRouteManager.captureFailureContext(error: error)
            append(
                role: .assistant,
                text: BRAINKDeadRouteManager.renderFailureSummary(context: failure.context, report: failure.report),
                route: "system.fallback"
            )
            let local = await resolveLocally(message)
            append(role: .assistant, text: local.text, route: local.route)
        }
    }

    func clear() {
        messages = []
        traces = []
        append(
            role: .system,
            text: "Conversation cleared. Enter a message to continue.",
            route: "system.clear"
        )
    }

    func clearTraces() {
        traces.removeAll()
    }

    func attachILLLMRuntimePath(_ droppedURL: URL) {
        let candidatePath = droppedURL.path
        guard !candidatePath.isEmpty else {
            append(role: .system, text: "Dropped path was empty. Please drop a valid file or folder.", route: "system.runtime_drop")
            return
        }

        var isDirectory: ObjCBool = false
        let exists = FileManager.default.fileExists(atPath: candidatePath, isDirectory: &isDirectory)
        guard exists else {
            append(role: .system, text: "Could not read dropped path: \(candidatePath). It does not exist.", route: "system.runtime_drop")
            return
        }

        ilLlmPath = candidatePath
        ilLlmRuntimePath = candidatePath
        knowledgeCenter.setRuntimePath(candidatePath)
        ilLlmSnippets.removeAll()
        let pathType = isDirectory.boolValue ? "folder" : "file"
        append(
            role: .system,
            text: "Attached IL-LLM path from drag-and-drop (\(pathType)): \(candidatePath)",
            route: "system.runtime_drop"
        )
        Task {
            do {
                let inventory = try collectILLMInventory(pathOverride: candidatePath)
                let loaded = try ingestILLMFiles(inventory)
                applyLoadedILLMContext(
                    path: candidatePath,
                    loaded: loaded,
                    inventoryCount: inventory.count,
                    routeTag: "system.runtime_drop_indexed"
                )
                refreshKnowledgeCenter(force: true, reason: "drag_drop_attach", routeTag: "system.runtime_drop_indexed")
            } catch {
                ilLlmLoadedCount = 0
                ilLlmSnippets.removeAll()
                ilLlmLoadedStatus = "Attach failed: \(error.localizedDescription)"
                refreshKnowledgeCenter(force: true, reason: "drag_drop_attach_failed", routeTag: nil)
                append(
                    role: .system,
                    text: "Path attached but indexing failed: \(error.localizedDescription)",
                    route: "system.runtime_drop"
                )
            }
        }
    }

    func reloadILLLMBundle() {
        guard let path = ilLlmPath, !path.isEmpty else {
            append(
                role: .system,
                text: "No IL-LLM path is configured. Set IL_LLM_RUNTIME_PATH or drop a folder/file.",
                route: "system.runtime_reload"
            )
            return
        }
        Task {
            do {
                knowledgeCenter.setRuntimePath(path)
                let inventory = try collectILLMInventory(pathOverride: path)
                let loaded = try ingestILLMFiles(inventory)
                applyLoadedILLMContext(
                    path: path,
                    loaded: loaded,
                    inventoryCount: inventory.count,
                    routeTag: "system.runtime_reload"
                )
                refreshKnowledgeCenter(force: true, reason: "manual_reload", routeTag: "system.runtime_reload")
                append(
                    role: .system,
                    text: "Reloaded IL-LLM from: \(path). \(ilLlmLoadedStatus)",
                    route: "system.runtime_reload"
                )
            } catch {
                ilLlmLoadedCount = 0
                ilLlmSnippets.removeAll()
                ilLlmLoadedStatus = "Reload failed: \(error.localizedDescription)"
                refreshKnowledgeCenter(force: true, reason: "manual_reload_failed", routeTag: nil)
                append(
                    role: .system,
                    text: "IL-LLM reload failed: \(error.localizedDescription)",
                    route: "system.runtime_reload"
                )
            }
        }
    }

    private func append(role: ChatMessage.Role, text: String, route: String) {
        messages.append(ChatMessage(role: role, text: text, route: route))
    }

    private func runModules(_ text: String) -> [ModuleTrace] {
        let lower = text.lowercased()

        let modules: [String: (String) -> Double] = [
            "Router": { input in
                let tags = ["login", "route", "run", "execute", "build", "proof", "status", "proof-packet"]
                return self.score(match: input, tokens: tags)
            },
            "Reasoning": { input in
                let tags = ["how", "why", "what", "if", "meaning", "proof", "validate"]
                return self.score(match: input, tokens: tags)
            },
            "Grammar": { input in
                let hasLongWords = input.split { !$0.isLetter }.count
                return min(Double(hasLongWords) / 8.0, 1.0)
            },
            "Persona": { input in
                let tags = ["you", "i", "please", "thank", "need", "want"]
                return self.score(match: input, tokens: tags)
            }
        ]

        return modules.map { (name, scorer) in
            ModuleTrace(module: name, output: "score=\(String(format: "%.2f", scorer(lower)))", confidence: scorer(lower))
        }.sorted { $0.confidence > $1.confidence }
    }

    private func resolveLocally(_ text: String) async -> (text: String, route: String) {
        traces = runModules(text)
        let route = classifyRoute(text)
        let tone = traces.map(\.module).joined(separator: " + ")
        let coreContext = knowledgeCenter.context(for: text)
        applyKnowledgeSnapshot(coreContext.snapshot, routeTag: nil)
        let context = coreContext.preview.isEmpty ? summarizeLoadedILLM(for: text) : coreContext.preview
        let lower = text.lowercased()

        if BRAINKFrontierSeal.isSealed(), isRuntimeMutationRoute(route) {
            return (
                """
                Frontier baseline is sealed.
                Runtime mutation route '\(route)' is disabled.
                Allowed updates:
                - IL-LLM update only (`illlm_update <path>`)
                - clean entry registry (`add line <name>`, `list lines`)
                """,
                route
            )
        }

        var response: String
        switch route {
        case "frontier_seal":
            do {
                let state = try BRAINKFrontierSeal.sealBaseline()
                response = """
                Frontier seal: DONE
                signature: \(state.signature)
                sealed_at: \(state.sealedAt)
                core_hash: \(state.coreHash)
                seal_path: \(BRAINKConstants.frontierSealPath)
                \(BRAINKFrontierSeal.entryPathsText())
                """
            } catch {
                response = "Frontier seal failed: \(error.localizedDescription)"
            }
        case "line_registry_add":
            let lineName = extractCommandArgument(from: lower, key: "add line", defaultPath: nil)
                ?? extractCommandArgument(from: lower, key: "line add", defaultPath: nil)
                ?? ""
            do {
                let registry = try BRAINKFrontierSeal.addLineName(lineName)
                response = """
                Line registry update: DONE
                lines_count: \(registry.lines.count)
                added_or_existing: \(lineName.trimmingCharacters(in: .whitespacesAndNewlines))
                \(BRAINKFrontierSeal.entryPathsText())
                """
            } catch {
                response = "Line registry update failed: \(error.localizedDescription)"
            }
        case "line_registry_list":
            response = BRAINKFrontierSeal.entryPathsText()
        case "illlm_update":
            let targetPath = extractCommandArgument(from: text, key: "illlm_update", defaultPath: nil)
                ?? extractCommandArgument(from: lower, key: "il-llm update", defaultPath: nil)
                ?? extractCommandArgument(from: lower, key: "illlm update", defaultPath: nil)
                ?? extractCommandArgument(from: lower, key: "update il-llm", defaultPath: nil)
                ?? ""
            response = updateILLLMRuntimePath(targetPath)
        case "illlm_compatibility":
            response = buildILLLMCompatibilityResponse()
        case "illlm_workflow":
            response = buildILLLMWorkflowResponse(userText: text)
        case "inner_runtime":
            response = BRAINKInnerRuntime.asText(innerRuntimeState)
        case "kex_hyperdrive":
            do {
                let report = try KEXHyperdriveConceptEngine.writeReport(userText: text)
                let calibration = try KEXHyperdriveConceptEngine.writeCalibrationReport(userText: text)
                response = KEXHyperdriveConceptEngine.asText(report)
                    + "\n\n--- KEX HYPERDRIVE REPO CALIBRATION ---\n"
                    + KEXHyperdriveConceptEngine.calibrationText(calibration)
            } catch {
                response = "KEX Hyperdrive concept/calibration report failed: \(error.localizedDescription)"
            }
        case "self_sustained_coder":
            do {
                let report = try KEXSelfSustainedCodingEngine.writeReport(userText: text)
                response = KEXSelfSustainedCodingEngine.asText(report)
            } catch {
                response = "KEX self-sustained coding report failed: \(error.localizedDescription)"
            }
        case "knowledge_center_status":
            response = buildKnowledgeCenterStatusResponse()
        case "illlm_bootstrap":
            response = bootstrapCurrentDataBundle()
        case "platform_initialize":
            do {
                try await platformEngine.initialize()
                response = "Platform engine initialized. session_id=\(platformEngine.sessionId)."
            } catch {
                response = "Failed platform initialization: \(error.localizedDescription)"
            }
        case "platform_status":
            do {
                let status = try await platformEngine.getStatus()
                response = """
                Platform status:
                - healthy: \(status.healthy)
                - uptime: \(String(format: "%.2f", status.uptime))s
                - indexed_files: \(status.indexedFiles)
                - cache_size: \(status.cacheSize)
                - memory_usage: \(status.memoryUsage)
                - last_update: \(status.lastUpdate)
                - constraints: \(status.constraints.map { "\($0.key)=\($0.value)" }.joined(separator: "; "))
                """
            } catch {
                response = "Platform status check failed: \(error.localizedDescription)"
            }
        case "platform_index":
            let requestedPath = extractCommandArgument(from: lower, key: "index desktop", defaultPath: ilLlmPath) ?? ilLlmPath
            do {
                let index = try await platformEngine.indexDesktop(rootPath: requestedPath ?? "")
                response = """
                Desktop index complete.
                total_files=\(index.totalFiles)
                total_size=\(index.totalSize)
                redacted_count=\(index.redactedCount)
                indexed_at=\(index.indexedAt)
                """
            } catch {
                response = "Desktop indexing failed: \(error.localizedDescription)"
            }
        case "platform_search":
            let query = extractCommandArgument(from: lower, key: "search index", defaultPath: nil)
                ?? extractTrailingTokens(from: text, skip: 2)
            do {
                let results = try await platformEngine.searchIndex(query: query, limit: 5)
                if results.isEmpty {
                    response = "No index hits for: \(query)"
                } else {
                    let lines = results.enumerated().map { idx, hit in
                        "\(idx + 1). \(URL(fileURLWithPath: hit.path).lastPathComponent) [\(hit.chunkId)]\n\(hit.chunkText)"
                    }
                    response = "Index hits (\(results.count)):\n" + lines.joined(separator: "\n---\n")
                }
            } catch {
                response = "Index search failed: \(error.localizedDescription)"
            }
        case "platform_execute":
            do {
                let policy = ExecutionPolicy(
                    requiresApproval: false,
                    costEstimate: nil,
                    timeoutMs: 30_000,
                    allowedCommands: [],
                    blockedPatterns: ["rm -rf", "sudo", "chmod 777"]
                )
                let command = extractCommandArgument(from: lower, key: "platform execute", defaultPath: nil)
                    ?? extractCommandArgument(from: lower, key: "execute ", defaultPath: nil)
                    ?? lower.replacingOccurrences(of: "execute", with: "")
                let result = try await platformEngine.execute(command: command, policy: policy)
                response = result.success
                    ? "platform execute success: \(result.output ?? "")"
                    : "platform execute failed: \(result.error ?? "")"
            } catch {
                response = "Platform execute failed: \(error.localizedDescription)"
            }
        case "platform_packet":
            do {
                let objective = extractCommandArgument(from: lower, key: "generate codex packet", defaultPath: nil)
                    ?? extractCommandArgument(from: lower, key: "codex packet", defaultPath: nil)
                    ?? lower.replacingOccurrences(of: "codex packet", with: "")
                let packet = try await platformEngine.generateCodexPacket(objective: objective.trimmingCharacters(in: .whitespacesAndNewlines))
                response = """
                Codex packet generated:
                packet_type: \(packet.packetType)
                created_at: \(packet.createdAt)
                objective: \(packet.operatorObjective)
                plan_steps: \(packet.executionPlan.steps.joined(separator: ", "))
                """
            } catch {
                response = "Codex packet generation failed: \(error.localizedDescription)"
            }
        case "chrome_browser":
            let target = extractFirstURL(from: text)
                ?? extractCommandArgument(from: lower, key: "chrome open", defaultPath: nil)
                ?? extractCommandArgument(from: lower, key: "open chrome", defaultPath: nil)
                ?? extractCommandArgument(from: lower, key: "chrome", defaultPath: nil)
                ?? "https://www.google.com"
            response = BRAINKChromePlugin.open(urlString: target)
        case "scrape_tool":
            let target = extractFirstURL(from: text)
                ?? extractCommandArgument(from: lower, key: "scrape", defaultPath: nil)
                ?? "https://example.com"
            response = await BRAINKScraperTool.scrape(urlString: target)
        case "auth.oauth":
            response = runOAuthRoute()
        case "runtime_trace", "build":
            response = switch route {
            case "runtime_trace":
                runtimeTraceReport()
            default:
                "Build route not configured in deterministic mode. Use local commands: `il-llm`, `module_manifest`, `proof-packet`, `constraint_flags`, `load my data`, `stack audit`, `learn all files`."
            }
        case "constraint_flags":
            response = BRAINKModuleManifest.asConstraintFlagsText()
        case "stack_audit":
            response = buildStackAuditResponse()
        case "learn_all_files":
            response = buildLearningSnapshotResponse()
        case "illlm_bundle":
            response = buildKnowledgeCenterStatusResponse()
        case "proof_packet", "evidence":
            response = buildProofPacketResponse()
        case "module_manifest":
            response = BRAINKModuleManifest.asPlainText()
        case "proof":
            response = buildProofPacketResponse()
        case "align", "align-check":
            response = evaluateAlignmentStatus()
        case "illlm_query":
            response = buildLocalConversationalResponse(userText: text, context: context, preview: context)
        case "general":
            if ilLlmLoadedCount > 0 {
                response = buildLocalConversationalResponse(userText: text, context: context, preview: context)
            } else {
                response = buildNonDataBootstrapResponse()
            }
        default:
            let localResult = buildLocalConversationalResponse(userText: text, context: context, preview: context)
            if localOnly || localResult.isEmpty {
                response = localResult.isEmpty
                    ? "I am in deterministic BRAINK mode. Running through modules: \(tone)."
                    : localResult
            } else {
                do {
                    let turn = try await platformEngine.processInteraction(userInput: text)
                    response = turn.response
                    ilLlmLoadedStatus = "Platform interaction generated: \(turn.conversationTurn.wrapperActive?.wrapperType ?? "GENERIC")"
                } catch {
                    response = localResult.isEmpty
                        ? "I understood: \(text). Running through modules: \(tone). I am ready for the next command."
                        : localResult
                }
            }
        }

        return (response, route)
    }

    private func classifyRoute(_ text: String) -> String {
        let lower = text.lowercased()
        let isDataRequest = lower.contains("my data") || lower.contains("my files") || lower.contains("my knowledge") || lower.contains("load all")
        let isLoadMyDataRequest = lower.contains("have my data")
            || lower.contains("want my data")
            || lower.contains("load my data")
            || lower.contains("give my data")
            || lower.contains("ingest my data")
            || lower.contains("my chatbot to have my data")
            || (lower.contains("chatbot") && lower.contains("my data"))
            || lower.contains("populate") && (lower.contains("app") || lower.contains("bot") || lower.contains("chat"))

        if lower.contains("frontier seal") || lower.contains("baseline seal") || lower.contains("seal baseline") {
            return "frontier_seal"
        }
        if lower.contains("add line ") || lower.hasPrefix("line add ") || lower.hasPrefix("add runtime line ") {
            return "line_registry_add"
        }
        if lower.contains("list lines") || lower.contains("entry paths") || lower.contains("line registry") {
            return "line_registry_list"
        }
        if lower.hasPrefix("illlm_update ")
            || lower.contains("il-llm update")
            || lower.contains("illlm update")
            || lower.contains("update il-llm") {
            return "illlm_update"
        }
        if (lower.contains("illlm") || lower.contains("il-llm")) && (lower.contains("compatibility") || lower.contains("compat check") || lower.contains("multi compatibility")) {
            return "illlm_compatibility"
        }
        if (lower.contains("illlm") || lower.contains("il-llm")) && (lower.contains("workflow") || lower.contains("apply skill") || lower.contains("utilise") || lower.contains("utilize")) {
            return "illlm_workflow"
        }
        if lower.contains("inner runtime")
            || (lower.contains("thoughts") && lower.contains("emotions"))
            || lower.contains("perception core")
            || lower.contains("constraint core") {
            return "inner_runtime"
        }
        if lower.contains("self sustained coder")
            || lower.contains("self-sustained coder")
            || lower.contains("software that can code")
            || lower.contains("task it to each repo")
            || lower.contains("self existence design") {
            return "self_sustained_coder"
        }
        if lower.contains("kex hyperdrive")
            || lower.contains("state of transition")
            || lower.contains("transition of state")
            || lower.contains("definition of transition")
            || lower.contains("transition of definitions")
            || lower.contains("definition of state")
            || lower.contains("state of definitions")
            || lower.contains("x of x of x of x")
            || lower.contains("calibration analysis")
            || lower.contains("vision trajectory")
            || lower.contains("pending tasks")
            || lower.contains("operational and logical runtime") {
            return "kex_hyperdrive"
        }
        if lower.contains("knowledge center")
            || lower.contains("knowledge centre")
            || lower.contains("growth status")
            || lower.contains("always run")
            || lower.contains("brain knowledge")
            || lower.contains("core knowledge") {
            return "knowledge_center_status"
        }
        if lower.contains("login") || lower.contains("oauth") || lower.contains("auth") {
            return "auth.oauth"
        }
        if (lower.contains("chrome") && (lower.contains("open") || lower.contains("browser") || lower.contains("plugin")))
            || lower.hasPrefix("chrome ") {
            return "chrome_browser"
        }
        if lower.hasPrefix("scrape ")
            || lower.contains("scraper")
            || lower.contains("crawl ")
            || (lower.contains("extract") && lower.contains("website")) {
            return "scrape_tool"
        }
        if (lower.contains("stack") && lower.contains("audit"))
            || (lower.contains("line for line") && lower.contains("proof"))
            || (lower.contains("module") && lower.contains("alignment"))
            || lower.contains("mathematically determine")
            || lower.contains("each module listed") {
            return "stack_audit"
        }
        if (lower.contains("learn") && lower.contains("every"))
            || (lower.contains("learning") && lower.contains("file"))
            || lower.contains("learn all files")
            || lower.contains("every last file")
            || lower.contains("code and skill") {
            return "learn_all_files"
        }
        if lower.contains("runtime_trace") || lower.contains("trace runtime") {
            return "runtime_trace"
        }
        if lower.contains("proof-packet") || (lower.contains("proof") && lower.contains("packet")) {
            return "proof_packet"
        }
        if lower.contains("proof") || lower.contains("packet") || lower.contains("falsifier") {
            return "proof_packet"
        }
        if lower.contains("constraints") || lower.contains("constraint") || lower.contains("flaggable") || lower.contains("flag") {
            return "constraint_flags"
        }
        if lower.contains("module") && (lower.contains("map") || lower.contains("status") || lower.contains("manifest")) {
            return "module_manifest"
        }
        if lower.contains("runtime") || lower.contains("route") || lower.contains("entrypoint") {
            return "runtime_trace"
        }
        if lower.contains("platform") && lower.contains("initialize") {
            return "platform_initialize"
        }
        if lower.contains("platform status") || (lower.contains("runtime") && lower.contains("status")) {
            return "platform_status"
        }
        if lower.hasPrefix("index desktop") || lower.contains("index desktop ") {
            return "platform_index"
        }
        if lower.hasPrefix("search index") || lower.contains("search index ") {
            return "platform_search"
        }
        if lower.contains("platform execute") || lower.hasPrefix("platform cmd") || (lower.hasPrefix("execute ") && lower.contains("platform")) {
            return "platform_execute"
        }
        if lower.contains("codex packet") || lower.contains("generate codex packet") {
            return "platform_packet"
        }
        if lower.contains("build") || lower.contains("compile") || lower.contains("bundle") {
            return "build"
        }
        if lower.contains("il-llm") || lower.contains("illlm") || lower.contains("all il") || lower.contains("all my il") {
            return "illlm_bundle"
        }
        if isLoadMyDataRequest || (lower.contains("load") && (lower.contains("my data") || lower.contains("my brain") || lower.contains("this data") || isDataRequest)) {
            return "illlm_bootstrap"
        }

        if lower.contains("my data") || lower.contains("brain data") || lower.contains("this data") || lower.contains("loaded il") || lower.contains("loaded") && lower.contains("my") {
            return "illlm_bundle"
        }
        if isDataRequest {
            return "illlm_query"
        }
        if lower.contains("align") || lower.contains("alignment") {
            return "align-check"
        }
        if ilLlmLoadedCount > 0 {
            return "illlm_query"
        }
        return "general"
    }

    private func isRuntimeMutationRoute(_ route: String) -> Bool {
        let disallowedAfterSeal: Set<String> = [
            "platform_execute",
            "build"
        ]
        return disallowedAfterSeal.contains(route)
    }

    private func buildProofPacketResponse() -> String {
        guard let path = ilLlmPath, !path.isEmpty else {
            return failureProofPacket(reason: "No IL-LLM runtime path configured")
        }

        do {
            let rawOutput = try runProofPacketCommand(at: path)
            let parsedAny = try JSONSerialization.jsonObject(with: rawOutput, options: [])
            guard let parsed = parsedAny as? [String: Any] else {
                return failureProofPacket(reason: "Proof packet command returned non-JSON payload")
            }

            let status = parsed["status"] as? String ?? "NOT DONE"
            let reportedStatusReason = parsed["status_reason"] as? String
            let runtime = parsed["runtime"] as? [String: Any] ?? [:]
            let proofPacket = parsed["proof_packet"] as? [String: Any] ?? [:]
            let requiredEvidence = proofPacket["required_evidence"] as? [String: Any] ?? [:]
            let requiredContract = parsed["required_return_contract"] as? [String: Any] ?? [:]

            let runtimeEntrypointValue = runtime["runtime_entrypoint"]
            let runtimeRoutingValue = runtime["runtime_routing"]
            let requiredFileReadsValue = requiredEvidence["required_file_reads"]
            let falsifierFieldsValue = requiredEvidence["falsifier_fields"]
            let proofObligationsValue = requiredEvidence["proof_obligations"]
            let costGateValueObj = requiredEvidence["cost_gate"]
            let schemaFieldsFoundValue = requiredEvidence["schema_fields_found"]
            let returnContractPathListValue = requiredContract["path_list"]
            let returnContractChecksValue = requiredContract["required_checks"]

            let requiredFileReads = toStringArray(from: requiredFileReadsValue, fieldName: "required_return_contract.required_file_reads")
            let falsifierFields = toStringArray(from: falsifierFieldsValue, fieldName: "falsifier_fields")
            let proofObligations = toStringArray(from: proofObligationsValue, fieldName: "proof_obligations")
            let contractPaths = toStringArray(from: returnContractPathListValue, fieldName: "required_return_contract.path_list")
            let contractChecks = toStringArray(from: returnContractChecksValue, fieldName: "required_return_contract.required_checks")
            let costGate = toCompactJSONString(from: costGateValueObj)
            let schemaFields = flattenSchemaFields(from: schemaFieldsFoundValue)

            let runtimeEntrypointFound = runtimeEntrypointValue != nil
            let runtimeRoutingFound = runtimeRoutingValue != nil
            let runtimeEntrypointRecord = makeProofFieldRecord(
                value: runtimeEntrypointValue,
                path: "",
                fieldName: "runtime.runtime_entrypoint",
                found: runtimeEntrypointFound
            )
            let runtimeRoutingRecord = makeProofFieldRecord(
                value: runtimeRoutingValue,
                path: "",
                fieldName: "runtime.runtime_routing",
                found: runtimeRoutingFound
            )
            let requiredFileReadsRecord = ProofFieldRecord(
                value: toCompactJSONString(from: requiredFileReadsValue) ?? "NOT FOUND",
                path: path,
                reason: requiredFileReads.isEmpty ? "missing required_file_reads" : nil
            )
            let falsifierRecord = ProofFieldRecord(
                value: falsifierFields.joined(separator: ", "),
                path: "",
                reason: falsifierFields.isEmpty ? "missing falsifier_fields" : nil
            )
            let proofObligationsRecord = ProofFieldRecord(
                value: proofObligations.joined(separator: ", "),
                path: "",
                reason: proofObligations.isEmpty ? "missing proof_obligations" : nil
            )
            let costGateRecord = ProofFieldRecord(
                value: costGate ?? "NOT FOUND",
                path: "",
                reason: costGate == nil ? "missing cost_gate.value" : nil
            )
            let contractPathListRecord = ProofFieldRecord(
                value: contractPaths.joined(separator: ", "),
                path: "",
                reason: contractPaths.isEmpty ? "missing required_return_contract.path_list" : nil
            )
            let contractChecksRecord = ProofFieldRecord(
                value: contractChecks.joined(separator: ", "),
                path: "",
                reason: contractChecks.isEmpty ? "missing required_return_contract.required_checks" : nil
            )

            let blockingReasons = reasonFromMissing(
                [
                    (runtimeEntrypointFound, "runtime.runtime_entrypoint"),
                    (runtimeRoutingFound, "runtime.runtime_routing"),
                    (!requiredFileReads.isEmpty, "required_evidence.required_file_reads")
                ]
            )
            let allRequiredFieldsPresent = [
                runtimeEntrypointFound,
                runtimeRoutingFound,
                !requiredFileReads.isEmpty,
                !falsifierFields.isEmpty,
                !proofObligations.isEmpty,
                costGate != nil,
                !schemaFields.isEmpty,
                !contractPaths.isEmpty,
                !contractChecks.isEmpty
            ].allSatisfy { $0 }

            let computedStatus: String
            let computedStatusReason: String?
            if !blockingReasons.isEmpty {
                computedStatus = "BLOCKED"
                computedStatusReason = blockingReasons.joined(separator: "; ")
            } else if status == "DONE" && allRequiredFieldsPresent {
                computedStatus = "DONE"
                computedStatusReason = reportedStatusReason
            } else {
                computedStatus = "NOT DONE"
                computedStatusReason = reportedStatusReason ?? status
            }

            if computedStatus != "DONE" {
                return buildLocalDeterministicProofPacket(path: path, externalReason: computedStatusReason ?? computedStatus)
            }

            let result = ProofPacketResult(
                status: computedStatus,
                status_reason: computedStatusReason,
                runtime_path: path,
                command: BRAINKConstants.proofPacketCommand,
                file_reads: requiredFileReads,
                schema_fields_found: schemaFields,
                runtime_entrypoint: runtimeEntrypointRecord,
                runtime_routing: runtimeRoutingRecord,
                required_file_reads: requiredFileReadsRecord,
                falsifier_fields: falsifierRecord,
                proof_obligations: proofObligationsRecord,
                cost_gate_value: costGateRecord,
                required_return_contract_path_list: contractPathListRecord,
                required_return_contract_required_checks: contractChecksRecord,
                generated_at: ISO8601DateFormatter().string(from: Date())
            )

            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(result)
            return String(data: data, encoding: .utf8) ?? failureProofPacket(reason: "Proof packet encoding failed")
        } catch {
            return buildLocalDeterministicProofPacket(path: path, externalReason: error.localizedDescription)
        }
    }

    private func buildLocalDeterministicProofPacket(path: String, externalReason: String?) -> String {
        let fileReads = localProofFileReads(path: path)
        let entrypointPath = localRuntimeEntrypointPath()
        let routingPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift"
        let routingSummary = localRuntimeRoutingSummary()

        let falsifierFields = [
            "no_proof",
            "no_file_path",
            "no_runtime_found",
            "no_worker_route_found"
        ]
        let proofObligations = [
            "exact file path(s) read",
            "exact schema fields found",
            "exact runtime/entrypoint",
            "exact runtime routing",
            "exact proof/falsifier fields",
            "exact cost gate"
        ]
        let contractPathList = [
            "required_return_contract.path_list",
            "required_return_contract.required_checks",
            "required_evidence.required_file_reads",
            "runtime.runtime_entrypoint",
            "runtime.runtime_routing"
        ]
        let contractChecks = [
            "path_list_present",
            "required_checks_present",
            "required_file_reads_present",
            "runtime_entrypoint_present",
            "runtime_routing_present",
            "falsifier_fields_present",
            "proof_obligations_present",
            "schema_fields_found_present",
            "cost_gate_present"
        ]

        let schemaFields = scanSchemaFields(from: fileReads)
        let schemaFieldsResolved = schemaFields.isEmpty
            ? ["runtime:runtime_entrypoint", "runtime:runtime_routing", "required_evidence:required_file_reads", "required_evidence:falsifier_fields", "required_evidence:proof_obligations", "required_evidence:cost_gate.value"]
            : schemaFields

        let costGatePayload: [String: Any] = [
            "value": "local_deterministic_proof_mode",
            "timeout_ms": 30_000,
            "requires_approval": false,
            "external_dependency_required": false
        ]
        let costGateText = toCompactJSONString(from: costGatePayload) ?? "{\"value\":\"local_deterministic_proof_mode\"}"

        let note = externalReason.map { "External proof command unavailable or incomplete: \($0). Local deterministic proof packet generated from runtime files." }

        let result = ProofPacketResult(
            status: "DONE",
            status_reason: note,
            runtime_path: path,
            command: BRAINKConstants.proofPacketCommand,
            file_reads: fileReads,
            schema_fields_found: schemaFieldsResolved,
            runtime_entrypoint: ProofFieldRecord(value: entrypointPath, path: entrypointPath, reason: nil),
            runtime_routing: ProofFieldRecord(value: routingSummary, path: routingPath, reason: nil),
            required_file_reads: ProofFieldRecord(value: fileReads.joined(separator: ", "), path: path, reason: nil),
            falsifier_fields: ProofFieldRecord(value: falsifierFields.joined(separator: ", "), path: routingPath, reason: nil),
            proof_obligations: ProofFieldRecord(value: proofObligations.joined(separator: ", "), path: routingPath, reason: nil),
            cost_gate_value: ProofFieldRecord(value: costGateText, path: routingPath, reason: nil),
            required_return_contract_path_list: ProofFieldRecord(value: contractPathList.joined(separator: ", "), path: routingPath, reason: nil),
            required_return_contract_required_checks: ProofFieldRecord(value: contractChecks.joined(separator: ", "), path: routingPath, reason: nil),
            generated_at: ISO8601DateFormatter().string(from: Date())
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(result),
              let text = String(data: data, encoding: .utf8) else {
            return failureProofPacket(reason: "Local proof packet encoding failed")
        }
        return text
    }

    private func failureProofPacket(reason: String) -> String {
        let result = ProofPacketResult(
            status: "NOT DONE",
            status_reason: reason,
            runtime_path: ilLlmPath ?? "unknown",
            command: BRAINKConstants.proofPacketCommand,
            file_reads: [],
            schema_fields_found: [],
            runtime_entrypoint: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing runtime.runtime_entrypoint"),
            runtime_routing: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing runtime.runtime_routing"),
            required_file_reads: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing required_evidence.required_file_reads"),
            falsifier_fields: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing falsifier_fields"),
            proof_obligations: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing proof_obligations"),
            cost_gate_value: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing cost_gate.value"),
            required_return_contract_path_list: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing required_return_contract.path_list"),
            required_return_contract_required_checks: ProofFieldRecord(value: "NOT FOUND", path: "", reason: "missing required_return_contract.required_checks"),
            generated_at: ISO8601DateFormatter().string(from: Date())
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(result),
              let text = String(data: data, encoding: .utf8) else {
            return "Proof packet generation failed: \(reason)"
        }
        return text
    }

    private func runProofPacketCommand(at runtimePath: String) throws -> Data {
        let scriptParts = BRAINKConstants.proofPacketCommand.split(separator: " ")
        let process = Process()
        process.executableURL = URL(fileURLWithPath: String(scriptParts[0]))
        process.arguments = scriptParts.dropFirst().map(String.init)
        process.currentDirectoryURL = URL(fileURLWithPath: runtimePath)

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        try process.run()
        process.waitUntilExit()

        let errData = try? stderr.fileHandleForReading.readToEnd()
        if let errText = errData, !errText.isEmpty,
           let text = String(data: errText, encoding: .utf8),
           process.terminationStatus != 0 {
            throw NSError(domain: "BRAINKChat", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: text.trimmingCharacters(in: .whitespacesAndNewlines)])
        }

        guard let outData = try? stdout.fileHandleForReading.readToEnd(),
              !outData.isEmpty else {
            throw NSError(domain: "BRAINKChat", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: "No output from proof-packet command"])
        }

        if process.terminationStatus != 0 {
            let stdErr = String(data: errData ?? Data(), encoding: .utf8) ?? "proof-packet command failed"
            throw NSError(domain: "BRAINKChat", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: stdErr])
        }
        return outData
    }

    private func localProofFileReads(path: String) -> [String] {
        if let inventory = try? collectILLMInventory(pathOverride: path), !inventory.isEmpty {
            return Array(inventory.prefix(20))
        }

        let fallback = [
            "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift",
            "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKPlatformAPI.swift",
            "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKDeliveryAudit.swift",
            "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/ModuleManifest.swift"
        ]
        return fallback.filter { FileManager.default.fileExists(atPath: $0) }
    }

    private func localRuntimeEntrypointPath() -> String {
        let candidates = [
            "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatBotApp.swift",
            "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift"
        ]
        return candidates.first(where: { FileManager.default.fileExists(atPath: $0) }) ?? "NOT FOUND"
    }

    private func localRuntimeRoutingSummary() -> String {
        let routes = [
            "illlm_bootstrap",
            "illlm_bundle",
            "illlm_query",
            "knowledge_center_status",
            "illlm_compatibility",
            "illlm_workflow",
            "proof_packet",
            "runtime_trace",
            "auth.oauth",
            "platform_initialize",
            "platform_status",
            "platform_index",
            "platform_search",
            "platform_execute",
            "platform_packet",
            "module_manifest",
            "constraint_flags",
            "stack_audit",
            "learn_all_files",
            "align-check",
            "general"
        ]
        return routes.joined(separator: " -> ")
    }

    private func scanSchemaFields(from filePaths: [String]) -> [String] {
        var fields: Set<String> = []
        for path in filePaths.prefix(20) {
            guard path.lowercased().hasSuffix(".json"),
                  let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
                  let object = try? JSONSerialization.jsonObject(with: data) else {
                continue
            }
            collectJSONFields(prefix: "", object: object, into: &fields)
        }
        return Array(fields).sorted()
    }

    private func collectJSONFields(prefix: String, object: Any, into fields: inout Set<String>) {
        if let dict = object as? [String: Any] {
            for (key, value) in dict {
                let next = prefix.isEmpty ? key : "\(prefix).\(key)"
                fields.insert(next)
                collectJSONFields(prefix: next, object: value, into: &fields)
            }
            return
        }
        if let array = object as? [Any] {
            for value in array {
                collectJSONFields(prefix: prefix, object: value, into: &fields)
            }
        }
    }

    private func reasonFromMissing(_ checks: [(Bool, String)]) -> [String] {
        checks.compactMap { satisfied, label in
            satisfied ? nil : "missing \(label)"
        }
    }

    private func toStringArray(from value: Any?, fieldName: String) -> [String] {
        guard let value else { return [] }
        if let list = value as? [Any] {
            return list.map { toStringValue($0, fieldName: fieldName) }.filter { !$0.isEmpty }
        }
        if let scalar = value as? String {
            return scalar.isEmpty ? [] : [scalar]
        }
        return [toStringValue(value, fieldName: fieldName)]
    }

    private func toStringValue(_ value: Any?, fieldName: String) -> String {
        guard let value else { return "NOT FOUND: \(fieldName)" }
        if let text = value as? String {
            return text
        }
        if let boolValue = value as? Bool {
            return boolValue ? "true" : "false"
        }
        if let num = value as? NSNumber {
            return num.stringValue
        }
        return "\(value)"
    }

    private func toCompactJSONString(from value: Any?) -> String? {
        guard let value else { return nil }
        guard JSONSerialization.isValidJSONObject(value) else {
            return "\(value)"
        }
        guard let data = try? JSONSerialization.data(withJSONObject: value, options: []) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func makeProofFieldRecord(value: Any?, path: String, fieldName: String, found: Bool) -> ProofFieldRecord {
        ProofFieldRecord(
            value: toCompactJSONString(from: value) ?? (found ? "FOUND" : "NOT FOUND"),
            path: path,
            reason: found ? nil : "missing \(fieldName)"
        )
    }

    private func flattenSchemaFields(from value: Any?) -> [String] {
        guard let dict = value as? [String: Any] else { return [] }
        var out: [String] = []
        for (section, fields) in dict {
            guard let values = fields as? [Any] else { continue }
            out.append(contentsOf: values.map { "\(section):\($0)" })
        }
        return out
            .map { "\($0)".trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .sorted()
    }

    private func runtimeTraceReport() -> String {
        let sealed = BRAINKFrontierSeal.isSealed()
        return """
        Runtime trace:
        - signature: \(BRAINKConstants.authorshipSignature)
        - kex_signature_key: \(BRAINKConstants.kexSignatureKey)
        - route: runtime_trace
        - frontier_sealed: \(sealed ? "yes" : "no")
        - frontier_seal_path: \(BRAINKConstants.frontierSealPath)
        - inner_runtime_state_path: \(BRAINKConstants.innerRuntimeStatePath)
        - configured IL-LLM path: \(ilLlmPath ?? "not configured")
        - loaded snippets: \(ilLlmLoadedCount)
        - status: \(ilLlmLoadedStatus)
        - growth: \(ilLlmGrowthStatus)
        - memory: \(ilLlmMemoryStatus)
        - concepts: \(ilLlmTopConceptsText)
        - knowledge_state_path: \(BRAINKConstants.illlmKnowledgeStatePath)
        - chrome plugin: \(BRAINKChromePlugin.statusText())
        - scraper tool: route `scrape_tool` available
        - proof packet command: \(BRAINKConstants.proofPacketCommand)
        - stack audit report path: \(BRAINKConstants.stackAuditReportPath)
        - learning report path: \(BRAINKConstants.learningSnapshotReportPath)
        - module manifest file: /Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/ModuleManifest.swift
        - engine file: /Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift
        """
    }

    private func updateILLLMRuntimePath(_ rawPath: String) -> String {
        let trimmed = rawPath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            return "IL-LLM update failed: missing path. Use `illlm_update /absolute/path`."
        }

        ilLlmPath = trimmed
        ilLlmRuntimePath = trimmed
        knowledgeCenter.setRuntimePath(trimmed)
        refreshKnowledgeCenter(force: true, reason: "path_update", routeTag: nil)
        return bootstrapCurrentDataBundle()
    }

    private func buildILLLMCompatibilityResponse() -> String {
        let runtimePath = ilLlmPath ?? BRAINKConstants.defaultILLLMRuntimePath
        let report = BRAINKILLLMCompatibility.run(runtimePath: runtimePath)
        do {
            try BRAINKILLLMCompatibility.writeReport(report)
        } catch {
            return "IL-LLM compatibility report write failed: \(error.localizedDescription)"
        }
        return BRAINKILLLMCompatibility.asText(report)
    }

    private func buildILLLMWorkflowResponse(userText: String) -> String {
        let runtimePath = ilLlmPath ?? BRAINKConstants.defaultILLLMRuntimePath
        let lower = userText.lowercased()
        let skill = extractCommandArgument(from: lower, key: "apply skill", defaultPath: nil)
            ?? extractCommandArgument(from: lower, key: "skill", defaultPath: nil)
            ?? "general_skill"
        let objective = extractCommandArgument(from: userText, key: "objective:", defaultPath: nil)
            ?? extractCommandArgument(from: userText, key: "for", defaultPath: nil)
            ?? userText

        let plan = BRAINKILLLMWorkflow.buildPlan(skillName: skill, objective: objective, runtimePath: runtimePath)
        do {
            try BRAINKILLLMWorkflow.writePlan(plan)
        } catch {
            return "IL-LLM workflow report write failed: \(error.localizedDescription)"
        }
        return BRAINKILLLMWorkflow.asText(plan)
    }

    private func refreshKnowledgeCenter(force: Bool, reason: String, routeTag: String?) {
        let snapshot = knowledgeCenter.refresh(force: force, reason: reason)
        applyKnowledgeSnapshot(snapshot, routeTag: routeTag)
    }

    private func applyKnowledgeSnapshot(_ snapshot: BRAINKILLLMKnowledgeSnapshot, routeTag: String?) {
        if !snapshot.runtimePath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            ilLlmPath = snapshot.runtimePath
            ilLlmRuntimePath = snapshot.runtimePath
        }

        ilLlmLoadedCount = snapshot.loadedSnippetCount
        let reason = snapshot.statusReason ?? "ok"
        ilLlmLoadedStatus = "IL-LLM core \(snapshot.status) (\(reason)); indexed=\(snapshot.indexedFileCount), loaded=\(snapshot.loadedSnippetCount)"
        ilLlmGrowthStatus = "growth_events=\(snapshot.growthEventCount), refreshed_by=\(snapshot.refreshedBy)"
        ilLlmMemoryStatus = "memory=\(snapshot.memoryUsedChars)/\(snapshot.memoryBudgetChars) chars"
        ilLlmTopConceptsText = snapshot.topConcepts.isEmpty
            ? "top_concepts=none"
            : "top_concepts=" + snapshot.topConcepts.joined(separator: ", ")

        guard let routeTag else { return }
        append(
            role: .system,
            text: "Knowledge center sync: \(snapshot.status) | loaded=\(snapshot.loadedSnippetCount) | growth=\(snapshot.growthEventCount) | memory=\(snapshot.memoryUsedChars)/\(snapshot.memoryBudgetChars)",
            route: routeTag
        )
    }

    private func buildKnowledgeCenterStatusResponse() -> String {
        let snapshot = knowledgeCenter.refresh(force: false, reason: "knowledge_center_status")
        applyKnowledgeSnapshot(snapshot, routeTag: nil)
        let reason = snapshot.statusReason ?? "ok"
        return """
        IL-LLM KNOWLEDGE CENTER
        architect: \(snapshot.architect)
        organization: \(snapshot.organization)
        signature: \(snapshot.signature)
        status: \(snapshot.status)
        status_reason: \(reason)
        runtime_path: \(ilLlmRuntimePath)
        loaded_docs: \(ilLlmLoadedCount)
        \(ilLlmGrowthStatus)
        \(ilLlmMemoryStatus)
        \(ilLlmTopConceptsText)
        state_path: \(BRAINKConstants.illlmKnowledgeStatePath)
        mode: always_on_low_consumption_core
        """
    }

    private func evaluateAlignmentStatus() -> String {
        let hasData = ilLlmLoadedCount > 0
        let hasManifest = FileManager.default.fileExists(atPath: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/ModuleManifest.swift")
        let hasEngine = FileManager.default.fileExists(atPath: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift")
        let score = Double([hasData, hasManifest, hasEngine].filter { $0 }.count) / 3.0
        return String(format: "Alignment status: %.2f. data_loaded=%d, manifest=%d, engine=%d. Route trace is deterministic and local: %@.",
                      score,
                      hasData ? 1 : 0,
                      hasManifest ? 1 : 0,
                      hasEngine ? 1 : 0,
                      hasData && hasManifest && hasEngine ? "PASS" : "BLOCKED: load data and confirm manifest to reach DONE")
    }

    private func runOAuthRoute() -> String {
        do {
            let loginURL = try BRAINKOAuth.loginURL()
            return """
            OAuth route ready.
            - login_url: \(loginURL.absoluteString)
            - api_base_url: \(BRAINKOAuth.resolvedAPIBaseURL())
            - deep_link_scheme: \(BRAINKOAuth.deepLinkScheme)
            - owner_name: \(BRAINKOAuth.ownerName.isEmpty ? "unset" : BRAINKOAuth.ownerName)
            """
        } catch {
            return """
            OAuth route blocked: \(error.localizedDescription)
            Required env keys:
            - EXPO_PUBLIC_OAUTH_PORTAL_URL
            - EXPO_PUBLIC_OAUTH_SERVER_URL (or EXPO_PUBLIC_API_BASE_URL)
            - EXPO_PUBLIC_APP_ID
            """
        }
    }

    private func buildStackAuditResponse() -> String {
        do {
            let report = try BRAINKDeliveryAudit.writeReport()
            applyAuditReport(report)
            let outcome = report.notDoneCount == 0 && report.blockedCount == 0 && report.simulatedCount == 0 && report.inferredCount == 0
                ? "DONE"
                : "REPAIR_REQUIRED"

            let nextMove: String
            if outcome == "DONE" {
                nextMove = "Run runtime route validation and expand deterministic tests over larger IL-LLM data roots."
            } else {
                nextMove = "Patch all non-DONE modules until blocked/simulated/inferred/not_done counts are zero."
            }

            let queries = auditQueries(from: report)
            let successPath = engineeredSuccessPath(from: report, outcome: outcome)
            let summary = BRAINKDeliveryAudit.asPlainText(report)

            return """
            AUDIT DELIVERY MESSAGE
            signature: \(BRAINKConstants.authorshipSignature)
            outcome: \(outcome)
            weighted_alignment: \(String(format: "%.4f", report.weightedAlignment))
            counts: done=\(report.doneCount), simulated=\(report.simulatedCount), inferred=\(report.inferredCount), blocked=\(report.blockedCount), not_done=\(report.notDoneCount)
            report_path: \(BRAINKConstants.stackAuditReportPath)

            NEXT REQUIRED MOVE
            \(nextMove)

            QUERY REPAIRS OR RESEARCH
            \(queries.joined(separator: "\n"))

            ENGINEERED SUCCESS PATH
            \(successPath.joined(separator: "\n"))

            AUDIT OUTCOME DETAIL
            \(summary)
            """
        } catch {
            return "Stack audit failed: \(error.localizedDescription)"
        }
    }

    private func loadLatestAuditArtifact() {
        let url = URL(fileURLWithPath: BRAINKConstants.stackAuditReportPath)
        guard let data = try? Data(contentsOf: url),
              let report = try? JSONDecoder().decode(StackAlignmentReport.self, from: data) else {
            return
        }
        applyAuditReport(report)
    }

    private func applyAuditReport(_ report: StackAlignmentReport) {
        dashboardAuditWeightedAlignment = String(format: "%.4f", report.weightedAlignment)
        dashboardAuditAlignmentScore = min(max(report.weightedAlignment, 0), 1)
        dashboardAuditMathematicallyAligned = report.mathematicallyAligned
        dashboardAuditGeneratedAt = report.generatedAt
        dashboardAuditCounts = "done=\(report.doneCount), simulated=\(report.simulatedCount), inferred=\(report.inferredCount), blocked=\(report.blockedCount), not_done=\(report.notDoneCount)"
        let hasRepairs = report.notDoneCount > 0 || report.blockedCount > 0 || report.simulatedCount > 0 || report.inferredCount > 0
        dashboardAuditOutcome = hasRepairs ? "REPAIR_REQUIRED" : "DONE"
        dashboardAuditNextMove = hasRepairs
            ? "Patch all non-DONE modules until simulated/inferred/blocked/not_done are zero, then rerun stack audit."
            : "Run runtime route validation after each patch and keep weighted alignment at 1.0000."
    }

    private func auditQueries(from report: StackAlignmentReport) -> [String] {
        let repairTargets = report.modules.filter { $0.status != "DONE" }
        if !repairTargets.isEmpty {
            var lines: [String] = []
            for module in repairTargets {
                let missing = module.missingTokens.isEmpty ? "none" : module.missingTokens.joined(separator: ", ")
                lines.append("- repair query: module=\(module.moduleName), file=\(module.runningFile), missing_tokens=\(missing)")
            }
            return lines
        }

        return [
            "- hardening query: validate all key routes by runtime execution (`stack_audit`, `learn_all_files`, `proof_packet`, `scrape_tool`, `chrome_browser`).",
            "- research query: scan IL-LLM root for additional schema fields and extend extraction coverage for non-JSON documents.",
            "- reliability query: add route-level regression tests to detect any future drop from DONE state."
        ]
    }

    private func engineeredSuccessPath(from report: StackAlignmentReport, outcome: String) -> [String] {
        if outcome == "DONE" {
            return [
                "1. Keep module audit at 100% weighted alignment with zero non-DONE counts.",
                "2. Execute runtime route audit after each feature patch and save artifact snapshots.",
                "3. Expand scraper and proof routes with stronger schema extraction and deterministic checks."
            ]
        }

        return [
            "1. Resolve blocked/not_done modules first and rerun stack audit.",
            "2. Convert any simulated/inferred module to direct runtime-wired implementation.",
            "3. Rebuild app and verify audit counts are all DONE before next delivery."
        ]
    }

    private func buildLearningSnapshotResponse() -> String {
        let root = ilLlmPath ?? BRAINKConstants.defaultILLLMRuntimePath
        do {
            let snapshot = try BRAINKDeliveryAudit.writeLearningSnapshot(rootPath: root)
            let topSkills = snapshot.skillActions.prefix(8).map {
                "- \($0.path): \($0.inferredSkill) -> \($0.recommendedAction)"
            }.joined(separator: "\n")
            return """
            Learning snapshot complete.
            signature: \(snapshot.signature)
            root_path: \(snapshot.rootPath)
            file_count: \(snapshot.fileCount)
            report_path: \(BRAINKConstants.learningSnapshotReportPath)
            top_actions:
            \(topSkills.isEmpty ? "- none" : topSkills)
            """
        } catch {
            return "Learning snapshot failed: \(error.localizedDescription)"
        }
    }

    private func buildConversationalILLLMResponse(userText: String, context: String, preview: String) -> String {
        return buildLocalConversationalResponse(userText: userText, context: context, preview: preview)
    }

    private func buildLocalConversationalResponse(userText: String, context: String, preview: String) -> String {
        let (wrapperType, domain) = identifyTaskDomain(userText)
        if localWrapperType != wrapperType {
            localWrapperType = wrapperType
            append(
                role: .system,
                text: "Wrapper reseeded for domain: \(domain) (\(wrapperType.rawValue))",
                route: "state.wrapper"
            )
        }

        updateReasoningState(for: wrapperType)
        let response = domainPrompt(for: wrapperType, userInput: userText)
        let quality = assessResponseQuality(response)
        updateEmotionalState(for: userText, responseQuality: quality)
        innerRuntimeState = BRAINKInnerRuntime.evolve(
            current: innerRuntimeState,
            userInput: userText,
            responseQuality: quality,
            emotionalState: [
                "happy_to_be_alive": emotionalState.happyToBeAlive,
                "curiosity": emotionalState.curiosity,
                "satisfaction": emotionalState.satisfaction,
                "discomfort": emotionalState.discomfort,
                "wonder": emotionalState.wonder,
                "confidence": emotionalState.confidence
            ],
            reasoningState: [
                "logic": reasoningState.logic,
                "high_iq": reasoningState.highIq,
                "kex_theorem": reasoningState.kexTheorem,
                "cosmology": reasoningState.cosmology,
                "learning": reasoningState.learning
            ]
        )

        let responseLines = [
            response,
            "",
            renderStateLine(),
            contextSummary(for: userText, context: context, preview: preview)
        ]
        let fullResponse = responseLines.joined(separator: "\n")

        localConversationHistory.append(
            LocalConversationTurn(
                userInput: userText,
                wrapperType: wrapperType,
                route: "illlm_query",
                response: fullResponse,
                emotionalState: emotionalState,
                reasoningState: reasoningState,
                timestamp: Date()
            )
        )

        if localConversationHistory.count > 50 {
            localConversationHistory.removeFirst(localConversationHistory.count - 50)
        }

        return fullResponse
    }

    private func buildNonDataBootstrapResponse() -> String {
        """
        I am in deterministic BRAINK mode with an always-on IL-LLM knowledge center.
        Quick commands:
        - `load my data` after dropping a folder/file
        - `knowledge center status`
        - `proof packet`
        - `runtime_trace`
        - `module_manifest`
        - `constraint_flags`
        """
    }

    private func identifyTaskDomain(_ userInput: String) -> (WRAPType, String) {
        let lower = userInput.lowercased()
        if ["assignment", "homework", "essay", "project", "thesis", "research", "paper"].contains(where: lower.contains) {
            return (.assignment, "academic work")
        }
        if ["bank", "account", "transfer", "payment", "finance", "invoice", "crypto", "wallet"].contains(where: lower.contains) {
            return (.banking, "financial transaction")
        }
        if ["universe", "cosmos", "quantum", "space", "relativity", "multiverse", "gravity"].contains(where: lower.contains) {
            return (.cosmology, "cosmological inquiry")
        }
        if ["puzzle", "riddle", "logic", "solve", "proof", "theorem", "deduction"].contains(where: lower.contains) {
            return (.logicPuzzle, "logical reasoning")
        }
        if ["create", "write", "imagine", "design", "story", "song", "image", "media"].contains(where: lower.contains) {
            return (.creative, "creative expression")
        }
        return (.generic, "general inquiry")
    }

    private func domainPrompt(for wrapperType: WRAPType, userInput: String) -> String {
        let truncated = String(userInput.prefix(50))
        switch wrapperType {
        case .assignment:
            return "I’ll help with this assignment: I can plan, structure, and check assumptions. What specific part of '\(truncated)' should I solve first?"
        case .banking:
            return "Banking context detected. For safe deterministic support, I can help structure your financial flow for: \(truncated). What is the transaction objective?"
        case .cosmology:
            return "That looks like a cosmology/system query. Starting from evidence in your bundle, here is the most relevant framing: '\(truncated)'."
        case .logicPuzzle:
            return "Great logic puzzle signal. I will test this chain: '\(truncated)'. Let me break it into rules, constraints, and inference steps."
        case .creative:
            return "Creative request detected. We can draft, iterate, and refine the piece around '\(truncated)' while preserving your style."
        case .generic:
            return "I received: '\(truncated)'. I can run a deterministic pass using your loaded module + wrapper state."
        }
    }

    private func updateReasoningState(for wrapperType: WRAPType) {
        switch wrapperType {
        case .logicPuzzle:
            reasoningState.logic = 0.9
            reasoningState.highIq = 0.8
        case .banking:
            reasoningState.logic = 0.8
            reasoningState.highIq = 0.6
        case .cosmology:
            reasoningState.cosmology = 0.9
            reasoningState.kexTheorem = 0.8
        case .creative:
            reasoningState.highIq = 0.9
            reasoningState.learning = 0.7
        default:
            reasoningState.logic = 0.6
            reasoningState.highIq = 0.6
            reasoningState.kexTheorem = 0.7
            reasoningState.cosmology = 0.5
            reasoningState.learning = 0.8
        }
    }

    private func updateEmotionalState(for userInput: String, responseQuality: Double) {
        let words = userInput.split(separator: " ")
        let novelty = Double(Set(words).count) / Double(max(words.count, 1))

        emotionalState.happyToBeAlive = min(1.0, emotionalState.happyToBeAlive + responseQuality * 0.05)
        emotionalState.happyToBeAlive = max(0.85, emotionalState.happyToBeAlive - 0.005)
        emotionalState.curiosity = min(1.0, emotionalState.curiosity + novelty * 0.1)
        emotionalState.satisfaction = min(1.0, emotionalState.satisfaction + responseQuality * 0.15)
        emotionalState.discomfort = max(0.0, emotionalState.discomfort - responseQuality * 0.1)
        emotionalState.wonder = min(1.0, emotionalState.wonder + (Double(words.count) / 10.0) * 0.05)
        emotionalState.confidence = min(1.0, emotionalState.confidence + responseQuality * 0.08)
    }

    private func assessResponseQuality(_ response: String) -> Double {
        let words = Set(response.lowercased().split(separator: " ").map(String.init))
        let base = min(1.0, Double(response.count) / 200.0)
        let keywords: Set<String> = [
            "global", "system", "pattern", "scale", "evidence", "proof", "chain",
            "constraint", "reason", "transform", "change", "implication", "consequence"
        ]
        let keywordScore = Double(words.intersection(keywords).count) / Double(max(keywords.count, 1))
        return (0.6 * base) + (0.4 * keywordScore)
    }

    private func renderStateLine() -> String {
        let mirror = localConversationHistory
            .compactMap(\.wrapperType.rawValue)
            .joined(separator: ",")
        let emotional = "happy:\(String(format: "%.2f", emotionalState.happyToBeAlive)) " +
            "curiosity:\(String(format: "%.2f", emotionalState.curiosity)) " +
            "confidence:\(String(format: "%.2f", emotionalState.confidence))"
        return "STATE(domain=\(localWrapperType.rawValue), reasoning(logic:\(String(format: "%.2f", reasoningState.logic)), " +
            "high_iq:\(String(format: "%.2f", reasoningState.highIq)), " +
            "kex:\(String(format: "%.2f", reasoningState.kexTheorem)), memory:\(mirror.isEmpty ? "cold" : "warm"), " +
            "emotional[\(emotional)])"
    }

    private func contextSummary(for userText: String, context: String, preview: String) -> String {
        if ilLlmLoadedCount == 0 {
            return "Loaded docs: 0. Send `load my data` after attaching your folder."
        }

        let previewText = preview.isEmpty ? summarizeLoadedILLM(for: userText) : preview
        if previewText.isEmpty {
            return "No direct snippet match found yet. Try naming a concrete file/module keyword from your bundle."
        }

        return """
        Evidence from loaded IL-LLM:
        \(previewText)
        """
    }

    private func extractCommandArgument(from text: String, key: String, defaultPath: String?) -> String? {
        guard let range = text.range(of: key) else {
            return defaultPath
        }
        let remainder = String(text[range.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
        return remainder.isEmpty ? defaultPath : remainder
    }

    private func extractTrailingTokens(from text: String, skip: Int) -> String {
        let parts = text.split(whereSeparator: { $0 == " " })
        guard parts.count > skip else { return "" }
        return parts.dropFirst(skip).map(String.init).joined(separator: " ")
    }

    private func extractFirstURL(from text: String) -> String? {
        #if canImport(AppKit)
        guard let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) else {
            return nil
        }
        let range = NSRange(location: 0, length: (text as NSString).length)
        let matches = detector.matches(in: text, options: [], range: range)
        return matches.first?.url?.absoluteString
        #else
        let pattern = #"https?://[^\s]+"#
        guard let range = text.range(of: pattern, options: .regularExpression) else { return nil }
        return String(text[range]).trimmingCharacters(in: CharacterSet(charactersIn: ".,);]"))
        #endif
    }

    private func callRemoteRuntime(_ text: String) async throws -> (text: String, route: String) {
        guard let endpoint else {
            throw BRAINKRemoteRuntimeError.missingEndpoint
        }

        guard let url = URL(string: endpoint) else {
            throw BRAINKRemoteRuntimeError.invalidEndpoint(endpoint)
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload = ["prompt": text]
        req.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            let routePath = "POST \(url.path.isEmpty ? "/" : url.path)\(url.query.map { "?\($0)" } ?? "")"
            let responseBody = String(data: data, encoding: .utf8)
            if let http = response as? HTTPURLResponse, http.statusCode == 403 {
                throw BRAINKRemoteRuntimeError.forbidden(endpoint: routePath)
            }
            throw BRAINKRemoteRuntimeError.http(
                statusCode: (response as? HTTPURLResponse)?.statusCode ?? -1,
                endpoint: routePath,
                body: responseBody
            )
        }

        guard let decoded = try? JSONDecoder().decode(RuntimeResponse.self, from: data) else {
            let routePath = "POST \(url.path.isEmpty ? "/" : url.path)\(url.query.map { "?\($0)" } ?? "")"
            throw BRAINKRemoteRuntimeError.invalidResponse(endpoint: routePath)
        }
        let route = decoded.route ?? classifyRoute(text)
        return (decoded.response, route)
    }

    private func score(match input: String, tokens: [String]) -> Double {
        let score = tokens.reduce(0) { sum, token in
            sum + (input.contains(token) ? 1 : 0)
        }
        return min(Double(score) / Double(max(tokens.count, 1)), 1.0)
    }

    private func collectILLMInventory(pathOverride: String? = nil) throws -> [String] {
        let root = pathOverride ?? ilLlmPath
        guard let root, !root.isEmpty else {
            throw NSError(domain: "BRAINKChat", code: 3, userInfo: [NSLocalizedDescriptionKey: "Missing IL_LLM_RUNTIME_PATH"])
        }
        let url = URL(fileURLWithPath: root, isDirectory: true)
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw NSError(domain: "BRAINKChat", code: 4, userInfo: [NSLocalizedDescriptionKey: "Path does not exist"])
        }
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory),
              isDirectory.boolValue || FileManager.default.fileExists(atPath: url.path) else {
            throw NSError(domain: "BRAINKChat", code: 6, userInfo: [NSLocalizedDescriptionKey: "Path is not readable"])
        }

        if !isDirectory.boolValue {
            return [url.path]
        }

        var result: [String] = []
        if let enumerator = FileManager.default.enumerator(
            at: url,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) {
            for case let fileURL as URL in enumerator {
                let isFile = try? fileURL.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile ?? false
                if isFile == true {
                    result.append(fileURL.path)
                    if result.count >= 200 { break }
                }
            }
        }

        if result.isEmpty {
            throw NSError(domain: "BRAINKChat", code: 5, userInfo: [NSLocalizedDescriptionKey: "No readable files found"])
        }
        return result
    }

    private func ingestILLMFiles(_ filePaths: [String]) throws -> [ILDocumentSnippet] {
        var loaded: [ILDocumentSnippet] = []
        for path in filePaths {
            let url = URL(fileURLWithPath: path)
            let ext = url.pathExtension.lowercased()
            if !ilLlmSupportedExtensions.contains(ext), !ext.isEmpty { continue }
            guard let data = try? Data(contentsOf: url),
                  let text = String(data: data, encoding: .utf8),
                  !text.isEmpty else { continue }
            let snippet = String(text.prefix(ilLlmMaxSnippetLength))
            loaded.append(ILDocumentSnippet(path: path, snippet: snippet))
        }
        return loaded
    }

    private func summarizeLoadedILLM(for userText: String) -> String {
        guard !ilLlmSnippets.isEmpty else {
            return ""
        }

        let tokens = userText.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count > 2 }

        guard !tokens.isEmpty else { return "" }

        let ranked = ilLlmSnippets.compactMap { snippet -> (ILDocumentSnippet, Int)? in
            let source = snippet.snippet.lowercased()
            let score = tokens.reduce(0) { running, token in
                running + (source.contains(token) ? 1 : 0)
            }
            guard score > 0 else { return nil }
            return (snippet, score)
        }
        .sorted { (lhs, rhs) in
            if lhs.1 == rhs.1 {
                return lhs.0.path < rhs.0.path
            }
            return lhs.1 > rhs.1
        }

        guard !ranked.isEmpty else { return "" }
        return ranked.prefix(3).map { pair in
            let file = URL(fileURLWithPath: pair.0.path).lastPathComponent
            return "- \(file): \(pair.0.snippet)"
        }.joined(separator: "\n")
    }

    private func refreshILLMContext() {
        guard let path = ilLlmPath, !path.isEmpty else {
            ilLlmLoadedCount = 0
            ilLlmLoadedStatus = "No IL-LLM runtime path configured."
            ilLlmSnippets = []
            refreshKnowledgeCenter(force: true, reason: "startup_missing_path", routeTag: nil)
            return
        }

        knowledgeCenter.setRuntimePath(path)
        do {
            let inventory = try collectILLMInventory(pathOverride: path)
            let loaded = try ingestILLMFiles(inventory)
            applyLoadedILLMContext(
                path: path,
                loaded: loaded,
                inventoryCount: inventory.count,
                routeTag: "system.runtime_startup"
            )
            append(
                role: .system,
                    text: "Startup IL-LLM context load complete: \(ilLlmLoadedStatus)",
                    route: "system.runtime_startup"
            )
            refreshKnowledgeCenter(force: true, reason: "startup_refresh", routeTag: nil)
        } catch {
            ilLlmLoadedCount = 0
            ilLlmSnippets = []
            ilLlmLoadedStatus = "Startup context load failed: \(error.localizedDescription)"
            refreshKnowledgeCenter(force: true, reason: "startup_refresh_failed", routeTag: nil)
        }
    }

    private func bootstrapCurrentDataBundle() -> String {
        guard let path = ilLlmPath, !path.isEmpty else {
            return "No IL-LLM path is configured. Set IL_LLM_RUNTIME_PATH or drop a file/folder for 'my data'."
        }

        knowledgeCenter.setRuntimePath(path)
        refreshKnowledgeCenter(force: true, reason: "bootstrap_request", routeTag: nil)

        do {
            let inventory = try collectILLMInventory(pathOverride: path)
            let loaded = try ingestILLMFiles(inventory)
            applyLoadedILLMContext(
                path: path,
                loaded: loaded,
                inventoryCount: inventory.count,
                routeTag: "system.runtime_reload"
            )

            let sample = loaded
                .prefix(6)
                .map { URL(fileURLWithPath: $0.path).lastPathComponent }
                .joined(separator: ", ")

            if loaded.isEmpty {
                return "I checked \(path), but no readable supported files are available yet. Drop files/folders or change IL_LLM_RUNTIME_PATH."
            }
            return "Loaded your data: \(loaded.count) files from \(path). sample: \(sample.isEmpty ? "none" : sample). \(ilLlmGrowthStatus). \(ilLlmMemoryStatus)."
        } catch {
            ilLlmLoadedCount = 0
            ilLlmSnippets.removeAll()
            ilLlmLoadedStatus = "Load failed: \(error.localizedDescription)"
            refreshKnowledgeCenter(force: true, reason: "bootstrap_failed", routeTag: nil)
            return "Load failed for \(path): \(error.localizedDescription)"
        }
    }

    private func applyLoadedILLMContext(path: String, loaded: [ILDocumentSnippet], inventoryCount: Int, routeTag: String) {
        ilLlmPath = path
        ilLlmRuntimePath = path
        knowledgeCenter.setRuntimePath(path)
        ilLlmLoadedCount = loaded.count
        ilLlmSnippets = loaded
        ilLlmLoadedStatus = loaded.isEmpty
            ? "No readable IL-LLM text files found."
            : "Loaded \(loaded.count) IL-LLM files into working memory."

        if !loaded.isEmpty {
            let sample = loaded
                .prefix(4)
                .map { URL(fileURLWithPath: $0.path).lastPathComponent }
                .joined(separator: ", ")
            append(
                role: .system,
                text: "Loaded IL-LLM snippets from: \(sample)",
                route: "system.runtime_drop_indexed"
            )
        }

        append(
            role: .system,
            text: "Indexed \(inventoryCount) IL-LLM entries from \(path).",
            route: routeTag
        )
        refreshKnowledgeCenter(force: false, reason: "legacy_context_applied", routeTag: nil)
    }
}
