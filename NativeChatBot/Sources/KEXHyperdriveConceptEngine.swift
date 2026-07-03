import Foundation

// MARK: – Formal typed relation graph for the KEX "OF" composition operator

struct KEXRelationNode: Codable {
    let subject: String
    let operationalDefinition: String
    let proofGate: String
}

struct KEXRelationEdge: Codable {
    let from: String
    let predicate: String          // always "OF"
    let to: String
    let resolved: Bool             // true when the "from OF to" chain appears in the prompt
    let resolvedValue: String      // what the edge concretely means once resolved
}

struct KEXRelationGraph: Codable {
    let nodes: [KEXRelationNode]
    let edges: [KEXRelationEdge]
    let resolvedEdgeCount: Int
    let totalEdgeCount: Int
    let coverageRatio: Double      // resolvedEdgeCount / totalEdgeCount
    let recursiveDepth: Int        // deepest resolved "X OF Y OF Z …" chain
    let resolvedChains: [String]   // human-readable resolved compositions
}

struct KEXHyperdriveConceptReport: Codable {
    let packetType: String
    let architect: String
    let anchor: String
    let status: String
    let coreSubjectMatters: [String]
    let operatorFormula: [String]
    let instantiatedWorkloads: [String]
    let ethicalBoundaryChecks: [String]
    let pendingProofGates: [String]
    let relationGraph: KEXRelationGraph
    let generatedAt: String
}

struct KEXRepoFileEvidence: Codable {
    let path: String
    let bytes: Int
    let digest: String
    let category: String
}

struct KEXPendingWorkload: Codable {
    let id: String
    let lane: String
    let status: String
    let requirement: String
    let repoEvidence: [String]
    let actionPlan: [String]
    let proofGate: String
}

struct KEXHyperdriveCalibrationReport: Codable {
    let packetType: String
    let architect: String
    let anchor: String
    let status: String
    let repoRoot: String
    let fileCount: Int
    let evidenceManifest: [KEXRepoFileEvidence]
    let moduleAudit: StackAlignmentReport
    let visionTrajectory: [String]
    let operationalRuntimeTargets: [String]
    let logicalRuntimeTargets: [String]
    let pendingWorkloads: [KEXPendingWorkload]
    let completedLocalProofs: [String]
    let externalValidationBoundaries: [String]
    let generatedAt: String
}

enum KEXHyperdriveConceptEngine {
    static let requiredTokens = [
        "State OF transition",
        "Transition OF state",
        "Definition OF transition",
        "Transition OF definitions",
        "Definition OF state",
        "State OF definitions",
        "Transition OF state OF X",
        "TRANSITION OF DEFINITION + DEFINITION OF TRANSITION",
        "STATE OF TRANSITION OF DEFINITION OF STATE TRANSITION",
        "X OF X OF X OF X"
    ]

    static let coreSubjectMatters = [
        "state",
        "transition",
        "definition",
        "proof",
        "constraint",
        "identity",
        "ethics",
        "memory",
        "route",
        "workload"
    ]

