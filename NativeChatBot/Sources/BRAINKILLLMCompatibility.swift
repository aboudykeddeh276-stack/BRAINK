import Foundation

struct ILLLMCompatibilityProfile: Codable {
    let name: String
    let required: Bool
    let found: Bool
    let evidence: [String]
    let repair: String?
}

struct ILLLMCompatibilityReport: Codable {
    let architect: String
    let organization: String
    let signature: String
    let status: String
    let runtimePath: String
    let profileCount: Int
    let passedCount: Int
    let compatibilityScore: Double
    let generatedAt: String
    let profiles: [ILLLMCompatibilityProfile]
    let nextMove: String
    let engineeredSuccessPath: [String]
}

enum BRAINKILLLMCompatibility {
    static func run(runtimePath: String) -> ILLLMCompatibilityReport {
        let inventory = collectInventory(rootPath: runtimePath, maxFiles: 10_000)
        let lowerPaths = inventory.map { $0.lowercased() }
        let filesWithContent = loadContentSamples(paths: inventory, maxFiles: 300, maxBytes: 24_000)

        let profiles = [
            pythonEngineProfile(lowerPaths: lowerPaths, samples: filesWithContent),
            typescriptBridgeProfile(lowerPaths: lowerPaths, samples: filesWithContent),
            workflowSpecProfile(lowerPaths: lowerPaths, samples: filesWithContent),
            indexDataProfile(lowerPaths: lowerPaths, samples: filesWithContent),
            automationProfile(lowerPaths: lowerPaths, samples: filesWithContent),
            testingProfile(lowerPaths: lowerPaths, samples: filesWithContent),
        ]

        let passedCount = profiles.filter { $0.found }.count
        let profileCount = profiles.count
        let score = profileCount == 0 ? 0.0 : Double(passedCount) / Double(profileCount)
        let status = score == 1.0 ? "DONE" : "NOT DONE"
        let nextMove = status == "DONE"
            ? "Runtime is fully IL-LLM multi-compatible. Continue through clean entry paths and IL-LLM updates only."
            : "Repair missing compatibility profiles, then rerun IL-LLM compatibility check."
        let successPath = status == "DONE"
            ? [
                "1. Keep baseline sealed and mutate only IL-LLM runtime content.",
                "2. Add new entry line names through line registry for targeted runtime focus.",
                "3. Re-run compatibility check after each IL-LLM update batch."
            ]
            : [
                "1. Repair all missing required profiles listed below.",
                "2. Validate route-level runtime behavior after repair.",
                "3. Re-run compatibility check until status becomes DONE."
            ]

        return ILLLMCompatibilityReport(
            architect: BRAINKConstants.architectName,
            organization: BRAINKConstants.organizationName,
            signature: BRAINKConstants.authorshipSignature,
            status: status,
            runtimePath: runtimePath,
            profileCount: profileCount,
            passedCount: passedCount,
            compatibilityScore: score,
            generatedAt: ISO8601DateFormatter().string(from: Date()),
            profiles: profiles,
            nextMove: nextMove,
            engineeredSuccessPath: successPath
        )
    }

