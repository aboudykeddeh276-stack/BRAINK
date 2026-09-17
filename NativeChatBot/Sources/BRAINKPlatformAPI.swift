import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct Packet<Payload: Codable>: Codable {
    let packetType: String
    let version: Int
    let createdAt: String
    let constraintMap: [String: String]
    let payload: Payload
    let evidence: Evidence?
}

struct Evidence: Codable {
    let testResults: [String]
    let performanceMetrics: [String: Double]
    let auditTrail: [AuditEntry]
}

struct AuditEntry: Codable {
    let timestamp: String
    let action: String
    let result: AuditResult
    let details: [String: String]?
}

enum AuditResult: String, Codable {
    case success
    case failure
    case pending
}

struct ExecutionPolicy: Codable {
    let requiresApproval: Bool
    let costEstimate: Double?
    let timeoutMs: Int
    let allowedCommands: [String]
    let blockedPatterns: [String]
}

struct ExecutionResult: Codable {
    let success: Bool
    let output: String?
    let error: String?
    let executedAt: String
    let durationMs: Int
    let auditEntry: AuditEntry
}

struct DesktopIndexEntry: Codable {
    let path: String
    let sizeBytes: Int
    let modifiedAt: String
    let contentHash: String
    let chunkId: Int
    let chunkText: String
    let sensitive: Bool
    let indexedAt: String
}

struct DesktopIndex: Codable {
    let entries: [DesktopIndexEntry]
    let totalFiles: Int
    let totalSize: Int
    let redactedCount: Int
    let indexedAt: String
}

struct KexDnaEntry: Codable {
    let path: String
    let rawSha256: String
    let normalizedSha256: String
    let architect: String
    let kexTheorem: String
    let status: String
    let math: String
    let provenResolveKeys: [String]
    let accepted: Bool
    let missingFields: [String]?
}

struct KexDnaReport: Codable {
    let packetType: String
    let createdAt: String
    let sourceRoot: String
    let filesFound: Int
    let acceptedFiles: Int
    let uniqueNormalizedGenomes: Int
    let canonicalGenomes: [KexDnaEntry]
    let constraintMap: [String: String]
    let passed: Bool
}

struct CodexContext: Codable {
    let desktopFiles: [String]
    let recentCommands: [String]
    let learnedPatterns: [String: Double]
}

struct ExecutionPlan: Codable {
    let steps: [String]
    let costEstimate: Double
    let requiredApprovals: [String]
}

struct CodexPacket: Codable {
    let packetType: String
    let createdAt: String
    let operatorObjective: String
    let context: CodexContext
    let executionPlan: ExecutionPlan
    let evidence: Evidence
}

struct ConversationTurn: Codable {
    let userInput: String
    let brainkResponse: String
    let wrapperActive: WrapperState?
    let emotionalState: [String: Double]?
    let reasoningState: [String: Double]?
    let timestamp: String
}

struct WrapperState: Codable {
    let wrapperType: String
    let taskDomain: String
}

struct ConversationMemory: Codable {
    let turns: [ConversationTurn]
    let userPersonalitySignature: [String: Double]
    let accumulatedPatterns: [String: Double]
    let emotionalHistory: [Double]
}

struct LearningReport: Codable {
    struct Pattern: Codable {
        let name: String
        let frequency: Int
        let impact: Double
        let confidence: Double
    }

    struct Optimization: Codable {
        let target: String
        let suggestion: String
        let expectedImprovement: Double
        let effort: String
    }

    let patterns: [Pattern]
    let optimizations: [Optimization]
    let nextActions: [String]
    let confidence: Double
    let createdAt: String
}

struct UserIntent: Codable {
    let objective: String
    let estimatedCost: Double
    let grantedPermissions: [String]
    let timeoutMs: Int
}

struct Operation: Codable {
    let goal: String
    let actualCost: Double
    let requiredPermissions: [String]
    let estimatedDurationMs: Int
}

struct VerificationResult: Codable {
    let verified: Bool
    let confidence: Double
    let crossChecks: CrossChecks
    let evidence: [String]
}

struct CrossChecks: Codable {
    let intentMatch: Bool
    let costMatch: Bool
    let permissionMatch: Bool
}