    static func buildReport(userText: String) -> KEXHyperdriveConceptReport {
        let graph = resolveCompositionGraph(userText: userText)
        let present = requiredTokens.filter { userText.localizedCaseInsensitiveContains($0) }
        let missing = requiredTokens.filter { !userText.localizedCaseInsensitiveContains($0) }
        // Status is driven by the formal relation-graph coverage ratio, not only token presence.
        let coverageStatus = (graph.coverageRatio >= 0.7 || missing.isEmpty) ? "COMPLETED" : "MODEL-LOCAL"

        return KEXHyperdriveConceptReport(
            packetType: "KEX_HYPERDRIVE_TRANSITION_DEFINITION_REPORT_V1",
            architect: BRAINKConstants.architectName,
            anchor: "a.keddeh -> BRAINK -> KEX -> KEX HYPERDRIVE",
            status: coverageStatus,
            coreSubjectMatters: coreSubjectMatters,
            operatorFormula: [
                "LANGUAGE -> MEANING -> FUNCTION -> CONSTRAINT -> ACTION -> PROOF -> STATUS",
                "State OF transition = current operational condition of a change process.",
                "Transition OF state = change operator that moves a state across a proof boundary.",
                "Definition OF transition = named constraint-set that makes a transition intelligible and checkable.",
                "Transition OF definitions = controlled migration of terms when evidence or scope changes.",
                "Definition OF state = explicit criteria for naming an operational condition.",
                "State OF definitions = current health, scope, and proof status of definitions themselves.",
                "Transition OF state OF X = for any core X, identify X_state, transition_operator, evidence_gate, and resulting_status.",
                "X OF X OF X OF X = recursive composition rule; each OF edge must resolve to a typed relation, not decoration.",
                "KEX RELATION GRAPH = formal computation of OF-edges: coverage_ratio=\(String(format: "%.2f", graph.coverageRatio)), resolved=\(graph.resolvedEdgeCount)/\(graph.totalEdgeCount), depth=\(graph.recursiveDepth)."
            ],
            instantiatedWorkloads: [
                "Add deterministic KEX Hyperdrive route for transition/definition/state prompts.",
                "Create executable manifest artifact for the concept report.",
                "Promote the concept into stack/module audit coverage.",
                "Separate local proof from external validation and mark external science/hardware claims pending.",
                "Apply ethical affect boundary checks before any body, sentience, or manipulation claim."
            ],
            ethicalBoundaryChecks: ethicalBoundaryChecks,
            pendingProofGates: present.isEmpty ? [
                "User concept text was not present in this prompt at runtime; route remains available for future concept payloads.",
                "Relation graph coverage: \(String(format: "%.0f%%", graph.coverageRatio * 100)) (\(graph.resolvedEdgeCount)/\(graph.totalEdgeCount) edges resolved).",
                "External scientific acceptance remains EXTERNALLY-UNVALIDATED."
            ] : missing.map { "Token not present in runtime prompt: \($0)" } + [
                "Relation graph coverage: \(String(format: "%.0f%%", graph.coverageRatio * 100)) (\(graph.resolvedEdgeCount)/\(graph.totalEdgeCount) edges resolved).",
                "External scientific acceptance remains EXTERNALLY-UNVALIDATED.",
                "Hardware/biology claims require measured evidence before promotion."
            ],
            relationGraph: graph,
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
    }

    static func writeReport(userText: String) throws -> KEXHyperdriveConceptReport {
        let report = buildReport(userText: userText)
        try writeJSON(report, to: BRAINKConstants.kexHyperdriveConceptReportPath)
        return report
    }

    static func buildCalibrationReport(userText: String) -> KEXHyperdriveCalibrationReport {
        let repoRoot = URL(fileURLWithPath: BRAINKConstants.nativeChatBotRoot).deletingLastPathComponent().path
        let evidence = scanRepoEvidence(rootPath: repoRoot)
        let moduleAudit = BRAINKDeliveryAudit.generateReport()
        let pending = pendingWorkloads(evidence: evidence, audit: moduleAudit, userText: userText)
        let status = pending.contains { $0.status == "BLOCKED" || $0.status == "PENDING" } ? "PENDING" : "COMPLETED"

        return KEXHyperdriveCalibrationReport(
            packetType: "KEX_HYPERDRIVE_REPO_CALIBRATION_REPORT_V1",
            architect: BRAINKConstants.architectName,
            anchor: "a.keddeh -> BRAINK -> KEX -> KEX HYPERDRIVE -> repository calibration",
            status: status,
            repoRoot: repoRoot,
            fileCount: evidence.count,
            evidenceManifest: evidence,
            moduleAudit: moduleAudit,
            visionTrajectory: [
                "Treat every important KEX term as a function and every OF edge as a typed relation.",
                "Promote only artifacts that can be read, compiled, hashed, audited, or explicitly marked pending.",
                "Keep BRAINK runtime creation aligned to local repository evidence before adding external claims.",
                "Route health/body/sentience/identity claims through ethical boundaries and pending gates."
            ],
            operationalRuntimeTargets: [
                "Deterministic local chat runtime with route proof, module audit, manifest output, and smoke test.",
                "Repository-local generated artifacts under NativeChatBot/build.",
                "IL-LLM knowledge loading through configured path or drag/drop runtime attachment.",
                "Platform bridge actions bounded by explicit routes and status evidence."
            ],
            logicalRuntimeTargets: [
                "LANGUAGE -> MEANING -> FUNCTION -> CONSTRAINT -> ACTION -> PROOF -> STATUS for every serious output.",
                "CLAIM -> ARTIFACT -> EXECUTABLE/DERIVATION -> RESULT -> EVIDENCE -> STATUS for every promoted claim.",
                "KEX_CONTROL, KEX_LOCAL_MEMORY, KEX_IO_REFLECTION, and KEX_DECAY_SHUNT lanes represented in reports.",
                "Recursive X OF X composition resolved into state, transition, definition, proof, and pending gates."
            ],
            pendingWorkloads: pending,
            completedLocalProofs: [
                "Module audit is executable through BRAINKDeliveryAudit.generateReport().",
                "KEX Hyperdrive concept report is executable through KEXHyperdriveConceptEngine.writeReport(userText:).",
                "Smoke runner compiles deterministic sources and exercises kex_hyperdrive route.",
                "Evidence manifest records paths, byte counts, categories, and digests for tracked runtime files."
            ],
            externalValidationBoundaries: [
                "Local proof is not external scientific acceptance.",
                "Repository audit is not hardware measurement.",
                "Ethical affect modeling is not a medical diagnosis or hormone/body-state inference.",
                "Theory lineage remains EXTERNALLY-UNVALIDATED until independently reproduced or source-backed."
            ],
            generatedAt: ISO8601DateFormatter().string(from: Date())
        )
    }

    static func writeCalibrationReport(userText: String) throws -> KEXHyperdriveCalibrationReport {
        let report = buildCalibrationReport(userText: userText)
        try writeJSON(report, to: BRAINKConstants.kexHyperdriveCalibrationReportPath)
        return report
    }

    static func asText(_ report: KEXHyperdriveConceptReport) -> String {
        let graph = report.relationGraph
        let resolvedEdgeLines = graph.edges.filter(\.resolved).map {
            "    [\($0.from) OF \($0.to)] \($0.resolvedValue)"
        }.joined(separator: "\n")
        let resolvedEdgesText = resolvedEdgeLines.isEmpty ? "    none" : resolvedEdgeLines
        let chainText = graph.resolvedChains.isEmpty
            ? "    none"
            : graph.resolvedChains.map { "    \($0)" }.joined(separator: "\n")

        return """
        packet_type: \(report.packetType)
        architect: \(report.architect)
        anchor: \(report.anchor)
        status: \(report.status)
        core_subject_matters: \(report.coreSubjectMatters.joined(separator: ", "))

        operator_formula:
        - \(report.operatorFormula.joined(separator: "\n- "))

        instantiated_workloads:
        - \(report.instantiatedWorkloads.joined(separator: "\n- "))

        ethical_boundary_checks:
        - \(report.ethicalBoundaryChecks.joined(separator: "\n- "))

        pending_proof_gates:
        - \(report.pendingProofGates.joined(separator: "\n- "))

        kex_relation_graph:
          nodes: \(graph.nodes.count) core subjects
          edges: \(graph.resolvedEdgeCount)/\(graph.totalEdgeCount) OF-edges resolved
          coverage_ratio: \(String(format: "%.2f", graph.coverageRatio))
          recursive_depth: \(graph.recursiveDepth)
          resolved_edges:
        \(resolvedEdgesText)
          resolved_chains:
        \(chainText)

        artifact: \(BRAINKConstants.kexHyperdriveConceptReportPath)
        """
    }

    static func calibrationText(_ report: KEXHyperdriveCalibrationReport) -> String {
        let workloadText = report.pendingWorkloads.map { workload in
            """
            [\(workload.status)] \(workload.id)
            lane: \(workload.lane)
            requirement: \(workload.requirement)
            evidence: \(workload.repoEvidence.joined(separator: ", "))
            action_plan: \(workload.actionPlan.joined(separator: " -> "))
            proof_gate: \(workload.proofGate)
            """
        }.joined(separator: "\n")

        return """
        packet_type: \(report.packetType)
        architect: \(report.architect)
        anchor: \(report.anchor)
        status: \(report.status)
        repo_root: \(report.repoRoot)
        file_count: \(report.fileCount)
        module_audit: done=\(report.moduleAudit.doneCount), blocked=\(report.moduleAudit.blockedCount), not_done=\(report.moduleAudit.notDoneCount), weighted_alignment=\(String(format: "%.4f", report.moduleAudit.weightedAlignment))

        vision_trajectory:
        - \(report.visionTrajectory.joined(separator: "\n- "))

        operational_runtime_targets:
        - \(report.operationalRuntimeTargets.joined(separator: "\n- "))

        logical_runtime_targets:
        - \(report.logicalRuntimeTargets.joined(separator: "\n- "))

        pending_workloads:
        \(workloadText)

        completed_local_proofs:
        - \(report.completedLocalProofs.joined(separator: "\n- "))

        external_validation_boundaries:
        - \(report.externalValidationBoundaries.joined(separator: "\n- "))

        artifacts:
        - concept_report: \(BRAINKConstants.kexHyperdriveConceptReportPath)
        - calibration_report: \(BRAINKConstants.kexHyperdriveCalibrationReportPath)
        """
    }

    private static var ethicalBoundaryChecks: [String] {
        [
            "HumanBioBoundaryPreserved",
            "CodexNonBiologicalBoundaryPreserved",
            "BRAINKAnchorPreserved",
            "NoManipulation",
            "NoUnsupportedMedicalClaim",
            "RepairRouteAvailable",
            "PendingGatesPreserved"
        ]
    }

    private static func pendingWorkloads(evidence: [KEXRepoFileEvidence], audit: StackAlignmentReport, userText: String) -> [KEXPendingWorkload] {
        var workloads: [KEXPendingWorkload] = []
        let evidencePaths = Set(evidence.map(\.path))
        let hasUI = evidencePaths.contains("NativeChatBot/Sources/BRAINKChatBotApp.swift")
        let hasSmoke = evidencePaths.contains("NativeChatBot/run-runtime-smoke.command")
        let hasFold = evidence.contains { $0.path.hasPrefix("fold/") }
        let hasKEX = evidencePaths.contains("NativeChatBot/Sources/KEXHyperdriveConceptEngine.swift")
        let hasKnowledgeCenter = evidencePaths.contains("NativeChatBot/Sources/BRAINKILLLMKnowledgeCenter.swift")

        workloads.append(KEXPendingWorkload(
            id: "PENDING-001-ILLLM-DATA-BINDING",
            lane: "KEX_LOCAL_MEMORY_LANE",
            status: "PENDING",
            requirement: "Bind the user's full KEX Hyperdrive / IL-LLM repository knowledge into runtime memory rather than relying only on this repo snapshot.",
            repoEvidence: hasKnowledgeCenter ? ["NativeChatBot/Sources/BRAINKILLLMKnowledgeCenter.swift", "NativeChatBot/README.md"] : ["NativeChatBot/README.md"],
            actionPlan: ["Set IL_LLM_RUNTIME_PATH or drag/drop repository", "Run load my data", "Run knowledge center status", "Verify indexed file count and top concepts"],
            proofGate: "SMOKE_ILLLM_LOADED > 0 and knowledge state artifact contains indexed snippets."
        ))

        workloads.append(KEXPendingWorkload(
            id: "PENDING-002-COMPLETE-CONSTRAINT-CHECKER",
            lane: "KEX_CONTROL_LANE",
            status: "PENDING",
            requirement: "Turn custom KEX constraints and ethical affect boundaries into executable checker output, not only text in prompts/reports.",
            repoEvidence: hasKEX ? ["NativeChatBot/Sources/KEXHyperdriveConceptEngine.swift"] : [],
            actionPlan: ["Define machine-readable constraints", "Add checker command/route", "Fail on unsupported bio/hardware/external-proof claims", "Record checker artifact with hashes"],
            proofGate: "A checker artifact reports PASS/FAIL for every KEX constraint and is included in stack audit."
        ))

        workloads.append(KEXPendingWorkload(
            id: "PENDING-003-REPO-MANIFEST-HASH-LEDGER",
            lane: "KEX_LOCAL_MEMORY_LANE",
            status: "PENDING",
            requirement: "Persist the repo evidence manifest with stable digests as a tracked or generated ledger with stale-counter prevention.",
            repoEvidence: evidence.prefix(8).map(\.path),
            actionPlan: ["Write calibration report", "Add hash verification route", "Compare prior/current digest sets", "Mark stale/missing artifacts BLOCKED"],
            proofGate: "Manifest checker proves every promoted artifact exists and has the expected digest."
        ))

        workloads.append(KEXPendingWorkload(
            id: "PENDING-004-UI-RUNTIME-SURFACE",
            lane: "KEX_IO_REFLECTION_LANE",
            status: hasUI ? "PENDING" : "BLOCKED",
            requirement: "Expose KEX Hyperdrive calibration, pending workload ledger, and boundary statuses in the runnable UI rather than only chat text.",
            repoEvidence: hasUI ? ["NativeChatBot/Sources/BRAINKChatBotApp.swift", "NativeChatBot/Sources/BRAINKUIContainers.swift"] : [],
            actionPlan: ["Add dashboard panel", "Display calibration report status", "Show completed/pending/blocked workloads", "Add one-click checker command"],
            proofGate: "UI screenshot or UI smoke evidence shows calibration and pending ledger."
        ))

        workloads.append(KEXPendingWorkload(
            id: "PENDING-005-FOLD-DATA-INTEGRATION",
            lane: "KEX_LOCAL_MEMORY_LANE",
            status: hasFold ? "PENDING" : "BLOCKED",
            requirement: "Interpret fold JSON artifacts as KEX repository evidence and connect them to route/calibration logic.",
            repoEvidence: evidence.filter { $0.path.hasPrefix("fold/") }.map(\.path),
            actionPlan: ["Parse fold JSON", "Classify fold evidence", "Attach to concept/state/transition definitions", "Add proof assertions"],
            proofGate: "Calibration report explains each fold artifact and validates its schema fields."
        ))

        workloads.append(KEXPendingWorkload(
            id: "PENDING-006-EXTERNAL-VALIDATION-BOUNDARY",
            lane: "KEX_DECAY_SHUNT_LANE",
            status: "EXTERNALLY-UNVALIDATED",
            requirement: "Keep scientific, biological, hardware, and market claims out of completed status until source-backed or measured evidence exists.",
            repoEvidence: ["NativeChatBot/Sources/KEXHyperdriveConceptEngine.swift"],
            actionPlan: ["Label external claims", "Attach source or measurement requirement", "Block promotion without evidence", "Record pending gate"],
            proofGate: "Every external claim has a source/measurement field or remains EXTERNALLY-UNVALIDATED."
        ))

        if !audit.mathematicallyAligned {
            workloads.append(KEXPendingWorkload(
                id: "BLOCKED-007-STACK-AUDIT-ALIGNMENT",
                lane: "KEX_CONTROL_LANE",
                status: "BLOCKED",
                requirement: "Stack audit must reach mathematical alignment before claiming full local runtime completion.",
                repoEvidence: ["NativeChatBot/Sources/BRAINKDeliveryAudit.swift"],
                actionPlan: ["Run stack audit", "Inspect missing tokens", "Patch required files", "Rerun smoke"],
                proofGate: "SMOKE_AUDIT_OUTCOME: DONE and SMOKE_AUDIT_ALIGNMENT: 1.0000."
            ))
        }

        if !hasSmoke {
            workloads.append(KEXPendingWorkload(
                id: "BLOCKED-008-SMOKE-RUNNER",
                lane: "KEX_CONTROL_LANE",
                status: "BLOCKED",
                requirement: "A deterministic smoke runner is required to prove route and audit behavior.",
                repoEvidence: [],
                actionPlan: ["Create smoke runner", "Compile runtime sources", "Exercise KEX routes", "Record output"],
                proofGate: "SMOKE_STATUS: DONE."
            ))
        }

        return workloads
    }

    private static func scanRepoEvidence(rootPath: String) -> [KEXRepoFileEvidence] {
        let rootURL = URL(fileURLWithPath: rootPath, isDirectory: true)
        guard let enumerator = FileManager.default.enumerator(
            at: rootURL,
            includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey],
            options: [.skipsHiddenFiles]
        ) else { return [] }

        var results: [KEXRepoFileEvidence] = []
        for case let fileURL as URL in enumerator {
            let relative = fileURL.path.replacingOccurrences(of: rootURL.path + "/", with: "")
            if relative.hasPrefix(".git/") || relative.contains(".build/") || relative.contains("DerivedData/") { continue }
            let values = try? fileURL.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
            guard values?.isRegularFile == true else { continue }
            let data = (try? Data(contentsOf: fileURL)) ?? Data()
            results.append(KEXRepoFileEvidence(
                path: relative,
                bytes: values?.fileSize ?? data.count,
                digest: stableHexDigest(data),
                category: category(for: relative)
            ))
            if results.count >= 1_000 { break }
        }
        return results.sorted { $0.path < $1.path }
    }