    static func writeReport(_ report: ILLLMCompatibilityReport) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(report)
        let url = URL(fileURLWithPath: BRAINKConstants.illlmCompatibilityReportPath)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
    }

    static func asText(_ report: ILLLMCompatibilityReport) -> String {
        let profileLines = report.profiles.map { profile in
            let status = profile.found ? "DONE" : "NOT DONE"
            let evidence = profile.evidence.isEmpty ? "none" : profile.evidence.prefix(4).joined(separator: " | ")
            let repair = profile.repair ?? "none"
            return """
            [\(status)] \(profile.name)
            evidence: \(evidence)
            repair: \(repair)
            """
        }.joined(separator: "\n")

        return """
        ILLLM COMPATIBILITY DELIVERY
        architect: \(report.architect)
        organization: \(report.organization)
        signature: \(report.signature)
        status: \(report.status)
        runtime_path: \(report.runtimePath)
        score: \(String(format: "%.4f", report.compatibilityScore))
        passed_profiles: \(report.passedCount)/\(report.profileCount)
        report_path: \(BRAINKConstants.illlmCompatibilityReportPath)

        NEXT REQUIRED MOVE
        \(report.nextMove)

        ENGINEERED SUCCESS PATH
        \(report.engineeredSuccessPath.joined(separator: "\n"))

        PROFILE RESULTS
        \(profileLines)
        """
    }

    private static func collectInventory(rootPath: String, maxFiles: Int) -> [String] {
        let rootURL = URL(fileURLWithPath: rootPath, isDirectory: true)
        guard FileManager.default.fileExists(atPath: rootURL.path) else { return [] }

        var paths: [String] = []
        if let enumerator = FileManager.default.enumerator(
            at: rootURL,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) {
            for case let fileURL as URL in enumerator {
                let isFile = (try? fileURL.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) ?? false
                guard isFile else { continue }
                paths.append(fileURL.path)
                if paths.count >= maxFiles { break }
            }
        }
        return paths
    }

    private static func loadContentSamples(paths: [String], maxFiles: Int, maxBytes: Int) -> [(path: String, content: String)] {
        var out: [(path: String, content: String)] = []
        for path in paths.prefix(maxFiles) {
            guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { continue }
            let slice = data.prefix(maxBytes)
            guard let text = String(data: slice, encoding: .utf8) else { continue }
            out.append((path, text.lowercased()))
        }
        return out
    }

    private static func pythonEngineProfile(lowerPaths: [String], samples: [(path: String, content: String)]) -> ILLLMCompatibilityProfile {
        let pathHits = lowerPaths.filter { $0.hasSuffix(".py") }
        let contentHits = samples
            .filter { $0.path.lowercased().hasSuffix(".py") && ($0.content.contains("class brainkengine") || $0.content.contains("kex") || $0.content.contains("process_interaction")) }
            .map(\.path)
        let found = !pathHits.isEmpty && !contentHits.isEmpty
        return ILLLMCompatibilityProfile(
            name: "python_engine_core",
            required: true,
            found: found,
            evidence: Array((contentHits.isEmpty ? pathHits : contentHits).prefix(6)),
            repair: found ? nil : "Add or expose Python BRAINK/IL-LLM engine files with core class/process pipeline."
        )
    }

    private static func typescriptBridgeProfile(lowerPaths: [String], samples: [(path: String, content: String)]) -> ILLLMCompatibilityProfile {
        let pathHits = lowerPaths.filter { $0.hasSuffix(".ts") || $0.hasSuffix(".tsx") }
        let contentHits = samples
            .filter { ($0.path.lowercased().hasSuffix(".ts") || $0.path.lowercased().hasSuffix(".tsx")) && ($0.content.contains("interface brainkengine") || $0.content.contains("class brainkbridge") || $0.content.contains("packet")) }
            .map(\.path)
        let found = !pathHits.isEmpty && !contentHits.isEmpty
        return ILLLMCompatibilityProfile(
            name: "typescript_bridge_contract",
            required: true,
            found: found,
            evidence: Array((contentHits.isEmpty ? pathHits : contentHits).prefix(6)),
            repair: found ? nil : "Add TS bridge/interface contracts for BRAINK packet/runtime integration."
        )
    }

    private static func workflowSpecProfile(lowerPaths: [String], samples: [(path: String, content: String)]) -> ILLLMCompatibilityProfile {
        let pathHits = lowerPaths.filter { $0.hasSuffix(".md") }
        let contentHits = samples
            .filter { $0.path.lowercased().hasSuffix(".md") && ($0.content.contains("workflow") || $0.content.contains("theorem") || $0.content.contains("constraint")) }
            .map(\.path)
        let found = !contentHits.isEmpty
        return ILLLMCompatibilityProfile(
            name: "workflow_and_constraint_specs",
            required: true,
            found: found,
            evidence: Array((contentHits.isEmpty ? pathHits : contentHits).prefix(6)),
            repair: found ? nil : "Provide workflow/spec markdown with theorem/constraint definitions."
        )
    }

    private static func indexDataProfile(lowerPaths: [String], samples: [(path: String, content: String)]) -> ILLLMCompatibilityProfile {
        let csvHits = lowerPaths.filter { $0.hasSuffix(".csv") }
        let jsonHits = lowerPaths.filter { $0.hasSuffix(".json") }
        let found = !csvHits.isEmpty || !jsonHits.isEmpty
        return ILLLMCompatibilityProfile(
            name: "index_and_packet_data",
            required: true,
            found: found,
            evidence: Array((csvHits + jsonHits).prefix(8)),
            repair: found ? nil : "Provide index or packet data files (.csv/.json) for IL-LLM retrieval and compatibility."
        )
    }

    private static func automationProfile(lowerPaths: [String], samples: [(path: String, content: String)]) -> ILLLMCompatibilityProfile {
        let scriptHits = lowerPaths.filter { $0.hasSuffix(".command") || $0.hasSuffix(".sh") }
        let contentHits = samples
            .filter { ($0.path.lowercased().hasSuffix(".sh") || $0.path.lowercased().hasSuffix(".command")) && ($0.content.contains("python") || $0.content.contains("braink") || $0.content.contains("kex")) }
            .map(\.path)
        let found = !scriptHits.isEmpty && !contentHits.isEmpty
        return ILLLMCompatibilityProfile(
            name: "automation_entrypoints",
            required: true,
            found: found,
            evidence: Array((contentHits.isEmpty ? scriptHits : contentHits).prefix(6)),
            repair: found ? nil : "Provide executable automation entrypoints with BRAINK/IL-LLM routing."
        )
    }

    private static func testingProfile(lowerPaths: [String], samples: [(path: String, content: String)]) -> ILLLMCompatibilityProfile {
        let pathHits = lowerPaths.filter {
            $0.contains("/tests/") || $0.contains("test_") || $0.hasSuffix(".spec.ts") || $0.hasSuffix(".test.ts")
        }
        let contentHits = samples
            .filter { ($0.path.contains("/tests/") || $0.path.contains("test_")) && ($0.content.contains("assert") || $0.content.contains("expect(") || $0.content.contains("pytest") || $0.content.contains("vitest")) }
            .map(\.path)
        let found = !pathHits.isEmpty && !contentHits.isEmpty
        return ILLLMCompatibilityProfile(
            name: "test_surface",
            required: true,
            found: found,
            evidence: Array((contentHits.isEmpty ? pathHits : contentHits).prefix(6)),
            repair: found ? nil : "Add test files asserting runtime behavior and contract compatibility."
        )
    }
}