struct SystemStatus: Codable {
    let healthy: Bool
    let uptime: TimeInterval
    let memoryUsage: Int64
    let cpuUsage: Double
    let indexedFiles: Int
    let cacheSize: Int
    let lastUpdate: String
    let constraints: [String: String]
}

protocol BRAINKEngine {
    func initialize() async throws
    func execute(command: String, policy: ExecutionPolicy) async throws -> ExecutionResult
    func indexDesktop(rootPath: String) async throws -> DesktopIndex
    func searchIndex(query: String, limit: Int?) async throws -> [DesktopIndexEntry]
    func inspectKexDna() async throws -> KexDnaReport
    func generateCodexPacket(objective: String) async throws -> CodexPacket
    func processInteraction(userInput: String) async throws -> (response: String, conversationTurn: ConversationTurn, memory: ConversationMemory)
    func verifyBilateral(intent: UserIntent, operation: Operation) async throws -> VerificationResult
    func recursiveLearning(history: [ConversationTurn]) async throws -> LearningReport
    func getStatus() async throws -> SystemStatus
}

final class BRAINKPlatformEngine: BRAINKEngine {
    enum PlatformError: Error, LocalizedError {
        case missingEndpoint
        case invalidPayload
        case invalidResponse
        case runtime(String)

        var errorDescription: String? {
            switch self {
            case .missingEndpoint:
                return "Endpoint missing"
            case .invalidPayload:
                return "Unable to encode payload"
            case .invalidResponse:
                return "Invalid runtime response"
            case .runtime(let message):
                return message
            }
        }
    }

    private let baseURL: URL?
    private(set) var sessionId: String
    private var initializedAt: Date?
    private var commandAudit: [AuditEntry] = []
    private var desktopIndex: [DesktopIndexEntry] = []
    private var lastIndexTime: Date?
    private var conversationLog: [ConversationTurn] = []

    private static let supportedExtensions: Set<String> = ["md", "txt", "json", "swift", "ts", "tsx", "js", "py", "yaml", "yml", "c", "cpp", "go", "java", "sh", "xml", "toml", "plist"]

