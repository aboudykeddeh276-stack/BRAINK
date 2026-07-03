import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif

enum BRAINKConstants {
    // MARK: - Root paths (self-locating, no host-specific hardcoding)
    static var nativeChatBotRoot: String { URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().path }
    static var buildRoot: String { URL(fileURLWithPath: nativeChatBotRoot).appendingPathComponent("build").path }
    /// Source directory: NativeChatBot/Sources — derived at compile time, portable across machines.
    static var sourceRoot: String { URL(fileURLWithPath: #filePath).deletingLastPathComponent().path }

    // MARK: - Authorship
    static let architectName = "A. KEDDEH"
    static let organizationName = "K-SYSTEMS"
    static let productSignature = "BRAINK by K-SYSTEMS"
    static let authorshipSignature = "Author: A. KEDDEH | Organization: K-SYSTEMS"
    static let kexSignatureKey = "KEY::2D8B9211E01A8CCD"

    // MARK: - KEX Engineering Standard constants (KEDDEH_ENGINEERING_STANDARD.md)
    /// K_RESONANCE: dimensional resonance constant used across KEX theorem proofs.
    static let kexResonance: Double = 0.297
    /// LATTICE_ROOT: base lattice value for KEX mathematical framework.
    static let kexLatticeRoot: Double = 28.085
    /// AXIS: ordered symmetry axis for KEX spectrum navigation (3|2|1|2|3).
    static let kexAxis: String = "3|2|1|2|3"
    /// BASELINE: zero-less baseline index — spectrum starts at 1, never 0.
    static let kexBaseline: Int = 1

    // MARK: - Shared ISO 8601 date formatter (one instance; thread-safe read)
    static let iso8601: ISO8601DateFormatter = ISO8601DateFormatter()

    // MARK: - Session/web constants
    static let cookieName = "app_session_id"
    static let oneYearMs = 1000 * 60 * 60 * 24 * 365
    static let axiosTimeoutMs = 30_000
    static let unauthedErrMsg = "Please login (10001)"
    static let notAdminErrMsg = "You do not have required permission (10002)"

    // MARK: - IL-LLM defaults (configurable via environment; no host-specific fallback)
    /// Default IL-LLM runtime path. Override with IL_LLM_RUNTIME_PATH environment variable.
    static var defaultILLLMRuntimePath: String {
        ProcessInfo.processInfo.environment["IL_LLM_RUNTIME_PATH"] ?? nativeChatBotRoot
    }
    static let defaultProofPacketRunId = "smart_manager_0074"
    static let proofPacketCommand = "python3 -m il_llm.cli proof-packet --run-id \(defaultProofPacketRunId)"

    // MARK: - Source file paths (portable, derived from #filePath at compile time)
    static var sourcePath_ChatEngine: String    { "\(sourceRoot)/BRAINKChatEngine.swift" }
    static var sourcePath_PlatformAPI: String   { "\(sourceRoot)/BRAINKPlatformAPI.swift" }
    static var sourcePath_DeliveryAudit: String { "\(sourceRoot)/BRAINKDeliveryAudit.swift" }
    static var sourcePath_ModuleManifest: String{ "\(sourceRoot)/ModuleManifest.swift" }
    static var sourcePath_AppEntry: String      { "\(sourceRoot)/BRAINKChatBotApp.swift" }

    // MARK: - Artifact report paths (all within build/, no host-specific paths)
    static var stackAuditReportPath: String         { "\(buildRoot)/braink_stack_alignment_report.json" }
    static var learningSnapshotReportPath: String   { "\(buildRoot)/braink_learning_snapshot.json" }
    static var frontierSealPath: String             { "\(buildRoot)/braink_frontier_seal.json" }
    static var runtimeLineRegistryPath: String      { "\(buildRoot)/braink_runtime_line_registry.json" }
    static var illlmCompatibilityReportPath: String { "\(buildRoot)/braink_illlm_compatibility_report.json" }
    static var illlmWorkflowReportPath: String      { "\(buildRoot)/braink_illlm_workflow_report.json" }
    static var illlmKnowledgeStatePath: String      { "\(buildRoot)/braink_illlm_knowledge_state.json" }
    static var innerRuntimeStatePath: String        { "\(buildRoot)/braink_inner_runtime_state.json" }
    static var kexHyperdriveConceptReportPath: String      { "\(buildRoot)/kex_hyperdrive_transition_definition_report.json" }
    static var kexHyperdriveCalibrationReportPath: String  { "\(buildRoot)/kex_hyperdrive_repo_calibration_report.json" }
    static var kexSelfSustainedCodingReportPath: String    { "\(buildRoot)/kex_self_sustained_coding_report.json" }
    static var skillRegistryReportPath: String      { "\(buildRoot)/braink_skill_registry_proof.json" }

    // MARK: - Shared digest utility (replaces per-file private copies)
    /// FNV-1a 64-bit hash — deterministic, no platform import required.
    /// Used wherever CryptoKit is unavailable (Linux, CI).
    static func fnv1aHex(_ data: Data) -> String {
        var hash: UInt64 = 0xcbf29ce484222325
        for byte in data {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        return String(format: "%016llx", hash)
    }

    /// SHA-256 hex digest when CryptoKit is available; falls back to FNV-1a.
    static func stableHexDigest(_ data: Data) -> String {
        #if canImport(CryptoKit)
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
        #else
        return fnv1aHex(data)
        #endif
    }
}
