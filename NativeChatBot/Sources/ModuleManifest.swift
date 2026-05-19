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
    static var modules: [ModuleDefinition] {
        BRAINKDeliveryAudit.moduleDefinitions()
    }

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