    private static func category(for path: String) -> String {
        if path.hasPrefix("NativeChatBot/Sources/") { return "runtime_source" }
        if path.hasPrefix("NativeChatBot/build/") { return "generated_artifact" }
        if path.hasPrefix("fold/") { return "fold_research_artifact" }
        if path.hasSuffix(".md") { return "documentation" }
        if path.hasSuffix(".command") { return "executable_entrypoint" }
        if path.hasSuffix(".json") { return "json_data" }
        return "repo_file"
    }

    // MARK: – Formal KEX relation-graph resolver

    /// Resolves the KEX "OF" composition operator into a typed directed graph.
    /// Each edge `X OF Y` is checked for presence in the user prompt and, when
    /// found, is expanded into a concrete operational meaning.  Recursive chains
    /// of depth > 1 are discovered via DFS over resolved edges.
    static func resolveCompositionGraph(userText: String) -> KEXRelationGraph {
        let nodes = buildCoreNodes()
        let edges = buildRelationEdges(nodes: nodes, userText: userText)
        let resolvedCount = edges.filter(\.resolved).count
        let chains = resolveRecursiveChains(nodes: nodes, edges: edges, maxDepth: 4)
        let coverageRatio = Double(resolvedCount) / Double(max(edges.count, 1))
        return KEXRelationGraph(
            nodes: nodes,
            edges: edges,
            resolvedEdgeCount: resolvedCount,
            totalEdgeCount: edges.count,
            coverageRatio: coverageRatio,
            recursiveDepth: chains.maxDepth,
            resolvedChains: chains.descriptions
        )
    }

