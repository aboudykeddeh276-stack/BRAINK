import Foundation

struct KEXCodingRepoTarget: Codable {
    let id: String
    let rootPath: String
    let relativePath: String
    let detectedKind: String
    let evidenceFiles: [String]
}

struct KEXCodingTaskPacket: Codable {
    let taskId: String
    let repoId: String
    let lane: String
    let status: String
    let objective: String
    let writeScope: [String]
    let readScope: [String]
    let actionPlan: [String]
    let commandPlan: [String]
    let proofGate: String
    let safetyBoundary: String
}

struct KEXSelfSustainedCodingReport: Codable {
    let packetType: String
    let architect: String
    let anchor: String
    let status: String
    let repoRoot: String
    let targets: [KEXCodingRepoTarget]
    let taskPackets: [KEXCodingTaskPacket]
    let selfExistenceDesign: [String]
    let escalationRules: [String]
    let pendingGates: [String]
    let generatedAt: String
}

enum KEXSelfSustainedCodingEngine {
    static func buildReport(userText: String) -> KEXSelfSustainedCodingReport {
        let repoRoot = URL(fileURLWithPath: BRAINKConstants.nativeChatBotRoot).deletingLastPathComponent().path
        let targets = discoverTargets(repoRoot: repoRoot)
        let packets = targets.flatMap { taskPackets(for: $0, userText: userText) }
        let status = packets.contains { $0.status == "PENDING" || $0.status == "BLOCKED" } ? "PENDING" : "COMPLETED"
        return KEXSelfSustainedCodingReport(
            packetType: "KEX_SELF_SUSTAINED_CODING_REPORT_V1",
            architect: BRAINKConstants.architectName,
            anchor: "a.keddeh -> BRAINK -> KEX -> KEX HYPERDRIVE -> self-sustained coding runtime",
            status: status,
            repoRoot: repoRoot,
            targets: targets,
            taskPackets: packets,
            selfExistenceDesign: [
                "Self-map: discover repo/project targets and record evidence before editing.",
                "Self-task: convert each target into bounded coding packets with explicit read/write scope.",
                "Self-code: only perform mutations through declared routes, commands, and proof gates.",
                "Self-proof: every completed mutation must compile, smoke, audit, or produce an artifact with status.",
                "Self-repair: failed checks route to pending or blocked repair packets instead of overclaiming completion."
            ],
            escalationRules: [
                "Never claim external scientific/hardware/medical proof from repo-local code output.",
                "Never run destructive commands as an autonomous default; require explicit operator route.",
                "Never edit outside declared writeScope for a packet.",
                "Mark missing data repositories PENDING, not failed, until the proof gate can be opened.",
                "Prefer deterministic local artifacts over unrecorded conversational assertions."
            ],
            pendingGates: pendingGates(for: targets, packets: packets),
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
    }

    static func writeReport(userText: String) throws -> KEXSelfSustainedCodingReport {
        let report = buildReport(userText: userText)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(report)
        let outputURL = URL(fileURLWithPath: BRAINKConstants.kexSelfSustainedCodingReportPath)
        try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: outputURL)
        return report
    }

    static func asText(_ report: KEXSelfSustainedCodingReport) -> String {
        let targetText = report.targets.map { target in
            "- \(target.id) [\(target.detectedKind)] path=\(target.relativePath) evidence=\(target.evidenceFiles.joined(separator: ", "))"
        }.joined(separator: "\n")

        // Sort packets by priority: BLOCKED > PENDING > MODEL-LOCAL > COMPLETED,
        // with KEX_CONTROL_LANE weighted 1.5× and evidence weight applied.
        let evidenceWeightMap = Dictionary(uniqueKeysWithValues: report.targets.map {
            ($0.id, evidenceWeight(for: $0))
        })
        let prioritized = report.taskPackets.sorted { lhs, rhs in
            priorityScore(for: lhs, evidenceWeightMap: evidenceWeightMap) >
            priorityScore(for: rhs, evidenceWeightMap: evidenceWeightMap)
        }

        let packetText = prioritized.map { packet in
            """
            [\(packet.status)] \(packet.taskId)
            repo: \(packet.repoId)
            lane: \(packet.lane)
            objective: \(packet.objective)
            write_scope: \(packet.writeScope.joined(separator: ", "))
            read_scope: \(packet.readScope.joined(separator: ", "))
            action_plan: \(packet.actionPlan.joined(separator: " -> "))
            command_plan: \(packet.commandPlan.joined(separator: " && "))
            proof_gate: \(packet.proofGate)
            safety_boundary: \(packet.safetyBoundary)
            """
        }.joined(separator: "\n")

        let proofChainText = buildProofChainText(from: report.taskPackets)

        return """
        packet_type: \(report.packetType)
        architect: \(report.architect)
        anchor: \(report.anchor)
        status: \(report.status)
        repo_root: \(report.repoRoot)

        targets:
        \(targetText)

        self_existence_design:
        - \(report.selfExistenceDesign.joined(separator: "\n- "))

        task_packets (priority-ordered):
        \(packetText)

        proof_chain (MAP → CODE/DATA within each target):
        \(proofChainText)

        escalation_rules:
        - \(report.escalationRules.joined(separator: "\n- "))

        pending_gates:
        - \(report.pendingGates.joined(separator: "\n- "))

        artifact: \(BRAINKConstants.kexSelfSustainedCodingReportPath)
        """
    }

