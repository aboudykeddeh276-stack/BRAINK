import Foundation

enum BRAINKConstants {
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

    static let defaultILLLMRuntimePath = "/Users/ak/Documents/New project"
    static let defaultProofPacketRunId = "smart_manager_0074"
    static let proofPacketCommand = "python3 -m il_llm.cli proof-packet --run-id \(defaultProofPacketRunId)"
    static let stackAuditReportPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_stack_alignment_report.json"
    static let learningSnapshotReportPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_learning_snapshot.json"
    static let frontierSealPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_frontier_seal.json"
    static let runtimeLineRegistryPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_runtime_line_registry.json"
    static let illlmCompatibilityReportPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_illlm_compatibility_report.json"
    static let illlmWorkflowReportPath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_illlm_workflow_report.json"
    static let illlmKnowledgeStatePath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_illlm_knowledge_state.json"
    static let innerRuntimeStatePath = "/Users/ak/Documents/BRAINK THE ACTUAL APPLICATION/NativeChatBot/build/braink_inner_runtime_state.json"
}