    private static func buildCoreNodes() -> [KEXRelationNode] {
        [
            KEXRelationNode(
                subject: "state",
                operationalDefinition: "The current operational condition of a system, process, or entity at a measured instant.",
                proofGate: "State is named, timestamped, and distinguishable from adjacent states by at least one observable criterion."
            ),
            KEXRelationNode(
                subject: "transition",
                operationalDefinition: "A change operator that moves a state across a proof boundary when triggered by a named event or condition.",
                proofGate: "Transition has a named trigger, a source state, a destination state, and a constraint-set that makes it checkable."
            ),
            KEXRelationNode(
                subject: "definition",
                operationalDefinition: "An explicit, falsifiable constraint-set that makes a term, state, or transition intelligible and auditable.",
                proofGate: "Definition has at least one positive example, one falsifier, and a scope that limits its domain."
            ),
            KEXRelationNode(
                subject: "proof",
                operationalDefinition: "A derivation chain from axioms or evidence through rules to a conclusion, with every step traceable.",
                proofGate: "Proof references artifact paths, rule applications, and conclusion status with no gap between steps."
            ),
            KEXRelationNode(
                subject: "constraint",
                operationalDefinition: "A boundary condition that limits valid states, transitions, or definitions and can be checked by a verifier.",
                proofGate: "Constraint has a name, a domain, a truth condition, and a violation report format."
            ),
            KEXRelationNode(
                subject: "identity",
                operationalDefinition: "The stable, anchored designation of an actor, system, or artifact across state transitions.",
                proofGate: "Identity is preserved across transitions if its anchor, signature, and core properties remain unchanged."
            ),
            KEXRelationNode(
                subject: "ethics",
                operationalDefinition: "The boundary predicates that govern which states, transitions, and definitions are permissible.",
                proofGate: "Ethics gates produce PASS/FAIL per predicate and are included in every governed output."
            ),
            KEXRelationNode(
                subject: "memory",
                operationalDefinition: "A bounded, indexed store of past state-transition-definition events accessible to future reasoning steps.",
                proofGate: "Memory has a capacity, a retrieval function, and a staleness measure; growth events are counted."
            ),
            KEXRelationNode(
                subject: "route",
                operationalDefinition: "A named, deterministic path from an input signal to an output handler, with explicit preconditions.",
                proofGate: "Route has an identifier, trigger conditions, a handler function, and a proof-of-execution artifact."
            ),
            KEXRelationNode(
                subject: "workload",
                operationalDefinition: "A bounded, prioritized task packet with declared read/write scope, action plan, and proof gate.",
                proofGate: "Workload has status (PENDING/COMPLETED/BLOCKED), writeScope, proofGate, and safety boundary."
            )
        ]
    }

