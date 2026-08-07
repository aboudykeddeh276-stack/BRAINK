import Foundation

enum BRAINKConstants {
    static var nativeChatBotRoot: String { URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().path }
    static var repositoryRoot: String { URL(fileURLWithPath: nativeChatBotRoot).deletingLastPathComponent().path }
    static var sourcesRoot: String { URL(fileURLWithPath: nativeChatBotRoot).appendingPathComponent("Sources").path }
    static func sourceFilePath(_ fileName: String) -> String {
        URL(fileURLWithPath: sourcesRoot).appendingPathComponent(fileName).path
    }
    static var buildRoot: String { URL(fileURLWithPath: nativeChatBotRoot).appendingPathComponent("build").path }
    static let architectName = "A. KEDDEH"
    static let organizationName = "K-SYSTEMS"
    static let productSignature = "BRAINK by K-SYSTEMS"
    static let authorshipSignature = "Author: A. KEDDEH | Organization: K-SYSTEMS"
    static let kexSignatureKey = "KEY::2D8B9211E01A8CCD"

    static let cookieName = "app_session_id"
    static let oneYearMs = 1000 * 60 * 60 * 24 * 365
    static let axiosTimeoutMs = 30_000
    static let unauthedErrMsg = "Please login (10001)"
    static let notAdminErrMsg = "You do not have required permission (10002)"

    static var defaultILLLMRuntimePath: String { repositoryRoot }
    static let defaultProofPacketRunId = "smart_manager_0074"
    static let proofPacketCommand = "python3 -m il_llm.cli proof-packet --run-id \(defaultProofPacketRunId)"
    static var stackAuditReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_stack_alignment_report.json").path }
    static var learningSnapshotReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_learning_snapshot.json").path }
    static var frontierSealPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_frontier_seal.json").path }
    static var runtimeLineRegistryPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_runtime_line_registry.json").path }
    static var illlmCompatibilityReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_illlm_compatibility_report.json").path }
    static var illlmWorkflowReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_illlm_workflow_report.json").path }
    static var illlmKnowledgeStatePath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_illlm_knowledge_state.json").path }
    static var innerRuntimeStatePath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("braink_inner_runtime_state.json").path }
    static var kexHyperdriveConceptReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("kex_hyperdrive_transition_definition_report.json").path }
    static var kexHyperdriveCalibrationReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("kex_hyperdrive_repo_calibration_report.json").path }
    static var kexSelfSustainedCodingReportPath: String { URL(fileURLWithPath: buildRoot).appendingPathComponent("kex_self_sustained_coding_report.json").path }
}