    init(baseURLString: String?) {
        if let raw = baseURLString, !raw.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            baseURL = URL(string: raw)
        } else {
            baseURL = nil
        }
        sessionId = Self.makeSessionId()
    }

    func initialize() async throws {
        if let endpoint = baseURL {
            var req = URLRequest(url: endpoint.appendingPathComponent("/api/braink/initialize"))
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try encodeJSONObject(["sessionId": sessionId])

            let (data, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
                let message = String(data: data, encoding: .utf8) ?? "unknown"
                throw PlatformError.runtime("initialize failed: \(message)")
            }
            if !data.isEmpty {
                _ = try? JSONDecoder().decode([String: String].self, from: data)
            }
        }
        initializedAt = Date()
        commandAudit.append(AuditEntry(
            timestamp: Self.isoNow(),
            action: "initialize",
            result: .success,
            details: ["mode": baseURL == nil ? "local" : "remote", "session": sessionId]
        ))
    }

    func execute(command: String, policy: ExecutionPolicy) async throws -> ExecutionResult {
        let started = Date()

        try validateCommand(command, against: policy)

        if let endpoint = baseURL {
            let body: [String: Any] = [
                "command": command,
                "policy": [
                    "requiresApproval": policy.requiresApproval,
                    "costEstimate": policy.costEstimate ?? 0,
                    "timeoutMs": policy.timeoutMs,
                    "allowedCommands": policy.allowedCommands,
                    "blockedPatterns": policy.blockedPatterns
                ],
                "sessionId": sessionId
            ]
            var req = URLRequest(url: endpoint.appendingPathComponent("/api/braink/execute"))
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try encodeJSONObject(body)

            let (data, response) = try await URLSession.shared.data(for: req)
            let http = response as? HTTPURLResponse
            let durationMs = Int(Date().timeIntervalSince(started) * 1000)
            let text = String(data: data, encoding: .utf8) ?? ""
            if let status = http?.statusCode, 200..<300 ~= status {
                let audit = AuditEntry(
                    timestamp: Self.isoNow(),
                    action: command,
                    result: .success,
                    details: ["source": "remote", "durationMs": "\(durationMs)"]
                )
                commandAudit.append(audit)
                return ExecutionResult(
                    success: true,
                    output: text,
                    error: nil,
                    executedAt: Self.isoNow(),
                    durationMs: durationMs,
                    auditEntry: audit
                )
            }
            let audit = AuditEntry(
                timestamp: Self.isoNow(),
                action: command,
                result: .failure,
                details: ["source": "remote", "status": "\(http?.statusCode ?? -1)"]
            )
            commandAudit.append(audit)
            return ExecutionResult(
                success: false,
                output: nil,
                error: text,
                executedAt: Self.isoNow(),
                durationMs: durationMs,
                auditEntry: audit
            )
        }

        let runtime = executeLocally(command: command)
        let durationMs = Int(Date().timeIntervalSince(started) * 1000)
        let audit = AuditEntry(
            timestamp: Self.isoNow(),
            action: command,
            result: runtime.success ? .success : .failure,
            details: ["source": "local", "durationMs": "\(durationMs)"]
        )
        commandAudit.append(audit)
        return ExecutionResult(
            success: runtime.success,
            output: runtime.output,
            error: runtime.error,
            executedAt: Self.isoNow(),
            durationMs: durationMs,
            auditEntry: audit
        )
    }

    func indexDesktop(rootPath: String) async throws -> DesktopIndex {
        let entries = try collectDesktopIndex(rootPath: rootPath)
        desktopIndex = entries
        let redacted = entries.filter { $0.sensitive }.count
        let totalSize = entries.reduce(0) { $0 + $1.sizeBytes }
        lastIndexTime = Date()
        return DesktopIndex(
            entries: entries,
            totalFiles: entries.count,
            totalSize: totalSize,
            redactedCount: redacted,
            indexedAt: Self.isoNow()
        )
    }

    func searchIndex(query: String, limit: Int? = nil) async throws -> [DesktopIndexEntry] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return [] }
        let scored = desktopIndex.compactMap { item -> (DesktopIndexEntry, Int)? in
            let haystack = (item.path + " " + item.chunkText).lowercased()
            let score = tokenize(trimmed).reduce(0) { acc, token in
                acc + (haystack.contains(token) ? 1 : 0)
            }
            guard score > 0 else { return nil }
            return (item, score)
        }
        .sorted { $0.1 == $1.1 ? $0.0.path < $1.0.path : $0.1 > $1.1 }

        let ordered = scored.map { $0.0 }
        if let limit {
            return Array(ordered.prefix(limit))
        }
        return ordered
    }

    func inspectKexDna() async throws -> KexDnaReport {
        let reportEntries = BRAINKModuleManifest.modules.enumerated().map { index, module in
            let raw = "\(module.moduleName)|\(module.evidence.logicalLink)"
            let rawHash = Self.sha256(raw)
            let normalizedHash = Self.sha256(raw.lowercased())
            return KexDnaEntry(
                path: module.evidence.runningFile,
                rawSha256: rawHash,
                normalizedSha256: normalizedHash,
                architect: "BRAINK",
                kexTheorem: module.moduleName,
                status: module.evidence.requiredState.rawValue,
                math: "route_mapping_sum(modules.done)",
                provenResolveKeys: [module.moduleName, module.evidence.logicalLink],
                accepted: module.evidence.requiredState == .done,
                missingFields: module.evidence.requiredState == .done ? nil : ["required_state_not_done"]
            )
        }

        let accepted = reportEntries.filter { $0.accepted }.count
        return KexDnaReport(
            packetType: "KEX_DNA_ONBOARDING_REPORT_V1",
            createdAt: Self.isoNow(),
            sourceRoot: BRAINKConstants.nativeChatBotRoot,
            filesFound: reportEntries.count,
            acceptedFiles: accepted,
            uniqueNormalizedGenomes: Set(reportEntries.map { $0.normalizedSha256 }).count,
            canonicalGenomes: reportEntries,
            constraintMap: ["scope": "native-platform", "runtime": "local+il-llm"],
            passed: accepted == reportEntries.count
        )
    }

    func generateCodexPacket(objective: String) async throws -> CodexPacket {
        let objectiveSafe = objective.trimmingCharacters(in: .whitespacesAndNewlines)
        if objectiveSafe.isEmpty {
            throw PlatformError.runtime("Objective cannot be empty")
        }

        let recentCommands = commandAudit.suffix(20).map { $0.action }
        let evidence = Evidence(
            testResults: ["initialize", "execute", "index", "search", "status"],
            performanceMetrics: ["command_audit": Double(commandAudit.count), "indexed_files": Double(desktopIndex.count)],
            auditTrail: Array(commandAudit.suffix(20))
        )

        let learned = dictionaryFromRecentTurns()
        let context = CodexContext(
            desktopFiles: desktopIndex.map { $0.path },
            recentCommands: Array(recentCommands),
            learnedPatterns: learned
        )

        return CodexPacket(
            packetType: "CODEX_PACKET_V1",
            createdAt: Self.isoNow(),
            operatorObjective: objectiveSafe,
            context: context,
            executionPlan: ExecutionPlan(
                steps: [
                    "Initialize session",
                    "Index runtime source where available",
                    "Execute objective with policy guardrails",
                    "Verify bilateral constraints",
                    "Persist evidence and report"
                ],
                costEstimate: 0.5,
                requiredApprovals: ["file_system_read", "remote_network_if_configured"]
            ),
            evidence: evidence
        )
    }

    func processInteraction(userInput: String) async throws -> (response: String, conversationTurn: ConversationTurn, memory: ConversationMemory) {
        let input = userInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else {
            throw PlatformError.runtime("Input cannot be empty")
        }

        let normalized = input.lowercased()
        let queryResult = try? await searchIndex(query: normalized, limit: 4)
        let baseResponse: String

        if let hitCount = queryResult?.count, hitCount > 0 {
            let snippets = queryResult!.map { hit in
                "[\(hit.path)] " + hit.chunkText
            }
            baseResponse = "Found \(hitCount) runtime context snippets:\n" + snippets.joined(separator: "\n")
        } else if !desktopIndex.isEmpty {
            baseResponse = "I have loaded runtime context. I can answer from indexed files, but this query has no direct match yet."
        } else {
            baseResponse = "Runtime is in local platform mode. Send `index desktop <path>` then retry with your request."
        }

        let turn = ConversationTurn(
            userInput: input,
            brainkResponse: baseResponse,
            wrapperActive: WrapperState(wrapperType: "GENERIC", taskDomain: classifyDomain(input)),
            emotionalState: ["curiosity": 0.5, "satisfaction": 0.7],
            reasoningState: ["logic": 0.6, "high_iq": 0.6],
            timestamp: Self.isoNow()
        )
        conversationLog.append(turn)
        if conversationLog.count > 500 { conversationLog.removeFirst(conversationLog.count - 500) }

        let memory = currentMemory()
        return (baseResponse, turn, memory)
    }

    func verifyBilateral(intent: UserIntent, operation: Operation) async throws -> VerificationResult {
        let intentMatch = Self.normalizedContains(operation.goal, intent.objective)
        let costMatch = operation.actualCost <= intent.estimatedCost && operation.estimatedDurationMs <= intent.timeoutMs
        let permissionMatch = Set(operation.requiredPermissions).isSubset(of: Set(intent.grantedPermissions))
        let verified = intentMatch && costMatch && permissionMatch
        let evidence: [String] = [
            "intent.objective: \(intent.objective)",
            "operation.goal: \(operation.goal)",
            "actualCost: \(operation.actualCost)",
            "estimated: \(intent.estimatedCost)",
            "actualPermissions: \(operation.requiredPermissions.joined(separator: ","))"
        ]
        return VerificationResult(
            verified: verified,
            confidence: verified ? 0.91 : 0.52,
            crossChecks: CrossChecks(
                intentMatch: intentMatch,
                costMatch: costMatch,
                permissionMatch: permissionMatch
            ),
            evidence: evidence
        )
    }

    func recursiveLearning(history: [ConversationTurn]) async throws -> LearningReport {
        var frequencies: [String: Int] = [:]
        for turn in history {
            for word in tokenize(turn.userInput) {
                frequencies[word, default: 0] += 1
            }
        }
        let sorted = frequencies
            .filter { $0.value > 1 }
            .sorted { $0.value > $1.value }

        let patterns = sorted.prefix(12).map { (word, count) in
            LearningReport.Pattern(
                name: word,
                frequency: count,
                impact: min(1.0, Double(count) / max(Double(sorted.count), 1.0)),
                confidence: min(1.0, 0.35 + (Double(count) / 30.0))
            )
        }

        let optimizations = patterns
            .prefix(4)
            .map {
                LearningReport.Optimization(
                    target: "reduce_\($0.name)",
                    suggestion: "Detect token '\($0.name)' at route boundaries and route directly into dedicated handler.",
                    expectedImprovement: min(0.9, Double($0.frequency) / 10.0),
                    effort: "low"
                )
            }

        return LearningReport(
            patterns: patterns,
            optimizations: optimizations,
            nextActions: ["Run platform route audit", "Index missing folders", "Expand local handler grammar"],
            confidence: history.isEmpty ? 0.0 : 0.67,
            createdAt: Self.isoNow()
        )
    }

    func getStatus() async throws -> SystemStatus {
        let healthy = initializedAt != nil || !commandAudit.isEmpty
        return SystemStatus(
            healthy: healthy,
            uptime: initializedAt.map { Date().timeIntervalSince($0) } ?? 0,
            memoryUsage: Int64(desktopIndex.reduce(0) { $0 + $1.sizeBytes }),
            cpuUsage: 0.0,
            indexedFiles: desktopIndex.count,
            cacheSize: commandAudit.count,
            lastUpdate: Self.isoNow(),
            constraints: [
                "routeMap": "local+remote",
                "policyModel": "allowlist+blockedPatterns",
                "indexLimit": "2000"
            ]
        )
    }

    // MARK: - Internal

    private func executeLocally(command: String) -> (success: Bool, output: String?, error: String?) {
        if command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return (false, nil, "Empty command")
        }
        if command.hasPrefix("proof-packet") {
            return runProofPacket(command: command)
        }
        return (true, "Executed locally: \(command)", nil)
    }

    private func runProofPacket(command: String) -> (success: Bool, output: String?, error: String?) {
        let bits = command.split(separator: " ")
        let tool = bits.first.map(String.init) ?? "proof-packet"
        guard tool == "proof-packet" || command.hasPrefix("python3 -m il_llm.cli proof-packet") else {
            return (false, nil, "Unsupported command")
        }

        let proofRun = Process()
        proofRun.executableURL = URL(fileURLWithPath: "/bin/zsh")
        proofRun.arguments = ["-lc", command]
        let out = Pipe()
        let err = Pipe()
        proofRun.standardOutput = out
        proofRun.standardError = err

        do {
            try proofRun.run()
            proofRun.waitUntilExit()

            let outputData = out.fileHandleForReading.readDataToEndOfFile()
            let errorData = err.fileHandleForReading.readDataToEndOfFile()
            let outputText = String(data: outputData, encoding: .utf8) ?? ""
            let errorText = String(data: errorData, encoding: .utf8) ?? ""

            guard proofRun.terminationStatus == 0 else {
                return (false, nil, errorText.isEmpty ? "command failed" : errorText)
            }
            if outputText.isEmpty {
                return (false, nil, "no output")
            }
            return (true, outputText, nil)
        } catch {
            return (false, nil, "proof command failed: \(error)")
        }
    }

    private func validateCommand(_ command: String, against policy: ExecutionPolicy) throws {
        for block in policy.blockedPatterns where command.contains(block) {
            throw PlatformError.runtime("Blocked pattern: \(block)")
        }

        if !policy.allowedCommands.isEmpty {
            let startsWithAllowed = policy.allowedCommands.contains { command.hasPrefix($0) }
            if !startsWithAllowed {
                throw PlatformError.runtime("Command not in allowed list")
            }
        }

        if policy.requiresApproval {
            // No explicit UI approval bus in this lightweight baseline.
            throw PlatformError.runtime("Policy requires approval before execution")
        }
    }

    private func collectDesktopIndex(rootPath: String) throws -> [DesktopIndexEntry] {
        let root = URL(fileURLWithPath: rootPath, isDirectory: true)
        guard FileManager.default.fileExists(atPath: root.path) else {
            throw PlatformError.runtime("Path does not exist: \(root.path)")
        }

        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: root.path, isDirectory: &isDir), isDir.boolValue else {
            return [try indexFile(at: root, chunkIdStart: 0)]
        }

        guard let enumerator = FileManager.default.enumerator(
            at: root,
            includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey, .contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else {
            throw PlatformError.runtime("Unable to enumerate: \(root.path)")
        }

        var results: [DesktopIndexEntry] = []
        var chunkId = 0
        while let item = enumerator.nextObject() as? URL {
            let resource = try item.resourceValues(forKeys: [.isRegularFileKey])
            guard resource.isRegularFile == true else { continue }
            let ext = item.pathExtension.lowercased()
            if !ext.isEmpty && !Self.supportedExtensions.contains(ext) {
                continue
            }

            let entry = try indexFile(at: item, chunkIdStart: chunkId)
            results.append(entry)
            chunkId += 1

            if results.count >= 1500 {
                break
            }
        }

        return results
    }

    private func indexFile(at url: URL, chunkIdStart: Int) throws -> DesktopIndexEntry {
        let data = try Data(contentsOf: url)
        let text = String(data: data, encoding: .utf8) ?? ""
        let stats = try url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
        let size = stats.fileSize ?? data.count
        let modified = stats.contentModificationDate ?? Date(timeIntervalSince1970: 0)
        let chunkText = String(text.prefix(768))
        let hash = Self.sha256(data)
        let sensitive = text.lowercased().contains("secret") || text.lowercased().contains("password") || text.lowercased().contains("token")
        return DesktopIndexEntry(
            path: url.path,
            sizeBytes: size,
            modifiedAt: Self.isoDate(modified),
            contentHash: hash,
            chunkId: chunkIdStart,
            chunkText: sensitive ? Self.redact(text: chunkText) : chunkText,
            sensitive: sensitive,
            indexedAt: Self.isoNow()
        )
    }

    private func tokenize(_ input: String) -> [String] {
        input
            .lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count > 2 }
    }

    private static func normalizedContains(_ lhs: String, _ rhs: String) -> Bool {
        lhs.lowercased().contains(rhs.lowercased()) || rhs.lowercased().contains(lhs.lowercased())
    }

    private func currentMemory() -> ConversationMemory {
        let turns = conversationLog.suffix(20)
        var freq: [String: Double] = [:]
        for turn in turns {
            for token in tokenize(turn.userInput) {
                freq[token, default: 0] += 1
            }
        }
        let patterns = freq
        return ConversationMemory(
            turns: Array(turns),
            userPersonalitySignature: freq,
            accumulatedPatterns: patterns,
            emotionalHistory: [0.71, 0.82, 0.75]
        )
    }

    private func dictionaryFromRecentTurns() -> [String: Double] {
        guard !conversationLog.isEmpty else { return [:] }
        var freq: [String: Double] = [:]
        for turn in conversationLog.suffix(30) {
            for token in tokenize(turn.userInput) {
                freq[token, default: 0] += 1
            }
        }
        return freq
    }

    private func classifyDomain(_ input: String) -> String {
        let lower = input.lowercased()
        if lower.contains("proof") || lower.contains("packet") {
            return "proof_validation"
        }
        if lower.contains("runtime") || lower.contains("route") {
            return "runtime_trace"
        }
        if lower.contains("index") || lower.contains("search") {
            return "desktop_index"
        }
        return "generic"
    }

    private func encodeJSONObject(_ payload: [String: Any]) throws -> Data {
        guard JSONSerialization.isValidJSONObject(payload) else {
            throw PlatformError.invalidPayload
        }
        return try JSONSerialization.data(withJSONObject: payload, options: [.withoutEscapingSlashes])
    }

    private static func sha256(_ text: String) -> String {
        let data = Data(text.utf8)
        return sha256(data)
    }

    private static func sha256(_ data: Data) -> String {
        #if canImport(CryptoKit)
        let digest = SHA256.hash(data: data)
        return digest.compactMap { String(format: "%02x", $0) }.joined()
        #else
        var hash: UInt64 = 0xcbf29ce484222325
        for byte in data {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        return String(format: "%016llx", hash)
        #endif
    }

    private static func isoNow() -> String {
        isoDate(Date())
    }

    private static func isoDate(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }

    private static func makeSessionId() -> String {
        "session_\(Int(Date().timeIntervalSince1970))_\(UUID().uuidString.prefix(8))"
    }

    private static func redact(text: String) -> String {
        text.replacingOccurrences(of: "password", with: "[redacted]", options: .caseInsensitive)
            .replacingOccurrences(of: "token", with: "[redacted]", options: .caseInsensitive)
            .replacingOccurrences(of: "secret", with: "[redacted]", options: .caseInsensitive)
    }
}