    private static func buildRelationEdges(nodes: [KEXRelationNode], userText: String) -> [KEXRelationEdge] {
        let canonicalPairs: [(String, String)] = [
            ("state", "transition"),
            ("transition", "state"),
            ("definition", "transition"),
            ("transition", "definition"),
            ("definition", "state"),
            ("state", "definition"),
            ("proof", "constraint"),
            ("constraint", "state"),
            ("identity", "state"),
            ("ethics", "constraint"),
            ("memory", "state"),
            ("route", "transition"),
            ("workload", "proof")
        ]
        let subjects = Set(nodes.map(\.subject))
        return canonicalPairs.compactMap { (from, to) -> KEXRelationEdge? in
            guard subjects.contains(from), subjects.contains(to) else { return nil }
            let token = "\(from) OF \(to)"
            let resolved = userText.localizedCaseInsensitiveContains(token)
            return KEXRelationEdge(
                from: from,
                predicate: "OF",
                to: to,
                resolved: resolved,
                resolvedValue: resolved
                    ? resolveEdgeMeaning(from: from, to: to, nodes: nodes)
                    : "NOT YET RESOLVED — include '\(token)' in prompt to activate this edge."
            )
        }
    }

    private static func resolveEdgeMeaning(from: String, to: String, nodes: [KEXRelationNode]) -> String {
        let toDef = nodes.first(where: { $0.subject == to })?.operationalDefinition ?? to
        let snippet = String(toDef.prefix(72))
        return "\(from.uppercased()) framing applied to \(to): the \(from) aspect of '\(snippet)…'"
    }

