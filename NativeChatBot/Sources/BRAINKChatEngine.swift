import Foundation

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

@MainActor
final class BRAINKChatEngine: ObservableObject {
    @Published private(set) var messages: [ChatMessage] = []
    @Published private(set) var traces: [ModuleTrace] = []
    @Published var isBusy = false
    @Published private(set) var ilLlmRuntimePath: String
    @Published private(set) var ilLlmLoadedCount: Int = 0
    @Published private(set) var ilLlmLoadedStatus: String = "No IL-LLM data loaded"

    private let localOnly: Bool
    private let endpoint: String?
    private var ilLlmPath: String?
    private var ilLlmSnippets: [ILDocumentSnippet] = []
    private let ilLlmMaxSnippetLength = 1_024
    private let ilLlmSupportedExtensions: Set<String> = ["md", "txt", "json", "py", "ts", "tsx", "js", "swift", "cpp", "c", "go", "java", "yaml", "yml"]

    init()
    {
        self.endpoint = ProcessInfo.processInfo.environment["BRAINK_CHAT_RUNTIME"]
        self.localOnly = (ProcessInfo.processInfo.environment["BRAINK_CHAT_RUNTIME"] ?? "").isEmpty
        self.ilLlmPath = ProcessInfo.processInfo.environment["IL_LLM_RUNTIME_PATH"]
            ?? "/Users/ak/Documents/New project"
        self.ilLlmRuntimePath = self.ilLlmPath ?? "not configured"

        append(
            role: .system,
            text: "BRAINK native chat runtime initialized. Mode: \(localOnly ? "deterministic local" : "bridged runtime")",
            route: "system.init"
        )

        Task {
            self.refreshILLMContext()
        }
    }

