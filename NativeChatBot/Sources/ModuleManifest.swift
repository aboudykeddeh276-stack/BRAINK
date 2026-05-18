import Foundation

enum ModuleDeliveryState: String, Codable {
    case done = "DONE"
    case simulated = "SIMULATED"
    case inferred = "INFERRED"
    case blocked = "BLOCKED"
    case notDone = "NOT DONE"
}

struct ModuleDeliveryEvidence: Codable {
    let requiredState: ModuleDeliveryState
    let runningFile: String
    let logicalLink: String
    let verification: String
}

struct ModuleDefinition: Codable {
    let moduleName: String
    let evidence: ModuleDeliveryEvidence
}

struct ConstraintFlag: Codable {
    let moduleName: String
    let requiredState: String
    let flaggable: Bool
    let runningFile: String
    let verificationHint: String
}

enum BRAINKModuleManifest {
    static let modules: [ModuleDefinition] = [
        ModuleDefinition(
            moduleName: "Screen container / safe content layout",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatBotApp.swift",
                logicalLink: "BrainkNativeChatbotView (outer VStacks + scroll + module/runtime side panel, route badge rendering, and divider boundaries)",
                verification: "Rendered UI proves content boundaries and deterministic layout in native SwiftUI at runtime."
            )
        ),
        ModuleDefinition(
            moduleName: "Themed view abstraction",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatBotApp.swift",
                logicalLink: "MessageBubble + TraceRow + section containers use explicit color/design modifiers per role; replaces React Native ThemedView semantics in native style.",
                verification: "Bubble and section color/contrast logic executes on every render."
            )
        ),
        ModuleDefinition(
            moduleName: "OAuth constants and redirect/url helpers",
            evidence: ModuleDeliveryEvidence(
                requiredState: .inferred,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift",
                logicalLink: "No direct OAuth runtime module exists in this native build; equivalent route execution is handled by local resolver + optional remote endpoint in callRemoteRuntime().",
                verification: "No Apple-app-login deep-link function exists yet in current codebase."
            )
        ),
        ModuleDefinition(
            moduleName: "Proof/evidence route handling",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift",
                logicalLink: "classifyRoute(...) maps proof/packet/falsifier terms to proof_packet; resolveLocally(...) returns evidence-focused reply text.",
                verification: "Send text including 'proof packet' and observe route 'proof_packet'."
            )
        ),
        ModuleDefinition(
            moduleName: "Runtime trace route handling",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift",
                logicalLink: "classifyRoute(...) maps runtime/route/entrypoint to runtime_trace; resolveLocally(...) returns deterministic routing response and traces.",
                verification: "Send text containing 'runtime entrypoint' and observe route 'runtime_trace'."
            )
        ),
        ModuleDefinition(
            moduleName: "IL-LLM drag-and-drop ingestion",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatBotApp.swift",
                logicalLink: "ChatInputBar .onDrop(...) -> handleILLLMDrop(...) -> BRAINKChatEngine.attachILLLMRuntimePath(_:).",
                verification: "Drop file/folder into input strip and observe messages: system.runtime_drop + startup/indexed trace lines."
            )
        ),
        ModuleDefinition(
            moduleName: "IL-LLM inventory + snippet search",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift",
                logicalLink: "collectILLMInventory(...), ingestILLMFiles(...), summarizeLoadedILLM(for:).",
                verification: "Attach folder with readable files; ask an IL-LLM question and inspect returned snippets."
            )
        ),
        ModuleDefinition(
            moduleName: "Data-first command and manual reload",
            evidence: ModuleDeliveryEvidence(
                requiredState: .done,
                runningFile: "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/Sources/BRAINKChatEngine.swift",
                logicalLink: "ClassifyRoute maps explicit data-intent phrases ('my data', 'want my data', 'have my data', 'load my data', 'chatbot'+'my data') to illlm_bootstrap and invokes bootstrapCurrentDataBundle().",
                verification: "Type 'i want my chatbot to have my data' and observe the immediate status message from route 'illlm_bootstrap'."
            )
        )
    ]

    static func asJSON() -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return (try? String(data: encoder.encode(modules), encoding: .utf8)) ?? "[]"
    }

    static func asConstraintFlagsJSON() -> String {
        let flags = modules.map { entry in
            ConstraintFlag(
                moduleName: entry.moduleName,
                requiredState: entry.evidence.requiredState.rawValue,
                flaggable: isFlaggable(entry.evidence.requiredState),
                runningFile: entry.evidence.runningFile,
                verificationHint: entry.evidence.verification
            )
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return (try? String(data: encoder.encode(flags), encoding: .utf8)) ?? "[]"
    }

    static func asConstraintFlagsText() -> String {
        modules.enumerated().map { idx, module in
            let file = module.evidence.runningFile
            let state = module.evidence.requiredState.rawValue
            let flaggable = isFlaggable(module.evidence.requiredState) ? "FLAGGABLE" : "NOT_FLAGGABLE"
            let link = module.evidence.logicalLink
            return """
            [\(state)] \(idx + 1). \(module.moduleName)
            file: \(file)
            tag: \(flaggable)
            link: \(link)
            """
        }.joined(separator: "\n")
    }

    private static func isFlaggable(_ state: ModuleDeliveryState) -> Bool {
        switch state {
        case .done, .simulated, .inferred, .notDone, .blocked:
            return true
        }
    }

    static func asPlainText() -> String {
        modules.enumerated().map { idx, module in
            """
            [\(module.evidence.requiredState.rawValue)] \(idx + 1). \(module.moduleName)
            - file: \(module.evidence.runningFile)
            - link: \(module.evidence.logicalLink)
            - verification: \(module.evidence.verification)
            """
        }.joined(separator: "\n")
    }
}