    private static func discoverTargets(repoRoot: String) -> [KEXCodingRepoTarget] {
        let rootURL = URL(fileURLWithPath: repoRoot, isDirectory: true)
        var targets: [KEXCodingRepoTarget] = []
        let rootEvidence = evidenceFiles(in: rootURL)
        targets.append(KEXCodingRepoTarget(
            id: "repo-root",
            rootPath: rootURL.path,
            relativePath: ".",
            detectedKind: "git_repository",
            evidenceFiles: rootEvidence
        ))

        let directChildren = (try? FileManager.default.contentsOfDirectory(
            at: rootURL,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        )) ?? []

        for child in directChildren.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            let values = try? child.resourceValues(forKeys: [.isDirectoryKey])
            guard values?.isDirectory == true else { continue }
            let name = child.lastPathComponent
            if name == ".git" || name == "NativeChatBot.app" { continue }
            let evidence = evidenceFiles(in: child)
            guard !evidence.isEmpty else { continue }
            let kind: String
            if FileManager.default.fileExists(atPath: child.appendingPathComponent(".git").path) {
                kind = "nested_git_repository"
            } else if evidence.contains(where: { $0.hasSuffix(".swift") }) {
                kind = "swift_runtime_project"
            } else if evidence.contains(where: { $0.hasSuffix(".json") }) {
                kind = "research_data_project"
            } else {
                kind = "repo_subsystem"
            }
            targets.append(KEXCodingRepoTarget(
                id: normalizedId(name),
                rootPath: child.path,
                relativePath: name,
                detectedKind: kind,
                evidenceFiles: evidence
            ))
        }
        return targets
    }

    private static func taskPackets(for target: KEXCodingRepoTarget, userText: String) -> [KEXCodingTaskPacket] {
        var packets: [KEXCodingTaskPacket] = []
        let readScope = target.evidenceFiles.isEmpty ? [target.relativePath] : target.evidenceFiles
        let wantsCoding = userText.localizedCaseInsensitiveContains("code")
            || userText.localizedCaseInsensitiveContains("software")
            || userText.localizedCaseInsensitiveContains("task")
            || userText.localizedCaseInsensitiveContains("self sustained")

        packets.append(KEXCodingTaskPacket(
            taskId: "\(target.id)-MAP-001",
            repoId: target.id,
            lane: "KEX_LOCAL_MEMORY_LANE",
            status: "COMPLETED",
            objective: "Map this target into KEX evidence before any coding mutation.",
            writeScope: [BRAINKConstants.kexSelfSustainedCodingReportPath],
            readScope: readScope,
            actionPlan: ["scan target", "classify evidence", "record target", "emit digest-backed packet"],
            commandPlan: ["self_sustained_coder route", "./NativeChatBot/run-runtime-smoke.command"],
            proofGate: "Target appears in KEX_SELF_SUSTAINED_CODING_REPORT_V1.",
            safetyBoundary: "Read-only mapping; no repository mutation outside generated report."
        ))

        if target.detectedKind.contains("swift") || target.relativePath == "NativeChatBot" || target.id == "repo-root" {
            packets.append(KEXCodingTaskPacket(
                taskId: "\(target.id)-CODE-002",
                repoId: target.id,
                lane: "KEX_CONTROL_LANE",
                status: wantsCoding ? "PENDING" : "MODEL-LOCAL",
                objective: "Generate bounded Swift/runtime coding work from KEX calibration tasks and verify by smoke/audit.",
                writeScope: ["\(target.relativePath)/Sources", "\(target.relativePath)/README.md", "\(target.relativePath)/run-runtime-smoke.command"],
                readScope: readScope,
                actionPlan: ["select one pending workload", "derive minimal patch", "compile/smoke", "write report", "commit with proof"],
                commandPlan: ["./NativeChatBot/run-runtime-smoke.command", "git diff --check", "git status --short"],
                proofGate: "SMOKE_STATUS: DONE and stack audit alignment remains 1.0000 after patch.",
                safetyBoundary: "No autonomous destructive commands; no edits outside writeScope."
            ))
        }

        if target.detectedKind == "research_data_project" || target.relativePath == "fold" {
            packets.append(KEXCodingTaskPacket(
                taskId: "\(target.id)-DATA-003",
                repoId: target.id,
                lane: "KEX_LOCAL_MEMORY_LANE",
                status: "PENDING",
                objective: "Convert research data artifacts into typed KEX evidence that can drive runtime creation.",
                writeScope: [BRAINKConstants.kexHyperdriveCalibrationReportPath, BRAINKConstants.kexSelfSustainedCodingReportPath],
                readScope: readScope,
                actionPlan: ["parse JSON", "extract schema fields", "bind to state/transition/definition", "add checker assertions"],
                commandPlan: ["python3 -m json.tool fold/index.json >/tmp/fold-index.check", "./NativeChatBot/run-runtime-smoke.command"],
                proofGate: "Fold artifacts are parsed and represented in calibration pending/completed evidence.",
                safetyBoundary: "Data interpretation only; no claim of external science acceptance."
            ))
        }
        return packets
    }

    private static func evidenceFiles(in directory: URL) -> [String] {
        guard let enumerator = FileManager.default.enumerator(
            at: directory,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) else { return [] }
        var files: [String] = []
        let repoRoot = URL(fileURLWithPath: BRAINKConstants.nativeChatBotRoot).deletingLastPathComponent().path
        for case let fileURL as URL in enumerator {
            let rel = fileURL.path.replacingOccurrences(of: repoRoot + "/", with: "")
            if rel.hasPrefix(".git/") || rel.contains(".app/") || rel.contains(".build/") { continue }
            let values = try? fileURL.resourceValues(forKeys: [.isRegularFileKey])
            guard values?.isRegularFile == true else { continue }
            if rel.hasSuffix(".swift") || rel.hasSuffix(".json") || rel.hasSuffix(".md") || rel.hasSuffix(".command") {
                files.append(rel)
            }
            if files.count >= 40 { break }
        }
        return files.sorted()
    }

    private static func pendingGates(for targets: [KEXCodingRepoTarget], packets: [KEXCodingTaskPacket]) -> [String] {
        var gates = packets
            .filter { $0.status != "COMPLETED" }
            .map { "\($0.taskId): \($0.proofGate)" }
        if targets.count <= 1 {
            gates.append("No nested repositories discovered; tasking is limited to current repo/project subsystems until more repos are attached.")
        }
        gates.append("Autonomous code mutation remains bounded by writeScope, smoke tests, audit, and explicit operator route.")
        return gates
    }

    // MARK: – Evidence-weighted prioritisation and proof-chain dependency model

    /// Scores a target by its evidence quality.  Swift source files carry the most
    /// operational weight; executable scripts next; JSON artifacts; then docs.
    private static func evidenceWeight(for target: KEXCodingRepoTarget) -> Double {
        guard !target.evidenceFiles.isEmpty else { return 0.0 }
        let total = target.evidenceFiles.reduce(0.0) { acc, path in
            let lower = path.lowercased()
            if lower.hasSuffix(".swift")   { return acc + 2.0 }
            if lower.hasSuffix(".command") { return acc + 1.8 }
            if lower.hasSuffix(".json")    { return acc + 1.5 }
            if lower.hasSuffix(".md")      { return acc + 1.0 }
            return acc + 0.5
        }
        return total / Double(target.evidenceFiles.count)
    }

    /// Computes a sortable priority score for a task packet.
    /// BLOCKED tasks are most urgent; KEX_CONTROL_LANE is weighted 1.5×;
    /// higher evidence weight on the owning target increases urgency.
    private static func priorityScore(
        for packet: KEXCodingTaskPacket,
        evidenceWeightMap: [String: Double]
    ) -> Double {
        let urgency: Double
        switch packet.status {
        case "BLOCKED":     urgency = 3.0
        case "PENDING":     urgency = 2.0
        case "MODEL-LOCAL": urgency = 1.0
        default:            urgency = 0.5
        }
        let laneBoost: Double = packet.lane == "KEX_CONTROL_LANE" ? 1.5 : 1.0
        let weight = evidenceWeightMap[packet.repoId] ?? 1.0
        return urgency * laneBoost * max(weight, 0.1)
    }

    /// Builds a textual proof-chain showing the MAP → CODE/DATA dependency order
    /// within each repository target.  This makes implicit dependency explicit and
    /// traceable: a CODE packet may not proceed before its MAP packet is COMPLETED.
    private static func buildProofChainText(from packets: [KEXCodingTaskPacket]) -> String {
        var byRepo: [String: [KEXCodingTaskPacket]] = [:]
        for packet in packets {
            byRepo[packet.repoId, default: []].append(packet)
        }
        return byRepo.sorted { $0.key < $1.key }.map { repoId, repoPackets in
            let ordered = repoPackets.sorted { lhs, rhs in
                let phase: (KEXCodingTaskPacket) -> Int = { p in
                    if p.taskId.contains("MAP")  { return 0 }
                    if p.taskId.contains("CODE") { return 1 }
                    return 2
                }
                return phase(lhs) < phase(rhs)
            }
            let chain = ordered.map { "[\($0.status)] \($0.taskId)" }.joined(separator: " → ")
            return "  \(repoId): \(chain)"
        }.joined(separator: "\n")
    }

    private static func normalizedId(_ value: String) -> String {
        value.lowercased()
            .replacingOccurrences(of: "[^a-z0-9]+", with: "-", options: .regularExpression)
            .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
    }
}