    func send(userInput: String) async {
        let message = userInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty, !isBusy else { return }

        isBusy = true
        defer { isBusy = false }

        append(role: .user, text: message, route: "user.input")

        do {
            let preRoute = classifyRoute(message)
            if preRoute == "illlm_bootstrap" {
                let bootstrapStatus = bootstrapCurrentDataBundle()
                append(role: .assistant, text: bootstrapStatus, route: preRoute)
                return
            }

            if !localOnly && self.endpoint != nil {
                let remote = try await callRemoteRuntime(message)
                append(role: .assistant, text: remote.text, route: remote.route)
            } else {
                let local = resolveLocally(message)
                append(role: .assistant, text: local.text, route: local.route)
            }
        } catch {
            append(
                role: .assistant,
                text: "Runtime error: \(error.localizedDescription). Falling back to local deterministic BRAINK engine.",
                route: "system.fallback"
            )
            let local = resolveLocally(message)
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
            } catch {
                ilLlmLoadedCount = 0
                ilLlmSnippets.removeAll()
                ilLlmLoadedStatus = "Attach failed: \(error.localizedDescription)"
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
                let inventory = try collectILLMInventory(pathOverride: path)
                let loaded = try ingestILLMFiles(inventory)
                applyLoadedILLMContext(
                    path: path,
                    loaded: loaded,
                    inventoryCount: inventory.count,
                    routeTag: "system.runtime_reload"
                )
                append(
                    role: .system,
                    text: "Reloaded IL-LLM from: \(path). \(ilLlmLoadedStatus)",
                    route: "system.runtime_reload"
                )
            } catch {
                ilLlmLoadedCount = 0
                ilLlmSnippets.removeAll()
                ilLlmLoadedStatus = "Reload failed: \(error.localizedDescription)"
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

    private func resolveLocally(_ text: String) -> (text: String, route: String) {
        traces = runModules(text)
        let route = classifyRoute(text)
        let tone = traces.map(\.module).joined(separator: " + ")
        let context = summarizeLoadedILLM(for: text)

        var response: String
        switch route {
        case "illlm_bootstrap":
            response = bootstrapCurrentDataBundle()
        case "auth.oauth", "runtime_trace", "build":
            response = "I can run that path. Confirm your current workspace and I will execute the exact worker route next: \(route)."
        case "constraint_flags":
            response = BRAINKModuleManifest.asConstraintFlagsText()
        case "illlm_bundle":
            do {
                let inventory = try collectILLMInventory()
                let sampleFiles = inventory
                    .prefix(12)
                    .map { URL(fileURLWithPath: $0).lastPathComponent }
                    .joined(separator: ", ")
                response = "IL-LLM bundle loaded from: \(ilLlmPath ?? "not configured"). " +
                    "Loaded snippets: \(ilLlmLoadedCount). " +
                    "sample files: \(sampleFiles.isEmpty ? "none" : sampleFiles). " +
                    "\(ilLlmLoadedStatus)."
                if ilLlmLoadedCount == 0 {
                    response += " Drag-drop a data folder into the input bar or set IL_LLM_RUNTIME_PATH then send 'load my data'."
                }
            } catch {
                response = "I could not read IL-LLM bundle at \(ilLlmPath ?? "not configured"). " +
                    "Error: \(error.localizedDescription). Set IL_LLM_RUNTIME_PATH to a readable directory."
            }
        case "proof_packet", "evidence":
            response = "I can return the proof packet route only with explicit runtime reads. Ask for a `proof-packet` request with the target route and I will map exact file/runtime fields."
        case "module_manifest":
            response = BRAINKModuleManifest.asPlainText()
        case "proof":
            response = "Evidence request received. I will return only verifiable fields: file path, schema fields found, route fields, falsifier fields, and cost gate values."
        case "align", "align-check":
            response = "Alignment check started. I am tracing every clicked module and verifying the runtime/route boundary plus file-read provenance."
        case "illlm_query":
            let preview = summarizeLoadedILLM(for: text)
            response = context.isEmpty
                ? "I can use IL-LLM, but I could not match your question to loaded snippets. Try a more specific phrase."
                : "I found relevant IL-LLM context:\n\(preview)"
        case "general":
            response = context.isEmpty
                ? "I am in deterministic BRAINK native mode. Tell me the module and route you want next and I’ll run it with exact proof output."
                : "I am in deterministic BRAINK native mode. I also matched IL-LLM context:\n\(context)"
        default:
            response = "I understood: \(text). Running through modules: \(tone). I am ready for the next command."
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

        if lower.contains("login") || lower.contains("oauth") || lower.contains("auth") {
            return "auth.oauth"
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

    private func callRemoteRuntime(_ text: String) async throws -> (text: String, route: String) {
        guard let endpoint else {
            throw NSError(domain: "BRAINKChat", code: 1)
        }

        let url = URL(string: endpoint)!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let payload = ["prompt": text]
        req.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw NSError(domain: "BRAINKChat", code: 2)
        }

        let decoded = try JSONDecoder().decode(RuntimeResponse.self, from: data)
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
            return
        }

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
        } catch {
            ilLlmLoadedCount = 0
            ilLlmSnippets = []
            ilLlmLoadedStatus = "Startup context load failed: \(error.localizedDescription)"
        }
    }

    private func bootstrapCurrentDataBundle() -> String {
        guard let path = ilLlmPath, !path.isEmpty else {
            return "No IL-LLM path is configured. Set IL_LLM_RUNTIME_PATH or drop a file/folder for 'my data'."
        }

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
            return "Loaded your data: \(loaded.count) files from \(path). sample: \(sample.isEmpty ? "none" : sample)."
        } catch {
            ilLlmLoadedCount = 0
            ilLlmSnippets.removeAll()
            ilLlmLoadedStatus = "Load failed: \(error.localizedDescription)"
            return "Load failed for \(path): \(error.localizedDescription)"
        }
    }

    private func applyLoadedILLMContext(path: String, loaded: [ILDocumentSnippet], inventoryCount: Int, routeTag: String) {
        ilLlmPath = path
        ilLlmRuntimePath = path
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
    }
}