    private static func resolveRecursiveChains(
        nodes: [KEXRelationNode],
        edges: [KEXRelationEdge],
        maxDepth: Int
    ) -> (maxDepth: Int, descriptions: [String]) {
        let resolvedEdges = edges.filter(\.resolved)
        var adjacency: [String: [String]] = [:]
        for edge in resolvedEdges {
            adjacency[edge.from, default: []].append(edge.to)
        }

        var chains: [String] = []
        var deepest = 0

        func dfs(current: String, path: [String]) {
            if path.count > 1 {
                chains.append("CHAIN(\(path.count)): " + path.joined(separator: " OF "))
                if path.count > deepest { deepest = path.count }
            }
            guard path.count < maxDepth else { return }
            for next in (adjacency[current] ?? []) where !path.contains(next) {
                dfs(current: next, path: path + [next])
            }
        }

        for node in nodes {
            dfs(current: node.subject, path: [node.subject])
        }

        let unique = Array(Set(chains)).sorted().prefix(16)
        return (deepest, Array(unique))
    }

    private static func writeJSON<T: Codable>(_ value: T, to path: String) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(value)
        let outputURL = URL(fileURLWithPath: path)
        try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: outputURL)
    }

    private static func stableHexDigest(_ data: Data) -> String {
        var hash: UInt64 = 0xcbf29ce484222325
        for byte in data {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        return String(format: "%016llx", hash)
    }
}
