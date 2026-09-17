import Foundation

struct FrontierSealState: Codable {
    let architect: String
    let organization: String
    let signature: String
    let sealed: Bool
    let sealedAt: String
    let coreHash: String
    let coreFiles: [String]
    let note: String
}

struct RuntimeLineRegistry: Codable {
    var lines: [String]
    var updatedAt: String
}

enum BRAINKFrontierSeal {
    static var coreFiles: [String] {
        let sourceRoot = URL(fileURLWithPath: #filePath).deletingLastPathComponent().path
        return [
            "\(sourceRoot)/BRAINKChatEngine.swift",
            "\(sourceRoot)/BRAINKPlatformAPI.swift",
            "\(sourceRoot)/BRAINKDeliveryAudit.swift",
            "\(sourceRoot)/BRAINKChromePlugin.swift",
            "\(sourceRoot)/BRAINKScraperTool.swift",
            "\(sourceRoot)/KEXHyperdriveConceptEngine.swift",
            "\(sourceRoot)/KEXSelfSustainedCodingEngine.swift"
        ]
    }

    static func isSealed() -> Bool {
        guard let state = readSealState() else { return false }
        return state.sealed
    }

    static func sealBaseline() throws -> FrontierSealState {
        let hash = computeCoreHash(paths: coreFiles)
        let state = FrontierSealState(
            architect: BRAINKConstants.architectName,
            organization: BRAINKConstants.organizationName,
            signature: BRAINKConstants.authorshipSignature,
            sealed: true,
            sealedAt: ISO8601DateFormatter().string(from: Date()),
            coreHash: hash,
            coreFiles: coreFiles,
            note: "Frontier baseline sealed. Runtime mutation routes are disabled; add line names through clean entry registry only."
        )
        try writeJSON(state, to: BRAINKConstants.frontierSealPath)
        _ = try ensureRegistry()
        return state
    }

    static func readSealState() -> FrontierSealState? {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: BRAINKConstants.frontierSealPath)) else {
            return nil
        }
        return try? JSONDecoder().decode(FrontierSealState.self, from: data)
    }

    static func ensureRegistry() throws -> RuntimeLineRegistry {
        if let existing = readRegistry() {
            return existing
        }
        let initial = RuntimeLineRegistry(lines: [], updatedAt: ISO8601DateFormatter().string(from: Date()))
        try writeJSON(initial, to: BRAINKConstants.runtimeLineRegistryPath)
        return initial
    }

    static func addLineName(_ rawName: String) throws -> RuntimeLineRegistry {
        let normalized = rawName
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
        guard !normalized.isEmpty else {
            throw NSError(domain: "BRAINKFrontierSeal", code: 1, userInfo: [NSLocalizedDescriptionKey: "line_name_empty"])
        }

        var registry = try ensureRegistry()
        if !registry.lines.contains(normalized) {
            registry.lines.append(normalized)
        }
        registry.updatedAt = ISO8601DateFormatter().string(from: Date())
        registry.lines.sort()
        try writeJSON(registry, to: BRAINKConstants.runtimeLineRegistryPath)
        return registry
    }

    static func readRegistry() -> RuntimeLineRegistry? {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: BRAINKConstants.runtimeLineRegistryPath)) else {
            return nil
        }
        return try? JSONDecoder().decode(RuntimeLineRegistry.self, from: data)
    }

    static func entryPathsText() -> String {
        let registry = readRegistry() ?? RuntimeLineRegistry(lines: [], updatedAt: "never")
        let linesText = registry.lines.isEmpty ? "- none" : registry.lines.map { "- \($0)" }.joined(separator: "\n")
        return """
        clean_entry_paths:
        \(linesText)
        registry_path: \(BRAINKConstants.runtimeLineRegistryPath)
        updated_at: \(registry.updatedAt)
        """
    }

    private static func computeCoreHash(paths: [String]) -> String {
        var joined = ""
        for path in paths {
            let content = (try? String(contentsOfFile: path, encoding: .utf8)) ?? ""
            let text = BRAINKConstants.stableHexDigest(Data(content.utf8))
            joined.append(path)
            joined.append(":")
            joined.append(text)
            joined.append("\n")
        }
        return BRAINKConstants.stableHexDigest(Data(joined.utf8))
    }

    private static func writeJSON<T: Codable>(_ value: T, to path: String) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(value)
        let url = URL(fileURLWithPath: path)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }
}
